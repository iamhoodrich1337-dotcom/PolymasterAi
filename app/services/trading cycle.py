import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.utils import utc_now
from app.database.session import AsyncSessionLocal
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient
from app.market_data.scanner import MarketScanner
from app.models.market import Market
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.signal import Signal
from app.paper_trading.engine import PaperTradingEngine
from app.risk.manager import RiskManager
from app.risk.overrides import effective, load_overrides
from app.services.portfolio_ops import manage_positions, valuate
from app.strategies.arbitrage import ArbitrageResearchStrategy
from app.strategies.base import BaseStrategy, StrategySignal
from app.strategies.latency_monitor import LatencyMonitorStrategy
from app.strategies.market_making import MarketMakingResearchStrategy
from app.strategies.sports import SportsStrategy
from app.strategies.weather import WeatherStrategy

logger = get_logger(__name__)

LAST_CYCLE: dict[str, Any] = {}

MIN_EDGE = 0.03
MIN_NET_EDGE = 0.01
MIN_CONFIDENCE = 0.30
MAX_ORDERS_PER_CYCLE = 3
DEDUPE_MINUTES = 60


def build_strategies(settings: Settings) -> list[BaseStrategy]:
    strategies: list[BaseStrategy] = [ArbitrageResearchStrategy(), MarketMakingResearchStrategy(), LatencyMonitorStrategy()]
    if settings.weather_provider_url:
        strategies.append(WeatherStrategy(settings.weather_provider_url, settings.weather_api_key))
    if settings.odds_provider_url:
        strategies.append(SportsStrategy(settings.odds_provider_url, settings.odds_api_key))
    return strategies


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def upsert_markets(db: AsyncSession, markets: list[dict[str, Any]]) -> set[str]:
    saved: set[str] = set()
    for m in markets:
        row = await db.get(Market, m["id"])
        if row is None:
            clash = await db.execute(select(Market.id).where(Market.condition_id == m["condition_id"]))
            if clash.first() is not None:
                continue
            row = Market(id=m["id"], condition_id=m["condition_id"], question=m.get("question") or "")
            db.add(row)
        row.question = m.get("question") or row.question or ""
        row.slug = m.get("slug")
        row.category = m.get("category")
        row.outcomes = json.dumps(m.get("outcomes") or [])
        row.clob_token_ids = json.dumps(m.get("clob_token_ids") or [])
        row.end_date = _parse_dt(m.get("end_date"))
        row.active = bool(m.get("active", True))
        row.closed = bool(m.get("closed", False))
        row.neg_risk = bool(m.get("neg_risk", False))
        row.liquidity = float(m.get("liquidity") or 0.0)
        row.volume = float(m.get("volume") or 0.0)
        row.volume_24hr = float(m.get("volume_24hr") or 0.0)
        row.spread = float(m.get("spread") or 1.0)
        saved.add(m["id"])
    await db.commit()
    return saved


def _rejection_reason(sig: StrategySignal, market: dict[str, Any], settings: Settings) -> str | None:
    if sig.rejection_reason:
        return sig.rejection_reason
    if sig.edge <= 0:
        return "Negative edge: short/opposite side is not supported in paper mode"
    if sig.edge < MIN_EDGE:
        return f"Edge {sig.edge:.4f} below minimum {MIN_EDGE}"
    if sig.confidence < MIN_CONFIDENCE:
        return f"Confidence {sig.confidence:.2f} below minimum {MIN_CONFIDENCE}"
    cost = float(market.get("spread") or 0.0) / 2.0 + (settings.paper_slippage_bps + settings.paper_fee_bps) / 10_000.0
    net = sig.edge - cost
    if net < MIN_NET_EDGE:
        return f"Net edge {net:.4f} after spread/slippage/fees is below {MIN_NET_EDGE}"
    return None


def _kelly_size(sig: StrategySignal, settings: Settings) -> float:
    """Fractional Kelly: bet more only when the estimated edge is larger. Capped by max_position_size."""
    p = min(max(sig.market_probability, 0.01), 0.99)
    q = min(max(sig.estimated_probability, 0.0), 1.0)
    fraction = max(0.0, (q - p) / (1.0 - p))
    size = settings.trading_budget * settings.kelly_fraction * fraction
    return min(max(size, 1.0), settings.max_position_size)


async def _recent_signal_exists(db: AsyncSession, strategy: str, market_id: str, since: datetime) -> bool:
    result = await db.execute(select(Signal.id).where(Signal.strategy == strategy, Signal.market_id == market_id, Signal.created_at >= since).limit(1))
    return result.first() is not None


async def _has_open_position(db: AsyncSession, market_id: str) -> bool:
    result = await db.execute(select(Position.id).where(Position.market_id == market_id, Position.size > 0).limit(1))
    return result.first() is not None


async def _evaluate_markets(db: AsyncSession, clob: ClobClient, markets: list[dict[str, Any]], settings: Settings, stats: dict[str, int]) -> None:
    saved = await upsert_markets(db, markets)
    markets = [m for m in markets if m["id"] in saved]
    stats["markets"] = len(markets)
    strategies = build_strategies(settings)
    engine = PaperTradingEngine(clob, RiskManager(), slippage_bps=settings.paper_slippage_bps, fee_bps=settings.paper_fee_bps)
    since = utc_now() - timedelta(minutes=DEDUPE_MINUTES)
    for market in markets:
        for strategy in strategies:
            try:
                sig = await strategy.evaluate(market)
            except Exception:
                logger.exception("Strategy %s failed on market %s", strategy.name, market["id"])
                continue
            if sig is None:
                continue
            if await _recent_signal_exists(db, sig.strategy, sig.market_id, since):
                continue
            rejection = _rejection_reason(sig, market, settings)
            row = Signal(
                strategy=sig.strategy, market_id=sig.market_id, outcome=sig.outcome[:32],
                market_probability=sig.market_probability, estimated_probability=sig.estimated_probability,
                edge=sig.edge, confidence=sig.confidence, sources_json=json.dumps(sig.sources),
                reason=sig.reason, rejection_reason=rejection, accepted=False,
            )
            db.add(row)
            await db.commit()
            stats["signals"] += 1
            if rejection is not None or not settings.auto_paper_trading or stats["orders"] >= MAX_ORDERS_PER_CYCLE:
                continue
            if await _has_open_position(db, sig.market_id):
                row.rejection_reason = "Position already open in this market"
                await db.commit()
                continue
            try:
                order = await engine.execute_signal(
                    db=db, signal_id=row.id, market_id=sig.market_id, token_id=sig.token_id,
                    outcome=sig.outcome, strategy=sig.strategy, size_usd=_kelly_size(sig, settings),
                )
            except Exception:
                logger.exception("Paper execution failed for signal %s", row.id)
                await db.rollback()
                order = None
            if order is not None:
                row.accepted = True
                stats["orders"] += 1
            else:
                row.rejection_reason = "Blocked by risk manager or no liquidity (see logs)"
            await db.commit()


async def _record_snapshot(db: AsyncSession, clob: ClobClient, settings: Settings) -> None:
    try:
        v = await valuate(db, clob, settings.initial_capital)
        db.add(PortfolioSnapshot(cash=v["cash"], positions_value=v["positions_value"], total_equity=v["total_equity"],
                                 realized_pnl=v["realized_pnl"], unrealized_pnl=v["unrealized_pnl"], drawdown=v["drawdown"]))
        await db.commit()
    except Exception:
        logger.exception("Snapshot failed")
        await db.rollback()


async def run_cycle() -> dict[str, int]:
    """One pass: manage open paper positions -> scan markets -> strategies -> risk -> paper orders -> snapshot.
    Paper trading only: this code never sends real orders."""
    settings = get_settings()
    stats = {"markets": 0, "signals": 0, "orders": 0, "closed": 0}
    gamma = GammaClient()
    clob = ClobClient()
    try:
        async with AsyncSessionLocal() as db:
            vals = effective(await load_overrides(db))
            try:
                closed = await manage_positions(db, clob, gamma, vals, settings.paper_slippage_bps, settings.paper_fee_bps)
                stats["closed"] = len(closed)
            except Exception:
                logger.exception("Position management failed")
        markets: list[dict[str, Any]] = []
        scanner = MarketScanner(gamma, clob)
        try:
            markets = await scanner.scan(limit=100)
        except Exception:
            logger.exception("Market scan failed")
        async with AsyncSessionLocal() as db:
            if markets:
                await _evaluate_markets(db, clob, markets, settings, stats)
            await _record_snapshot(db, clob, settings)
        LAST_CYCLE.clear()
        LAST_CYCLE.update({**stats, "at": utc_now().isoformat(), "scanner": dict(scanner.last_stats)})
        logger.info("Cycle done: markets=%d signals=%d paper_orders=%d closed=%d", stats["markets"], stats["signals"], stats["orders"], stats["closed"])
    finally:
        await gamma.close()
        await clob.close()
    return stats

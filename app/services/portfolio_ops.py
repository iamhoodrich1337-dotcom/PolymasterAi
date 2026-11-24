import time
from typing import Any
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.core.utils import parse_float, safe_json_loads, utc_now
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient
from app.models.market import Market
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.trade import Trade
from app.paper_trading.simulator import PaperSimulator

logger = get_logger(__name__)
_price_cache: dict[str, tuple[float, float]] = {}


async def _mark_price(clob: ClobClient, token_id: str, fallback: float) -> float:
    now = time.time()
    cached = _price_cache.get(token_id)
    if cached and now - cached[0] < 20:
        return cached[1]
    price = fallback
    try:
        book = await clob.get_order_book(token_id)
        bids = book.get("bids") or []
        if bids:
            price = float(bids[0][0])
    except Exception:
        pass
    _price_cache[token_id] = (now, price)
    return price


async def _buy_strategies(db: AsyncSession) -> dict[int, str]:
    result = await db.execute(select(Trade.position_id, Trade.strategy).where(Trade.side == "BUY").order_by(desc(Trade.executed_at)))
    out: dict[int, str] = {}
    for pid, strategy in result.all():
        if pid is not None and pid not in out:
            out[pid] = strategy
    return out


async def valuate(db: AsyncSession, clob: ClobClient, initial_capital: float) -> dict[str, Any]:
    realized = float(await db.scalar(select(func.coalesce(func.sum(Trade.realized_pnl), 0.0))) or 0.0)
    rows = (await db.execute(
        select(Position, Market.question).join(Market, Market.id == Position.market_id, isouter=True).where(Position.size > 0)
    )).all()
    strategies = await _buy_strategies(db)
    positions: list[dict[str, Any]] = []
    total_cost = 0.0
    total_value = 0.0
    for pos, question in rows:
        price = await _mark_price(clob, pos.token_id, float(pos.avg_price))
        cost = float(pos.size) * float(pos.avg_price)
        value = float(pos.size) * price
        total_cost += cost
        total_value += value
        positions.append({
            "id": pos.id, "market_id": pos.market_id, "question": question or pos.market_id, "outcome": pos.outcome,
            "size": round(float(pos.size), 4), "avg_price": round(float(pos.avg_price), 4), "current_price": round(price, 4),
            "cost": round(cost, 2), "value": round(value, 2), "pnl": round(value - cost, 2),
            "pnl_pct": round((value / cost - 1) * 100, 1) if cost > 0 else 0.0,
            "strategy": strategies.get(pos.id, "unknown"), "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
        })
    cash = initial_capital + realized - total_cost
    equity = cash + total_value
    peak = await db.scalar(select(func.max(PortfolioSnapshot.total_equity)))
    peak = max(float(peak or 0.0), initial_capital, equity)
    return {
        "cash": round(cash, 2), "positions_value": round(total_value, 2), "total_equity": round(equity, 2),
        "realized_pnl": round(realized, 2), "unrealized_pnl": round(total_value - total_cost, 2),
        "drawdown": round(max(0.0, peak - equity), 2), "exposure": round(total_cost, 2),
        "open_positions": len(positions), "positions": positions, "timestamp": utc_now().isoformat(),
    }


async def trade_stats(db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(select(Trade.strategy, Trade.realized_pnl).where(Trade.side == "SELL"))
    pnls = [(s, float(p or 0.0)) for s, p in result.all()]
    wins = [p for _, p in pnls if p > 0]
    losses = [p for _, p in pnls if p < 0]
    by_strategy: dict[str, dict[str, float]] = {}
    for s, p in pnls:
        d = by_strategy.setdefault(s, {"trades": 0, "wins": 0, "pnl": 0.0})
        d["trades"] += 1
        d["wins"] += 1 if p > 0 else 0
        d["pnl"] = round(d["pnl"] + p, 2)
    gross_loss = abs(sum(losses))
    return {
        "closed_trades": len(pnls), "wins": len(wins),
        "win_rate": round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0,
        "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "by_strategy": by_strategy,
    }


async def manage_positions(db: AsyncSession, clob: ClobClient, gamma: GammaClient, vals: dict[str, float], slippage_bps: float, fee_bps: float) -> list[dict[str, Any]]:
    """Paper exits: settle resolved markets, take profit, stop loss. Never touches real money."""
    sim = PaperSimulator(slippage_bps=slippage_bps, fee_bps=fee_bps)
    take_profit = vals["exit_take_profit_pct"]
    stop_loss = vals["exit_stop_loss_pct"]
    closed: list[dict[str, Any]] = []
    positions = (await db.execute(select(Position).where(Position.size > 0))).scalars().all()
    for pos in positions:
        try:
            market = await db.get(Market, pos.market_id)
            tokens = safe_json_loads(market.clob_token_ids if market else None, [])
            idx = tokens.index(pos.token_id) if pos.token_id in tokens else 0
            settle: float | None = None
            try:
                gm = await gamma.get_market(pos.market_id)
            except Exception:
                gm = None
            if gm and gm.get("closed"):
                prices = safe_json_loads(gm.get("outcomePrices"), [])
                if idx < len(prices):
                    p = parse_float(prices[idx], -1.0)
                    if p >= 0.99:
                        settle = 1.0
                    elif 0.0 <= p <= 0.01:
                        settle = 0.0
            if settle is not None:
                sold, price, sell_fee, proceeds, reason = float(pos.size), settle, 0.0, settle * float(pos.size), "resolved"
            else:
                book = await clob.get_order_book(pos.token_id)
                bids = book.get("bids") or []
                if not bids or pos.avg_price <= 0:
                    continue
                bid = float(bids[0][0])
                ret = bid / float(pos.avg_price) - 1.0
                if ret >= take_profit:
                    reason = "take_profit"
                elif ret <= -stop_loss:
                    reason = "stop_loss"
                elif bid >= 0.97:
                    reason = "lock_profit"
                else:
                    continue
                fill = sim.simulate_sell(bids, float(pos.size))
                sold, price, sell_fee, proceeds = fill.sold_size, fill.avg_price, fill.fee, fill.proceeds
            fee_share = float(pos.fees_paid) * (sold / float(pos.size)) if pos.size > 0 else 0.0
            pnl = proceeds - float(pos.avg_price) * sold - fee_share
            last_buy = (await db.execute(
                select(Trade.strategy).where(Trade.position_id == pos.id, Trade.side == "BUY").order_by(desc(Trade.executed_at)).limit(1)
            )).scalar_one_or_none()
            pos.size = max(0.0, float(pos.size) - sold)
            if pos.size < 1e-9:
                pos.size = 0.0
            pos.realized_pnl = float(pos.realized_pnl) + pnl
            pos.fees_paid = max(0.0, float(pos.fees_paid) - fee_share)
            db.add(Trade(position_id=pos.id, market_id=pos.market_id, token_id=pos.token_id, side="SELL", price=price, size=sold, fee=sell_fee, realized_pnl=round(pnl, 6), strategy=last_buy or "unknown"))
            await db.commit()
            _price_cache.pop(pos.token_id, None)
            closed.append({"market_id": pos.market_id, "reason": reason, "pnl": round(pnl, 4)})
            logger.info("Paper position closed: market=%s reason=%s pnl=%.4f", pos.market_id, reason, pnl)
        except Exception:
            logger.exception("Could not manage position %s", getattr(pos, "id", "?"))
            await db.rollback()
    return closed

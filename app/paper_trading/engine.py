from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.market_data.book_validation import check_book, normalize_levels
from app.market_data.clob_client import ClobClient
from app.models.market import Market
from app.models.paper_fill import PaperFill
from app.models.paper_order import PaperOrder
from app.models.position import Position
from app.models.trade import Trade
from app.paper_trading.simulator import PaperSimulator
from app.risk.manager import RiskManager

logger = get_logger(__name__)
CAPITAL_LOCK_KEY = 727001


async def _lock_capital(db: AsyncSession) -> None:
    """PostgreSQL: serialises 'risk check -> write position' so two strategies cannot both pass the same limit.
    The advisory lock is released on commit/rollback. Other databases (SQLite in tests) need no lock."""
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    if getattr(dialect, "name", "") == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": CAPITAL_LOCK_KEY})


class PaperTradingEngine:
    def __init__(self, clob: ClobClient, risk: RiskManager, slippage_bps: float = 50.0, fee_bps: float = 0.0) -> None:
        self.clob = clob
        self.risk = risk
        self.simulator = PaperSimulator(slippage_bps=slippage_bps, fee_bps=fee_bps)

    async def execute_signal(self, db: AsyncSession, signal_id: int, market_id: str, token_id: str, outcome: str, strategy: str, size_usd: float) -> PaperOrder | None:
        await _lock_capital(db)
        market = (await db.execute(select(Market).where(Market.id == market_id))).scalar_one_or_none()
        if not market:
            logger.warning("Market %s not found", market_id)
            await db.commit()
            return None
        try:
            book = await self.clob.get_order_book(token_id)
        except Exception as exc:
            logger.warning("Order book unavailable for %s: %s", token_id, exc)
            await db.commit()
            return None
        check = check_book(book, require_bids=False)
        if not check.ok:
            logger.info("Signal %s skipped: invalid order book (%s)", signal_id, check.reason)
            await db.commit()
            return None
        asks = normalize_levels(book.get("asks"), False)
        best_ask = float(check.best_ask)
        # Buying any binary outcome token (YES or NO, any label) can lose the whole stake, so it is always a full-loss risk.
        decision = await self.risk.check_trade(db=db, market_id=market_id, token_id=token_id, intended_size_usd=size_usd, entry_price=best_ask, is_full_loss=True)
        if not decision.allowed:
            logger.info("Risk blocked signal %s: %s", signal_id, decision.reason)
            await db.commit()
            return None
        size_usd = decision.adjusted_size
        try:
            fill = self.simulator.simulate_buy(asks, size_usd)
        except Exception as exc:
            logger.warning("Simulation failed for %s: %s", token_id, exc)
            await db.commit()
            return None
        order = PaperOrder(signal_id=signal_id, market_id=market_id, token_id=token_id, outcome=outcome, side="BUY", price=best_ask, size=round(size_usd / best_ask, 8), filled_size=fill.filled_size, avg_fill_price=fill.avg_price, fee=fill.fee, slippage=fill.slippage, status="PARTIAL" if fill.partial else "FILLED", reason="paper simulation")
        db.add(order)
        await db.flush()
        db.add(PaperFill(order_id=order.id, price=fill.avg_price, size=fill.filled_size, fee=fill.fee))
        position = (await db.execute(select(Position).where(Position.market_id == market_id, Position.token_id == token_id))).scalar_one_or_none()
        if position:
            total_size = position.size + fill.filled_size
            position.avg_price = round(((position.avg_price * position.size) + (fill.avg_price * fill.filled_size)) / total_size, 8)
            position.size = round(total_size, 8)
            position.fees_paid = round(position.fees_paid + fill.fee, 8)
        else:
            position = Position(market_id=market_id, token_id=token_id, outcome=outcome, size=fill.filled_size, avg_price=fill.avg_price, fees_paid=fill.fee)
            db.add(position)
            await db.flush()
        db.add(Trade(position_id=position.id, market_id=market_id, token_id=token_id, side="BUY", price=fill.avg_price, size=fill.filled_size, fee=fill.fee, realized_pnl=0.0, strategy=strategy))
        await db.commit()
        logger.info("Paper order %s filled: %.4f shares @ %.4f (cost %.4f)", order.id, fill.filled_size, fill.avg_price, fill.cost)
        return order

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.core.utils import safe_json_loads
from app.market_data.clob_client import ClobClient
from app.models.market import Market
from app.models.paper_fill import PaperFill
from app.models.paper_order import PaperOrder
from app.models.position import Position
from app.models.trade import Trade
from app.paper_trading.simulator import PaperSimulator
from app.risk.manager import RiskManager

logger = get_logger(__name__)

class PaperTradingEngine:
    def __init__(self, clob: ClobClient, risk: RiskManager, slippage_bps: float = 50.0, fee_bps: float = 0.0) -> None:
        self.clob = clob
        self.risk = risk
        self.simulator = PaperSimulator(slippage_bps=slippage_bps, fee_bps=fee_bps)

    async def execute_signal(self, db: AsyncSession, signal_id: int, market_id: str, token_id: str, outcome: str, strategy: str, size_usd: float) -> PaperOrder | None:
        result = await db.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one_or_none()
        if not market:
            logger.warning("Market %s not found", market_id)
            return None
        book = await self.clob.get_order_book(token_id)
        asks = [[float(p), float(q)] for p, q in (book.get("asks") or [])]
        if not asks:
            logger.info("No asks for %s; signal skipped", token_id)
            return None
        best_ask = asks[0][0]
        first_token = safe_json_loads(market.clob_token_ids, [""])[0]
        is_full_loss = outcome.lower() in ("yes", "no") and token_id == first_token
        decision = await self.risk.check_trade(db=db, market_id=market_id, token_id=token_id, intended_size_usd=size_usd, entry_price=best_ask, is_full_loss=is_full_loss)
        if not decision.allowed:
            logger.info("Risk blocked signal %s: %s", signal_id, decision.reason)
            return None
        size_usd = decision.adjusted_size
        try:
            fill = self.simulator.simulate_buy(asks, size_usd)
        except Exception as exc:
            logger.warning("Simulation failed for %s: %s", token_id, exc)
            return None
        order = PaperOrder(signal_id=signal_id, market_id=market_id, token_id=token_id, outcome=outcome, side="BUY", price=best_ask, size=size_usd / best_ask, filled_size=fill.filled_size, avg_fill_price=fill.avg_price, fee=fill.fee, slippage=fill.slippage, status="PARTIAL" if fill.partial else "FILLED", reason="paper simulation")
        db.add(order)
        await db.flush()
        db.add(PaperFill(order_id=order.id, price=fill.avg_price, size=fill.filled_size, fee=fill.fee))
        pos_result = await db.execute(select(Position).where(Position.market_id == market_id, Position.token_id == token_id))
        position = pos_result.scalar_one_or_none()
        if position:
            total_size = position.size + fill.filled_size
            position.avg_price = ((position.avg_price * position.size) + (fill.avg_price * fill.filled_size)) / total_size
            position.size = total_size
            position.fees_paid += fill.fee
        else:
            position = Position(market_id=market_id, token_id=token_id, outcome=outcome, size=fill.filled_size, avg_price=fill.avg_price, fees_paid=fill.fee)
            db.add(position)
            await db.flush()
        db.add(Trade(position_id=position.id, market_id=market_id, token_id=token_id, side="BUY", price=fill.avg_price, size=fill.filled_size, fee=fill.fee, realized_pnl=0.0, strategy=strategy))
        await db.commit()
        logger.info("Paper order %s filled: %.4f @ %.4f", order.id, fill.filled_size, fill.avg_price)
        return order

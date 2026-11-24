from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.utils import utc_now
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.trade import Trade
from app.schemas.portfolio import PortfolioSummary

class PortfolioManager:
    def __init__(self, initial_capital: float) -> None:
        self.initial_capital = initial_capital

    async def snapshot(self, db: AsyncSession) -> PortfolioSummary:
        realized = await db.scalar(select(func.coalesce(func.sum(Trade.realized_pnl), 0.0)))
        realized = float(realized or 0.0)
        positions_result = await db.execute(select(Position))
        positions = positions_result.scalars().all()
        positions_value = sum(float(p.size) * float(p.avg_price) for p in positions)
        unrealized = 0.0
        cash = self.initial_capital + realized - positions_value
        equity = cash + positions_value
        peak = max(self.initial_capital, equity)
        drawdown = max(0.0, peak - equity)
        snap = PortfolioSnapshot(cash=round(cash, 4), positions_value=round(positions_value, 4), total_equity=round(equity, 4), realized_pnl=round(realized, 4), unrealized_pnl=round(unrealized, 4), drawdown=round(drawdown, 4))
        db.add(snap)
        await db.commit()
        return PortfolioSummary(cash=round(cash, 4), positions_value=round(positions_value, 4), total_equity=round(equity, 4), realized_pnl=round(realized, 4), unrealized_pnl=round(unrealized, 4), drawdown=round(drawdown, 4), open_positions=len(positions), timestamp=utc_now())

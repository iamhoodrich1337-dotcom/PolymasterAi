from datetime import datetime
from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    positions_value: Mapped[float] = mapped_column(Float, default=0.0)
    total_equity: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

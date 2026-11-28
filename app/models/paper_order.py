from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base
from app.database.types import Money

class PaperOrder(Base):
    __tablename__ = "paper_orders"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    token_id: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    price: Mapped[float] = mapped_column(Money)
    size: Mapped[float] = mapped_column(Money)
    filled_size: Mapped[float] = mapped_column(Money, default=0.0)
    avg_fill_price: Mapped[float] = mapped_column(Money, default=0.0)
    fee: Mapped[float] = mapped_column(Money, default=0.0)
    slippage: Mapped[float] = mapped_column(Money, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

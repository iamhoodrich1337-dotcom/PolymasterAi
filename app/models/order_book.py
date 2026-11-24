from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class OrderBook(Base):
    __tablename__ = "order_books"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    token_id: Mapped[str] = mapped_column(String(128), index=True)
    bids_json: Mapped[str] = mapped_column(Text)
    asks_json: Mapped[str] = mapped_column(Text)
    tick_size: Mapped[float] = mapped_column(Float, default=0.01)
    min_order_size: Mapped[float] = mapped_column(Float, default=5.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

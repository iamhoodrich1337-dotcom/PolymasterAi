from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class Market(Base):
    __tablename__ = "markets"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    condition_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)
    clob_token_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    neg_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    volume_24hr: Mapped[float] = mapped_column(Float, default=0.0)
    spread: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

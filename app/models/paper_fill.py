from datetime import datetime
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base
from app.database.types import Money

class PaperFill(Base):
    __tablename__ = "paper_fills"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("paper_orders.id"), index=True)
    price: Mapped[float] = mapped_column(Money)
    size: Mapped[float] = mapped_column(Money)
    fee: Mapped[float] = mapped_column(Money, default=0.0)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

from datetime import datetime
from pydantic import BaseModel

class PortfolioSummary(BaseModel):
    cash: float
    positions_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    drawdown: float
    open_positions: int
    timestamp: datetime

from dataclasses import dataclass
from app.config import get_settings

@dataclass
class RiskLimits:
    max_position_size: float
    max_loss_per_trade: float
    max_market_exposure: float
    max_total_exposure: float
    max_correlated_exposure: float
    daily_stop_loss: float
    weekly_stop_loss: float
    max_drawdown: float

def load_limits() -> RiskLimits:
    s = get_settings()
    return RiskLimits(max_position_size=s.max_position_size, max_loss_per_trade=s.max_loss_per_trade, max_market_exposure=s.max_market_exposure, max_total_exposure=s.max_total_exposure, max_correlated_exposure=s.max_correlated_exposure, daily_stop_loss=s.daily_stop_loss, weekly_stop_loss=s.weekly_stop_loss, max_drawdown=s.max_drawdown)

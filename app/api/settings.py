from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("")
async def get_settings_endpoint() -> dict:
    s = get_settings()
    return {"initial_capital": s.initial_capital, "reserve": s.reserve, "trading_budget": s.trading_budget, "execution_reserve": s.execution_reserve, "untouchable_reserve": s.untouchable_reserve, "max_position_size": s.max_position_size, "max_loss_per_trade": s.max_loss_per_trade, "live_trading_enabled": s.live_trading_enabled, "live_mode": "LOCKED" if not s.live_trading_enabled else "UNLOCKED"}

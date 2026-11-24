from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database.session import get_db
from app.risk.kill_switch import KillSwitch
from app.risk.limits import load_limits
from app.risk.manager import RiskManager

router = APIRouter(prefix="/risk", tags=["risk"])
kill_switch = KillSwitch()

@router.get("")
async def risk_status() -> dict:
    limits = load_limits()
    return {"kill_switch_engaged": kill_switch.engaged, "kill_switch_reason": kill_switch.reason, "limits": {"max_position_size": limits.max_position_size, "max_loss_per_trade": limits.max_loss_per_trade, "max_total_exposure": limits.max_total_exposure, "daily_stop_loss": limits.daily_stop_loss, "weekly_stop_loss": limits.weekly_stop_loss, "max_drawdown": limits.max_drawdown}, "live_mode": "LOCKED"}

@router.get("/monthly")
async def monthly_risk(db: AsyncSession = Depends(get_db)) -> dict:
    settings = get_settings()
    manager = RiskManager()
    return await manager.monthly_performance(db, settings.initial_capital)

@router.post("/emergency-stop")
async def emergency_stop(reason: str = "manual API call") -> dict:
    kill_switch.engage(reason)
    return {"engaged": True, "reason": reason}

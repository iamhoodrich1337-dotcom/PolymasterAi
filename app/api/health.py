from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.core.live_guard import live_mode_label
from app.database.session import AsyncSessionLocal
from app.services import trading_cycle

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    db_ok = False
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    # Market-data health = the last scan cycle saw markets recently (no fake token probes).
    cycle = trading_cycle.LAST_CYCLE
    age = None
    data_ok = False
    if cycle.get("at"):
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(cycle["at"])).total_seconds()
        data_ok = bool(cycle.get("markets")) and age < 600
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "polymarket_clob": data_ok,
            "last_cycle_age_seconds": round(age) if age is not None else None, "live_mode": live_mode_label(get_settings().live_trading_enabled)}

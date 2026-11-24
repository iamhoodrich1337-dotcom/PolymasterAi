from fastapi import APIRouter
from sqlalchemy import text
from app.database.session import AsyncSessionLocal
from app.market_data.clob_client import ClobClient

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
    clob_ok = False
    client = ClobClient()
    try:
        await client.get_midpoint("0")
        clob_ok = True
    except Exception:
        pass
    finally:
        await client.close()
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "polymarket_clob": clob_ok, "live_mode": "LOCKED"}

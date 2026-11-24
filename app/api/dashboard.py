from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.session import get_db
from app.market_data.clob_client import ClobClient
from app.models.market import Market
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.signal import Signal
from app.models.trade import Trade
from app.risk.manager import RiskManager
from app.risk.overrides import (
    ALL_FIELDS, defaults, effective, get_kill, load_overrides, save_overrides, set_kill, validate,
)
from app.services import trading_cycle
from app.services.portfolio_ops import trade_stats, valuate

router = APIRouter(prefix="/dash", tags=["dashboard"])


def _iso(dt: Any) -> str | None:
    return dt.isoformat() if dt else None


async def _valuate(db: AsyncSession) -> dict[str, Any]:
    clob = ClobClient()
    try:
        return await valuate(db, clob, get_settings().initial_capital)
    finally:
        await clob.close()


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    v = await _valuate(db)
    vals = effective(await load_overrides(db))
    daily = await RiskManager()._daily_realized_pnl(db)
    return {
        "mode": "PAPER", "live": "LOCKED", "initial_capital": get_settings().initial_capital,
        "total_equity": v["total_equity"], "cash": v["cash"], "realized_pnl": v["realized_pnl"],
        "unrealized_pnl": v["unrealized_pnl"], "drawdown": v["drawdown"], "exposure": v["exposure"],
        "open_positions": v["open_positions"], "daily_pnl": round(daily, 2),
        "limits": {"max_drawdown": vals["max_drawdown"], "exposure": vals["max_total_exposure"], "daily_stop": vals["daily_stop_loss"]},
        "kill": await get_kill(db), "stats": await trade_stats(db), "last_cycle": trading_cycle.LAST_CYCLE or None,
    }


@router.get("/equity")
async def equity_curve(limit: int = 300, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(PortfolioSnapshot.captured_at, PortfolioSnapshot.total_equity).order_by(desc(PortfolioSnapshot.captured_at)).limit(min(limit, 1000))
    )).all()
    return [{"t": _iso(t), "equity": float(e)} for t, e in reversed(rows)]


@router.get("/positions")
async def positions(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return (await _valuate(db))["positions"]


@router.get("/trades")
async def trades(limit: int = 100, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(Trade, Market.question).join(Market, Market.id == Trade.market_id, isouter=True).order_by(desc(Trade.executed_at)).limit(min(limit, 500))
    )).all()
    return [{
        "id": t.id, "question": q or t.market_id, "side": t.side, "strategy": t.strategy,
        "size": round(float(t.size), 4), "price": round(float(t.price), 4),
        "usd": round(float(t.size) * float(t.price), 2), "pnl": round(float(t.realized_pnl), 2), "at": _iso(t.executed_at),
    } for t, q in rows]


@router.get("/signals")
async def signals(limit: int = 60, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(Signal, Market.question).join(Market, Market.id == Signal.market_id, isouter=True).order_by(desc(Signal.created_at)).limit(min(limit, 300))
    )).all()
    return [{
        "id": s.id, "question": q or s.market_id, "strategy": s.strategy, "outcome": s.outcome,
        "market_probability": round(float(s.market_probability), 3), "estimated_probability": round(float(s.estimated_probability), 3),
        "edge": round(float(s.edge), 3), "accepted": bool(s.accepted), "rejection_reason": s.rejection_reason, "at": _iso(s.created_at),
    } for s, q in rows]


@router.get("/risk")
async def risk_get(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    overrides = await load_overrides(db)
    base = defaults()
    values = effective(overrides)
    rm = RiskManager()
    v = await _valuate(db)
    return {
        "values": values, "defaults": base,
        "overridden": [k for k in overrides if abs(overrides[k] - base.get(k, 0.0)) > 1e-12],
        "usage": {
            "exposure": v["exposure"], "daily_pnl": round(await rm._daily_realized_pnl(db), 2),
            "weekly_pnl": round(await rm._weekly_realized_pnl(db), 2), "total_pnl": round(await rm._all_time_pnl(db), 2),
        },
        "kill": await get_kill(db),
    }


@router.put("/risk")
async def risk_put(payload: dict = Body(...), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    updates = payload.get("values")
    if not isinstance(updates, dict):
        raise HTTPException(status_code=422, detail="Нужен объект values")
    existing = await load_overrides(db)
    clean, errors = validate(updates, get_settings().initial_capital, effective(existing))
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    await save_overrides(db, {**existing, **clean})
    return {"saved": sorted(clean)}


@router.post("/risk/kill")
async def risk_kill(payload: dict = Body(...), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    engaged = bool(payload.get("engaged"))
    await set_kill(db, engaged, str(payload.get("reason") or "")[:200] if engaged else "")
    return await get_kill(db)


@router.post("/risk/reset")
async def risk_reset(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    await save_overrides(db, {})
    return {"reset": True, "fields": list(ALL_FIELDS)}

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.models.signal import Signal

router = APIRouter(prefix="/signals", tags=["signals"])

@router.get("")
async def list_signals(limit: int = 100, db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(Signal).order_by(desc(Signal.created_at)).limit(limit))
    signals = result.scalars().all()
    return [{"id": s.id, "strategy": s.strategy, "market_id": s.market_id, "outcome": s.outcome, "market_probability": s.market_probability, "estimated_probability": s.estimated_probability, "edge": s.edge, "confidence": s.confidence, "accepted": s.accepted, "rejection_reason": s.rejection_reason, "created_at": s.created_at.isoformat()} for s in signals]

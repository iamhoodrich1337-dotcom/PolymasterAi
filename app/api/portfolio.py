from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database.session import get_db
from app.portfolio.manager import PortfolioManager

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("")
async def get_portfolio(db: AsyncSession = Depends(get_db)) -> dict:
    settings = get_settings()
    manager = PortfolioManager(settings.initial_capital)
    summary = await manager.snapshot(db)
    return summary.model_dump(mode="json")

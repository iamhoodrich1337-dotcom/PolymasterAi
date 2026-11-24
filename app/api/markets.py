from fastapi import APIRouter, Query
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient
from app.market_data.scanner import MarketScanner

router = APIRouter(prefix="/markets", tags=["markets"])

@router.get("")
async def list_markets(limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    gamma = GammaClient(); clob = ClobClient()
    scanner = MarketScanner(gamma, clob)
    try:
        return await scanner.scan(limit=limit)
    finally:
        await gamma.close(); await clob.close()

@router.get("/{market_id}/book")
async def order_book(market_id: str, token_id: str) -> dict:
    clob = ClobClient()
    try:
        return await clob.get_order_book(token_id)
    finally:
        await clob.close()

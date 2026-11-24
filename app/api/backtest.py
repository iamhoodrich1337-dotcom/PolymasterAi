from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.backtesting.engine import BacktestEngine
from app.backtesting.historical_loader import HistoricalDataLoader
from app.backtesting.metrics import monthly_returns_pct
from app.database.session import get_db
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient

router = APIRouter(prefix="/backtest", tags=["backtest"])

class BacktestRequest(BaseModel):
    strategy: str
    trades: list[dict]
    out_of_sample: bool = False

class HistoricalBacktestRequest(BaseModel):
    strategy: str
    closed_within_days: int = 365
    limit_markets: int = 50
    fidelity: int = 60

@router.post("/run")
async def run_backtest(payload: BacktestRequest, db: AsyncSession = Depends(get_db)) -> dict:
    engine = BacktestEngine()
    run = await engine.run(db, payload.strategy, payload.trades, payload.out_of_sample)
    return {"run_id": run.id, "strategy": run.strategy, "roi": run.roi, "max_drawdown": run.max_drawdown, "win_rate": run.win_rate, "profit_factor": run.profit_factor, "total_trades": run.total_trades, "out_of_sample": run.out_of_sample}

@router.post("/historical")
async def backtest_historical(payload: HistoricalBacktestRequest) -> dict:
    gamma = GammaClient(); clob = ClobClient()
    loader = HistoricalDataLoader(gamma, clob)
    try:
        markets = await loader.load_closed_markets(closed_within_days=payload.closed_within_days, limit=payload.limit_markets)
        pnls_with_dates: list[tuple] = []
        initial_capital = 100.0
        for m in markets:
            histories = await loader.load_price_history_for_market(m, interval="max", fidelity=payload.fidelity)
            yes_points = histories.get(m["token_ids"][0], [])
            for i in range(len(yes_points) - 1):
                p_now = float(yes_points[i].get("p") or yes_points[i].get("price") or 0)
                p_next = float(yes_points[i + 1].get("p") or yes_points[i + 1].get("price") or 0)
                if p_now <= 0.0 or p_next <= 0.0:
                    continue
                if p_now < 0.30 and p_next >= 0.50:
                    size = 1.0 / p_now
                    pnl = (p_next - p_now) * size
                    ts = yes_points[i + 1].get("t") or yes_points[i + 1].get("timestamp")
                    try:
                        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    except Exception:
                        continue
                    pnls_with_dates.append((dt, pnl))
        monthly = monthly_returns_pct(pnls_with_dates, initial_capital)
        total_pnl = sum(p for _, p in pnls_with_dates)
        return {"strategy": payload.strategy, "markets_loaded": len(markets), "simulated_trades": len(pnls_with_dates), "total_pnl": round(total_pnl, 4), "monthly_returns_pct": monthly, "initial_capital": initial_capital}
    finally:
        await gamma.close(); await clob.close()

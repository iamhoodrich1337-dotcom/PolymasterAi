from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path
from app.api import backtest, health, markets, portfolio, risk, settings, signals, strategies
from app.core.auth import require_admin
from app.core.logging import get_logger, setup_logging
from app.database.init_db import init_db
from app.services.scheduler import start_scheduler, stop_scheduler

setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting POLYMASTER AI")
    await init_db()
    await start_scheduler()
    yield
    await stop_scheduler()
    logger.info("POLYMASTER AI stopped")

app = FastAPI(title="POLYMASTER AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router, prefix="/api")
_protected = [Depends(require_admin)]
app.include_router(markets.router, prefix="/api", dependencies=_protected)
app.include_router(signals.router, prefix="/api", dependencies=_protected)
app.include_router(portfolio.router, prefix="/api", dependencies=_protected)
app.include_router(risk.router, prefix="/api", dependencies=_protected)
app.include_router(strategies.router, prefix="/api", dependencies=_protected)
app.include_router(backtest.router, prefix="/api", dependencies=_protected)
app.include_router(settings.router, prefix="/api", dependencies=_protected)

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    template = Path("app/dashboard/templates/index.html")
    return template.read_text() if template.exists() else "POLYMASTER AI"

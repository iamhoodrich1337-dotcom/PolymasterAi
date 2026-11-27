from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse

from app.api import backtest, dashboard, health, markets, portfolio, risk, settings, signals, strategies
from app.core.auth import require_admin
from app.core.logging import get_logger, setup_logging
from app.database.init_db import init_db
from app.database.migrate import run_migrations
from app.services.scheduler import start_scheduler, stop_scheduler

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting POLYMASTER AI")
    await init_db()
    await run_migrations()
    await start_scheduler()
    yield
    await stop_scheduler()
    logger.info("POLYMASTER AI stopped")


app = FastAPI(title="POLYMASTER AI", version="1.0.0", lifespan=lifespan)

app.include_router(health.router, prefix="/api")
_protected = [Depends(require_admin)]
for _router in (dashboard, markets, signals, portfolio, risk, strategies, backtest, settings):
    app.include_router(_router.router, prefix="/api", dependencies=_protected)


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    template = Path("app/dashboard/templates/index.html")
    return template.read_text() if template.exists() else "POLYMASTER AI"

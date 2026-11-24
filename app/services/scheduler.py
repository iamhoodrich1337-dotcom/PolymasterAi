from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.core.logging import get_logger
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient
from app.market_data.scanner import MarketScanner

logger = get_logger(__name__)
scheduler = AsyncIOScheduler()

async def scan_job() -> None:
    gamma = GammaClient(); clob = ClobClient()
    scanner = MarketScanner(gamma, clob)
    try:
        markets = await scanner.scan(limit=100)
        logger.info("Scheduled scan complete: %d markets", len(markets))
    except Exception:
        logger.exception("Scheduled scan failed")
    finally:
        await gamma.close(); await clob.close()

async def start_scheduler() -> None:
    settings = get_settings()
    scheduler.add_job(scan_job, IntervalTrigger(seconds=settings.scan_interval_seconds), id="market_scan", replace_existing=True, max_instances=1)
    scheduler.start()
    logger.info("Scheduler started (scan every %ss)", settings.scan_interval_seconds)

async def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)

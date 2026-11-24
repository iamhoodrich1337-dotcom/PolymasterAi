from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.core.logging import get_logger
from app.services.trading_cycle import run_cycle

logger = get_logger(__name__)
scheduler = AsyncIOScheduler()

async def scan_job() -> None:
    try:
        await run_cycle()
    except Exception:
        logger.exception("Trading cycle failed")

async def start_scheduler() -> None:
    settings = get_settings()
    scheduler.add_job(scan_job, IntervalTrigger(seconds=settings.scan_interval_seconds), id="market_scan", replace_existing=True, max_instances=1)
    scheduler.start()
    logger.info("Scheduler started (cycle every %ss)", settings.scan_interval_seconds)

async def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)

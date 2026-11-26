from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.core.logging import get_logger
from app.services.trading_cycle import run_cycle
from app.weather.engine import run_weather_scan
from app.weather.settle import settle_weather

logger = get_logger(__name__)
scheduler = AsyncIOScheduler()

async def scan_job() -> None:
    try:
        await run_cycle()
    except Exception:
        logger.exception("Trading cycle failed")

async def weather_job() -> None:
    try:
        await run_weather_scan()
    except Exception:
        logger.exception("Weather scan failed")
    try:
        await settle_weather()
    except Exception:
        logger.exception("Weather settle failed")

async def start_scheduler() -> None:
    settings = get_settings()
    scheduler.add_job(scan_job, IntervalTrigger(seconds=settings.scan_interval_seconds), id="market_scan", replace_existing=True, max_instances=1)
    scheduler.add_job(weather_job, IntervalTrigger(minutes=30), id="weather_scan", replace_existing=True, max_instances=1, next_run_time=datetime.now(timezone.utc) + timedelta(seconds=40))
    scheduler.start()
    logger.info("Scheduler started (cycle every %ss)", settings.scan_interval_seconds)

async def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)

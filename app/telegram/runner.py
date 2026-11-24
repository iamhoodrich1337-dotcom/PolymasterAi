import asyncio
from app.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.telegram.bot import build_application

setup_logging()
logger = get_logger(__name__)

async def main() -> None:
    settings = get_settings()
    app = build_application()
    if app is None:
        logger.error("Cannot start Telegram bot: token missing")
        return
    if not settings.telegram_owner_id:
        logger.error("TELEGRAM_OWNER_ID is not set; bot will refuse all commands")
    async with app:
        await app.start()
        await app.updater.start_polling()
        logger.info("Telegram bot started")
        try:
            await asyncio.Event().wait()
        finally:
            await app.updater.stop()
            await app.stop()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


def _upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")


async def run_migrations() -> None:
    """Applies Alembic migrations at startup. A failure is logged but never stops the app (the existing schema keeps working)."""
    try:
        await asyncio.to_thread(_upgrade)
        logger.info("Database migrations are up to date")
    except Exception:
        logger.exception("Database migration failed; continuing with the existing schema")

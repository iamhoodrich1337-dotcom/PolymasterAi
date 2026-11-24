from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

def _owner_only(update: Update) -> bool:
    settings = get_settings()
    user = update.effective_user
    return bool(user and user.id == settings.telegram_owner_id)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text("POLYMASTER AI\n\nPaper trading mode is active. Live mode is LOCKED.\nUse /status, /balance, /risk, /pause.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    await update.message.reply_text("System: online\nMode: PAPER\nLive mode: LOCKED")

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    await update.message.reply_text("Paper balance available via dashboard /api/portfolio")

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    await update.message.reply_text("Risk limits: max position $5, max loss/trade $1, daily stop $3.")

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    from app.risk.kill_switch import KillSwitch
    KillSwitch().engage("paused via Telegram")
    await update.message.reply_text("Kill switch engaged. New trades blocked.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    from app.risk.kill_switch import KillSwitch
    KillSwitch().disengage("resumed via Telegram")
    await update.message.reply_text("Kill switch disengaged.")

async def cmd_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    await update.message.reply_text("Mode is always PAPER. Live trading requires manual unlock and gate completion.")

def build_application() -> Application | None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("Telegram token not configured; bot disabled")
        return None
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("paper", cmd_paper))
    return app

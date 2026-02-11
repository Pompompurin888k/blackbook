"""
Blackbook Bot - Main Entry Point
Orchestrates the modular bot architecture with persistence and centralized logging.
"""
import os
from datetime import timedelta
from telegram import Update
from telegram.ext import Application, PicklePersistence

from config import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from database import Database
from handlers import register_all_handlers
from utils.logger import get_logger, configure_root_logger
from db_context import set_db

# Setup centralized logging
configure_root_logger()
logger = get_logger(__name__)

# Persistence file path (keeps conversation state across restarts)
PERSISTENCE_FILE = os.path.join(os.path.dirname(__file__), "bot_persistence.pickle")


def main() -> None:
    """Run the bot."""
    # Validate required environment variables
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN environment variable not set!")
        raise ValueError("TELEGRAM_TOKEN environment variable is required")
    
    if not ADMIN_CHAT_ID:
        logger.warning("⚠️ ADMIN_CHAT_ID not set! Verification system will not work.")
    
    # Initialize database
    logger.info("🗄️ Initializing database connection...")
    db = Database()
    
    # Setup persistence (preserves conversation state across restarts)
    logger.info("💾 Loading conversation persistence...")
    persistence = PicklePersistence(filepath=PERSISTENCE_FILE)
    
    # Create the Application with persistence
    logger.info("🤖 Building Telegram application...")
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .persistence(persistence)
        .build()
    )
    
    # IMPORTANT: Store database in db_context module (NOT bot_data)
    # Database objects are not picklable, so they can't be stored in persisted bot_data
    set_db(db)
    logger.info("🗄️ Database registered in db_context")
    
    # Register all handlers from modular structure
    logger.info("📦 Registering handlers...")
    register_all_handlers(application, db)
    
    # ==================== SCHEDULED JOBS ====================
    job_queue = application.job_queue
    
    # Deactivate expired subscriptions every 15 minutes
    async def check_expired_subscriptions(context):
        """Periodic job: deactivate providers whose subscription has expired."""
        count = db.deactivate_expired_subscriptions()
        if count > 0:
            logger.info(f"⏰ Deactivated {count} expired subscription(s)")
    
    # Check overdue safety sessions every 2 minutes
    async def check_overdue_sessions(context):
        """Periodic job: alert admin about overdue safety sessions."""
        overdue = db.get_overdue_sessions()
        for session in overdue:
            provider_name = session.get("display_name", "Unknown")
            provider_phone = session.get("phone", "N/A")
            telegram_id = session.get("telegram_id")
            expected_back = session.get("expected_check_back")
            
            alert_text = (
                "🚨 *EMERGENCY: OVERDUE CHECK-IN*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Provider: *{provider_name}*\n"
                f"📱 Phone: `{provider_phone}`\n"
                f"⏰ Expected back: {expected_back.strftime('%H:%M') if expected_back else 'Unknown'}\n\n"
                "*Provider has NOT checked in!*\n"
                "Immediate follow-up recommended."
            )
            
            try:
                if ADMIN_CHAT_ID:
                    await context.bot.send_message(
                        chat_id=int(ADMIN_CHAT_ID),
                        text=alert_text,
                        parse_mode="Markdown"
                    )
                    db.mark_session_alerted(session["id"])
                    logger.warning(f"🚨 Overdue session alert sent for {provider_name}")
            except Exception as e:
                logger.error(f"❌ Failed to send overdue alert: {e}")
    
    if job_queue is not None:
        job_queue.run_repeating(check_expired_subscriptions, interval=timedelta(minutes=15), first=timedelta(seconds=30))
        job_queue.run_repeating(check_overdue_sessions, interval=timedelta(minutes=2), first=timedelta(seconds=60))
        logger.info("⏰ Scheduled jobs registered (expiry check / session alerts)")
    else:
        logger.warning(
            "⚠️ JobQueue is unavailable. Install with: pip install \"python-telegram-bot[job-queue]\" "
            "to enable scheduled expiry/session checks."
        )
    
    # Start the bot
    logger.info("🚀 Blackbook Bot is starting...")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  Modules loaded:")
    logger.info("    ✓ handlers/auth.py")
    logger.info("    ✓ handlers/safety.py")
    logger.info("    ✓ handlers/payment.py")
    logger.info("    ✓ handlers/admin.py")
    logger.info("    ✓ services/metapay.py")
    logger.info("    ✓ utils/logger.py")
    logger.info("  Features:")
    logger.info("    ✓ PicklePersistence (conversation state survives restarts)")
    logger.info("    ✓ Centralized logging (module-aware)")
    logger.info("    ✓ Scheduled subscription expiry checks (every 15 min)")
    logger.info("    ✓ Scheduled overdue session alerts (every 2 min)")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

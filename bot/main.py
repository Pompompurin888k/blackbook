"""
Blackbook Bot - Main Entry Point
Orchestrates the modular bot architecture with persistence and centralized logging.
"""
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, PicklePersistence

from config import (
    TELEGRAM_TOKEN,
    ADMIN_CHAT_ID,
    FREE_TRIAL_REMINDER_DAY5_HOURS,
    FREE_TRIAL_FINAL_REMINDER_HOURS,
)
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

        # Notify providers when free trial has ended (single notification).
        expired_trials = db.get_unnotified_expired_trials()
        for provider in expired_trials:
            tg_id = provider.get("telegram_id")
            name = provider.get("display_name", "there")
            try:
                await context.bot.send_message(
                    chat_id=tg_id,
                    text=(
                        "⌛ *Free Trial Ended*\n\n"
                        f"Hi {name}, your trial has ended and your listing is now paused.\n\n"
                        "To go live again immediately, choose any paid package in 💰 Top up Balance."
                    ),
                    parse_mode="Markdown",
                )
                db.mark_trial_expired_notified(tg_id)
            except Exception as e:
                logger.error(f"❌ Failed to send trial-expired notification to {tg_id}: {e}")

    async def check_trial_reminders(context):
        """Periodic job: send day-5 and last-day trial reminders."""
        now = datetime.now()
        candidates = db.get_trial_reminder_candidates()
        day5_sent = 0
        final_sent = 0

        for provider in candidates:
            tg_id = provider.get("telegram_id")
            expiry = provider.get("expiry_date")
            if not tg_id or not expiry:
                continue

            hours_left = (expiry - now).total_seconds() / 3600.0
            if hours_left <= 0:
                continue

            display_name = provider.get("display_name", "there")
            if (
                hours_left <= FREE_TRIAL_FINAL_REMINDER_HOURS
                and not provider.get("trial_reminder_lastday_sent")
            ):
                try:
                    await context.bot.send_message(
                        chat_id=tg_id,
                        text=(
                            "⚠️ *Trial Ending Soon*\n\n"
                            f"Hi {display_name}, your free trial ends in less than 24 hours.\n\n"
                            "Tap 💰 Top up Balance now to keep your listing live with no downtime."
                        ),
                        parse_mode="Markdown",
                    )
                    db.mark_trial_reminder_sent(tg_id, "lastday")
                    final_sent += 1
                except Exception as e:
                    logger.error(f"❌ Failed sending final trial reminder to {tg_id}: {e}")
                continue

            if (
                hours_left <= FREE_TRIAL_REMINDER_DAY5_HOURS
                and not provider.get("trial_reminder_day5_sent")
            ):
                try:
                    await context.bot.send_message(
                        chat_id=tg_id,
                        text=(
                            "🔔 *Trial Reminder*\n\n"
                            f"Hi {display_name}, your free trial is nearing its end.\n\n"
                            "Choose a paid package in 💰 Top up Balance to stay visible without interruption."
                        ),
                        parse_mode="Markdown",
                    )
                    db.mark_trial_reminder_sent(tg_id, "day5")
                    day5_sent += 1
                except Exception as e:
                    logger.error(f"❌ Failed sending day-5 trial reminder to {tg_id}: {e}")

        if day5_sent or final_sent:
            logger.info(f"🔔 Trial reminders sent: day5={day5_sent}, final={final_sent}")
    
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
        job_queue.run_repeating(check_trial_reminders, interval=timedelta(minutes=30), first=timedelta(minutes=2))
        job_queue.run_repeating(check_overdue_sessions, interval=timedelta(minutes=2), first=timedelta(seconds=60))
        logger.info("⏰ Scheduled jobs registered (expiry / trial reminders / session alerts)")
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
    logger.info("    ✓ Scheduled free-trial reminders (every 30 min)")
    logger.info("    ✓ Scheduled overdue session alerts (every 2 min)")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

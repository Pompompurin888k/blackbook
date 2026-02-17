"""
Blackbook Bot - Main Entry Point
Orchestrates the modular bot architecture with persistence and centralized logging.
"""
import os
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, PicklePersistence

from config import (
    TELEGRAM_TOKEN,
    ADMIN_CHAT_ID,
    FREE_TRIAL_REMINDER_DAY2_HOURS,
    FREE_TRIAL_REMINDER_DAY5_HOURS,
    FREE_TRIAL_FINAL_REMINDER_HOURS,
    TRIAL_WINBACK_AFTER_HOURS,
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
HEARTBEAT_FILE = os.getenv("BOT_HEARTBEAT_FILE", "/tmp/blackbook_bot_heartbeat")


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

    def touch_heartbeat() -> None:
        """Writes a heartbeat file used by container health checks."""
        try:
            heartbeat_path = Path(HEARTBEAT_FILE)
            heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            heartbeat_path.write_text(datetime.utcnow().isoformat(), encoding="utf-8")
        except Exception as e:
            logger.error(f"❌ Failed to write bot heartbeat: {e}")

    async def send_admin_alert(bot, message: str) -> None:
        """Sends basic operational alerts to admin Telegram."""
        if not ADMIN_CHAT_ID:
            return
        try:
            await bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=f"ALERT:\n{message[:3800]}")
        except Exception as alert_err:
            logger.error(f"❌ Failed to send admin alert: {alert_err}")

    async def on_error(update: object, context) -> None:
        """Global async error handler for uncaught bot exceptions."""
        logger.error(f"Unhandled bot exception: {context.error}")
        await send_admin_alert(context.bot, f"Unhandled bot exception: {context.error}")

    application.add_error_handler(on_error)
    
    # ==================== SCHEDULED JOBS ====================
    job_queue = application.job_queue
    
    # Deactivate expired subscriptions every 15 minutes
    async def check_expired_subscriptions(context):
        """Periodic job: deactivate providers whose subscription has expired."""
        touch_heartbeat()
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
                await send_admin_alert(context.bot, f"Trial-expired notification failed for {tg_id}: {e}")

        winback_candidates = db.get_trial_winback_candidates(TRIAL_WINBACK_AFTER_HOURS)
        winback_sent = 0
        for provider in winback_candidates:
            tg_id = provider.get("telegram_id")
            name = provider.get("display_name", "there")
            try:
                await context.bot.send_message(
                    chat_id=tg_id,
                    text=(
                        "*We can bring you back live today*\n\n"
                        f"Hi {name}, it has been about {TRIAL_WINBACK_AFTER_HOURS} hours since your trial ended.\n\n"
                        "Activate any paid package in Top up Balance and we can put your listing back online instantly."
                    ),
                    parse_mode="Markdown",
                )
                db.mark_trial_winback_sent(tg_id)
                winback_sent += 1
            except Exception as e:
                logger.error(f"❌ Failed to send trial winback to {tg_id}: {e}")
                await send_admin_alert(context.bot, f"Trial winback send failed for {tg_id}: {e}")

        if winback_sent:
            logger.info(f"🔁 Trial winback messages sent: {winback_sent}")

    async def check_trial_reminders(context):
        """Periodic job: send day-2, day-5 and last-day trial reminders."""
        touch_heartbeat()
        now = datetime.now()
        candidates = db.get_trial_reminder_candidates()
        day2_sent = 0
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
                    await send_admin_alert(context.bot, f"Final trial reminder failed for {tg_id}: {e}")
                continue

            if (
                hours_left <= FREE_TRIAL_REMINDER_DAY5_HOURS
                and hours_left > FREE_TRIAL_FINAL_REMINDER_HOURS
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
                    await send_admin_alert(context.bot, f"Day-5 trial reminder failed for {tg_id}: {e}")
                continue

            if (
                hours_left <= FREE_TRIAL_REMINDER_DAY2_HOURS
                and hours_left > FREE_TRIAL_REMINDER_DAY5_HOURS
                and not provider.get("trial_reminder_day2_sent")
            ):
                try:
                    await context.bot.send_message(
                        chat_id=tg_id,
                        text=(
                            "💡 *Trial Day-2 Check-in*\n\n"
                            f"Hi {display_name}, your listing is now live and clients are already browsing.\n\n"
                            "Quick win: keep photos and rates updated today so you get more responses this week."
                        ),
                        parse_mode="Markdown",
                    )
                    db.mark_trial_reminder_sent(tg_id, "day2")
                    day2_sent += 1
                except Exception as e:
                    logger.error(f"❌ Failed sending day-2 trial reminder to {tg_id}: {e}")
                    await send_admin_alert(context.bot, f"Day-2 trial reminder failed for {tg_id}: {e}")

        if day2_sent or day5_sent or final_sent:
            logger.info(f"🔔 Trial reminders sent: day2={day2_sent}, day5={day5_sent}, final={final_sent}")
    
    # Check overdue safety sessions every 2 minutes
    async def check_overdue_sessions(context):
        """Periodic job: alert admin about overdue safety sessions."""
        touch_heartbeat()
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
                await send_admin_alert(context.bot, f"Overdue-session alert send failed for {provider_name}: {e}")

    async def heartbeat_job(context):
        """Periodic heartbeat writer for container healthcheck."""
        touch_heartbeat()
    
    if job_queue is not None:
        touch_heartbeat()
        job_queue.run_repeating(check_expired_subscriptions, interval=timedelta(minutes=15), first=timedelta(seconds=30))
        job_queue.run_repeating(check_trial_reminders, interval=timedelta(minutes=30), first=timedelta(minutes=2))
        job_queue.run_repeating(check_overdue_sessions, interval=timedelta(minutes=2), first=timedelta(seconds=60))
        job_queue.run_repeating(heartbeat_job, interval=timedelta(minutes=1), first=timedelta(seconds=15))
        logger.info("⏰ Scheduled jobs registered (expiry / trial reminders / session alerts / heartbeat)")
    else:
        touch_heartbeat()
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
    logger.info("    ✓ Scheduled free-trial reminders day-2/day-5/final (every 30 min)")
    logger.info("    ✓ Trial post-expiry winback reminders")
    logger.info("    ✓ Scheduled overdue session alerts (every 2 min)")
    logger.info(f"    ✓ Heartbeat file updates ({HEARTBEAT_FILE})")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

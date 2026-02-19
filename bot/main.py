"""
Blackbook Bot - Main Entry Point
Orchestrates client/admin bot roles with shared database and modular handlers.
"""
import os
from pathlib import Path
from datetime import datetime, timedelta

import httpx
from telegram import Update
from telegram.ext import Application, PicklePersistence

from config import (
    TELEGRAM_TOKEN,
    ADMIN_CHAT_ID,
    ADMIN_BOT_TOKEN,
    FREE_TRIAL_REMINDER_DAY2_HOURS,
    FREE_TRIAL_REMINDER_DAY5_HOURS,
    FREE_TRIAL_FINAL_REMINDER_HOURS,
    TRIAL_WINBACK_AFTER_HOURS,
)
from database import Database
from handlers import register_all_handlers, register_admin_only_handlers
from utils.logger import get_logger, configure_root_logger
from db_context import set_db

configure_root_logger()
logger = get_logger(__name__)


def _resolve_role() -> str:
    role = os.getenv("BOT_ROLE", "client").strip().lower()
    if role not in {"client", "admin"}:
        logger.warning(f"Unknown BOT_ROLE '{role}', defaulting to client")
        role = "client"
    return role


def _default_heartbeat_file(role: str) -> str:
    if role == "admin":
        return "/tmp/blackbook_admin_bot_heartbeat"
    return "/tmp/blackbook_bot_heartbeat"


def main() -> None:
    role = _resolve_role()
    primary_token = ADMIN_BOT_TOKEN if role == "admin" else TELEGRAM_TOKEN
    admin_token_raw = os.getenv("ADMIN_BOT_TOKEN", "").strip()

    if not primary_token:
        env_name = "ADMIN_BOT_TOKEN" if role == "admin" else "TELEGRAM_TOKEN"
        logger.error(f"{env_name} environment variable not set")
        raise ValueError(f"{env_name} environment variable is required")

    if role == "admin":
        if not admin_token_raw:
            logger.error("BOT_ROLE=admin requires ADMIN_BOT_TOKEN to be set in .env")
            raise ValueError("ADMIN_BOT_TOKEN is required when BOT_ROLE=admin")
        if ADMIN_BOT_TOKEN == TELEGRAM_TOKEN:
            logger.error("ADMIN_BOT_TOKEN must be different from TELEGRAM_TOKEN for BOT_ROLE=admin")
            raise ValueError("ADMIN_BOT_TOKEN must be different from TELEGRAM_TOKEN")

    if not ADMIN_CHAT_ID:
        logger.warning("ADMIN_CHAT_ID not set; admin alerts disabled")

    if role == "client" and ADMIN_BOT_TOKEN and ADMIN_BOT_TOKEN != TELEGRAM_TOKEN:
        logger.info("Separate ADMIN_BOT_TOKEN detected; moderation alerts go to admin bot")

    persistence_file = os.path.join(os.path.dirname(__file__), f"bot_persistence_{role}.pickle")
    heartbeat_file = os.getenv("BOT_HEARTBEAT_FILE", _default_heartbeat_file(role))

    logger.info(f"Starting bot role: {role}")
    logger.info("Initializing database connection...")
    db = Database()

    logger.info("Loading conversation persistence...")
    persistence = PicklePersistence(filepath=persistence_file)

    logger.info("Building Telegram application...")
    application = (
        Application.builder()
        .token(primary_token)
        .persistence(persistence)
        .build()
    )

    set_db(db)
    logger.info("Database registered in db_context")

    if role == "admin":
        logger.info("Registering admin-only handlers...")
        register_admin_only_handlers(application, db)
    else:
        logger.info("Registering client handlers...")
        register_all_handlers(application, db)

    def touch_heartbeat() -> None:
        """Write heartbeat file used by container health checks."""
        try:
            heartbeat_path = Path(heartbeat_file)
            heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            heartbeat_path.write_text(datetime.utcnow().isoformat(), encoding="utf-8")
        except Exception as err:
            logger.error(f"Failed to write heartbeat: {err}")

    async def send_admin_alert(message: str, parse_mode: str | None = None) -> bool:
        """Send operational alerts to admin chat via admin token when available."""
        if not ADMIN_CHAT_ID:
            return False

        alert_token = ADMIN_BOT_TOKEN or primary_token
        if not alert_token:
            return False

        payload = {
            "chat_id": int(ADMIN_CHAT_ID),
            "text": f"ALERT:\n{message[:3800]}",
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{alert_token}/sendMessage",
                    json=payload,
                )
                if response.status_code != 200:
                    logger.error(f"Failed to send admin alert: {response.text}")
                    return False
                return True
        except Exception as err:
            logger.error(f"Failed to send admin alert: {err}")
            return False

    async def on_error(update: object, context) -> None:
        """Global error handler for uncaught bot exceptions."""
        error_text = str(context.error)
        if "message is not modified" in error_text.lower():
            logger.info(f"Ignoring benign Telegram edit no-op ({role}): {error_text}")
            return
        logger.error(f"Unhandled bot exception ({role}): {context.error}")
        await send_admin_alert(f"Unhandled bot exception ({role}): {context.error}")

    application.add_error_handler(on_error)

    async def heartbeat_job(context) -> None:
        _ = context
        touch_heartbeat()

    job_queue = application.job_queue

    if role == "client":
        async def check_expired_subscriptions(context):
            """Deactivate expired subscriptions and send trial expiry/winback messages."""
            touch_heartbeat()
            count = db.deactivate_expired_subscriptions()
            if count > 0:
                logger.info(f"Deactivated {count} expired subscription(s)")

            expired_trials = db.get_unnotified_expired_trials()
            for provider in expired_trials:
                tg_id = provider.get("telegram_id")
                name = provider.get("display_name", "there")
                try:
                    await context.bot.send_message(
                        chat_id=tg_id,
                        text=(
                            "? *Free Trial Ended*\n\n"
                            f"Hi {name}, your trial has ended and your listing is now paused.\n\n"
                            "To go live again immediately, choose any paid package in ?? Top up Balance."
                        ),
                        parse_mode="Markdown",
                    )
                    db.mark_trial_expired_notified(tg_id)
                except Exception as err:
                    logger.error(f"Failed trial-expired notification to {tg_id}: {err}")
                    await send_admin_alert(f"Trial-expired notification failed for {tg_id}: {err}")

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
                except Exception as err:
                    logger.error(f"Failed trial winback to {tg_id}: {err}")
                    await send_admin_alert(f"Trial winback send failed for {tg_id}: {err}")

            if winback_sent:
                logger.info(f"Trial winback messages sent: {winback_sent}")

        async def check_trial_reminders(context):
            """Send day-2, day-5 and final trial reminders."""
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
                                "?? *Trial Ending Soon*\n\n"
                                f"Hi {display_name}, your free trial ends in less than 24 hours.\n\n"
                                "Tap ?? Top up Balance now to keep your listing live with no downtime."
                            ),
                            parse_mode="Markdown",
                        )
                        db.mark_trial_reminder_sent(tg_id, "lastday")
                        final_sent += 1
                    except Exception as err:
                        logger.error(f"Failed final trial reminder to {tg_id}: {err}")
                        await send_admin_alert(f"Final trial reminder failed for {tg_id}: {err}")
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
                                "?? *Trial Reminder*\n\n"
                                f"Hi {display_name}, your free trial is nearing its end.\n\n"
                                "Choose a paid package in ?? Top up Balance to stay visible without interruption."
                            ),
                            parse_mode="Markdown",
                        )
                        db.mark_trial_reminder_sent(tg_id, "day5")
                        day5_sent += 1
                    except Exception as err:
                        logger.error(f"Failed day-5 trial reminder to {tg_id}: {err}")
                        await send_admin_alert(f"Day-5 trial reminder failed for {tg_id}: {err}")
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
                                "?? *Trial Day-2 Check-in*\n\n"
                                f"Hi {display_name}, your listing is now live and clients are already browsing.\n\n"
                                "Quick win: keep photos and rates updated today so you get more responses this week."
                            ),
                            parse_mode="Markdown",
                        )
                        db.mark_trial_reminder_sent(tg_id, "day2")
                        day2_sent += 1
                    except Exception as err:
                        logger.error(f"Failed day-2 trial reminder to {tg_id}: {err}")
                        await send_admin_alert(f"Day-2 trial reminder failed for {tg_id}: {err}")

            if day2_sent or day5_sent or final_sent:
                logger.info(f"Trial reminders sent: day2={day2_sent}, day5={day5_sent}, final={final_sent}")

        async def check_overdue_sessions(context):
            """Alert admin about overdue safety sessions."""
            _ = context
            touch_heartbeat()
            overdue = db.get_overdue_sessions()
            for session in overdue:
                provider_name = session.get("display_name", "Unknown")
                provider_phone = session.get("phone", "N/A")
                expected_back = session.get("expected_check_back")

                alert_text = (
                    "?? *EMERGENCY: OVERDUE CHECK-IN*\n"
                    "??????????????????????????\n\n"
                    f"?? Provider: *{provider_name}*\n"
                    f"?? Phone: `{provider_phone}`\n"
                    f"? Expected back: {expected_back.strftime('%H:%M') if expected_back else 'Unknown'}\n\n"
                    "*Provider has NOT checked in!*\n"
                    "Immediate follow-up recommended."
                )

                try:
                    sent = await send_admin_alert(alert_text, parse_mode="Markdown")
                    if sent:
                        db.mark_session_alerted(session["id"])
                        logger.warning(f"Overdue session alert sent for {provider_name}")
                except Exception as err:
                    logger.error(f"Failed overdue alert for {provider_name}: {err}")

        if job_queue is not None:
            touch_heartbeat()
            job_queue.run_repeating(check_expired_subscriptions, interval=timedelta(minutes=15), first=timedelta(seconds=30))
            job_queue.run_repeating(check_trial_reminders, interval=timedelta(minutes=30), first=timedelta(minutes=2))
            job_queue.run_repeating(check_overdue_sessions, interval=timedelta(minutes=2), first=timedelta(seconds=60))
            job_queue.run_repeating(heartbeat_job, interval=timedelta(minutes=1), first=timedelta(seconds=15))
            logger.info("Scheduled jobs registered (expiry / trial reminders / session alerts / heartbeat)")
        else:
            touch_heartbeat()
            logger.warning(
                "JobQueue unavailable. Install with: pip install \"python-telegram-bot[job-queue]\" "
                "to enable scheduled jobs."
            )
    else:
        if job_queue is not None:
            touch_heartbeat()
            job_queue.run_repeating(heartbeat_job, interval=timedelta(minutes=1), first=timedelta(seconds=10))
            logger.info("Admin bot heartbeat job registered")
        else:
            touch_heartbeat()
            logger.warning("JobQueue unavailable; admin heartbeat will only update on startup")

    logger.info("Bot is starting...")
    logger.info(f"Role: {role}")
    logger.info(f"Heartbeat file: {heartbeat_file}")
    logger.info(f"Persistence file: {persistence_file}")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

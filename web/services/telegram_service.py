"""
Telegram Service — notifications and admin alerts.
"""
import logging
from typing import Optional

import httpx

from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, ADMIN_BOT_TOKEN

logger = logging.getLogger(__name__)


async def send_telegram_notification(
    chat_id: int,
    message: str,
    parse_mode: Optional[str] = "Markdown",
    bot_token: Optional[str] = None,
    reply_markup: Optional[dict] = None,
):
    """Sends a notification to a user via Telegram Bot API."""
    token = bot_token or TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("⚠️ TELEGRAM_TOKEN not set, cannot send notification")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                logger.info(f"📨 Notification sent to {chat_id}")
            else:
                logger.warning(f"⚠️ Notification failed: {response.text}")
    except Exception as e:
        logger.error(f"❌ Telegram notification error: {e}")


async def send_admin_alert(
    message: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[dict] = None,
):
    """Sends basic operational alerts to admin via Telegram."""
    if not ADMIN_CHAT_ID or not ADMIN_BOT_TOKEN:
        return
    try:
        await send_telegram_notification(
            int(ADMIN_CHAT_ID),
            f"ALERT:\n{message}",
            parse_mode=parse_mode,
            bot_token=ADMIN_BOT_TOKEN,
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"❌ Failed to send admin alert: {e}")

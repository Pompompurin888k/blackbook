import logging
import os
from urllib.parse import quote
import httpx
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config import (
    ADMIN_CHAT_ID,
    ADMIN_BOT_TOKEN,
    TELEGRAM_TOKEN,
    AWAITING_PHOTO,
    is_admin,
    FREE_TRIAL_DAYS,
)
from db_context import get_db
from utils.keyboards import get_admin_verification_keyboard

logger = logging.getLogger(__name__)

def is_verification_pending(provider: dict) -> bool:
    """Returns True when provider has submitted verification and is awaiting admin action."""
    if not provider:
        return False
    return bool(provider.get("verification_photo_id")) and not bool(provider.get("is_verified"))

async def send_admin_verification_request(
    context: ContextTypes.DEFAULT_TYPE,
    provider_id: int,
    photo_file_id: str,
    caption: str,
) -> bool:
    """
    Sends verification request to admin chat.
    If admin bot token matches client bot token, include inline approve/reject buttons.
    If different token is used, send notification-only message to avoid dead callback buttons.
    """
    if not ADMIN_CHAT_ID:
        return False

    if ADMIN_BOT_TOKEN == TELEGRAM_TOKEN:
        await context.bot.send_photo(
            chat_id=int(ADMIN_CHAT_ID),
            photo=photo_file_id,
            caption=caption,
            reply_markup=get_admin_verification_keyboard(provider_id),
            parse_mode="Markdown",
        )
        return True

    # Different admin bot token: file_id from client bot cannot be reused directly.
    # Send a publicly reachable photo URL through the web proxy endpoint.
    public_base_url = os.getenv("PUBLIC_WEB_BASE_URL", "https://innbucks.org").rstrip("/")
    photo_ref = photo_file_id
    if not photo_file_id.startswith(("http://", "https://")):
        photo_ref = f"{public_base_url}/photo/{quote(photo_file_id, safe='')}"

    keyboard = get_admin_verification_keyboard(provider_id)
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": button.text,
                    "callback_data": button.callback_data,
                }
                for button in row
            ]
            for row in keyboard.inline_keyboard
        ]
    }
    url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": int(ADMIN_CHAT_ID),
        "photo": photo_ref,
        "caption": caption,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.error(f"❌ Failed to send admin verification photo notification: {resp.text}")
            # Fallback to plain text notification so moderation still proceeds.
            fallback_payload = {
                "chat_id": int(ADMIN_CHAT_ID),
                "text": f"{caption}\n\nPhoto URL:\n{photo_ref}",
                "parse_mode": "Markdown",
                "reply_markup": reply_markup,
            }
            resp2 = await client.post(
                f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
                json=fallback_payload,
            )
            if resp2.status_code != 200:
                logger.error(f"❌ Failed to send admin verification fallback notification: {resp2.text}")
                return False
    return True

async def send_provider_message(
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown",
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Sends provider-facing message via client bot token."""
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN missing; cannot notify provider")
        return False

    payload = {
        "chat_id": int(chat_id),
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {
                        "text": button.text,
                        "callback_data": button.callback_data,
                    }
                    for button in row
                ]
                for row in reply_markup.inline_keyboard
            ]
        }

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(f"❌ Failed provider notification ({chat_id}): {resp.text}")
                return False
        return True
    except Exception as e:
        logger.error(f"❌ Provider notification error ({chat_id}): {e}")
        return False


async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the verification process - simple photo upload for manual review."""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You need to /register first before verification.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if provider.get("is_verified"):
        await update.message.reply_text(
            "✅ You are already verified! ✔️",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    if is_verification_pending(provider):
        await update.message.reply_text(
            "⏳ *Verification Pending*\n\n"
            "Your profile is already awaiting admin approval.\n"
            "You will be notified once approved.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📸 *Profile Verification*\n\n"
        "Upload the pictures you will be using on your profile.\n\n"
        "Our team will review and approve within *2-4 hours*.\n\n"
        "📷 Send your photo now:",
        parse_mode="Markdown"
    )
    db.log_funnel_event(user.id, "verification_started")
    return AWAITING_PHOTO

async def handle_verification_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the verification photo submission."""
    user = update.effective_user
    db = get_db()
    
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send a photo, not text or file.\n\n"
            "Use the 📷 camera or gallery to send your picture.",
            parse_mode="Markdown"
        )
        return AWAITING_PHOTO
    
    photo = update.message.photo[-1]
    photo_file_id = photo.file_id
    
    provider = db.get_provider(user.id)
    display_name = provider.get("display_name", "Unknown") if provider else "Unknown"
    
    db.save_verification_photo(user.id, photo_file_id)
    
    if not ADMIN_CHAT_ID:
        logger.error("❌ ADMIN_CHAT_ID not set!")
        await update.message.reply_text(
            "⚠️ Verification system error. Please contact support."
        )
        return ConversationHandler.END
    
    caption = (
        "🔍 *NEW VERIFICATION REQUEST*\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 Provider: {display_name}\n"
        f"📍 City: {provider.get('city', 'N/A') if provider else 'N/A'}\n"
        f"🆔 User ID: `{user.id}`\n"
    )
    
    sent = await send_admin_verification_request(
        context=context,
        provider_id=user.id,
        photo_file_id=photo_file_id,
        caption=caption,
    )
    if not sent:
        await update.message.reply_text(
            "⚠️ Verification queue notification failed. Please contact support.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END
    db.log_funnel_event(user.id, "verification_submitted")
    
    await update.message.reply_text(
        "✅ *Photo Uploaded Successfully*\n\n"
        "Your verification is in queue for manual review.\n\n"
        "_Review time: Usually within 2-4 hours._",
        parse_mode="Markdown"
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def handle_document_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Rejects document uploads during verification (anti-catfish measure)."""
    await update.message.reply_text(
        "🚫 *Security Alert: Gallery Upload Detected.*\n\n"
        "For the safety of our clients and the integrity of the Blue Tick, "
        "we only accept *Live Camera Photos*.\n\n"
        "Please try /verify again using your camera.",
        parse_mode="Markdown"
    )
    return AWAITING_PHOTO

async def admin_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin approval/rejection of verification requests."""
    query = update.callback_query
    await query.answer()
    db = get_db()

    if not is_admin(query.from_user.id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    data = query.data
    parts = data.split("_")

    if len(parts) < 3:
        return
    
    action = parts[1]
    provider_id = int(parts[2])
    reason_code = parts[3] if action == "reject" and len(parts) > 3 else "generic"
    reject_reasons = {
        "photo": "photo quality issue",
        "mismatch": "identity mismatch",
        "incomplete": "incomplete profile details",
        "generic": "verification requirements not met",
    }
    
    provider = db.get_provider(provider_id)
    if not provider:
        await query.answer("Provider not found.", show_alert=True)
        return
    display_name = provider.get("display_name", "Unknown")
    is_portal_account = str(provider.get("auth_channel") or "telegram").lower() == "portal"

    async def _edit_admin_result(text: str) -> None:
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=text, parse_mode="Markdown")
        else:
            await query.edit_message_text(text=text, parse_mode="Markdown")
    
    if action == "approve":
        updated = db.verify_provider(provider_id, True, admin_tg_id=query.from_user.id)
        if not updated:
            await query.answer("Approve failed. Please retry.", show_alert=True)
            logger.error(f"❌ Failed to approve provider {provider_id}; verify_provider returned False")
            return
        if not is_portal_account:
            db.log_funnel_event(provider_id, "verified")
            is_active = provider.get("is_active", False)
            if is_active:
                await send_provider_message(
                    chat_id=provider_id,
                    text="🎉 *VERIFIED! You're Now Live!*\n\n"
                    "✅ Blue Tick status granted\n"
                    "✅ Profile is active on innbucks.org\n\n"
                    "Your profile is now visible to premium clients!\n\n"
                    "🌐 View your listing at: *https://innbucks.org*",
                )
            else:
                await send_provider_message(
                    chat_id=provider_id,
                    text="✅ *Verification Approved!*\n\n"
                    "🎉 You now have the Blue Tick ✔️\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📋 *Your profile is saved but not yet live.*\n\n"
                    f"🎁 You can start a *{FREE_TRIAL_DAYS}-day free trial* once,\n"
                    "or activate a paid package immediately.\n\n"
                    "💡 Once activated, your profile goes live instantly!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"🎁 Start {FREE_TRIAL_DAYS}-Day Free Trial", callback_data="menu_trial_activate")],
                        [InlineKeyboardButton("💰 Choose Paid Package", callback_data="menu_topup")],
                    ]),
                )
        approved_text = (
            f"✅ **APPROVED**\n\n"
            f"Provider: {display_name}\n"
            f"User ID: `{provider_id}`"
        )
        if is_portal_account:
            approved_text += "\nType: `portal` (login unlocked)"
        await _edit_admin_result(approved_text)
        logger.info(f"✅ Provider {provider_id} ({display_name}) verified by admin")
        return

    elif action == "reject":
        reason_text = reject_reasons.get(reason_code, reject_reasons["generic"])
        updated = db.verify_provider(provider_id, False, admin_tg_id=query.from_user.id, reason=reason_text)
        if not updated:
            await query.answer("Reject failed. Please retry.", show_alert=True)
            logger.error(f"❌ Failed to reject provider {provider_id}; verify_provider returned False")
            return
        if not is_portal_account:
            db.log_funnel_event(provider_id, "verification_rejected", {"reason": reason_text})
            db.update_provider_profile(provider_id, {"verification_photo_id": None})
            await send_provider_message(
                chat_id=provider_id,
                text="❌ **Verification Rejected**\n\n"
                     f"Reason: **{reason_text}**\n\n"
                     "Please tap 📸 Get Verified in your profile to submit a corrected photo/profile and try again.",
            )
        rejected_text = (
            f"❌ **REJECTED**\n\n"
            f"Provider: {display_name}\n"
            f"User ID: `{provider_id}`\n"
            f"Reason: {reason_text}"
        )
        if is_portal_account:
            rejected_text += "\nType: `portal` (login remains blocked)"
        await _edit_admin_result(rejected_text)
        logger.info(f"❌ Provider {provider_id} ({display_name}) rejected by admin")
        return
    else:
        await query.answer("Unknown moderation action.", show_alert=True)

def register_handlers(application):
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
    from config import AWAITING_PHOTO
    
    verification_handler = ConversationHandler(
        entry_points=[CommandHandler("verify", verify)],
        states={
            AWAITING_PHOTO: [
                MessageHandler(filters.PHOTO, handle_verification_photo),
                MessageHandler(filters.Document.ALL, handle_document_rejection),
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    application.add_handler(verification_handler)

def register_admin_verification_handlers(application):
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(
        admin_verification_callback,
        pattern="^verify_(approve|reject)_"
    ))

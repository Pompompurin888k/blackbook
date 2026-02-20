import logging
from telegram import Update
from telegram.ext import ContextTypes

from db_context import get_db
from utils.keyboards import get_online_toggle_keyboard, get_back_button

logger = logging.getLogger(__name__)

async def toggle_online_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles online status toggle from /status command."""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You're not registered yet. Tap 👤 My Profile to get started.",
            parse_mode="Markdown"
        )
        return
    
    if not provider.get("is_active"):
        await update.message.reply_text(
            "⚠️ *Status Unavailable*\n\n"
            "You need an active subscription to toggle your status.\n\n"
            "Use 💰 Top up Balance to go live first!",
            parse_mode="Markdown"
        )
        return
    
    is_online = provider.get("is_online", False)
    await update.message.reply_text(
        "🔄 *Online Status*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Toggle your visibility on the website.\n"
        "When online, you'll have a 🟢 Live badge.",
        reply_markup=get_online_toggle_keyboard(is_online),
        parse_mode="Markdown"
    )

async def toggle_online_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles online toggle button press."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "noop":
        return  # Do nothing for status display button
    
    user = query.from_user
    db = get_db()
    
    new_status = db.toggle_online_status(user.id)
    status_text = "🟢 ONLINE" if new_status else "⚫ OFFLINE"
    
    await query.edit_message_text(
        f"✅ *Status Updated!*\n\n"
        f"You are now: {status_text}\n\n"
        f"{'Your profile shows a Live badge on the website! 🌟' if new_status else 'Your Live badge has been removed.'}",
        reply_markup=get_online_toggle_keyboard(new_status),
        parse_mode="Markdown"
    )

def register_handlers(application):
    from telegram.ext import CommandHandler, CallbackQueryHandler
    
    application.add_handler(CommandHandler("status", toggle_online_status))
    application.add_handler(CallbackQueryHandler(
        toggle_online_callback,
        pattern="^(toggle_online|noop)$"
    ))

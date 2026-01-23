"""
Blackbook Bot - Safety Handlers
Handles: /check, /report, /session, /checkin, /status, and safety menu callbacks
"""
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import ADMIN_CHAT_ID
from utils.keyboards import (
    get_safety_menu_keyboard,
    get_session_duration_keyboard,
    get_session_active_keyboard,
    get_back_button,
    get_status_toggle_keyboard,
    get_inactive_status_keyboard,
)

logger = logging.getLogger(__name__)


def get_db():
    """Gets the database instance from db_context module."""
    from db_context import get_db as _get_db
    return _get_db()


# ==================== MENU CALLBACKS ====================

async def safety_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles safety-related menu callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    action = query.data.replace("menu_", "")
    db = get_db()
    provider = db.get_provider(user.id)
    
    # === SAFETY SUITE MENU ===
    if action == "safety":
        await query.edit_message_text(
            "🛡️ *SAFETY SUITE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your protection tools:\n\n"
            "📞 *Check* — Screen client numbers\n"
            "⏱️ *Session* — Start safety timer\n"
            "🚫 *Report* — Flag dangerous clients\n"
            "✅ *Check In* — Confirm you're safe",
            reply_markup=get_safety_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    # === SAFETY: CHECK NUMBER ===
    elif action == "safety_check":
        await query.edit_message_text(
            "📞 *CLIENT INTELLIGENCE CHECK*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Type the command:\n"
            "`/check 0712345678`\n\n"
            "We'll search our database for reports of:\n"
            "• Non-payment\n"
            "• Violence\n"
            "• Suspicious behavior",
            reply_markup=get_back_button("menu_safety"),
            parse_mode="Markdown"
        )
    
    # === SAFETY: START SESSION ===
    elif action == "safety_session":
        await query.edit_message_text(
            "⏱️ *SAFETY SESSION TIMER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select session duration:\n\n"
            "If you don't /checkin on time, an *Emergency Alert* "
            "will be sent to the Management Team.",
            reply_markup=get_session_duration_keyboard(),
            parse_mode="Markdown"
        )
    
    # === SAFETY: SESSION DURATION SELECTED ===
    elif action.startswith("session_"):
        minutes = int(action.replace("session_", ""))
        session_id = db.start_session(user.id, minutes)
        
        if session_id:
            check_back_time = datetime.now() + timedelta(minutes=minutes)
            
            await query.edit_message_text(
                "✅ *SAFETY TIMER ACTIVE*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏱️ Duration: {minutes} Minutes\n"
                f"⏰ Check-in Due: {check_back_time.strftime('%H:%M')}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "We are watching the clock.\n\n"
                "Tap *Check In Now* when you're safe.",
                reply_markup=get_session_active_keyboard(),
                parse_mode="Markdown"
            )
    
    # === SAFETY: CHECK IN ===
    elif action == "safety_checkin":
        success = db.end_session(user.id)
        
        if success:
            await query.edit_message_text(
                "✅ *CHECK-IN CONFIRMED*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Glad you're safe! 💚\n\n"
                "Remember to start a new session before your next meeting.",
                reply_markup=get_back_button(),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "ℹ️ *No Active Session*\n\n"
                "You don't have an active safety timer.\n\n"
                "Use the Safety Suite to start one before your next meeting.",
                reply_markup=get_back_button(),
                parse_mode="Markdown"
            )
    
    # === SAFETY: REPORT ===
    elif action == "safety_report":
        await query.edit_message_text(
            "🚫 *REPORT A CLIENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Type the command:\n"
            "`/report 0712345678 Reason here`\n\n"
            "Example:\n"
            "`/report 0712345678 Did not pay, aggressive`\n\n"
            "_Help protect your sisters. Only report genuine issues._",
            reply_markup=get_back_button("menu_safety"),
            parse_mode="Markdown"
        )
    
    # === STATUS TOGGLE ===
    elif action == "status":
        if provider and provider.get("is_active"):
            new_status = db.toggle_online_status(user.id)
            neighborhood = provider.get('neighborhood', 'your area')
            
            if new_status:
                await query.edit_message_text(
                    "🟢 *Status: LIVE*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Your profile now shows the 'Available Now' badge.\n"
                    f"You are prioritized in {neighborhood} search results.",
                    reply_markup=get_status_toggle_keyboard(),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "⚫ *Status: HIDDEN*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Your profile is still visible, but clients see you are unavailable.",
                    reply_markup=get_status_toggle_keyboard(),
                    parse_mode="Markdown"
                )
        else:
            await query.edit_message_text(
                "❌ *Cannot Toggle Status*\n\n"
                "You need an active subscription to appear on the website.\n\n"
                "Get listed now:",
                reply_markup=get_inactive_status_keyboard(),
                parse_mode="Markdown"
            )
    
    # === SAFETY CHECK (from menu) ===
    elif action == "check":
        await query.edit_message_text(
            "🛡️ *Safety Check*\n\n"
            "Use the /check command to screen a client:\n"
            "`/check 0712345678`",
            reply_markup=get_back_button(),
            parse_mode="Markdown"
        )


# ==================== /CHECK COMMAND ====================

async def check_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks if a phone number is blacklisted. Usage: /check 0712345678"""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You need to /register first.",
            parse_mode="Markdown"
        )
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "📞 *Client Intelligence Check*\n\n"
            "Usage: `/check 0712345678`\n\n"
            "We check our national database for reports of non-payment, "
            "violence, or suspicious behavior.",
            parse_mode="Markdown"
        )
        return
    
    phone = context.args[0]
    result = db.check_blacklist(phone)
    
    if result.get("blacklisted"):
        await update.message.reply_text(
            "🚨 *SECURITY ALERT: BLACKLISTED*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 Client: `{phone}`\n"
            f"⚠️ Risk: {result.get('reason', 'Not specified')}\n"
            f"📅 Reported: {result.get('date', 'Unknown')}\n\n"
            "*Recommendation: ABORT CONNECTION. Do not meet this individual.*",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✅ *Security Check: PASSED*\n\n"
            f"No reports found for `{phone}`.\n\n"
            "_Note: Always use /session regardless of check results._",
            parse_mode="Markdown"
        )
    
    logger.info(f"🔍 Blacklist check by {user.id}: {phone} - {'FOUND' if result.get('blacklisted') else 'CLEAR'}")


# ==================== /REPORT COMMAND ====================

async def report_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reports a phone number to the blacklist. Usage: /report 0712345678 Reason here"""
    user = update.effective_user
    db = get_db()
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🚫 **Report to Blacklist**\n\n"
            "Usage: `/report 0712345678 Reason for report`\n\n"
            "Example: `/report 0712345678 Did not pay, threatened me`",
            parse_mode="Markdown"
        )
        return
    
    phone = context.args[0]
    reason = " ".join(context.args[1:])
    
    success = db.add_to_blacklist(phone, reason, user.id)
    
    if success:
        await update.message.reply_text(
            "✅ **Number Reported**\n\n"
            f"📱 `{phone}` has been added to the blacklist.\n"
            f"📝 Reason: {reason}\n\n"
            "_Thank you for keeping our community safe._",
            parse_mode="Markdown"
        )
        
        # Alert admin
        if ADMIN_CHAT_ID:
            try:
                provider = db.get_provider(user.id)
                name = provider.get("display_name", "Unknown") if provider else "Unknown"
                await context.bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text=f"🚨 **New Blacklist Report**\n\n"
                         f"📱 Number: `{phone}`\n"
                         f"📝 Reason: {reason}\n"
                         f"👤 Reported by: {name}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to alert admin: {e}")
    else:
        await update.message.reply_text(
            "❌ Failed to add to blacklist. Please try again.",
            parse_mode="Markdown"
        )


# ==================== /SESSION COMMAND ====================

async def start_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts a safety session timer. Usage: /session 60 (for 60 minutes)"""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text("❌ You need to /register first.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "⏱️ **Safety Session Timer**\n\n"
            "Usage: `/session 60` (for 60 minutes)\n\n"
            "This starts a timer. If you don't send /checkin before the time is up, "
            "the admin will be alerted.\n\n"
            "**Always use this before meeting a client!**",
            parse_mode="Markdown"
        )
        return
    
    try:
        minutes = int(context.args[0])
        if minutes < 15 or minutes > 480:
            await update.message.reply_text(
                "⚠️ Session time must be between 15 and 480 minutes.",
                parse_mode="Markdown"
            )
            return
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number of minutes.")
        return
    
    session_id = db.start_session(user.id, minutes)
    
    if session_id:
        check_back_time = datetime.now() + timedelta(minutes=minutes)
        
        await update.message.reply_text(
            "✅ *Safety Timer Active.*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏱️ Duration: {minutes} Minutes\n"
            f"⏰ Check-in Due: {check_back_time.strftime('%H:%M')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "We are watching the clock. You are expected to /checkin by the deadline.\n\n"
            "If you do not check in, an *Emergency Alert* including your last known "
            "location will be sent to the Management Team.",
            parse_mode="Markdown"
        )
        logger.info(f"⏱️ Session started by {user.id} for {minutes} minutes")
    else:
        await update.message.reply_text("❌ Failed to start session. Please try again.")


# ==================== /CHECKIN COMMAND ====================

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks in after a session - confirms provider is safe."""
    user = update.effective_user
    db = get_db()
    
    success = db.end_session(user.id)
    
    if success:
        await update.message.reply_text(
            "✅ **Check-in Confirmed!**\n\n"
            "Glad you're safe! 💚\n\n"
            "_Remember to /session before your next meeting._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ℹ️ No active session to check in for.\n\n"
            "Use `/session <minutes>` to start a safety timer.",
            parse_mode="Markdown"
        )


# ==================== /STATUS COMMAND ====================

async def toggle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles online/offline status for the website."""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text("❌ You need to /register first.")
        return
    
    if not provider.get("is_active"):
        await update.message.reply_text(
            "❌ You need an active subscription to go online.\n\n"
            "Use /topup to get listed on the website.",
            parse_mode="Markdown"
        )
        return
    
    new_status = db.toggle_online_status(user.id)
    neighborhood = provider.get('neighborhood', 'your area')
    
    if new_status:
        await update.message.reply_text(
            "🟢 *Status: LIVE*\n\n"
            f"Your profile now shows the 'Available Now' badge. "
            f"You will be prioritized in {neighborhood} search results.\n\n"
            "_Send /status again to go offline._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "⚫ *Status: HIDDEN*\n\n"
            "Your profile is still visible, but clients see you are currently unavailable.\n\n"
            "_Send /status again to go back online._",
            parse_mode="Markdown"
        )
    
    logger.info(f"📡 Status toggle by {user.id}: {'ONLINE' if new_status else 'OFFLINE'}")


# ==================== HANDLER REGISTRATION ====================

def register_handlers(application):
    """Registers all safety-related handlers with the application."""
    
    # Command handlers
    application.add_handler(CommandHandler("check", check_number))
    application.add_handler(CommandHandler("report", report_number))
    application.add_handler(CommandHandler("session", start_session))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("status", toggle_status))
    
    # Menu callback handler
    application.add_handler(CallbackQueryHandler(
        safety_menu_callback,
        pattern="^menu_(safety|safety_check|safety_session|safety_checkin|safety_report|session_\\d+|status|check)$"
    ))

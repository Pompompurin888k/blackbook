"""
Blackbook Bot - Safety Handlers
Handles: check, report, session, checkin, and safety menu callbacks.
All features are accessible via buttons — no slash commands required.
"""
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import ADMIN_CHAT_ID
from utils.keyboards import (
    get_safety_menu_keyboard,
    get_session_duration_keyboard,
    get_session_active_keyboard,
    get_back_button,
    get_safety_input_cancel_keyboard,
)

logger = logging.getLogger(__name__)


def get_db():
    """Gets the database instance from db_context module."""
    from db_context import get_db as _get_db
    return _get_db()


# ==================== SAFETY MENU (for persistent menu) ====================

async def safety_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the safety suite menu (called from persistent menu buttons)."""
    # Clear any pending safety input state when returning to menu
    context.user_data.pop("safety_input", None)
    context.user_data.pop("safety_report_phone", None)

    await update.message.reply_text(
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
        # Clear any pending safety input state
        context.user_data.pop("safety_input", None)
        context.user_data.pop("safety_report_phone", None)
        
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
    
    # === SAFETY: CHECK NUMBER (guided flow) ===
    elif action == "safety_check":
        context.user_data["safety_input"] = "check"
        
        await query.edit_message_text(
            "📞 *CLIENT INTELLIGENCE CHECK*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send the *phone number* you want to check:\n\n"
            "📱 Example: `0712345678`\n\n"
            "_We'll search our database for reports of non-payment, "
            "violence, or suspicious behavior._",
            reply_markup=get_safety_input_cancel_keyboard(),
            parse_mode="Markdown"
        )
    
    # === SAFETY: START SESSION ===
    elif action == "safety_session":
        await query.edit_message_text(
            "⏱️ *SAFETY SESSION TIMER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select session duration:\n\n"
            "If you don't check in on time, an *Emergency Alert* "
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
    
    # === SAFETY: REPORT (guided flow) ===
    elif action == "safety_report":
        context.user_data["safety_input"] = "report_phone"
        
        await query.edit_message_text(
            "🚫 *REPORT A CLIENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send the *phone number* of the client to report:\n\n"
            "📱 Example: `0712345678`\n\n"
            "_Help protect your sisters. Only report genuine issues._",
            reply_markup=get_safety_input_cancel_keyboard(),
            parse_mode="Markdown"
        )


# ==================== GUIDED INPUT HANDLER ====================

async def handle_safety_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text input during safety check/report flows."""
    safety_action = context.user_data.get("safety_input")
    
    if not safety_action:
        return  # Not in safety input mode
    
    user = update.effective_user
    db = get_db()
    text = update.message.text.strip()
    
    # Skip if it's a menu button press
    menu_buttons = [
        "👑 The Collection", "👤 My Profile", "💰 Top up Balance",
        "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"
    ]
    if text in menu_buttons:
        context.user_data.pop("safety_input", None)
        context.user_data.pop("safety_report_phone", None)
        return  # Let menu handler process it
    
    # === CHECK NUMBER ===
    if safety_action == "check":
        context.user_data.pop("safety_input", None)
        
        phone = text.replace(" ", "").replace("-", "")
        
        # Basic validation
        if len(phone) < 9 or not phone.replace("+", "").isdigit():
            await update.message.reply_text(
                "⚠️ Invalid phone number. Please send a valid number.\n\n"
                "📱 Example: `0712345678`",
                reply_markup=get_safety_input_cancel_keyboard(),
                parse_mode="Markdown"
            )
            context.user_data["safety_input"] = "check"  # Keep in check mode
            return
        
        result = db.check_blacklist(phone)
        
        if result.get("blacklisted"):
            await update.message.reply_text(
                "🚨 *SECURITY ALERT: BLACKLISTED*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 Client: `{phone}`\n"
                f"⚠️ Risk: {result.get('reason', 'Not specified')}\n"
                f"📅 Reported: {result.get('date', 'Unknown')}\n\n"
                "*Recommendation: ABORT CONNECTION. Do not meet this individual.*",
                reply_markup=get_back_button("menu_safety"),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "✅ *Security Check: PASSED*\n\n"
                f"No reports found for `{phone}`.\n\n"
                "_Always start a ⏱️ Session before meeting a client._",
                reply_markup=get_back_button("menu_safety"),
                parse_mode="Markdown"
            )
        
        logger.info(f"🔍 Blacklist check by {user.id}: {phone} - {'FOUND' if result.get('blacklisted') else 'CLEAR'}")
    
    # === REPORT: STEP 1 — PHONE NUMBER ===
    elif safety_action == "report_phone":
        phone = text.replace(" ", "").replace("-", "")
        
        if len(phone) < 9 or not phone.replace("+", "").isdigit():
            await update.message.reply_text(
                "⚠️ Invalid phone number. Please send a valid number.\n\n"
                "📱 Example: `0712345678`",
                reply_markup=get_safety_input_cancel_keyboard(),
                parse_mode="Markdown"
            )
            return  # Stay in report_phone mode
        
        context.user_data["safety_report_phone"] = phone
        context.user_data["safety_input"] = "report_reason"
        
        await update.message.reply_text(
            "📝 *What happened?*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Reporting: `{phone}`\n\n"
            "Describe the incident in a few words.\n\n"
            "_Example: Did not pay, was aggressive_",
            reply_markup=get_safety_input_cancel_keyboard(),
            parse_mode="Markdown"
        )
    
    # === REPORT: STEP 2 — REASON ===
    elif safety_action == "report_reason":
        phone = context.user_data.get("safety_report_phone", "")
        reason = text
        
        # Clean up state
        context.user_data.pop("safety_input", None)
        context.user_data.pop("safety_report_phone", None)
        
        if len(reason) < 3:
            await update.message.reply_text(
                "⚠️ Please provide a more detailed reason.",
                reply_markup=get_safety_input_cancel_keyboard(),
                parse_mode="Markdown"
            )
            context.user_data["safety_input"] = "report_reason"
            context.user_data["safety_report_phone"] = phone
            return
        
        success = db.add_to_blacklist(phone, reason, user.id)
        
        if success:
            await update.message.reply_text(
                "✅ *Number Reported*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 `{phone}` has been added to the blacklist.\n"
                f"📝 Reason: {reason}\n\n"
                "_Thank you for keeping our community safe._",
                reply_markup=get_back_button("menu_safety"),
                parse_mode="Markdown"
            )
            
            # Alert admin
            if ADMIN_CHAT_ID:
                try:
                    provider = db.get_provider(user.id)
                    name = provider.get("display_name", "Unknown") if provider else "Unknown"
                    await context.bot.send_message(
                        chat_id=int(ADMIN_CHAT_ID),
                        text=f"🚨 *New Blacklist Report*\n\n"
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
                reply_markup=get_back_button("menu_safety"),
                parse_mode="Markdown"
            )


# ==================== SLASH COMMAND FALLBACKS ====================
# These still work for power users but are no longer required.

async def check_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks if a phone number is blacklisted. Usage: /check 0712345678"""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You're not registered yet. Tap 👤 My Profile to get started.",
            parse_mode="Markdown"
        )
        return
    
    if not context.args or len(context.args) < 1:
        # No args — start the guided flow instead
        context.user_data["safety_input"] = "check"
        await update.message.reply_text(
            "📞 *CLIENT INTELLIGENCE CHECK*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send the *phone number* you want to check:\n\n"
            "📱 Example: `0712345678`",
            reply_markup=get_safety_input_cancel_keyboard(),
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
            reply_markup=get_back_button("menu_safety"),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✅ *Security Check: PASSED*\n\n"
            f"No reports found for `{phone}`.\n\n"
            "_Always start a ⏱️ Session before meeting a client._",
            reply_markup=get_back_button("menu_safety"),
            parse_mode="Markdown"
        )
    
    logger.info(f"🔍 Blacklist check by {user.id}: {phone} - {'FOUND' if result.get('blacklisted') else 'CLEAR'}")


async def report_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reports a phone number to the blacklist. Usage: /report 0712345678 Reason"""
    user = update.effective_user
    db = get_db()
    
    if not context.args or len(context.args) < 2:
        # No args — start the guided flow instead
        context.user_data["safety_input"] = "report_phone"
        await update.message.reply_text(
            "🚫 *REPORT A CLIENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send the *phone number* of the client to report:\n\n"
            "📱 Example: `0712345678`",
            reply_markup=get_safety_input_cancel_keyboard(),
            parse_mode="Markdown"
        )
        return
    
    phone = context.args[0]
    reason = " ".join(context.args[1:])
    
    success = db.add_to_blacklist(phone, reason, user.id)
    
    if success:
        await update.message.reply_text(
            "✅ *Number Reported*\n\n"
            f"📱 `{phone}` has been added to the blacklist.\n"
            f"📝 Reason: {reason}\n\n"
            "_Thank you for keeping our community safe._",
            reply_markup=get_back_button("menu_safety"),
            parse_mode="Markdown"
        )
        
        # Alert admin
        if ADMIN_CHAT_ID:
            try:
                provider = db.get_provider(user.id)
                name = provider.get("display_name", "Unknown") if provider else "Unknown"
                await context.bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text=f"🚨 *New Blacklist Report*\n\n"
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
            reply_markup=get_back_button("menu_safety"),
            parse_mode="Markdown"
        )


async def start_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts a safety session timer. Usage: /session 60"""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You're not registered yet. Tap 👤 My Profile to get started."
        )
        return
    
    if not context.args or len(context.args) < 1:
        # No args — show duration buttons instead
        await update.message.reply_text(
            "⏱️ *SAFETY SESSION TIMER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select session duration:\n\n"
            "If you don't check in on time, an *Emergency Alert* "
            "will be sent to the Management Team.",
            reply_markup=get_session_duration_keyboard(),
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
            "We are watching the clock.\n\n"
            "Tap ✅ *Check In* in the 🛡️ Safety Suite when you're done.",
            parse_mode="Markdown"
        )
        logger.info(f"⏱️ Session started by {user.id} for {minutes} minutes")
    else:
        await update.message.reply_text("❌ Failed to start session. Please try again.")


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks in after a session - confirms provider is safe."""
    user = update.effective_user
    db = get_db()
    
    success = db.end_session(user.id)
    
    if success:
        await update.message.reply_text(
            "✅ *Check-in Confirmed!*\n\n"
            "Glad you're safe! 💚\n\n"
            "_Start a new ⏱️ Session before your next meeting._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ℹ️ No active session to check in for.\n\n"
            "Use 🛡️ Safety Suite → ⏱️ Start Session to set a timer.",
            parse_mode="Markdown"
        )


# ==================== HANDLER REGISTRATION ====================

def register_handlers(application):
    """Registers all safety-related handlers with the application."""
    
    # Command handlers (still work as fallbacks)
    application.add_handler(CommandHandler("check", check_number))
    application.add_handler(CommandHandler("report", report_number))
    application.add_handler(CommandHandler("session", start_session))
    application.add_handler(CommandHandler("checkin", checkin))
    
    # Menu callback handler
    application.add_handler(CallbackQueryHandler(
        safety_menu_callback,
        pattern="^menu_(safety|safety_check|safety_session|safety_checkin|safety_report|session_\\d+)$"
    ))
    
    # Safety input handler (check/report guided flows)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_safety_input
    ), group=0)

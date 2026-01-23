"""
Blackbook Bot - Authentication Handlers
Handles: /start, /register, /verify, /myprofile, verification callbacks
"""
import logging
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import (
    STAGE_NAME, CITY, NEIGHBORHOOD, AWAITING_PHOTO,
    ADMIN_CHAT_ID,
)
from utils.keyboards import (
    get_main_menu_keyboard,
    get_city_keyboard,
    get_profile_keyboard,
    get_verification_start_keyboard,
    get_back_button,
    get_admin_verification_keyboard,
)
from utils.formatters import (
    generate_verification_code,
    format_welcome_message,
    format_returning_user_message,
    format_profile_text,
    format_main_menu_header,
)

logger = logging.getLogger(__name__)


# ==================== HELPER FUNCTIONS ====================

def get_db(context: ContextTypes.DEFAULT_TYPE):
    """Gets the database instance from bot_data."""
    return context.bot_data.get("db")


# ==================== /START COMMAND ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command with premium welcome message."""
    logger.info(f"🚀 /start command received from user {update.effective_user.id}")
    user = update.effective_user
    db = get_db(context)
    
    if db is None:
        logger.error("❌ Database is None! Handler cannot proceed.")
        await update.message.reply_text("⚠️ System error. Please try again.")
        return
    
    logger.info(f"📊 Looking up provider for user {user.id}")
    provider = db.get_provider(user.id)
    
    if provider:
        logger.info(f"👋 Returning user: {provider.get('display_name', 'Unknown')}")
        # Existing user - show status with menu
        await update.message.reply_text(
            format_returning_user_message(provider),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    else:
        logger.info(f"🆕 New user: {user.first_name}")
        # New user - full welcome
        await update.message.reply_text(
            format_welcome_message(),
            parse_mode="Markdown"
        )


# ==================== MENU CALLBACK (AUTH SECTION) ====================

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles auth-related menu callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    action = query.data.replace("menu_", "")
    db = get_db(context)
    provider = db.get_provider(user.id)
    
    # === MAIN MENU ===
    if action == "main":
        if provider:
            await query.edit_message_text(
                format_main_menu_header(provider),
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown"
            )
    
    # === PROFILE SCREEN ===
    elif action == "profile":
        if provider:
            await query.edit_message_text(
                format_profile_text(provider),
                reply_markup=get_profile_keyboard(provider),
                parse_mode="Markdown"
            )
    
    # === VERIFY PROMPTS ===
    elif action == "verify_start":
        await query.edit_message_text(
            "📸 *BLUE TICK VERIFICATION*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "To get verified, you'll need to:\n\n"
            "1. Receive a unique code\n"
            "2. Write it on paper\n"
            "3. Take a live selfie with it\n\n"
            "Ready to begin?",
            reply_markup=get_verification_start_keyboard(),
            parse_mode="Markdown"
        )
    
    elif action == "verify_go":
        code = generate_verification_code()
        context.user_data["verification_code"] = code
        
        await query.edit_message_text(
            "📸 *YOUR VERIFICATION CODE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Your code is: `{code}`\n\n"
            "*INSTRUCTIONS:*\n"
            "1. Write this code on paper\n"
            "2. Hold it next to your face\n"
            "3. Take a *live camera photo*\n"
            "4. Send it here\n\n"
            "⚠️ Gallery uploads will be rejected.",
            reply_markup=get_back_button(),
            parse_mode="Markdown"
        )
        context.user_data["awaiting_verification_photo"] = True


# ==================== REGISTRATION CONVERSATION ====================

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the registration conversation and asks for Stage Name."""
    from config import MAINTENANCE_MODE
    
    if MAINTENANCE_MODE:
        await update.message.reply_text(
            "🛠️ **Maintenance Mode Active**\n\n"
            "We're currently performing system updates. "
            "Please try again later.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "👋 *Let's build your brand.*\n\n"
        "Please enter your *Stage Name* (The name clients will see on the website):",
        parse_mode="Markdown"
    )
    return STAGE_NAME


async def stage_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the stage name and asks for city selection."""
    user = update.effective_user
    db = get_db(context)
    stage_name_input = update.message.text.strip()
    
    context.user_data["stage_name"] = stage_name_input
    db.add_provider(user.id, stage_name_input)
    
    await update.message.reply_text(
        f"✅ Excellent, *{stage_name_input}*.\n\n"
        "Now, select your *Primary City* where you operate:",
        reply_markup=get_city_keyboard(),
        parse_mode="Markdown"
    )
    return CITY


async def city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles city button selection and asks for neighborhood."""
    query = update.callback_query
    await query.answer()
    
    city = query.data.replace("city_", "")
    context.user_data["city"] = city
    
    await query.edit_message_text(
        f"📍 *{city} Selection Confirmed.*\n\n"
        "To help local high-value clients find you, please enter your specific "
        "*Neighborhood* (e.g., Westlands, Lower Kabete, Roysambu):",
        parse_mode="Markdown"
    )
    return NEIGHBORHOOD


async def neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the neighborhood and completes registration."""
    user = update.effective_user
    db = get_db(context)
    neighborhood_input = update.message.text.strip()
    
    city = context.user_data.get("city")
    stage_name = context.user_data.get("stage_name")
    
    db.update_provider_profile(user.id, city, neighborhood_input)
    
    await update.message.reply_text(
        "✨ *Profile Initialized!*\n\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 Name: {stage_name}\n"
        f"📍 Area: {neighborhood_input}, {city}\n"
        "━━━━━━━━━━━━━━━\n\n"
        "⚠️ *Note:* Your profile is currently *HIDDEN*.\n"
        "Next step: Use /verify to prove your identity and unlock listing features.",
        parse_mode="Markdown"
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current conversation."""
    await update.message.reply_text(
        "❌ Cancelled. Use /register or /verify to start again."
    )
    context.user_data.clear()
    return ConversationHandler.END


# ==================== VERIFICATION CONVERSATION ====================

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the verification process by giving user a unique code."""
    user = update.effective_user
    db = get_db(context)
    
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
    
    code = generate_verification_code()
    context.user_data["verification_code"] = code
    
    await update.message.reply_text(
        "📸 *Blue Tick Verification*\n\n"
        f"Your unique session code is: `{code}`\n\n"
        "*INSTRUCTIONS:*\n"
        "1. Write this code clearly on a piece of paper.\n"
        "2. Take a *Live Selfie* holding the paper.\n"
        "3. Ensure your face and the code are clearly visible.\n\n"
        "⚠️ *Security Note:* Gallery uploads and 'View Once' documents are "
        "automatically blocked to prevent fraud. Use your Telegram camera.",
        parse_mode="Markdown"
    )
    return AWAITING_PHOTO


async def handle_verification_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the verification photo submission."""
    user = update.effective_user
    db = get_db(context)
    
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send a **photo taken with your camera**, not a file or document.\n"
            "Use the camera icon 📷 to take a live photo.",
            parse_mode="Markdown"
        )
        return AWAITING_PHOTO
    
    photo = update.message.photo[-1]
    photo_file_id = photo.file_id
    
    code = context.user_data.get("verification_code", "N/A")
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
        "🔍 *NEW VETTING REQUEST*\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 Provider: {display_name}\n"
        f"📍 City: {provider.get('city', 'N/A') if provider else 'N/A'}\n"
        f"🔑 Code: `{code}`\n"
    )
    
    await context.bot.send_photo(
        chat_id=int(ADMIN_CHAT_ID),
        photo=photo_file_id,
        caption=caption,
        reply_markup=get_admin_verification_keyboard(user.id),
        parse_mode="Markdown"
    )
    
    await update.message.reply_text(
        "✅ *Encrypted Upload Complete.*\n\n"
        "Your verification is in the queue. Our team will review the match "
        "between your profile and live photo.\n\n"
        "_Review time: 15–120 minutes._",
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


# ==================== ADMIN VERIFICATION CALLBACK ====================

async def admin_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin approval/rejection of verification requests."""
    query = update.callback_query
    await query.answer()
    db = get_db(context)
    
    data = query.data
    parts = data.split("_")
    
    if len(parts) != 3:
        return
    
    action = parts[1]
    provider_id = int(parts[2])
    
    provider = db.get_provider(provider_id)
    display_name = provider.get("display_name", "Unknown") if provider else "Unknown"
    
    if action == "approve":
        db.verify_provider(provider_id, True)
        
        await context.bot.send_message(
            chat_id=provider_id,
            text="🎉 *Status: VERIFIED*\n\n"
                 "You now have the Blue Tick ✔️. Your trust score has increased.\n\n"
                 "Use /topup to appear in the 'Collection.'",
            parse_mode="Markdown"
        )
        
        await query.edit_message_caption(
            caption=f"✅ **APPROVED**\n\n"
                    f"Provider: {display_name}\n"
                    f"User ID: `{provider_id}`",
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ Provider {provider_id} ({display_name}) verified by admin")
        
    elif action == "reject":
        await context.bot.send_message(
            chat_id=provider_id,
            text="❌ **Verification Rejected**\n\n"
                 "Your verification photo was not approved.\n"
                 "Please use /verify to try again with a clearer photo.",
            parse_mode="Markdown"
        )
        
        await query.edit_message_caption(
            caption=f"❌ **REJECTED**\n\n"
                    f"Provider: {display_name}\n"
                    f"User ID: `{provider_id}`",
            parse_mode="Markdown"
        )
        
        logger.info(f"❌ Provider {provider_id} ({display_name}) rejected by admin")


# ==================== MY PROFILE COMMAND ====================

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the provider's current profile status."""
    user = update.effective_user
    db = get_db(context)
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You're not registered yet. Use /register to get started.",
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text(
        format_profile_text(provider) + "\n\n"
        "_Use /status to toggle your Live badge._\n"
        "_Use /topup to extend your subscription._",
        parse_mode="Markdown"
    )


# ==================== HANDLER REGISTRATION ====================

def register_handlers(application):
    """Registers all auth-related handlers with the application."""
    
    # /start command
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myprofile", myprofile))
    
    # Registration conversation
    registration_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register)],
        states={
            STAGE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, stage_name)
            ],
            CITY: [
                CallbackQueryHandler(city_callback, pattern="^city_")
            ],
            NEIGHBORHOOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, neighborhood)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(registration_handler)
    
    # Verification conversation
    verification_handler = ConversationHandler(
        entry_points=[CommandHandler("verify", verify)],
        states={
            AWAITING_PHOTO: [
                MessageHandler(filters.PHOTO, handle_verification_photo),
                MessageHandler(filters.Document.ALL, handle_document_rejection),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(verification_handler)
    
    # Admin verification callback
    application.add_handler(CallbackQueryHandler(
        admin_verification_callback,
        pattern="^verify_(approve|reject)_"
    ))
    
    # Menu callbacks (auth section)
    application.add_handler(CallbackQueryHandler(
        menu_callback,
        pattern="^menu_(main|profile|verify_start|verify_go)$"
    ))

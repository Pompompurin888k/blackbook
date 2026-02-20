"""
Blackbook Bot - Authentication Handlers
Handles: /start, /register, menu navigation
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import (
    STAGE_NAME, CITY, NEIGHBORHOOD,
    ADMIN_CHAT_ID,
    CITIES,
)
from utils.keyboards import (
    get_main_menu_keyboard,
    get_persistent_main_menu,
    get_city_keyboard,
    get_profile_keyboard,
    get_verification_start_keyboard,
    get_back_button,
    get_neighborhood_keyboard,
    get_online_toggle_keyboard,
)
from utils.formatters import (
    format_welcome_message,
    format_returning_user_message,
    format_profile_text,
    format_main_menu_header,
)
from handlers.verification import is_verification_pending
from handlers.profile import is_profile_complete, myprofile, get_profile_states

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================

def get_db():
    """Gets the database instance from db_context module."""
    from db_context import get_db as _get_db
    return _get_db()


def build_go_live_checklist(provider: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Builds checklist text + actionable keyboard for activation funnel."""
    complete = is_profile_complete(provider)
    verified = bool(provider.get("is_verified"))
    active = bool(provider.get("is_active"))
    trial_used = bool(provider.get("trial_used"))
    expiry = provider.get("expiry_date")
    expiry_text = expiry.strftime("%Y-%m-%d %H:%M") if expiry else "N/A"
    tier = (provider.get("subscription_tier") or "none").title()

    checks = [
        f"{'✅' if complete else '❌'} Profile completed",
        f"{'✅' if verified else '❌'} Verification approved",
        f"{'✅' if active else '❌'} Listing active",
    ]

    next_step = "🎯 *Next:* "
    buttons = []
    if not complete:
        next_step += "Tap *✏️ Complete Profile* and finish missing details."
        buttons.append([InlineKeyboardButton("✏️ Complete Profile", callback_data="menu_complete_profile")])
    elif not verified:
        next_step += "Tap *📸 Get Verified* to submit verification photos."
        buttons.append([InlineKeyboardButton("📸 Get Verified", callback_data="menu_verify_start")])
    elif not active:
        if not trial_used:
            next_step += "Start your *7-day free trial* or choose a paid package."
            buttons.append([InlineKeyboardButton("🎁 Start Free Trial", callback_data="menu_trial_activate")])
        else:
            next_step += "Choose a paid package to go live."
        buttons.append([InlineKeyboardButton("💰 Go Live Now", callback_data="menu_topup")])
    else:
        next_step += "You are live. Keep status online and refresh photos/rates regularly."
        buttons.append([InlineKeyboardButton("🟢 Toggle Status", callback_data="menu_status")])

    buttons.append([InlineKeyboardButton("🔙 Back to Profile", callback_data="menu_profile")])
    text = (
        "🚀 *GO LIVE CHECKLIST*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{checks[0]}\n{checks[1]}\n{checks[2]}\n\n"
        f"👑 Tier: *{tier}*\n"
        f"⏱️ Expires: *{expiry_text}*\n\n"
        f"{next_step}"
    )
    return text, InlineKeyboardMarkup(buttons)


# ==================== /START COMMAND ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command with premium welcome message and referral deep links."""
    logger.info(f"🚀 /start command received from user {update.effective_user.id}")
    user = update.effective_user
    db = get_db()
    
    if db is None:
        logger.error("❌ Database is None! Handler cannot proceed.")
        await update.message.reply_text("⚠️ System error. Please try again.")
        return
    
    # Check for referral deep link: /start ref_BBXXXXXX
    referral_code = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            referral_code = arg.replace("ref_", "").upper()
            context.user_data["referral_code"] = referral_code
            logger.info(f"🤝 Referral code detected: {referral_code}")
    
    logger.info(f"📊 Looking up provider for user {user.id}")
    provider = db.get_provider(user.id)
    db.log_funnel_event(user.id, "start_seen", {"has_provider": bool(provider)})
    
    if provider:
        logger.info(f"👋 Returning user: {provider.get('display_name', 'Unknown')}")
        # Update stored username in case it changed
        if user.username and provider.get("telegram_username") != user.username:
            db.update_provider_profile(user.id, {"telegram_username": user.username})
        # Existing user - show status with persistent menu
        await update.message.reply_text(
            format_returning_user_message(provider),
            reply_markup=get_persistent_main_menu(),
            parse_mode="Markdown"
        )
    else:
        logger.info(f"🆕 New user: {user.first_name}")
        # New user - full welcome with persistent menu
        welcome_extra = ""
        if referral_code:
            referrer = db.get_referrer_by_code(referral_code)
            if referrer:
                welcome_extra = f"\n\n🤝 _Referred by {referrer.get('display_name', 'a friend')}_"
        
        await update.message.reply_text(
            format_welcome_message() + welcome_extra,
            reply_markup=get_persistent_main_menu(),
            parse_mode="Markdown"
        )


# ==================== PERSISTENT MENU HANDLER ====================

async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text messages from persistent menu buttons."""
    text = update.message.text
    user = update.effective_user
    db = get_db()
    
    # Define valid menu buttons
    valid_buttons = [
        "👑 The Collection",
        "💰 Top up Balance",
        "🛡️ Safety Suite",
        "🤝 Affiliate Program",
        "📞 Support",
        "📋 Rules"
    ]
    
    # Only process if text is a menu button - otherwise let ConversationHandlers handle it
    if text not in valid_buttons:
        return
    
    # Map button text to command handlers
    if text == "👑 The Collection":
        await update.message.reply_text(
            "🌐 *Visit Our Premium Directory*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Browse our exclusive collection of verified providers:\n\n"
            "🔗 **https://innbucks.org**\n\n"
            "💎 All profiles are verified\n"
            "🔒 Discreet & Professional\n"
            "⭐ Premium Experience Guaranteed",
            parse_mode="Markdown"
        )
    
    elif text == "💰 Top up Balance":
        # Trigger the topup flow
        provider = db.get_provider(user.id)
        if not provider:
            await update.message.reply_text(
                "⚠️ Please register first using /register",
                reply_markup=get_persistent_main_menu()
            )
            return
        
        # Import and call topup from payment handler
        from handlers.payment import topup
        await topup(update, context)
    
    elif text == "🛡️ Safety Suite":
        # Trigger safety menu
        from handlers.safety import safety_menu
        await safety_menu(update, context)
    
    elif text == "🤝 Affiliate Program":
        provider = db.get_provider(user.id)
        if not provider:
            await update.message.reply_text(
                "⚠️ Please register first to access the Affiliate Program.",
                reply_markup=get_persistent_main_menu()
            )
            return
        
        # Generate or retrieve referral code
        ref_code = db.generate_referral_code(user.id)
        stats = db.get_referral_stats(user.id)
        
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
        
        await update.message.reply_text(
            "💰 *Affiliate Program*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Earn rewards by referring new providers!\n\n"
            "🎁 *Your Rewards:*\n"
            "• 1 free day added per signup\n"
            "• 20% commission credit on their first payment\n\n"
            f"🔗 *Your Referral Link:*\n"
            f"`{ref_link}`\n\n"
            f"👥 *Total Referrals:* {stats.get('total_referred', 0)}\n"
            f"💰 *Credits Earned:* {stats.get('credits', 0)} KES\n\n"
            "_Share your link — earn every time they subscribe!_",
            parse_mode="Markdown",
            reply_markup=get_persistent_main_menu()
        )
    
    elif text == "📞 Support":
        admin_contact = ADMIN_CHAT_ID if ADMIN_CHAT_ID else "Admin"
        if admin_contact and str(admin_contact).isdigit():
            contact_line = f"📱 Contact Telegram ID: `{admin_contact}`"
        elif admin_contact:
            contact_line = f"📱 Contact: @{str(admin_contact).lstrip('@')}"
        else:
            contact_line = "📱 Contact: Admin"
        await update.message.reply_text(
            "📞 *Customer Support*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Need help? We're here for you.\n\n"
            f"{contact_line}\n"
            "⏰ Response Time: Within 2-4 hours\n\n"
            "For urgent safety issues, use the 🛡️ Safety Suite.",
            parse_mode="Markdown",
            reply_markup=get_persistent_main_menu()
        )
    
    elif text == "📋 Rules":
        await update.message.reply_text(
            "📋 *Blackbook Rules & Guidelines*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Allowed:*\n"
            "• Professional, verified providers only\n"
            "• Accurate photos and information\n"
            "• Respectful communication\n\n"
            "❌ *Prohibited:*\n"
            "• Fake photos or catfishing\n"
            "• Unprofessional behavior\n"
            "• Harassment of clients\n\n"
            "⚠️ Violations result in immediate ban.\n\n"
            "📜 By using Blackbook, you agree to maintain professionalism and discretion.",
            parse_mode="Markdown",
            reply_markup=get_persistent_main_menu()
        )


# ==================== MENU CALLBACK (AUTH SECTION) ====================

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles auth-related menu callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    action = query.data.replace("menu_", "")
    db = get_db()
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

    # === GO LIVE CHECKLIST ===
    elif action == "checklist":
        if provider:
            db.log_funnel_event(user.id, "checklist_viewed")
            checklist_text, checklist_keyboard = build_go_live_checklist(provider)
            await query.edit_message_text(
                checklist_text,
                reply_markup=checklist_keyboard,
                parse_mode="Markdown",
            )
    
    # === VERIFY PROMPTS ===
    elif action == "verify_start":
        if provider and provider.get("is_verified"):
            await query.edit_message_text(
                "✅ *Already Verified*\n\nYour profile already has admin approval.",
                reply_markup=get_back_button("menu_profile"),
                parse_mode="Markdown",
            )
            return

        if provider and is_verification_pending(provider):
            await query.edit_message_text(
                "⏳ *Verification Pending*\n\n"
                "Your profile is awaiting admin approval.\n"
                "You will get notified once approved.",
                reply_markup=get_back_button("menu_profile"),
                parse_mode="Markdown",
            )
            return

        await query.edit_message_text(
            "📸 *Profile Verification*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "To get verified:\n\n"
            "1. Upload your profile pictures\n"
            "2. We'll review your photos\n"
            "3. Approval in 2-4 hours\n\n"
            "Ready to begin?",
            reply_markup=get_verification_start_keyboard(),
            parse_mode="Markdown"
        )
    
    elif action == "verify_go":
        if provider and provider.get("is_verified"):
            await query.edit_message_text(
                "✅ *Already Verified*\n\nYour profile already has admin approval.",
                reply_markup=get_back_button("menu_profile"),
                parse_mode="Markdown",
            )
            return

        if provider and is_verification_pending(provider):
            await query.edit_message_text(
                "⏳ *Verification Pending*\n\n"
                "Your profile is awaiting admin approval.\n"
                "You will get notified once approved.",
                reply_markup=get_back_button("menu_profile"),
                parse_mode="Markdown",
            )
            return

        await query.edit_message_text(
            "📸 *Profile Verification*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Upload the pictures you will be using on your profile.\n\n"
            "Our team will review and approve within *2-4 hours*.\n\n"
            "📷 Send your photo now:",
            reply_markup=get_back_button(),
            parse_mode="Markdown"
        )
        context.user_data["awaiting_verification_photo"] = True
    
    # === STATUS TOGGLE ===
    elif action == "status":
        if provider:
            is_online = provider.get("is_online", False)
            if not provider.get("is_active"):
                await query.edit_message_text(
                    "⚠️ *Status Unavailable*\n\n"
                    "You need an active subscription to toggle your status.\n\n"
                    "Use 💰 Top up Balance to go live first!",
                    reply_markup=get_back_button(),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "🔄 *Online Status*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Toggle your visibility on the website.\n"
                    "When online, you'll have a 🟢 Live badge.",
                    reply_markup=get_online_toggle_keyboard(is_online),
                    parse_mode="Markdown"
                )


# ==================== REGISTRATION CONVERSATION ====================

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the registration conversation and asks for Stage Name."""
    from config import MAINTENANCE_MODE
    user = update.effective_user
    db = get_db()
    
    if MAINTENANCE_MODE:
        await update.message.reply_text(
            "🛠️ *Maintenance Mode Active*\n\n"
            "We're currently performing system updates. "
            "Please try again later.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Existing users should be routed to profile, not forced through registration again.
    provider = db.get_provider(user.id) if user else None
    if provider:
        await myprofile(update, context)
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
    db = get_db()
    stage_name_input = update.message.text.strip()
    
    context.user_data["stage_name"] = stage_name_input
    db.add_provider(user.id, stage_name_input)
    
    # Store Telegram username for contact links on the website
    if user.username:
        db.update_provider_profile(user.id, {"telegram_username": user.username})
    
    # Apply referral if they came via a referral link
    referral_code = context.user_data.pop("referral_code", None)
    if referral_code:
        referrer = db.get_referrer_by_code(referral_code)
        if referrer and referrer["telegram_id"] != user.id:
            db.set_referred_by(user.id, referrer["telegram_id"])
            logger.info(f"🤝 User {user.id} referred by {referrer['telegram_id']}")
    db.log_funnel_event(
        user.id,
        "registered",
        {"city_pending": True, "has_username": bool(user.username)},
    )
    
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
    
    # Check if city is available
    city_info = next((c for c in CITIES if c[0] == city), None)
    if city_info and len(city_info) == 3:
        _, _, is_available = city_info
        if not is_available:
            await query.answer(
                f"⚠️ {city} is launching soon! Choose Nairobi or Eldoret for now.",
                show_alert=True
            )
            return CITY
    
    context.user_data["city"] = city
    
    await query.edit_message_text(
        f"📍 *{city} Selected*\n\n"
        "Choose your neighborhood from the list below:",
        reply_markup=get_neighborhood_keyboard(city, 0),
        parse_mode="Markdown"
    )
    return NEIGHBORHOOD


async def neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the neighborhood (for custom text input) and completes registration."""
    user = update.effective_user
    from config import PROFILE_AGE
    db = get_db()
    neighborhood_input = update.message.text.strip()
    
    city = context.user_data.get("city")
    stage_name = context.user_data.get("stage_name")
    
    db.update_provider_profile(user.id, {"city": city, "neighborhood": neighborhood_input})
    
    # Continue to profile completion
    await update.message.reply_text(
        "✨ *Great!* Location saved.\n\n"
        f"📍 {neighborhood_input}, {city}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "*Step 3 of 8* — Now let's add your details\n\n"
        "How old are you? (Enter your age):",
        parse_mode="Markdown"
    )
    return PROFILE_AGE


async def neighborhood_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles neighborhood keyboard selection."""
    from config import PROFILE_AGE
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    db = get_db()
    data = query.data
    
    city = context.user_data.get("city")
    stage_name = context.user_data.get("stage_name")
    
    # Handle pagination
    if data.startswith("hood_page_"):
        page = int(data.replace("hood_page_", ""))
        await query.edit_message_text(
            f"📍 *{city} Selected*\n\n"
            "Choose your neighborhood from the list below:",
            reply_markup=get_neighborhood_keyboard(city, page),
            parse_mode="Markdown"
        )
        return NEIGHBORHOOD
    
    # Handle custom text input option
    if data == "hood_custom":
        await query.edit_message_text(
            f"📍 *{city} Selected*\n\n"
            "Please type your neighborhood name:",
            parse_mode="Markdown"
        )
        return NEIGHBORHOOD
    
    # Handle neighborhood selection
    neighborhood_selected = data.replace("hood_", "")
    db.update_provider_profile(user.id, {"city": city, "neighborhood": neighborhood_selected})
    
    # Continue to profile completion
    await query.edit_message_text(
        "✨ *Great!* Location saved.\n\n"
        f"📍 {neighborhood_selected}, {city}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "*Step 3 of 8* — Now let's add your details\n\n"
        "How old are you? (Enter your age):",
        parse_mode="Markdown"
    )
    return PROFILE_AGE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current conversation."""
    await update.message.reply_text(
        "❌ Cancelled. Tap 👤 My Profile to start again."
    )
    context.user_data.clear()
    return ConversationHandler.END

def register_handlers(application):
    """Registers auth-related handlers with the application."""
    
    application.add_handler(CommandHandler("start", start))
    
    registration_states = {
        STAGE_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, stage_name)
        ],
        CITY: [
            CallbackQueryHandler(city_callback, pattern="^city_")
        ],
        NEIGHBORHOOD: [
            CallbackQueryHandler(neighborhood_callback, pattern="^hood_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, neighborhood)
        ],
        **get_profile_states(),
    }
    registration_handler = ConversationHandler(
        entry_points=[
            CommandHandler("register", register),
            MessageHandler(filters.Regex("^👤 My Profile$"), register),
        ],
        states=registration_states,
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(registration_handler)
    
    application.add_handler(CallbackQueryHandler(
        menu_callback,
        pattern="^menu_(main|profile|checklist|verify_start|verify_go|status)$"
    ))
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_menu_buttons
    ), group=1)

def register_admin_verification_handlers(application):
    # Moved to handlers/verification.py, this is kept empty for backwards compatibility during reload
    pass


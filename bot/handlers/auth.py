"""
Blackbook Bot - Authentication Handlers
Handles: /start, /register, /verify, /myprofile, verification callbacks
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
    PROFILE_AGE, PROFILE_HEIGHT, PROFILE_WEIGHT, PROFILE_BUILD, 
    PROFILE_AVAILABILITY, PROFILE_SERVICES, PROFILE_BIO, PROFILE_NEARBY, PROFILE_PHOTOS, PROFILE_RATES, PROFILE_LANGUAGES,
    AWAITING_PHOTO,
    ADMIN_CHAT_ID,
    CITIES,
    RATE_DURATIONS,
    LANGUAGES,
    FREE_TRIAL_DAYS,
)
from utils.keyboards import (
    get_main_menu_keyboard,
    get_persistent_main_menu,
    get_city_keyboard,
    get_profile_keyboard,
    get_verification_start_keyboard,
    get_back_button,
    get_admin_verification_keyboard,
    get_languages_keyboard,
    get_build_keyboard,
    get_availability_keyboard,
    get_services_keyboard,
    get_neighborhood_keyboard,
    get_photo_management_keyboard,
    get_photo_delete_keyboard,
    get_photo_reorder_keyboard,
    get_online_toggle_keyboard,
    get_full_profile_keyboard,
    get_photo_viewer_keyboard,
    get_skip_cancel_keyboard,
)
from utils.formatters import (
    generate_verification_code,
    format_welcome_message,
    format_returning_user_message,
    format_profile_text,
    format_main_menu_header,
    format_full_profile_text,
)

logger = logging.getLogger(__name__)


# ==================== HELPER FUNCTIONS ====================

def get_db():
    """Gets the database instance from db_context module."""
    from db_context import get_db as _get_db
    return _get_db()


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
        "👤 My Profile",
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
    
    elif text == "👤 My Profile":
        provider = db.get_provider(user.id)
        if not provider:
            # Registration flow is handled by the ConversationHandler entry point.
            return
        # Trigger the /myprofile command for existing users
        await myprofile(update, context)
    
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
    
    # === VERIFY PROMPTS ===
    elif action == "verify_start":
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


# ==================== ONLINE STATUS TOGGLE ====================

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
            "⚠️ You need an active subscription to toggle your status.\n\n"
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


# ==================== PHOTO MANAGEMENT ====================

async def photos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /photos command for photo gallery management."""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You're not registered yet. Use /register first.",
            parse_mode="Markdown"
        )
        return
    
    photos = provider.get("profile_photos") or []
    if isinstance(photos, str):
        import json
        try:
            photos = json.loads(photos)
        except (json.JSONDecodeError, TypeError):
            photos = []
    
    photo_count = len(photos)
    
    await update.message.reply_text(
        "📸 *Photo Gallery Manager*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"You have *{photo_count}* photos in your gallery.\n\n"
        "Manage your profile photos below:",
        reply_markup=get_photo_management_keyboard(photo_count),
        parse_mode="Markdown"
    )


async def photos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles photo management callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    db = get_db()
    data = query.data
    
    provider = db.get_provider(user.id)
    photos = provider.get("profile_photos") or []
    if isinstance(photos, str):
        import json
        try:
            photos = json.loads(photos)
        except (json.JSONDecodeError, TypeError):
            photos = []
    
    # View photos (first photo or specific index)
    if data == "photos_view" or data.startswith("photo_view_"):
        if not photos:
            await query.answer("No photos to view!", show_alert=True)
            return
        
        # Get photo index
        if data == "photos_view":
            idx = 0
        else:
            idx = int(data.replace("photo_view_", ""))
        
        if idx >= len(photos):
            idx = 0
        
        # Send the photo with navigation keyboard
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_photo(
            chat_id=user.id,
            photo=photos[idx],
            caption=f"📸 *Photo {idx + 1} of {len(photos)}*",
            reply_markup=get_photo_viewer_keyboard(idx, len(photos)),
            parse_mode="Markdown"
        )
        return
    
    # Delete photo menu
    if data == "photos_delete":
        if not photos:
            await query.answer("No photos to delete!", show_alert=True)
            return
        
        await query.edit_message_text(
            "🗑️ *Delete Photo*\n\n"
            "Select which photo to remove:",
            reply_markup=get_photo_delete_keyboard(photos),
            parse_mode="Markdown"
        )
        return
    
    # Reorder photos menu
    if data == "photos_reorder":
        if len(photos) < 2:
            await query.answer("Need at least 2 photos to reorder!", show_alert=True)
            return
        
        await query.edit_message_text(
            "🔄 *Reorder Photos*\n\n"
            "Select which photo to move to the first position\n"
            "(This will be your primary profile photo):",
            reply_markup=get_photo_reorder_keyboard(photos),
            parse_mode="Markdown"
        )
        return
    
    # Add photos
    if data == "photos_add":
        await query.edit_message_text(
            "📸 *Add Photos*\n\n"
            "Tap ✏️ Edit Profile in 👤 My Profile to add more photos.",
            parse_mode="Markdown"
        )
        return
    
    # Back to photo management
    if data == "photos_manage":
        await query.edit_message_text(
            "📸 *Photo Gallery Manager*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"You have *{len(photos)}* photos in your gallery.\n\n"
            "Manage your profile photos below:",
            reply_markup=get_photo_management_keyboard(len(photos)),
            parse_mode="Markdown"
        )
        return
    
    # Delete specific photo
    if data.startswith("photo_del_"):
        idx = int(data.replace("photo_del_", ""))
        if 0 <= idx < len(photos):
            photos.pop(idx)
            db.save_provider_photos(user.id, photos)
            await query.edit_message_text(
                f"✅ *Photo #{idx + 1} Deleted!*\n\n"
                f"You now have {len(photos)} photos.",
                reply_markup=get_photo_management_keyboard(len(photos)),
                parse_mode="Markdown"
            )
        return
    
    # Move photo to first position
    if data.startswith("photo_first_"):
        idx = int(data.replace("photo_first_", ""))
        if 0 < idx < len(photos):
            photo_to_move = photos.pop(idx)
            photos.insert(0, photo_to_move)
            db.save_provider_photos(user.id, photos)
            await query.edit_message_text(
                f"✅ *Photo #{idx + 1} is now your primary photo!*\n\n"
                "This will be the first photo visitors see.",
                reply_markup=get_photo_management_keyboard(len(photos)),
                parse_mode="Markdown"
            )
        return


# ==================== VERIFICATION CONVERSATION ====================

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
    
    await update.message.reply_text(
        "📸 *Profile Verification*\n\n"
        "Upload the pictures you will be using on your profile.\n\n"
        "Our team will review and approve within *2-4 hours*.\n\n"
        "📷 Send your photo now:",
        parse_mode="Markdown"
    )
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
    
    await context.bot.send_photo(
        chat_id=int(ADMIN_CHAT_ID),
        photo=photo_file_id,
        caption=caption,
        reply_markup=get_admin_verification_keyboard(user.id),
        parse_mode="Markdown"
    )
    
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


# ==================== PROFILE COMPLETION CONVERSATION ====================

async def complete_profile_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the profile completion flow from button click."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    db = get_db()
    
    logger.info(f"🔘 Complete profile button clicked by user {user.id}")
    
    provider = db.get_provider(user.id)
    if not provider:
        await query.answer("❌ You need to /register first.", show_alert=True)
        logger.warning(f"❌ User {user.id} not registered")
        return ConversationHandler.END
    
    await query.message.reply_text(
        "✨ *Professional Portfolio Builder*\n\n"
        "Let's make your profile stand out to high-value clients.\n"
        "We'll collect your stats, services, bio, and photos.\n\n"
        "*Step 1/8: Age*\n"
        "Please enter your age (e.g., 24):",
        parse_mode="Markdown"
    )
    logger.info(f"→ Conversation started, waiting for age input in PROFILE_AGE state")
    return PROFILE_AGE


async def complete_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the profile completion flow."""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text("❌ You need to /register first.")
        return ConversationHandler.END
        
    await update.message.reply_text(
        "✨ *Professional Portfolio Builder*\n\n"
        "Let's make your profile stand out to high-value clients.\n"
        "We'll collect your stats, services, bio, and photos.\n\n"
        "*Step 1/8: Age*\n"
        "Please enter your age (e.g., 24):",
        parse_mode="Markdown"
    )
    return PROFILE_AGE

async def profile_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores age and asks for height."""
    logger.info(f"📊 profile_age handler called for user {update.effective_user.id}")
    
    text = update.message.text.strip()
    logger.info(f"📝 Received text: {text}")
    
    # Allow user to exit by clicking menu buttons
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if text in menu_buttons or text.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Tap 👤 My Profile to start again.")
        return ConversationHandler.END
    
    try:
        age = int(text)
        logger.info(f"✅ Parsed age: {age}")
        if age < 18 or age > 60:
            await update.message.reply_text("⚠️ Age must be between 18 and 60. Try again.")
            return PROFILE_AGE
        context.user_data["p_age"] = age
    except ValueError:
        logger.warning(f"❌ Failed to parse age from: {text}")
        await update.message.reply_text("⚠️ Please enter a valid number (e.g., 24).")
        return PROFILE_AGE
        
    await update.message.reply_text(
        "📏 **Step 2/8: Height**\n"
        "Enter your height in cm (e.g., 170):"
    )
    logger.info(f"→ Moving to PROFILE_HEIGHT state")
    return PROFILE_HEIGHT

async def profile_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores height and asks for weight."""
    text = update.message.text.strip()
    
    # Allow user to exit by clicking menu buttons
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if text in menu_buttons or text.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
    try:
        height = int(text)
        context.user_data["p_height"] = height
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number (e.g., 170).")
        return PROFILE_HEIGHT
        
    await update.message.reply_text(
        "⚖️ **Step 3/8: Weight**\n"
        "Enter your weight in kg (e.g., 55):"
    )
    return PROFILE_WEIGHT

async def profile_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores weight and asks for build."""
    logger.info(f"📊 profile_weight handler called for user {update.effective_user.id}")
    
    text = update.message.text.strip()
    logger.info(f"📝 Received text: {text}")
    
    # Allow user to exit by clicking menu buttons
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if text in menu_buttons or text.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
    try:
        weight = int(text)
        logger.info(f"✅ Parsed weight: {weight}")
        context.user_data["p_weight"] = weight
    except ValueError:
        logger.warning(f"❌ Failed to parse weight from: {text}")
        await update.message.reply_text("⚠️ Please enter a valid number (e.g., 55).")
        return PROFILE_WEIGHT
        
    logger.info(f"→ Sending build keyboard and moving to PROFILE_BUILD state")
    await update.message.reply_text(
        "🧘‍♀️ **Step 4/8: Body Build**\n"
        "Select your body type:",
        reply_markup=get_build_keyboard()
    )
    logger.info(f"✅ Build keyboard sent successfully")
    return PROFILE_BUILD

async def profile_build(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores build and asks for availability."""
    query = update.callback_query
    await query.answer()
    
    build = query.data.replace("build_", "")
    context.user_data["p_build"] = build
    
    await query.edit_message_text(
        f"✅ Build: {build}\n\n"
        "🏠 **Step 5/8: Availability**\n"
        "Where do you provide services?",
        reply_markup=get_availability_keyboard()
    )
    return PROFILE_AVAILABILITY

async def profile_availability(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores availability and asks for services."""
    query = update.callback_query
    await query.answer()
    
    avail = query.data.replace("avail_", "")
    context.user_data["p_avail"] = avail
    
    context.user_data["p_services"] = [] # Initialize services list
    
    await query.edit_message_text(
        f"✅ Availability: {avail}\n\n"
        "💆‍♀️ **Step 6/8: Services Menu**\n"
        "Select all that apply (Multi-select). Click Done when finished.",
        reply_markup=get_services_keyboard([])
    )
    return PROFILE_SERVICES

async def profile_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles multi-select services."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    current_services = context.user_data.get("p_services", [])
    
    if data == "service_done":
        if not current_services:
            await query.answer("⚠️ Select at least one service", show_alert=True)
            return PROFILE_SERVICES
            
        await query.edit_message_text(
            f"✅ Selected: {', '.join(current_services)}\n\n"
            "📝 **Step 7/8: Your Bio**\n"
            "Write a short, elegant description about yourself (2-3 sentences). "
            "Sell the fantasy!",
            parse_mode="Markdown"
        )
        return PROFILE_BIO
        
    service = data.replace("service_", "")
    if service in current_services:
        current_services.remove(service)
    else:
        current_services.append(service)
        
    context.user_data["p_services"] = current_services
    
    # Update keyboard to show checks
    await query.edit_message_reply_markup(
        reply_markup=get_services_keyboard(current_services)
    )
    return PROFILE_SERVICES

async def profile_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores bio and asks for nearby places."""
    bio = update.message.text.strip()
    
    # Allow user to exit by clicking menu buttons
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if bio in menu_buttons or bio.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
    if len(bio) < 20:
        await update.message.reply_text("⚠️ Too short. Please write at least one full sentence.")
        return PROFILE_BIO
        
    context.user_data["p_bio"] = bio
    
    await update.message.reply_text(
        "🗺️ *Step 7/8: Location Highlights*\n"
        "List popular malls or landmarks near you (for SEO).\n"
        "e.g., 'Near Yaya Center, Prestige Plaza'",
        parse_mode="Markdown"
    )
    return PROFILE_NEARBY

async def profile_nearby(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores nearby places and asks for photos."""
    nearby = update.message.text.strip()
    
    # Allow user to exit by clicking menu buttons
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if nearby in menu_buttons or nearby.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
    context.user_data["p_nearby"] = nearby
    
    await update.message.reply_text(
        "📸 *Step 8/8: Gallery Photos*\n\n"
        "Upload *3 photos minimum* (you can send up to 5).\n\n"
        "Tips:\n"
        "• Use good lighting\n"
        "• Show variety (full body, face, different angles)\n"
        "• Professional quality attracts premium clients\n\n"
        "Send your first photo now:",
        parse_mode="Markdown"
    )
    context.user_data["p_photos"] = []
    return PROFILE_PHOTOS

async def profile_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles photo uploads for profile."""
    user = update.effective_user
    db = get_db()
    
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send a photo, not text. Use the 📷 camera or gallery.",
            parse_mode="Markdown"
        )
        return PROFILE_PHOTOS
    
    photo = update.message.photo[-1]
    photo_file_id = photo.file_id
    
    photos = context.user_data.get("p_photos", [])
    photos.append(photo_file_id)
    context.user_data["p_photos"] = photos
    
    photo_count = len(photos)
    
    if photo_count < 3:
        await update.message.reply_text(
            f"✅ Photo {photo_count}/3 received.\n\n"
            f"Send {3 - photo_count} more photo(s) (minimum 3 required):",
            parse_mode="Markdown"
        )
        return PROFILE_PHOTOS
    elif photo_count == 3:
        await update.message.reply_text(
            "✅ Minimum photos received!\n\n"
            "You can:\n"
            "• Send 2 more photos (recommended for better visibility)\n"
            "• Or type /done to finish",
            parse_mode="Markdown"
        )
        return PROFILE_PHOTOS
    elif photo_count < 5:
        await update.message.reply_text(
            f"✅ Photo {photo_count}/5 received.\n\n"
            f"Send {5 - photo_count} more or type /done to finish:",
            parse_mode="Markdown"
        )
        return PROFILE_PHOTOS
    else:
        # 5 photos reached, move to rates
        await update.message.reply_text(
            "✅ All 5 photos received! Looking great! 📸\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Next: Set your hourly rates...",
            parse_mode="Markdown"
        )
        return await ask_rates(update, context)


async def ask_rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for hourly rates."""
    await update.message.reply_text(
        "💰 *Set Your Hourly Rates*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Please provide your pricing in KES for each duration.\n\n"
        "Send them in this exact format (one message):\n\n"
        "`30min: 2000`\n"
        "`1hr: 3500`\n"
        "`2hr: 6000`\n"
        "`3hr: 8000`\n"
        "`overnight: 15000`\n\n"
        "💡 *Example:*\n"
        "```\n30min: 3000\n1hr: 5000\n2hr: 8500\n3hr: 12000\novernight: 20000```\n\n"
        "⚠️ Copy the format above and just change the numbers.",
        parse_mode="Markdown"
    )
    return PROFILE_RATES


async def profile_rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parses and stores hourly rates."""
    text = update.message.text.strip()
    
    # Allow user to exit by clicking menu buttons
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if text in menu_buttons or text.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
    # Parse rates from text
    rates = {}
    lines = text.split('\n')
    
    expected_keys = ['30min', '1hr', '2hr', '3hr', 'overnight']
    
    for line in lines:
        if ':' not in line:
            continue
        parts = line.split(':')
        if len(parts) != 2:
            continue
        key = parts[0].strip().lower()
        try:
            value = int(parts[1].strip().replace(',', '').replace('KES', '').replace('kes', ''))
            if key in expected_keys:
                rates[f'rate_{key}'] = value
        except ValueError:
            continue
    
    # Validate we got all rates
    if len(rates) != 5:
        await update.message.reply_text(
            "❌ Invalid format. Please provide all 5 rates.\n\n"
            "Copy this template and change the numbers:\n\n"
            "```\n30min: 3000\n1hr: 5000\n2hr: 8500\n3hr: 12000\novernight: 20000```",
            parse_mode="Markdown"
        )
        return PROFILE_RATES
    
    # Store rates
    context.user_data.update(rates)
    
    # Show confirmation and move to languages
    await update.message.reply_text(
        "✅ *Rates Saved!*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💵 30 min: {rates['rate_30min']:,} KES\n"
        f"💵 1 hour: {rates['rate_1hr']:,} KES\n"
        f"💵 2 hours: {rates['rate_2hr']:,} KES\n"
        f"💵 3 hours: {rates['rate_3hr']:,} KES\n"
        f"💵 Overnight: {rates['rate_overnight']:,} KES\n\n"
        "Almost done! One more step...",
        parse_mode="Markdown"
    )
    
    # Ask for languages
    await update.message.reply_text(
        "🌍 *Languages You Speak*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select all languages you can communicate in.\n"
        "This helps attract international clients!\n\n"
        "Tap to select/deselect:",
        reply_markup=get_languages_keyboard(),
        parse_mode="Markdown"
    )
    context.user_data["p_languages"] = []
    return PROFILE_LANGUAGES


async def profile_languages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles language selection (multi-select)."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    current_languages = context.user_data.get("p_languages", [])
    
    if data == "lang_done":
        if not current_languages:
            await query.answer("⚠️ Select at least one language", show_alert=True)
            return PROFILE_LANGUAGES
            
        await query.edit_message_text(
            f"✅ Languages: {', '.join(current_languages)}\n\n"
            "Saving your complete profile...",
            parse_mode="Markdown"
        )
        return await save_complete_profile(update, context)
        
    # Extract language name from callback
    language_code = data.replace("lang_", "")
    # Find full language name with emoji
    full_language = next((lang for lang in LANGUAGES if lang.startswith(language_code)), None)
    
    if full_language:
        if full_language in current_languages:
            current_languages.remove(full_language)
        else:
            current_languages.append(full_language)
        
        context.user_data["p_languages"] = current_languages
        
        # Update keyboard to show checks
        await query.edit_message_reply_markup(
            reply_markup=get_languages_keyboard(current_languages)
        )
    
    return PROFILE_LANGUAGES

async def save_complete_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the complete profile to database."""
    user = update.effective_user
    db = get_db()
    
    # Pack data
    import json
    languages_list = context.user_data.get("p_languages", [])
    data = {
        "age": context.user_data["p_age"],
        "height_cm": context.user_data["p_height"],
        "weight_kg": context.user_data["p_weight"],
        "build": context.user_data["p_build"],
        "availability_type": context.user_data["p_avail"],
        "services": json.dumps(context.user_data["p_services"]),
        "bio": context.user_data["p_bio"],
        "nearby_places": context.user_data["p_nearby"],
        "rate_30min": context.user_data.get("rate_30min"),
        "rate_1hr": context.user_data.get("rate_1hr"),
        "rate_2hr": context.user_data.get("rate_2hr"),
        "rate_3hr": context.user_data.get("rate_3hr"),
        "rate_overnight": context.user_data.get("rate_overnight"),
        "languages": json.dumps(languages_list),
    }
    
    db.update_provider_profile(user.id, data)
    
    # Save photos (store as JSON array of file_ids)
    photos = context.user_data["p_photos"]
    db.save_provider_photos(user.id, photos)
    
    photo_count = len(photos)
    bonus_msg = ""
    if photo_count >= 5:
        bonus_msg = "\n\n🌟 *5-Photo Bonus:* Premium visibility in search results!"
    
    lang_count = len(languages_list)
    await update.message.reply_text(
        f"✅ *Profile Saved Successfully!*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📸 {photo_count} photos uploaded{bonus_msg}\n"
        f"💰 Rates configured\n"
        f"🌍 {lang_count} language(s) set\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ *Awaiting Admin Approval*\n\n"
        "Your profile will be reviewed within *30 minutes*.\n"
        "You'll receive a notification once approved!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 *While you wait:*\n"
        "• Use 👤 My Profile to view/edit your info\n"
        "• Use 💰 Top up Balance to activate your listing",
        parse_mode="Markdown",
        reply_markup=get_persistent_main_menu()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles /done command to finish photo upload early."""
    photos = context.user_data.get("p_photos", [])
    
    if len(photos) < 3:
        await update.message.reply_text(
            f"❌ You've only uploaded {len(photos)} photo(s).\n"
            "Minimum 3 photos required. Please send more photos.",
            parse_mode="Markdown"
        )
        return PROFILE_PHOTOS
    
    await update.message.reply_text(
        f"✅ {len(photos)} photos saved!\n\n"
        "Moving to rates setup...",
        parse_mode="Markdown"
    )
    
    return await ask_rates(update, context)


# ==================== VERIFICATION CONVERSATION ====================

async def admin_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin approval/rejection of verification requests."""
    query = update.callback_query
    await query.answer()
    db = get_db()
    
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
        
        # Check if they have an active subscription
        is_active = provider.get("is_active", False) if provider else False
        
        if is_active:
            # Already paid - they're now live
            await context.bot.send_message(
                chat_id=provider_id,
                text="🎉 *VERIFIED! You're Now Live!*\n\n"
                     "✅ Blue Tick status granted\n"
                     "✅ Profile is active on innbucks.org\n\n"
                     "Your profile is now visible to premium clients!\n\n"
                     "🌐 View your listing at: *https://innbucks.org*",
                parse_mode="Markdown"
            )
        else:
            # Not paid yet - verified but need subscription
            await context.bot.send_message(
                chat_id=provider_id,
                text="✅ *Verification Approved!*\n\n"
                     "🎉 You now have the Blue Tick ✔️\n\n"
                     "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     "📋 *Your profile is saved but not yet live.*\n\n"
                     f"🎁 You can start a *{FREE_TRIAL_DAYS}-day free trial* once,\n"
                     "or activate a paid package immediately.\n\n"
                     "💡 Once activated, your profile goes live instantly!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🎁 Start {FREE_TRIAL_DAYS}-Day Free Trial", callback_data="menu_trial_activate")],
                    [InlineKeyboardButton("💰 Choose Paid Package", callback_data="menu_topup")],
                ])
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
                 "Please tap 📸 Get Verified in your profile to try again with a clearer photo.",
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
    """Shows the provider's full profile with edit options."""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You're not registered yet.\n\n"
            "Tap 👤 My Profile in the menu below to get started!",
            parse_mode="Markdown",
            reply_markup=get_persistent_main_menu()
        )
        return
    
    # Check if this is a new registration that needs completion
    profile_fields = ['age', 'height_cm', 'weight_kg', 'build', 'services', 'bio', 'profile_photos']
    is_incomplete = any(not provider.get(field) for field in profile_fields)
    
    if is_incomplete:
        # Prompt to complete profile
        await update.message.reply_text(
            "👤 *Complete Your Profile*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Welcome, *{provider.get('display_name', 'there')}*!\n\n"
            "Your profile needs a few more details before you can go live.\n\n"
            "Tap below to complete your profile:",
            reply_markup=get_profile_keyboard(provider),
            parse_mode="Markdown"
        )
    else:
        # Show full profile with edit options
        await update.message.reply_text(
            format_full_profile_text(provider),
            reply_markup=get_full_profile_keyboard(provider),
            parse_mode="Markdown"
        )


# ==================== PROFILE EDIT SECTION HANDLERS ====================

async def edit_section_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles edit section button callbacks for individual profile sections."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    db = get_db()
    data = query.data
    
    provider = db.get_provider(user.id)
    if not provider:
        await query.edit_message_text("❌ Profile not found. Please /register first.")
        return
    
    # Handle each edit section
    if data == "edit_basic":
        await query.edit_message_text(
            "📝 *Edit Basic Info*\n\n"
            f"Current name: *{provider.get('display_name', 'Not set')}*\n"
            f"Location: *{provider.get('neighborhood', '')}, {provider.get('city', '')}*\n\n"
            "Send your new stage name to update it:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭️ Skip", callback_data="edit_cancel")],
                [InlineKeyboardButton("❌ Cancel", callback_data="edit_cancel")]
            ]),
            parse_mode="Markdown"
        )
        context.user_data["editing"] = "name"
        return
    
    elif data == "edit_stats":
        await query.edit_message_text(
            "📏 *Edit Stats*\n\n"
            f"Age: {provider.get('age', '—')}\n"
            f"Height: {provider.get('height_cm', '—')} cm\n"
            f"Weight: {provider.get('weight_kg', '—')} kg\n"
            f"Build: {provider.get('build', '—')}\n\n"
            "Send your new age to start updating:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="edit_cancel")]
            ]),
            parse_mode="Markdown"
        )
        context.user_data["editing"] = "age"
        return
    
    elif data == "edit_bio":
        current_bio = provider.get('bio', 'Not set')
        if current_bio and len(current_bio) > 100:
            current_bio = current_bio[:97] + "..."
        await query.edit_message_text(
            "💬 *Edit Bio*\n\n"
            f"Current: _{current_bio}_\n\n"
            "Send your new bio:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="edit_cancel")]
            ]),
            parse_mode="Markdown"
        )
        context.user_data["editing"] = "bio"
        return
    
    elif data == "edit_services":
        await query.edit_message_text(
            "✨ *Edit Services*\n\n"
            "Select the services you offer:",
            reply_markup=get_services_keyboard(context.user_data.get("selected_services", [])),
            parse_mode="Markdown"
        )
        context.user_data["editing"] = "services"
        return
    
    elif data == "edit_rates":
        await query.edit_message_text(
            "💰 *Edit Rates*\n\n"
            "Enter your rates in this format:\n"
            "`30min: 3000`\n"
            "`1hr: 5000`\n"
            "`2hr: 8500`\n"
            "`3hr: 12000`\n"
            "`overnight: 20000`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="edit_cancel")]
            ]),
            parse_mode="Markdown"
        )
        context.user_data["editing"] = "rates"
        return
    
    elif data == "edit_location":
        await query.edit_message_text(
            "📍 *Edit Location*\n\n"
            "Select your city:",
            reply_markup=get_city_keyboard(),
            parse_mode="Markdown"
        )
        context.user_data["editing"] = "location"
        return


async def handle_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text input when user is editing a profile section."""
    editing = context.user_data.get("editing")
    
    if not editing:
        return  # Not in edit mode, let other handlers process
    
    user = update.effective_user
    db = get_db()
    text = update.message.text.strip()
    
    # Handle cancel
    if text.lower() == "cancel" or text.lower() == "skip":
        context.user_data.pop("editing", None)
        provider = db.get_provider(user.id)
        await update.message.reply_text(
            format_full_profile_text(provider),
            reply_markup=get_full_profile_keyboard(provider),
            parse_mode="Markdown"
        )
        return
    
    # Process based on what we're editing
    if editing == "name":
        db.update_provider_profile(user.id, {"display_name": text})
        await update.message.reply_text(
            f"✅ *Name Updated!*\n\nYour stage name is now: *{text}*",
            parse_mode="Markdown"
        )
    
    elif editing == "bio":
        db.update_provider_profile(user.id, {"bio": text})
        await update.message.reply_text(
            f"✅ *Bio Updated!*\n\nYour new bio has been saved.",
            parse_mode="Markdown"
        )
    
    elif editing == "age":
        try:
            age = int(text)
            if age < 18 or age > 65:
                await update.message.reply_text("⚠️ Age must be between 18-65. Try again:")
                return
            db.update_provider_profile(user.id, {"age": age})
            await update.message.reply_text(
                f"✅ *Age Updated!*\n\nNow send your height in cm (e.g. 165):",
                parse_mode="Markdown"
            )
            context.user_data["editing"] = "height"
            return
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid number for age:")
            return
    
    elif editing == "height":
        try:
            height = int(text)
            db.update_provider_profile(user.id, {"height_cm": height})
            await update.message.reply_text(
                f"✅ *Height Updated!*\n\nNow send your weight in kg:",
                parse_mode="Markdown"
            )
            context.user_data["editing"] = "weight"
            return
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid number for height:")
            return
    
    elif editing == "weight":
        try:
            weight = int(text)
            db.update_provider_profile(user.id, {"weight_kg": weight})
            await update.message.reply_text(
                f"✅ *Stats Updated!*\n\nAge, height and weight have been saved.",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid number for weight:")
            return
    
    elif editing == "rates":
        import re
        lines = text.split("\n")
        rates = {}
        for line in lines:
            match = re.match(r"(\w+):\s*(\d+)", line)
            if match:
                period, amount = match.groups()
                if "30" in period:
                    rates["rate_30min"] = int(amount)
                elif "1" in period:
                    rates["rate_1hr"] = int(amount)
                elif "2" in period:
                    rates["rate_2hr"] = int(amount)
                elif "3" in period:
                    rates["rate_3hr"] = int(amount)
                elif "over" in period.lower():
                    rates["rate_overnight"] = int(amount)
        
        if rates:
            db.update_provider_profile(user.id, rates)
            await update.message.reply_text(
                "✅ *Rates Updated!*\n\nYour new rates have been saved.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Could not parse rates. Use format:\n`30min: 3000`\n`1hr: 5000`", parse_mode="Markdown")
            return
    
    # Clear editing state and show profile
    context.user_data.pop("editing", None)
    provider = db.get_provider(user.id)
    await update.message.reply_text(
        format_full_profile_text(provider),
        reply_markup=get_full_profile_keyboard(provider),
        parse_mode="Markdown"
    )


async def edit_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles cancel/skip button during edit mode."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    db = get_db()
    
    context.user_data.pop("editing", None)
    
    provider = db.get_provider(user.id)
    await query.edit_message_text(
        format_full_profile_text(provider),
        reply_markup=get_full_profile_keyboard(provider),
        parse_mode="Markdown"
    )



def register_handlers(application):
    """Registers all auth-related handlers with the application."""
    
    # /start command
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myprofile", myprofile))
    
    # /status command for online toggle
    application.add_handler(CommandHandler("status", toggle_online_status))
    
    # /photos command for photo management
    application.add_handler(CommandHandler("photos", photos_command))
    
    # Shared profile completion states used by both profile_handler and registration_handler
    profile_states = {
        PROFILE_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_age)],
        PROFILE_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_height)],
        PROFILE_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_weight)],
        PROFILE_BUILD: [CallbackQueryHandler(profile_build, pattern="^build_")],
        PROFILE_AVAILABILITY: [CallbackQueryHandler(profile_availability, pattern="^avail_")],
        PROFILE_SERVICES: [CallbackQueryHandler(profile_services, pattern="^service_")],
        PROFILE_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_bio)],
        PROFILE_NEARBY: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_nearby)],
        PROFILE_PHOTOS: [
            MessageHandler(filters.PHOTO, profile_photos),
            CommandHandler("done", done_photos),
        ],
        PROFILE_RATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_rates)],
        PROFILE_LANGUAGES: [CallbackQueryHandler(profile_languages, pattern="^lang_")],
    }
    
    # Profile Completion Conversation
    profile_handler = ConversationHandler(
        entry_points=[
            CommandHandler("complete_profile", complete_profile),
            CallbackQueryHandler(complete_profile_from_button, pattern="^menu_complete_profile$")
        ],
        states=profile_states,
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(profile_handler)
    
    # Registration conversation - UNIFIED FLOW (name → city → neighborhood → profile details)
    registration_states = {
        # Basic registration
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
        # Profile completion states (continues from neighborhood)
        **profile_states,
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
    
    # Online toggle callback
    application.add_handler(CallbackQueryHandler(
        toggle_online_callback,
        pattern="^(toggle_online|noop)$"
    ))
    
    # Photo management callbacks
    application.add_handler(CallbackQueryHandler(
        photos_callback,
        pattern="^(photos_|photo_del_|photo_first_|photo_view_)"
    ))
    
    # Edit section callbacks
    application.add_handler(CallbackQueryHandler(
        edit_section_callback,
        pattern="^edit_(basic|stats|bio|services|rates|location)$"
    ))
    
    # Menu callbacks (auth section)
    application.add_handler(CallbackQueryHandler(
        menu_callback,
        pattern="^menu_(main|profile|verify_start|verify_go|status)$"
    ))
    
    # Edit cancel callback
    application.add_handler(CallbackQueryHandler(
        edit_cancel_callback,
        pattern="^edit_cancel$"
    ))
    
    # Edit input handler (catch text when in edit mode - runs before menu handler)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_edit_input
    ), group=0)
    
    # Persistent menu button handler (add at lower priority to not interfere with conversations)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_menu_buttons
    ), group=1)


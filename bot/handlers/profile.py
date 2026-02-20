import logging
import json
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters
)

from config import (
    PROFILE_AGE, PROFILE_HEIGHT, PROFILE_WEIGHT, PROFILE_BUILD,
    PROFILE_AVAILABILITY, PROFILE_SERVICES, PROFILE_BIO,
    PROFILE_NEARBY, PROFILE_PHOTOS, PROFILE_RATES, PROFILE_LANGUAGES,
    LANGUAGES,
    ADMIN_CHAT_ID
)
from db_context import get_db
from utils.keyboards import (
    get_profile_keyboard, get_full_profile_keyboard, get_city_keyboard,
    get_build_keyboard, get_availability_keyboard, get_services_keyboard,
    get_languages_keyboard, get_persistent_main_menu
)
from utils.formatters import format_full_profile_text
from handlers.verification import (
    is_verification_pending,
    send_admin_verification_request
)

logger = logging.getLogger(__name__)

PROFILE_REQUIRED_FIELDS = ["age", "height_cm", "weight_kg", "build", "services", "bio", "profile_photos"]
PROFILE_FLOW_TOTAL_STEPS = 11

def is_profile_complete(provider: dict) -> bool:
    """Checks if key profile data required for listing exists."""
    if not provider:
        return False
    return all(provider.get(field) for field in PROFILE_REQUIRED_FIELDS)

def format_profile_step(step: int, title: str, body: str) -> str:
    """Returns a consistent, premium-looking profile step message."""
    return (
        "✨ *Professional Portfolio Builder*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Step {step}/{PROFILE_FLOW_TOTAL_STEPS}: {title}*\n\n"
        f"{body}"
    )

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
        return ConversationHandler.END
    
    await query.message.reply_text(
        format_profile_step(
            1,
            "Age",
            "Let's make your profile stand out to high-value clients.\n"
            "We will collect your stats, services, bio, photos, rates, and languages.\n\n"
            "Please enter your age (e.g., 24).",
        ),
        parse_mode="Markdown",
    )
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
        format_profile_step(
            1,
            "Age",
            "Let's make your profile stand out to high-value clients.\n"
            "We will collect your stats, services, bio, photos, rates, and languages.\n\n"
            "Please enter your age (e.g., 24).",
        ),
        parse_mode="Markdown",
    )
    return PROFILE_AGE

async def profile_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores age and asks for height."""
    text = update.message.text.strip()
    
    # Allow user to exit by clicking menu buttons
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if text in menu_buttons or text.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Tap 👤 My Profile to start again.")
        return ConversationHandler.END
    
    try:
        age = int(text)
        if age < 18 or age > 60:
            await update.message.reply_text("⚠️ Age must be between 18 and 60. Try again.")
            return PROFILE_AGE
        context.user_data["p_age"] = age
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number (e.g., 24).")
        return PROFILE_AGE
        
    await update.message.reply_text(
        format_profile_step(
            2,
            "Height",
            "Enter your height in cm (e.g., 170).",
        ),
        parse_mode="Markdown",
    )
    return PROFILE_HEIGHT

async def profile_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores height and asks for weight."""
    text = update.message.text.strip()
    
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
        format_profile_step(
            3,
            "Weight",
            "Enter your weight in kg (e.g., 55).",
        ),
        parse_mode="Markdown",
    )
    return PROFILE_WEIGHT

async def profile_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores weight and asks for build."""
    text = update.message.text.strip()
    
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if text in menu_buttons or text.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
    try:
        weight = int(text)
        context.user_data["p_weight"] = weight
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number (e.g., 55).")
        return PROFILE_WEIGHT
        
    await update.message.reply_text(
        format_profile_step(
            4,
            "Body Build",
            "Select your body type from the options below.",
        ),
        parse_mode="Markdown",
        reply_markup=get_build_keyboard(),
    )
    return PROFILE_BUILD

async def profile_build(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores build and asks for availability."""
    query = update.callback_query
    await query.answer()
    
    build = query.data.replace("build_", "")
    context.user_data["p_build"] = build
    
    await query.edit_message_text(
        format_profile_step(
            5,
            "Availability",
            f"✅ Build selected: *{build}*\n\nWhere do you provide services?",
        ),
        parse_mode="Markdown",
        reply_markup=get_availability_keyboard(),
    )
    return PROFILE_AVAILABILITY

async def profile_availability(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores availability and asks for services."""
    query = update.callback_query
    await query.answer()
    
    avail = query.data.replace("avail_", "")
    context.user_data["p_avail"] = avail
    
    context.user_data["p_services"] = []
    
    await query.edit_message_text(
        format_profile_step(
            6,
            "Services Menu",
            f"✅ Availability selected: *{avail}*\n\n"
            "Select all services that apply.\n"
            "You can multi-select, then tap *Done / Continue*.",
        ),
        parse_mode="Markdown",
        reply_markup=get_services_keyboard([]),
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
            format_profile_step(
                7,
                "Your Bio",
                f"✅ Services selected: {', '.join(current_services)}\n\n"
                "Write a short, elegant description about yourself (2-3 sentences).\n"
                "Focus on vibe, professionalism, and what makes you memorable.",
            ),
            parse_mode="Markdown",
        )
        return PROFILE_BIO
        
    service = data.replace("service_", "")
    if service in current_services:
        current_services.remove(service)
    else:
        current_services.append(service)
        
    context.user_data["p_services"] = current_services
    
    await query.edit_message_reply_markup(
        reply_markup=get_services_keyboard(current_services)
    )
    return PROFILE_SERVICES

async def profile_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores bio and asks for nearby places."""
    bio = update.message.text.strip()
    
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if bio in menu_buttons or bio.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
    if len(bio) < 20:
        await update.message.reply_text("⚠️ Too short. Please write at least one full sentence.")
        return PROFILE_BIO
        
    context.user_data["p_bio"] = bio
    
    await update.message.reply_text(
        format_profile_step(
            8,
            "Location Highlights",
            "List popular malls or landmarks near you.\n"
            "This helps discovery in search.\n\n"
            "Example: `Near Yaya Centre, Prestige Plaza`",
        ),
        parse_mode="Markdown",
    )
    return PROFILE_NEARBY

async def profile_nearby(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores nearby places and asks for photos."""
    nearby = update.message.text.strip()
    
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if nearby in menu_buttons or nearby.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
    context.user_data["p_nearby"] = nearby
    
    await update.message.reply_text(
        format_profile_step(
            9,
            "Gallery Photos",
            "Upload *3 photos minimum* (you can send up to 5).\n\n"
            "*Tips:*\n"
            "• Use good lighting\n"
            "• Show variety (full body, face, different angles)\n"
            "• Professional quality attracts premium clients\n\n"
            "Send your first photo now.",
        ),
        parse_mode="Markdown",
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
        format_profile_step(
            10,
            "Set Your Rates",
            "Provide your pricing in KES for each duration.\n\n"
            "Send in this exact format (one message):\n"
            "`30min: 2000`\n"
            "`1hr: 3500`\n"
            "`2hr: 6000`\n"
            "`3hr: 8000`\n"
            "`overnight: 15000`\n\n"
            "Example:\n"
            "```\n30min: 3000\n1hr: 5000\n2hr: 8500\n3hr: 12000\novernight: 20000\n```",
        ),
        parse_mode="Markdown",
    )
    return PROFILE_RATES

async def profile_rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parses and stores hourly rates."""
    text = update.message.text.strip()
    
    menu_buttons = ["👑 The Collection", "👤 My Profile", "💰 Top up Balance", "🛡️ Safety Suite", "🤝 Affiliate Program", "📞 Support", "📋 Rules"]
    if text in menu_buttons or text.startswith("/"):
        await update.message.reply_text("❌ Profile completion cancelled. Use /complete_profile to start again.")
        return ConversationHandler.END
    
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
    
    if len(rates) != 5:
        await update.message.reply_text(
            "❌ Invalid format. Please provide all 5 rates.\n\n"
            "Copy this template and change the numbers:\n\n"
            "```\n30min: 3000\n1hr: 5000\n2hr: 8500\n3hr: 12000\novernight: 20000```",
            parse_mode="Markdown"
        )
        return PROFILE_RATES
    
    context.user_data.update(rates)
    
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
    
    await update.message.reply_text(
        format_profile_step(
            11,
            "Languages You Speak",
            "Select all languages you can communicate in.\n"
            "This helps attract international and premium clients.\n\n"
            "Tap to select/deselect, then tap *Done / Continue*.",
        ),
        reply_markup=get_languages_keyboard(),
        parse_mode="Markdown",
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
        
    language_code = data.replace("lang_", "")
    full_language = next((lang for lang in LANGUAGES if lang.startswith(language_code)), None)
    
    if full_language:
        if full_language in current_languages:
            current_languages.remove(full_language)
        else:
            current_languages.append(full_language)
        
        context.user_data["p_languages"] = current_languages
        
        await query.edit_message_reply_markup(
            reply_markup=get_languages_keyboard(current_languages)
        )
    
    return PROFILE_LANGUAGES

async def save_complete_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the complete profile to database."""
    user = update.effective_user
    db = get_db()
    provider_before = db.get_provider(user.id) or {}
    
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
    
    # Save photos
    photos = context.user_data["p_photos"]
    db.save_provider_photos(user.id, photos)

    auto_submitted_for_review = False
    if photos and not provider_before.get("is_verified") and not is_verification_pending(provider_before):
        db.save_verification_photo(user.id, photos[0])
        provider_after = db.get_provider(user.id) or {}
        if ADMIN_CHAT_ID:
            try:
                caption = (
                    "🔍 *NEW VERIFICATION REQUEST*\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"👤 Provider: {provider_after.get('display_name', 'Unknown')}\n"
                    f"📍 City: {provider_after.get('city', 'N/A')}\n"
                    f"🆔 User ID: `{user.id}`\n"
                    "Source: Profile completion"
                )
                sent = await send_admin_verification_request(
                    context=context,
                    provider_id=user.id,
                    photo_file_id=photos[0],
                    caption=caption,
                )
                if not sent:
                    logger.error(f"❌ Failed sending auto verification request for {user.id}")
                else:
                    db.log_funnel_event(user.id, "verification_submitted", {"source": "profile_complete_auto"})
                    auto_submitted_for_review = True
            except Exception as e:
                logger.error(f"❌ Failed to auto-submit verification request for {user.id}: {e}")
    db.log_funnel_event(
        user.id,
        "profile_complete",
        {"photo_count": len(photos), "languages_count": len(languages_list)},
    )
    
    photo_count = len(photos)
    bonus_msg = ""
    if photo_count >= 5:
        bonus_msg = "\n\n🌟 *5-Photo Bonus:* Premium visibility in search results!"
    
    lang_count = len(languages_list)
    if update.message:
        responder = update.message
    elif update.callback_query and update.callback_query.message:
        responder = update.callback_query.message
    else:
        responder = None

    final_text = (
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
        "• Use 💰 Top up Balance to activate your listing"
    )

    if auto_submitted_for_review:
        final_text += "\n\n✅ Your verification request has been submitted to admin."

    if responder:
        await responder.reply_text(
            final_text,
            parse_mode="Markdown",
            reply_markup=get_persistent_main_menu()
        )
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text=final_text,
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
        format_profile_step(
            10,
            "Set Your Rates",
            f"✅ {len(photos)} photos saved.\n\nNow let us set your rates.",
        ),
        parse_mode="Markdown",
    )
    
    return await ask_rates(update, context)

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
    
    is_incomplete = not is_profile_complete(provider)
    
    if is_incomplete:
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
    
    if text.lower() == "cancel" or text.lower() == "skip":
        context.user_data.pop("editing", None)
        provider = db.get_provider(user.id)
        await update.message.reply_text(
            format_full_profile_text(provider),
            reply_markup=get_full_profile_keyboard(provider),
            parse_mode="Markdown"
        )
        return
    
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


def get_profile_states() -> dict:
    """Returns the profile conversation states dict. Called at registration time, not import time."""
    return {
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

def register_handlers(application):
    """Registers profile-related handlers."""
    profile_states = get_profile_states()
    application.add_handler(CommandHandler("myprofile", myprofile))
    
    profile_handler = ConversationHandler(
        entry_points=[
            CommandHandler("complete_profile", complete_profile),
            CallbackQueryHandler(complete_profile_from_button, pattern="^menu_complete_profile$")
        ],
        states=profile_states,
        fallbacks=[CommandHandler("cancel", edit_cancel_callback)]
    )
    application.add_handler(profile_handler)
    
    application.add_handler(CallbackQueryHandler(
        edit_section_callback,
        pattern="^edit_(basic|stats|bio|services|rates|location)$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        edit_cancel_callback,
        pattern="^edit_cancel$"
    ))
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_edit_input
    ), group=0)

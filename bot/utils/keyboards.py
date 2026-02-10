"""
Blackbook Bot Keyboards
All InlineKeyboardMarkup and ReplyKeyboardMarkup builders.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import (
    CITIES, PACKAGES, TIERS, SESSION_DURATIONS, BUILDS, AVAILABILITIES,
    SERVICES, LANGUAGES, NAIROBI_NEIGHBORHOODS, ELDORET_NEIGHBORHOODS,
    BOOST_PRICE, BOOST_DURATION_HOURS, PREMIUM_VERIFY_PRICE,
)


# ==================== PERSISTENT MAIN MENU ====================

def get_persistent_main_menu() -> ReplyKeyboardMarkup:
    """Returns the persistent bottom menu (always visible)."""
    keyboard = [
        [KeyboardButton("👑 The Collection")],
        [KeyboardButton("👤 My Profile"), KeyboardButton("💰 Top up Balance")],
        [KeyboardButton("🛡️ Safety Suite"), KeyboardButton("🤝 Affiliate Program")],
        [KeyboardButton("📞 Support"), KeyboardButton("📋 Rules")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


# ==================== MAIN MENU ====================

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Returns the main menu keyboard for existing users."""
    keyboard = [
        [
            InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"),
            InlineKeyboardButton("💰 Go Live", callback_data="menu_topup"),
        ],
        [
            InlineKeyboardButton("🟢 Toggle Status", callback_data="menu_status"),
            InlineKeyboardButton("🛡️ Safety Suite", callback_data="menu_safety"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_button(callback_data: str = "menu_main") -> InlineKeyboardMarkup:
    """Returns a simple back button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Menu", callback_data=callback_data)]
    ])


def get_skip_cancel_keyboard(skip_to: str = None) -> InlineKeyboardMarkup:
    """Returns skip and cancel buttons for edit prompts."""
    buttons = []
    if skip_to:
        buttons.append([InlineKeyboardButton("⏭️ Skip", callback_data=skip_to)])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="menu_profile")])
    return InlineKeyboardMarkup(buttons)


# ==================== REGISTRATION ====================

def get_city_keyboard() -> InlineKeyboardMarkup:
    """Returns city selection keyboard."""
    keyboard = []
    for item in CITIES:
        if len(item) == 3:
            city, emoji, is_available = item
            if is_available:
                text = f"{emoji} {city}"
            else:
                text = f"{emoji} {city} (Coming Soon)"
        else:
            # Backwards compatibility
            city, emoji = item
            text = f"{emoji} {city}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"city_{city}")])
    return InlineKeyboardMarkup(keyboard)


# ==================== PROFILE ====================

def get_full_profile_keyboard(provider: dict) -> InlineKeyboardMarkup:
    """Returns profile keyboard with section edit buttons."""
    buttons = []
    
    # Online toggle (only if active)
    if provider.get("is_active"):
        is_online = provider.get("is_online", False)
        toggle_text = "🟢 Online" if is_online else "⚫ Offline"
        buttons.append([InlineKeyboardButton(f"{toggle_text} (tap to toggle)", callback_data="toggle_online")])
    
    # Edit sections row 1
    buttons.append([
        InlineKeyboardButton("📝 Basic Info", callback_data="edit_basic"),
        InlineKeyboardButton("📏 Stats", callback_data="edit_stats"),
    ])
    
    # Edit sections row 2
    buttons.append([
        InlineKeyboardButton("💬 Bio", callback_data="edit_bio"),
        InlineKeyboardButton("✨ Services", callback_data="edit_services"),
    ])
    
    # Edit sections row 3
    buttons.append([
        InlineKeyboardButton("💰 Rates", callback_data="edit_rates"),
        InlineKeyboardButton("📸 Photos", callback_data="photos_manage"),
    ])
    
    # Verification (if not verified)
    if not provider.get("is_verified"):
        buttons.append([InlineKeyboardButton("✅ Get Verified", callback_data="menu_verify_start")])
    
    # Go live (if not active)
    if not provider.get("is_active"):
        buttons.append([InlineKeyboardButton("💳 Go Live Now", callback_data="menu_topup")])
    
    return InlineKeyboardMarkup(buttons)


def get_profile_keyboard(provider: dict) -> InlineKeyboardMarkup:
    """Returns profile action buttons based on provider state (legacy)."""
    buttons = []
    
    # Check if profile is incomplete
    profile_fields = ['age', 'height_cm', 'weight_kg', 'build', 'services', 'bio', 'nearby_places', 'profile_photos']
    is_incomplete = any(not provider.get(field) for field in profile_fields)
    
    if is_incomplete:
        buttons.append([InlineKeyboardButton("✏️ Complete Profile", callback_data="menu_complete_profile")])
    else:
        buttons.append([InlineKeyboardButton("✏️ Edit Profile", callback_data="menu_complete_profile")])
    
    if not provider.get("is_verified"):
        buttons.append([InlineKeyboardButton("📸 Get Verified", callback_data="menu_verify_start")])
    if not provider.get("is_active"):
        buttons.append([InlineKeyboardButton("💰 Go Live Now", callback_data="menu_topup")])
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")])
    return InlineKeyboardMarkup(buttons)


# ==================== PAYMENT ====================

def get_package_keyboard() -> InlineKeyboardMarkup:
    """Returns tier package selection keyboard."""
    keyboard = []
    for days in sorted(PACKAGES.keys()):
        tier = TIERS.get(days, {})
        emoji = tier.get("emoji", "📦")
        name = tier.get("name", f"{days}d")
        price = PACKAGES[days]
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {name} — {days} Days — {price:,} KES",
            callback_data=f"topup_{days}"
        )])
    return InlineKeyboardMarkup(keyboard)


def get_menu_package_keyboard() -> InlineKeyboardMarkup:
    """Returns tier package selection keyboard (menu version with extras)."""
    keyboard = []
    for days in sorted(PACKAGES.keys()):
        tier = TIERS.get(days, {})
        emoji = tier.get("emoji", "📦")
        name = tier.get("name", f"{days}d")
        price = PACKAGES[days]
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {name} — {days} Days — {price:,} KES",
            callback_data=f"menu_pay_{days}"
        )])
    # Boost option
    keyboard.append([InlineKeyboardButton(
        f"🚀 Boost Profile ({BOOST_DURATION_HOURS}h) — {BOOST_PRICE} KES",
        callback_data="menu_boost"
    )])
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)


def get_boost_keyboard() -> InlineKeyboardMarkup:
    """Returns boost confirmation keyboard."""
    keyboard = [
        [InlineKeyboardButton(
            f"🚀 Boost Now — {BOOST_PRICE} KES",
            callback_data="menu_boost_confirm"
        )],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_topup")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_referral_keyboard(referral_code: str) -> InlineKeyboardMarkup:
    """Returns referral/affiliate info keyboard."""
    keyboard = [
        [InlineKeyboardButton("📊 My Referral Stats", callback_data="menu_referral_stats")],
        [InlineKeyboardButton("📋 Copy My Link", callback_data="menu_referral_copy")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_phone_confirm_keyboard(saved_phone: str) -> InlineKeyboardMarkup:
    """Returns phone confirmation keyboard."""
    keyboard = [
        [InlineKeyboardButton(f"✅ Use {saved_phone}", callback_data="menu_pay_confirm")],
        [InlineKeyboardButton("📱 New Number", callback_data="menu_pay_newphone")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_topup")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_topup_phone_confirm_keyboard(saved_phone: str) -> InlineKeyboardMarkup:
    """Returns phone confirmation keyboard for /topup command."""
    keyboard = [
        [InlineKeyboardButton(f"✅ Use {saved_phone}", callback_data="topup_use_saved")],
        [InlineKeyboardButton("📱 Enter New Number", callback_data="topup_new_phone")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_payment_failed_keyboard() -> InlineKeyboardMarkup:
    """Returns keyboard for failed payment."""
    keyboard = [
        [InlineKeyboardButton("🔄 Try Again", callback_data="menu_topup")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== SAFETY ====================

def get_safety_menu_keyboard() -> InlineKeyboardMarkup:
    """Returns the safety suite menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("📞 Check Number", callback_data="menu_safety_check")],
        [InlineKeyboardButton("⏱️ Start Session", callback_data="menu_safety_session")],
        [InlineKeyboardButton("🚫 Report Client", callback_data="menu_safety_report")],
        [InlineKeyboardButton("✅ Check In", callback_data="menu_safety_checkin")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_session_duration_keyboard() -> InlineKeyboardMarkup:
    """Returns session duration selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("30 min", callback_data="menu_session_30"),
            InlineKeyboardButton("60 min", callback_data="menu_session_60"),
        ],
        [
            InlineKeyboardButton("90 min", callback_data="menu_session_90"),
            InlineKeyboardButton("120 min", callback_data="menu_session_120"),
        ],
        [InlineKeyboardButton("🔙 Back to Safety", callback_data="menu_safety")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_session_active_keyboard() -> InlineKeyboardMarkup:
    """Returns keyboard for active session."""
    keyboard = [
        [InlineKeyboardButton("✅ Check In Now", callback_data="menu_safety_checkin")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== VERIFICATION ====================

def get_verification_start_keyboard() -> InlineKeyboardMarkup:
    """Returns verification prompt keyboard."""
    keyboard = [
        [InlineKeyboardButton("📸 Start Verification", callback_data="menu_verify_go")],
        [InlineKeyboardButton("🔙 Back to Profile", callback_data="menu_profile")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_verification_keyboard(provider_id: int) -> InlineKeyboardMarkup:
    """Returns admin verification approval keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"verify_approve_{provider_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"verify_reject_{provider_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== STATUS ====================

def get_status_toggle_keyboard() -> InlineKeyboardMarkup:
    """Returns status toggle keyboard."""
    keyboard = [
        [InlineKeyboardButton("🔄 Toggle Again", callback_data="menu_status")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_inactive_status_keyboard() -> InlineKeyboardMarkup:
    """Returns keyboard for users without active subscription."""
    keyboard = [
        [InlineKeyboardButton("💰 Go Live", callback_data="menu_topup")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== PROFILE COMPLETION ====================

def get_build_keyboard() -> InlineKeyboardMarkup:
    """Returns build selection keyboard."""
    keyboard = [
        [InlineKeyboardButton(build, callback_data=f"build_{build}")]
        for build in BUILDS
    ]
    return InlineKeyboardMarkup(keyboard)


def get_availability_keyboard() -> InlineKeyboardMarkup:
    """Returns availability selection keyboard."""
    keyboard = [
        [InlineKeyboardButton(avail, callback_data=f"avail_{avail}")]
        for avail in AVAILABILITIES
    ]
    return InlineKeyboardMarkup(keyboard)


def get_services_keyboard(selected_services=None) -> InlineKeyboardMarkup:
    """Returns multi-select services keyboard."""
    if selected_services is None:
        selected_services = []
        
    keyboard = []
    row = []
    for service in SERVICES:
        # Show checkmark if selected
        text = f"✅ {service}" if service in selected_services else service
        # Toggle logic in callback data
        callback = f"service_{service}"
        row.append(InlineKeyboardButton(text, callback_data=callback))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
        
    # Add Done button
    keyboard.append([InlineKeyboardButton("✅ Done / Continue", callback_data="service_done")])
    
    return InlineKeyboardMarkup(keyboard)


def get_languages_keyboard(selected_languages=None) -> InlineKeyboardMarkup:
    """Returns multi-select languages keyboard."""
    if selected_languages is None:
        selected_languages = []
        
    keyboard = []
    row = []
    for language in LANGUAGES:
        # Show checkmark if selected
        text = f"✅ {language}" if language in selected_languages else language
        # Toggle logic in callback data
        # Use language without emoji for callback
        lang_code = language.split()[0]  # Get "English" from "English 🇬🇧"
        callback = f"lang_{lang_code}"
        row.append(InlineKeyboardButton(text, callback_data=callback))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
        
    # Add Done button
    keyboard.append([InlineKeyboardButton("✅ Done / Continue", callback_data="lang_done")])
    
    return InlineKeyboardMarkup(keyboard)


# ==================== NEIGHBORHOOD SELECTION ====================

def get_neighborhood_keyboard(city: str, page: int = 0) -> InlineKeyboardMarkup:
    """Returns paginated neighborhood keyboard for a city."""
    neighborhoods = []
    if city == "Nairobi":
        neighborhoods = NAIROBI_NEIGHBORHOODS
    elif city == "Eldoret":
        neighborhoods = ELDORET_NEIGHBORHOODS
    else:
        # Fallback - allow freeform text input
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Type my neighborhood", callback_data="hood_custom")]
        ])
    
    # Pagination: 15 items per page (5 rows of 3)
    items_per_page = 15
    total_pages = (len(neighborhoods) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(neighborhoods))
    page_items = neighborhoods[start_idx:end_idx]
    
    keyboard = []
    row = []
    for hood in page_items:
        row.append(InlineKeyboardButton(hood, callback_data=f"hood_{hood}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # Navigation buttons
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data=f"hood_page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️ More", callback_data=f"hood_page_{page + 1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Custom option
    keyboard.append([InlineKeyboardButton("📝 Other (type it)", callback_data="hood_custom")])
    
    return InlineKeyboardMarkup(keyboard)


# ==================== PHOTO MANAGEMENT ====================

def get_photo_management_keyboard(photo_count: int) -> InlineKeyboardMarkup:
    """Returns photo management keyboard."""
    keyboard = []
    
    if photo_count > 0:
        keyboard.append([InlineKeyboardButton(f"📸 View Photos ({photo_count})", callback_data="photos_view")])
        keyboard.append([InlineKeyboardButton("🗑️ Delete Photo", callback_data="photos_delete")])
        if photo_count > 1:
            keyboard.append([InlineKeyboardButton("🔄 Reorder Photos", callback_data="photos_reorder")])
    
    keyboard.append([InlineKeyboardButton("➕ Add More Photos", callback_data="photos_add")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")])
    
    return InlineKeyboardMarkup(keyboard)


def get_photo_delete_keyboard(photos: list) -> InlineKeyboardMarkup:
    """Returns keyboard to select which photo to delete."""
    keyboard = []
    for i, _ in enumerate(photos):
        keyboard.append([InlineKeyboardButton(f"🗑️ Delete Photo #{i + 1}", callback_data=f"photo_del_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="photos_manage")])
    return InlineKeyboardMarkup(keyboard)


def get_photo_reorder_keyboard(photos: list) -> InlineKeyboardMarkup:
    """Returns keyboard to reorder photos (move to first position)."""
    keyboard = []
    for i, _ in enumerate(photos):
        if i > 0:  # Can't move first photo to first position
            keyboard.append([InlineKeyboardButton(f"⬆️ Move Photo #{i + 1} to First", callback_data=f"photo_first_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="photos_manage")])
    return InlineKeyboardMarkup(keyboard)


def get_photo_viewer_keyboard(current_idx: int, total: int) -> InlineKeyboardMarkup:
    """Returns photo viewer keyboard with navigation and delete."""
    keyboard = []
    
    # Navigation row
    nav_row = []
    if current_idx > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"photo_view_{current_idx - 1}"))
    nav_row.append(InlineKeyboardButton(f"{current_idx + 1}/{total}", callback_data="noop"))
    if current_idx < total - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"photo_view_{current_idx + 1}"))
    keyboard.append(nav_row)
    
    # Delete and set as primary row
    action_row = []
    action_row.append(InlineKeyboardButton("🗑️ Delete This", callback_data=f"photo_del_{current_idx}"))
    if current_idx > 0:
        action_row.append(InlineKeyboardButton("⭐ Set Primary", callback_data=f"photo_first_{current_idx}"))
    keyboard.append(action_row)
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Gallery", callback_data="photos_manage")])
    
    return InlineKeyboardMarkup(keyboard)


# ==================== ONLINE STATUS ====================

def get_online_toggle_keyboard(is_online: bool) -> InlineKeyboardMarkup:
    """Returns online status toggle keyboard with current status."""
    status_text = "🟢 ONLINE" if is_online else "⚫ OFFLINE"
    toggle_text = "Go Offline 🔴" if is_online else "Go Online 🟢"
    
    keyboard = [
        [InlineKeyboardButton(f"Current: {status_text}", callback_data="noop")],
        [InlineKeyboardButton(toggle_text, callback_data="toggle_online")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


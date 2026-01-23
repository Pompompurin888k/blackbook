"""
Blackbook Bot Keyboards
All InlineKeyboardMarkup and ReplyKeyboardMarkup builders.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import CITIES, PACKAGES, SESSION_DURATIONS, BUILDS, AVAILABILITIES, SERVICES


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


# ==================== REGISTRATION ====================

def get_city_keyboard() -> InlineKeyboardMarkup:
    """Returns city selection keyboard."""
    keyboard = [
        [InlineKeyboardButton(f"{emoji} {city}", callback_data=f"city_{city}")]
        for city, emoji in CITIES
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== PROFILE ====================

def get_profile_keyboard(provider: dict) -> InlineKeyboardMarkup:
    """Returns profile action buttons based on provider state."""
    buttons = []
    if not provider.get("is_verified"):
        buttons.append([InlineKeyboardButton("📸 Get Verified", callback_data="menu_verify_start")])
    if not provider.get("is_active"):
        buttons.append([InlineKeyboardButton("💰 Go Live Now", callback_data="menu_topup")])
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")])
    return InlineKeyboardMarkup(buttons)


# ==================== PAYMENT ====================

def get_package_keyboard() -> InlineKeyboardMarkup:
    """Returns package selection keyboard."""
    keyboard = [
        [InlineKeyboardButton("🧪 1 Day TEST - 1 KES", callback_data="topup_1")],
        [InlineKeyboardButton("⏰ 3 Days - 400 KES", callback_data="topup_3")],
        [InlineKeyboardButton("🔥 7 Days - 800 KES", callback_data="topup_7")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_menu_package_keyboard() -> InlineKeyboardMarkup:
    """Returns package selection keyboard (menu version with back button)."""
    keyboard = [
        [InlineKeyboardButton("⏰ 3 Days — 400 KES", callback_data="menu_pay_3")],
        [InlineKeyboardButton("🔥 7 Days — 800 KES", callback_data="menu_pay_7")],
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

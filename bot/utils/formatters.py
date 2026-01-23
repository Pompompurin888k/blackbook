"""
Blackbook Bot Text Formatters
Utility functions for formatting messages and text styling.
"""
import random
import string


def generate_verification_code() -> str:
    """Generates a random 6-character verification code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def format_status_badge(is_online: bool, is_active: bool, is_verified: bool) -> dict:
    """Returns formatted status badges."""
    return {
        "status": "🟢 Active" if is_active else "⚫ Inactive",
        "online": "🟢 Live" if is_online else "⚫ Offline",
        "verified": "✔️ Verified" if is_verified else "❌ Unverified",
    }


def format_expiry_date(expiry_date) -> str:
    """Formats the expiry date for display."""
    if expiry_date:
        return expiry_date.strftime("%Y-%m-%d %H:%M")
    return "No active subscription"


def format_profile_text(provider: dict) -> str:
    """Formats the full profile text for display."""
    name = provider.get("display_name", "Unknown")
    city = provider.get("city", "Not set")
    neighborhood = provider.get("neighborhood", "Not set")
    
    badges = format_status_badge(
        provider.get("is_online", False),
        provider.get("is_active", False),
        provider.get("is_verified", False)
    )
    
    expiry_text = format_expiry_date(provider.get("expiry_date"))
    
    return (
        f"👤 *YOUR PROFILE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎭 *Stage Name:* {name}\n"
        f"📍 *Location:* {neighborhood}, {city}\n\n"
        f"🛡️ *Trust Level:* {badges['verified']}\n"
        f"📱 *Listing Status:* {badges['status']}\n"
        f"🌐 *Website Badge:* {badges['online']}\n\n"
        f"⏱️ *Expires:* {expiry_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_welcome_message() -> str:
    """Returns the full welcome message for new users."""
    return (
        "🎩 *BLACKBOOK: Private Concierge Network*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Welcome to the inner circle. This bot is your command center for managing "
        "your professional presence, safety, and earnings on the Blackbook directory.\n\n"
        "📜 *How to get started:*\n"
        "1️⃣ *Register* — Setup your stage name and location.\n"
        "2️⃣ *Verify* — Complete our anti-catfish protocol to get your Blue Tick ✔️.\n"
        "3️⃣ *Topup* — Activate your listing to appear on the \"Dark Room\" directory.\n\n"
        "🛠 *Your Command Reference:*\n\n"
        "👤 *IDENTITY*\n"
        "/register — Create or edit your profile.\n"
        "/verify — Submit proof of identity (Required for listing).\n"
        "/myprofile — View your status, rating, and expiry.\n\n"
        "💰 *VISIBILITY*\n"
        "/topup — Purchase listing credits (3 or 7 days).\n"
        "/status — Toggle your 'Live Now' 🟢 badge on the website.\n\n"
        "🛡 *SAFETY SUITE*\n"
        "/check <number> — Search the national blacklist.\n"
        "/report <number> <reason> — Flag a dangerous client.\n"
        "/session <mins> — Start a safety timer before a meeting.\n"
        "/checkin — Confirm you are safe after a session.\n\n"
        "🚫 Use /cancel at any time to stop a current process.\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Blackbook: Privacy is Power._"
    )


def format_returning_user_message(provider: dict) -> str:
    """Formats the welcome back message for returning users."""
    badges = format_status_badge(
        provider.get("is_online", False),
        provider.get("is_active", False),
        provider.get("is_verified", False)
    )
    
    expiry = provider.get("expiry_date")
    time_left = expiry.strftime('%Y-%m-%d') if expiry else "No active subscription"
    
    return (
        f"Welcome back, *{provider.get('display_name', 'Unknown')}*.\n\n"
        f"📱 *Current Status:* {badges['status']}\n"
        f"🛡️ *Trust Level:* {badges['verified']}\n"
        f"⏱️ *Expires:* {time_left}\n\n"
        "Use the menu below or type a command:"
    )


def format_main_menu_header(provider: dict) -> str:
    """Formats the main menu header."""
    badges = format_status_badge(
        provider.get("is_online", False),
        provider.get("is_active", False),
        provider.get("is_verified", False)
    )
    
    expiry = provider.get("expiry_date")
    time_left = expiry.strftime('%Y-%m-%d') if expiry else "No subscription"
    
    return (
        "🎩 *BLACKBOOK COMMAND CENTER*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 *Status:* {badges['status']}\n"
        f"🛡️ *Trust:* {badges['verified']}\n"
        f"⏱️ *Expires:* {time_left}\n\n"
        "Select an option below:"
    )

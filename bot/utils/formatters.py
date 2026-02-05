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
    
    # Format rates if available
    rates_section = ""
    if provider.get("rate_1hr"):
        rates_lines = []
        if provider.get('rate_30min'):
            rates_lines.append(f"   30 min: {provider.get('rate_30min'):,} KES")
        if provider.get('rate_1hr'):
            rates_lines.append(f"   1 hour: {provider.get('rate_1hr'):,} KES")
        if provider.get('rate_2hr'):
            rates_lines.append(f"   2 hours: {provider.get('rate_2hr'):,} KES")
        if provider.get('rate_3hr'):
            rates_lines.append(f"   3 hours: {provider.get('rate_3hr'):,} KES")
        if provider.get('rate_overnight'):
            rates_lines.append(f"   Overnight: {provider.get('rate_overnight'):,} KES")
        
        if rates_lines:
            rates_section = "\n💰 *Hourly Rates:*\n" + "\n".join(rates_lines)
    
    # Format languages if available
    languages_section = ""
    if provider.get("languages"):
        import json
        try:
            languages = json.loads(provider.get("languages"))
            if languages:
                languages_section = f"\n🌍 *Languages:* {', '.join(languages)}"
        except:
            pass
    
    return (
        f"👤 *YOUR PROFILE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎭 *Stage Name:* {name}\n"
        f"📍 *Location:* {neighborhood}, {city}\n\n"
        f"🛡️ *Trust Level:* {badges['verified']}\n"
        f"📱 *Listing Status:* {badges['status']}\n"
        f"🌐 *Website Badge:* {badges['online']}\n"
        f"{rates_section}"
        f"{languages_section}\n"
        f"⏱️ *Expires:* {expiry_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_welcome_message() -> str:
    """Returns the full welcome message for new users."""
    return (
        "� *WELCOME TO BLACKBOOK*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Your exclusive command center for managing your premium presence on Kenya's most discreet directory.\n\n"
        "📜 *Quick Start Guide:*\n\n"
        "1️⃣ */register* — Create your professional profile\n"
        "2️⃣ */complete_profile* — Add photos & details\n"
        "3️⃣ */verify* — Get verified (required)\n"
        "4️⃣ */topup* — Go live on innbucks.org\n\n"
        "💎 *Why Blackbook?*\n"
        "• Verified profiles only\n"
        "• Premium clientele\n"
        "• Built-in safety tools\n"
        "• Professional discretion\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Use the menu below to navigate_"
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
        f"👋 Welcome back, *{provider.get('display_name', 'Unknown')}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Status Overview:*\n\n"
        f"📱 Listing: {badges['status']}\n"
        f"🛡️ Trust: {badges['verified']}\n"
        f"⏱️ Expires: {time_left}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Use the menu below to manage your profile_"
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

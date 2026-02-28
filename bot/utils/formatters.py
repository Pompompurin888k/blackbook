"""
Blackbook Bot Text Formatters
Utility functions for formatting messages and text styling.
"""
import ast
import json
import random
import string


def generate_verification_code() -> str:
    """Generates a random 6-character verification code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# Tier display mapping
TIER_BADGES = {
    "trial": "🎁 Trial",
    "platinum": "💎 Platinum",
    "gold": "🥇 Gold",
    "silver": "🥈 Silver",
    "bronze": "🥉 Bronze",
    "none": "—",
}


def format_tier_badge(tier: str) -> str:
    """Returns the formatted tier badge string."""
    return TIER_BADGES.get(tier, "—")


def format_status_badge(is_online: bool, is_active: bool, is_verified: bool, tier: str = "none") -> dict:
    """Returns formatted status badges."""
    return {
        "status": "🟢 Active" if is_active else "⚫ Inactive",
        "online": "🟢 Live" if is_online else "⚫ Offline",
        "verified": "✔️ Verified" if is_verified else "❌ Unverified",
        "tier": format_tier_badge(tier),
    }


def format_expiry_date(expiry_date) -> str:
    """Formats the expiry date for display."""
    if expiry_date:
        return expiry_date.strftime("%Y-%m-%d %H:%M")
    return "No active subscription"


def _clean_item(value: str) -> str:
    """Cleans list-like text values for pretty display."""
    cleaned = str(value).strip().strip("\"'").strip()
    return " ".join(cleaned.split())


def _parse_list_field(value) -> list[str]:
    """Parses list-like DB fields that may be list/json/csv/python-list strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in (_clean_item(v) for v in value) if item]

    raw = str(value).strip()
    if not raw:
        return []

    # JSON list string
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [item for item in (_clean_item(v) for v in parsed) if item]
        except Exception:
            pass
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple)):
                return [item for item in (_clean_item(v) for v in parsed) if item]
        except Exception:
            pass

    # Comma-separated fallback
    if "," in raw:
        return [item for item in (_clean_item(v) for v in raw.split(",")) if item]

    item = _clean_item(raw)
    return [item] if item else []


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
    languages = _parse_list_field(provider.get("languages"))
    if languages:
        languages_section = f"\n🌍 *Languages:* {', '.join(languages)}"
    
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
        "👑 *WELCOME TO ACE GIRLS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Your exclusive command center for managing your premium presence on Kenya's most discreet directory.\n\n"
        "📜 *Quick Start Guide:*\n\n"
        "1️⃣ */register* — Create your professional profile\n"
        "2️⃣ */complete_profile* — Add photos & details\n"
        "3️⃣ */verify* — Get verified (required)\n"
        "4️⃣ */topup* — Go live on innbucks.org\n\n"
        "💎 *Why Ace Girls?*\n"
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
        provider.get("is_verified", False),
        provider.get("subscription_tier", "none")
    )
    
    expiry = provider.get("expiry_date")
    time_left = expiry.strftime('%Y-%m-%d') if expiry else "No active subscription"
    
    tier_line = ""
    if badges['tier'] != '—':
        tier_line = f"👑 Tier: {badges['tier']}\n"
    
    return (
        f"👋 Welcome back, *{provider.get('display_name', 'Unknown')}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Status Overview:*\n\n"
        f"📱 Listing: {badges['status']}\n"
        f"{tier_line}"
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
        "🎩 *ACE GIRLS COMMAND CENTER*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 *Status:* {badges['status']}\n"
        f"🛡️ *Trust:* {badges['verified']}\n"
        f"⏱️ *Expires:* {time_left}\n\n"
        "Select an option below:"
    )


def format_full_profile_text(provider: dict) -> str:
    """Formats the complete profile with ALL data for the My Profile view."""
    name = provider.get("display_name", "Not set")
    city = provider.get("city", "Not set")
    neighborhood = provider.get("neighborhood", "Not set")
    
    badges = format_status_badge(
        provider.get("is_online", False),
        provider.get("is_active", False),
        provider.get("is_verified", False)
    )
    
    expiry_text = format_expiry_date(provider.get("expiry_date"))
    
    # Basic stats
    age = provider.get("age", "—")
    height = provider.get("height_cm", "—")
    weight = provider.get("weight_kg", "—")
    build = provider.get("build", "—")
    
    # Bio
    bio = provider.get("bio", "Not set")
    if bio and len(bio) > 100:
        bio = bio[:97] + "..."
    
    # Nearby places
    nearby = provider.get("nearby_places", "Not set")
    if nearby and len(nearby) > 50:
        nearby = nearby[:47] + "..."
    
    # Services
    services = _parse_list_field(provider.get("services"))
    services_text = " • ".join(services[:6]) if services else "Not set"
    
    # Photos count
    photos = provider.get("profile_photos") or []
    if isinstance(photos, str):
        try:
            photos = json.loads(photos)
        except:
            photos = []
    photo_count = len(photos)
    
    # Rates
    rates_lines = []
    if provider.get('rate_30min'):
        rates_lines.append(f"• 30 min — {provider.get('rate_30min'):,}")
    if provider.get('rate_1hr'):
        rates_lines.append(f"• 1 hour — {provider.get('rate_1hr'):,}")
    if provider.get('rate_2hr'):
        rates_lines.append(f"• 2 hours — {provider.get('rate_2hr'):,}")
    if provider.get('rate_3hr'):
        rates_lines.append(f"• 3 hours — {provider.get('rate_3hr'):,}")
    if provider.get('rate_overnight'):
        rates_lines.append(f"• Overnight — {provider.get('rate_overnight'):,}")
    rates_text = "\n".join(rates_lines) if rates_lines else "• Not set"
    
    # Languages
    languages = _parse_list_field(provider.get("languages"))
    languages_text = " • ".join(languages[:6]) if languages else "Not set"

    # Display helpers
    location_line = f"{neighborhood}, {city}" if neighborhood != "Not set" else city
    listing_line = "Live on directory" if provider.get("is_active") else "Profile saved, not live"
    
    return (
        f"💎 *{name}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📍 *Location:* {location_line}\n"
        f"🟢 *Status:* {badges['online']} • {badges['verified']}\n\n"
        "📌 *About*\n"
        f"• Age: {age} yrs\n"
        f"• Height: {height} cm\n"
        f"• Weight: {weight} kg\n"
        f"• Build: {build}\n"
        f"• Nearby: {nearby}\n\n"
        "📝 *Bio*\n"
        f"{bio}\n\n"
        "✨ *Services*\n"
        f"{services_text}\n\n"
        "💰 *Rates (KES)*\n"
        f"{rates_text}\n\n"
        f"🌍 *Languages:* {languages_text}\n"
        f"📸 *Gallery:* {photo_count} photo(s)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ *Subscription:* {expiry_text}\n"
        f"👑 *Tier:* {format_tier_badge(provider.get('subscription_tier', 'none'))}\n"
        f"🚀 *Visibility:* {listing_line}"
    )


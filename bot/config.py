"""
Blackbook Bot Configuration
Centralized environment variables, constants, and conversation states.
"""
import os

# ==================== TELEGRAM CONFIG ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
PARTNER_TELEGRAM_ID = os.getenv("PARTNER_TELEGRAM_ID")

# ==================== DATABASE CONFIG ====================
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "blackbook_db")
DB_USER = os.getenv("DB_USER", "bb_operator")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")

# ==================== MEGAPAY CONFIG ====================
MEGAPAY_API_KEY = os.getenv("MEGAPAY_API_KEY", "YOUR_API_KEY_HERE")
MEGAPAY_EMAIL = os.getenv("MEGAPAY_EMAIL", "your_email@example.com")
MEGAPAY_CALLBACK_URL = os.getenv("MEGAPAY_CALLBACK_URL", "https://yourdomain.com/payments/callback")
MEGAPAY_STK_ENDPOINT = os.getenv("MEGAPAY_STK_ENDPOINT", "https://megapay.co.ke/backend/v1/initiatestk")

# ==================== CONVERSATION STATES ====================
# Registration flow
STAGE_NAME, CITY, NEIGHBORHOOD = range(3)

# Verification flow
# Profile Completion flow
PROFILE_AGE, PROFILE_HEIGHT, PROFILE_WEIGHT, PROFILE_BUILD, PROFILE_AVAILABILITY, PROFILE_SERVICES, PROFILE_BIO, PROFILE_NEARBY = range(30, 38)

# ==================== STATIC DATA ====================
CITIES = [
    ("Nairobi", "🏙️"),
    ("Eldoret", "🌆"),
    ("Mombasa", "🏖️"),
]

# Profile Options
BUILDS = ["Slim", "Athletic", "Curvy", "BBW", "Petite"]
AVAILABILITIES = ["Incall", "Outcall", "Both"]
SERVICES = [
    "GFE", "Massage", "Dinner Date", "Travel", 
    "Parties", "Overnight", "Couples", "Fetish"
]

# Package pricing (days: KES)
PACKAGES = {
    1: 1,     # 1 day = 1 KES (TEST ONLY)
    3: 400,   # 3 days = 400 KES
    7: 800,   # 7 days = 800 KES
}

# Session durations (minutes)
SESSION_DURATIONS = [30, 60, 90, 120]

# ==================== GLOBAL STATE ====================
# Note: For production, consider using Redis or database for this
MAINTENANCE_MODE = False


def is_admin(user_id: int) -> bool:
    """Checks if a user is the admin."""
    return ADMIN_CHAT_ID and user_id == int(ADMIN_CHAT_ID)


def is_authorized_partner(user_id: int) -> bool:
    """Checks if a user is authorized to access the partner dashboard."""
    authorized_ids = []
    if ADMIN_CHAT_ID:
        authorized_ids.append(int(ADMIN_CHAT_ID))
    if PARTNER_TELEGRAM_ID:
        authorized_ids.append(int(PARTNER_TELEGRAM_ID))
    return user_id in authorized_ids


def get_package_price(days: int) -> int:
    """Gets the price for a package."""
    return PACKAGES.get(days, 0)

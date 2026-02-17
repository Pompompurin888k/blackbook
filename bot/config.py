"""
Blackbook Bot Configuration
Centralized environment variables, constants, and conversation states.
"""
import os

# ==================== TELEGRAM CONFIG ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", TELEGRAM_TOKEN)
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

# Payment/Topup flow
TOPUP_PHONE, TOPUP_CONFIRM = range(20, 22)

# Verification flow
AWAITING_PHOTO = 10

# Profile Completion flow
PROFILE_AGE, PROFILE_HEIGHT, PROFILE_WEIGHT, PROFILE_BUILD, PROFILE_AVAILABILITY, PROFILE_SERVICES, PROFILE_BIO, PROFILE_NEARBY, PROFILE_PHOTOS, PROFILE_RATES, PROFILE_LANGUAGES = range(30, 41)

# ==================== STATIC DATA ====================
CITIES = [
    ("Nairobi", "🏙️", True),
    ("Eldoret", "🌆", True),
    ("Mombasa", "🏖️", False),
    ("Kisumu", "🌊", False),
    ("Nakuru", "🦩", False),
]
# Format: (city_name, emoji, is_available)

# Neighborhoods per city for inline keyboard selection
NAIROBI_NEIGHBORHOODS = [
    "Allsops", "Athi River", "Banana", "Buru Buru", "Chokaa", "Dagoretti",
    "Dandora", "Donholm", "Eastlands", "Eastleigh", "Embakasi", "Garden City",
    "Githurai 44", "Githurai 45", "Homeland", "Hurlingham", "Huruma", "Imara Daima",
    "Jamhuri", "Joska", "Juja", "Kabete", "Kahawa Sukari", "Kahawa Wendani",
    "Kahawa West", "Kamulu", "Kangemi", "Karen", "Kariobangi", "Kasarani",
    "Kawangware", "Kayole", "Kenyatta Road", "Kibera", "Kikuyu", "Kileleshwa",
    "Kilimani", "Kitengela", "Kitisuru", "Komarock", "Langata", "Lavington",
    "Loresho", "Madaraka", "Makadara", "Malaa", "Mathare", "Milimani",
    "Mlolongo", "Muthaiga", "Muthangari", "Muthurwa", "Mwiki", "Nairobi Town",
    "Nairobi West", "Ndenderu", "Ngara", "Ngong", "Ngumba", "Njiru",
    "Ongata Rongai", "Pangani", "Parklands", "Roasters", "Roysambu", "Ruai",
    "Ruaka", "Ruaraka", "Ruiru", "Runda", "Saika", "South B", "South C",
    "Syokimau", "Thika", "Thogoto", "Thome", "Umoja", "Upper Hill",
    "Utawala", "Uthiru", "Westlands"
]

ELDORET_NEIGHBORHOODS = ["Town Centre", "Elgon View", "Langas", "Kapsoya"]

# Profile Options
BUILDS = ["Slim", "Athletic", "Curvy", "BBW", "Petite"]
AVAILABILITIES = ["Incall", "Outcall", "Both"]
SERVICES = [
    "GFE", "Massage", "Dinner Date", "Travel", 
    "Parties", "Overnight", "Couples", "Fetish"
]

# Rate durations (for pricing)
RATE_DURATIONS = [
    ("30min", "30 Minutes"),
    ("1hr", "1 Hour"),
    ("2hr", "2 Hours"),
    ("3hr", "3 Hours"),
    ("overnight", "Overnight (8+ hrs)")
]

# Languages
LANGUAGES = [
    "English 🇬🇧",
    "Swahili 🇰🇪",
    "French 🇫🇷",
    "Arabic 🇸🇦",
    "German 🇩🇪",
    "Italian 🇮🇹",
    "Spanish 🇪🇸",
    "Chinese 🇨🇳"
]

# Package pricing (days: KES)
PACKAGES = {
    3: 300,    # Bronze — 3 days = 300 KES
    7: 600,    # Silver — 7 days = 600 KES
    30: 1500,  # Gold   — 30 days = 1,500 KES
    90: 4000,  # Platinum — 90 days = 4,000 KES
}

# Tier names and perks
TIERS = {
    3:  {"name": "Bronze",   "emoji": "🥉", "perks": "Basic listing, text-only"},
    7:  {"name": "Silver",   "emoji": "🥈", "perks": "Photos, live badge, neighborhood SEO"},
    30: {"name": "Gold",     "emoji": "🥇", "perks": "Priority placement, Featured badge, recommendation boost"},
    90: {"name": "Platinum", "emoji": "💎", "perks": "Top of search, homepage spotlight, analytics"},
}

# Boost pricing
BOOST_PRICE = 100       # KES per boost
BOOST_DURATION_HOURS = 12  # Hours of boost visibility

# Free trial
FREE_TRIAL_DAYS = int(os.getenv("FREE_TRIAL_DAYS", "7"))
FREE_TRIAL_REMINDER_DAY2_HOURS = int(os.getenv("FREE_TRIAL_REMINDER_DAY2_HOURS", "120"))
FREE_TRIAL_REMINDER_DAY5_HOURS = int(os.getenv("FREE_TRIAL_REMINDER_DAY5_HOURS", "48"))
FREE_TRIAL_FINAL_REMINDER_HOURS = int(os.getenv("FREE_TRIAL_FINAL_REMINDER_HOURS", "24"))
TRIAL_WINBACK_AFTER_HOURS = int(os.getenv("TRIAL_WINBACK_AFTER_HOURS", "24"))

# Referral rewards
REFERRAL_REWARD_DAYS = 1      # Free days given to referrer per signup
REFERRAL_COMMISSION_PCT = 20  # % commission on referred user's first payment (as credit)

# Premium verification
PREMIUM_VERIFY_PRICE = 500  # KES one-time for premium verification badge

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

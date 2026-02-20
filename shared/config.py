"""
Shared Configuration for Blackbook
Contains environment variables, constants, and shared structures for both Web and Bot.
"""
import os

# ==================== TELEGRAM ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
PARTNER_TELEGRAM_ID = os.getenv("PARTNER_TELEGRAM_ID")

# ==================== DATABASE ====================
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "blackbook_db")
DB_USER = os.getenv("DB_USER", "bb_operator")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")
SUPPRESS_MIGRATIONS = os.getenv("SUPPRESS_MIGRATIONS", "false").lower() == "true"

# ==================== PUBLIC WEB ====================
PUBLIC_BASE_URL = os.getenv("PUBLIC_WEB_BASE_URL", "https://innbucks.org").rstrip("/")

# ==================== MEGAPAY ====================
MEGAPAY_API_KEY = os.getenv("MEGAPAY_API_KEY", "YOUR_API_KEY_HERE")
MEGAPAY_EMAIL = os.getenv("MEGAPAY_EMAIL", "your_email@example.com")
MEGAPAY_CALLBACK_URL = os.getenv("MEGAPAY_CALLBACK_URL", f"{PUBLIC_BASE_URL}/payments/callback")
MEGAPAY_STK_ENDPOINT = os.getenv("MEGAPAY_STK_ENDPOINT", "https://megapay.co.ke/backend/v1/initiatestk")
MEGAPAY_CALLBACK_SECRET = os.getenv("MEGAPAY_CALLBACK_SECRET")

# ==================== PAYMENTS & PACKAGES ====================
VALID_PACKAGE_DAYS = {0, 3, 7, 30, 90}
BOOST_DURATION_HOURS = int(os.getenv("BOOST_DURATION_HOURS", "12"))
BOOST_PRICE = int(os.getenv("BOOST_PRICE", "100"))

PACKAGE_PRICES = {
    3: int(os.getenv("PACKAGE_PRICE_3", "300")),
    7: int(os.getenv("PACKAGE_PRICE_7", "600")),
    30: int(os.getenv("PACKAGE_PRICE_30", "1500")),
    90: int(os.getenv("PACKAGE_PRICE_90", "4000")),
}

TIERS = {
    3:  {"name": "Bronze",   "emoji": "🥉", "perks": "Basic listing, text-only"},
    7:  {"name": "Silver",   "emoji": "🥈", "perks": "Photos, live badge, neighborhood SEO"},
    30: {"name": "Gold",     "emoji": "🥇", "perks": "Priority placement, Featured badge, recommendation boost"},
    90: {"name": "Platinum", "emoji": "💎", "perks": "Top of search, homepage spotlight, analytics"},
}

PREMIUM_VERIFY_PRICE = 500  # KES one-time for premium verification badge

# ==================== TRIALS & REFERRALS ====================
FREE_TRIAL_DAYS = int(os.getenv("FREE_TRIAL_DAYS", "7"))
FREE_TRIAL_REMINDER_DAY2_HOURS = int(os.getenv("FREE_TRIAL_REMINDER_DAY2_HOURS", "120"))
FREE_TRIAL_REMINDER_DAY5_HOURS = int(os.getenv("FREE_TRIAL_REMINDER_DAY5_HOURS", "48"))
FREE_TRIAL_FINAL_REMINDER_HOURS = int(os.getenv("FREE_TRIAL_FINAL_REMINDER_HOURS", "24"))
TRIAL_WINBACK_AFTER_HOURS = int(os.getenv("TRIAL_WINBACK_AFTER_HOURS", "24"))

REFERRAL_REWARD_DAYS = 1
REFERRAL_COMMISSION_PCT = 20

# ==================== DOMAIN CONSTANTS ====================
# Note: For bot UI logic vs Web UI logic, CITIES formats differ slightly in older code.
# Bot used `[("Nairobi", "🏙️", True), ...]`. Web used `["Nairobi", "Eldoret", ...]`.
# We unify them, retaining the rich structure for the bot and mapping for the web.
CITIES_RICH = [
    ("Nairobi", "🏙️", True),
    ("Eldoret", "🌆", True),
    ("Mombasa", "🏖️", False),
    ("Kisumu", "🌊", False),
    ("Nakuru", "🦩", False),
]

# Provide simple CITIES list for web templates
CITIES = [city[0] for city in CITIES_RICH if city[2]]

NEIGHBORHOODS = {
    "Nairobi": [
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
    ],
    "Eldoret": ["Town Centre", "Elgon View", "Langas", "Kapsoya"],
    "Mombasa": ["Nyali", "Bamburi", "Mtwapa", "Diani", "Town Centre"]
}

NAIROBI_NEIGHBORHOODS = NEIGHBORHOODS["Nairobi"]
ELDORET_NEIGHBORHOODS = NEIGHBORHOODS["Eldoret"]

BUILDS = ["Slim", "Athletic", "Curvy", "BBW", "Petite"]
AVAILABILITIES = ["Incall", "Outcall", "Both"]
SERVICES = ["GFE", "Massage", "Dinner Date", "Travel", "Parties", "Overnight", "Couples", "Fetish"]

RATE_DURATIONS = [
    ("30min", "30 Minutes"),
    ("1hr", "1 Hour"),
    ("2hr", "2 Hours"),
    ("3hr", "3 Hours"),
    ("overnight", "Overnight (8+ hrs)")
]

LANGUAGES = [
    "English 🇬🇧", "Swahili 🇰🇪", "French 🇫🇷", "Arabic 🇸🇦",
    "German 🇩🇪", "Italian 🇮🇹", "Spanish 🇪🇸", "Chinese 🇨🇳"
]

SESSION_DURATIONS = [30, 60, 90, 120]

# ==================== GLOBAL STATE ====================
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
    return PACKAGE_PRICES.get(days, 0)

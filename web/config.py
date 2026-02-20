"""
Blackbook Web Configuration
Imports shared constants and adds web-specific portal and cache settings.
"""
import os
from collections import OrderedDict
from shared.config import *

# ==================== PORTAL SPECIFIC ====================
PORTAL_ADMIN_WHATSAPP = os.getenv("PORTAL_ADMIN_WHATSAPP", "")
PORTAL_MAX_PROFILE_PHOTOS = int(os.getenv("PORTAL_MAX_PROFILE_PHOTOS", "8"))
PORTAL_MIN_PROFILE_PHOTOS = max(
    1,
    min(PORTAL_MAX_PROFILE_PHOTOS, int(os.getenv("PORTAL_MIN_PROFILE_PHOTOS", "3"))),
)
PORTAL_RECOMMENDED_PROFILE_PHOTOS = max(
    PORTAL_MIN_PROFILE_PHOTOS,
    min(
        PORTAL_MAX_PROFILE_PHOTOS,
        int(os.getenv("PORTAL_RECOMMENDED_PROFILE_PHOTOS", "5")),
    ),
)
PORTAL_MAX_UPLOAD_BYTES = int(os.getenv("PORTAL_MAX_UPLOAD_BYTES", str(6 * 1024 * 1024)))
ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PORTAL_VERIFY_CODE_TTL_MINUTES = int(os.getenv("PORTAL_VERIFY_CODE_TTL_MINUTES", "30"))
PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY = int(os.getenv("PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY", "5"))
PORTAL_LOGIN_MAX_ATTEMPTS = int(os.getenv("PORTAL_LOGIN_MAX_ATTEMPTS", "5"))
PORTAL_LOGIN_LOCK_MINUTES = int(os.getenv("PORTAL_LOGIN_LOCK_MINUTES", "15"))
PORTAL_LOGIN_RATE_LIMIT_ATTEMPTS = int(os.getenv("PORTAL_LOGIN_RATE_LIMIT_ATTEMPTS", "20"))
PORTAL_LOGIN_RATE_WINDOW_SECONDS = int(os.getenv("PORTAL_LOGIN_RATE_WINDOW_SECONDS", "900"))
PORTAL_VERIFY_REGEN_WINDOW_SECONDS = int(os.getenv("PORTAL_VERIFY_REGEN_WINDOW_SECONDS", "86400"))
PORTAL_VERIFY_CODE_PEPPER = os.getenv(
    "PORTAL_VERIFY_CODE_PEPPER",
    os.getenv("PROVIDER_PORTAL_SESSION_SECRET", "replace-this-portal-secret"),
)

# Account states
PORTAL_ACCOUNT_APPROVED = "approved"
PORTAL_ACCOUNT_PENDING = "pending_review"
PORTAL_ACCOUNT_REJECTED = "rejected"
PORTAL_ACCOUNT_SUSPENDED = "suspended"

# ==================== REDIS / CACHE / API ====================
ENABLE_REDIS_RATE_LIMITING = os.getenv("ENABLE_REDIS_RATE_LIMITING", "true").strip().lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
ENABLE_REDIS_PAGE_CACHE = os.getenv("ENABLE_REDIS_PAGE_CACHE", "true").strip().lower() == "true"
HOME_PAGE_CACHE_TTL_SECONDS = int(os.getenv("HOME_PAGE_CACHE_TTL_SECONDS", "60"))
GRID_CACHE_TTL_SECONDS = int(os.getenv("GRID_CACHE_TTL_SECONDS", "45"))
RECOMMENDATIONS_CACHE_TTL_SECONDS = int(os.getenv("RECOMMENDATIONS_CACHE_TTL_SECONDS", "45"))
ENABLE_ARQ_PAYMENT_QUEUE = os.getenv("ENABLE_ARQ_PAYMENT_QUEUE", "true").strip().lower() == "true"
INTERNAL_TASK_TOKEN = os.getenv("INTERNAL_TASK_TOKEN", "")

# Web specific payment seed endpoint (from old config)
ENABLE_SEED_ENDPOINT = os.getenv("ENABLE_SEED_ENDPOINT", "false").strip().lower() == "true"
LOCALHOSTS = {"127.0.0.1", "::1", "localhost"}

# Photo proxy cache
MAX_PHOTO_CACHE_ITEMS = int(os.getenv("MAX_PHOTO_CACHE_ITEMS", "2000"))
photo_url_cache = OrderedDict()

# Fallback images
FALLBACK_PROFILE_IMAGES = [
    "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&q=80&w=900",
]

# ==================== PORTAL ONBOARDING UI META ====================
ONBOARDING_TOTAL_STEPS = 4
ONBOARDING_STEP_META = {
    1: {
        "title": "Step 1: Profile Basics",
        "subtitle": "Start with your name, city, and body stats.",
    },
    2: {
        "title": "Step 2: About You",
        "subtitle": "Write a strong bio and your availability details.",
    },
    3: {
        "title": "Step 3: Services and Rates",
        "subtitle": "Add services, languages, and your pricing.",
    },
    4: {
        "title": "Step 4: Photos and Final Preview",
        "subtitle": "Upload photos, verify, and submit for admin approval.",
    },
}

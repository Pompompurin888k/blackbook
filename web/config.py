"""
Blackbook Web Configuration
Imports shared constants and adds web-specific portal and cache settings.
"""
import logging
import os
from collections import OrderedDict
from ipaddress import ip_network
from shared.config import *

logger = logging.getLogger(__name__)


_INSECURE_SECRET_MARKERS = {
    "",
    "replace-this-portal-secret",
    "replace_with_long_random_secret",
    "replace_with_random_secret",
    "change-me",
    "changeme",
    "your_secret_here",
}


def _is_insecure_secret(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return True
    if normalized in _INSECURE_SECRET_MARKERS:
        return True
    return normalized.startswith("replace")


APP_ENV = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production", "staging"}

_session_cookie_secure_raw = os.getenv("SESSION_COOKIE_SECURE")
if _session_cookie_secure_raw is None:
    SESSION_COOKIE_SECURE = IS_PRODUCTION
else:
    SESSION_COOKIE_SECURE = _session_cookie_secure_raw.strip().lower() == "true"
if IS_PRODUCTION and not SESSION_COOKIE_SECURE:
    logger.warning("SESSION_COOKIE_SECURE is false in production/staging; session cookies may be exposed over HTTP.")

_DEV_PORTAL_SESSION_SECRET_FALLBACK = "dev-portal-session-secret-not-for-production"
_DEV_PORTAL_CODE_PEPPER_FALLBACK = "dev-portal-code-pepper-not-for-production"

PROVIDER_PORTAL_SESSION_SECRET = os.getenv("PROVIDER_PORTAL_SESSION_SECRET", "").strip()
if _is_insecure_secret(PROVIDER_PORTAL_SESSION_SECRET):
    if IS_PRODUCTION:
        raise RuntimeError(
            "PROVIDER_PORTAL_SESSION_SECRET must be a strong random secret in production."
        )
    PROVIDER_PORTAL_SESSION_SECRET = os.getenv(
        "PROVIDER_PORTAL_SESSION_SECRET_DEV_FALLBACK",
        _DEV_PORTAL_SESSION_SECRET_FALLBACK,
    ).strip() or _DEV_PORTAL_SESSION_SECRET_FALLBACK
    logger.warning(
        "PROVIDER_PORTAL_SESSION_SECRET is missing or insecure; using a deterministic development fallback."
    )

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
PORTAL_REGISTER_RATE_LIMIT_ATTEMPTS = int(os.getenv("PORTAL_REGISTER_RATE_LIMIT_ATTEMPTS", "8"))
PORTAL_REGISTER_RATE_WINDOW_SECONDS = int(os.getenv("PORTAL_REGISTER_RATE_WINDOW_SECONDS", "3600"))
PORTAL_VERIFY_REGEN_WINDOW_SECONDS = int(os.getenv("PORTAL_VERIFY_REGEN_WINDOW_SECONDS", "86400"))
PORTAL_VERIFY_REGEN_RATE_LIMIT_ATTEMPTS = int(os.getenv("PORTAL_VERIFY_REGEN_RATE_LIMIT_ATTEMPTS", "10"))
PORTAL_VERIFY_REGEN_RATE_WINDOW_SECONDS = int(os.getenv("PORTAL_VERIFY_REGEN_RATE_WINDOW_SECONDS", "3600"))
PORTAL_VERIFY_CONFIRM_RATE_LIMIT_ATTEMPTS = int(os.getenv("PORTAL_VERIFY_CONFIRM_RATE_LIMIT_ATTEMPTS", "10"))
PORTAL_VERIFY_CONFIRM_RATE_WINDOW_SECONDS = int(os.getenv("PORTAL_VERIFY_CONFIRM_RATE_WINDOW_SECONDS", "900"))
PORTAL_PASSWORD_RESET_CODE_TTL_MINUTES = int(os.getenv("PORTAL_PASSWORD_RESET_CODE_TTL_MINUTES", "30"))
PORTAL_PASSWORD_RESET_REQUEST_LIMIT = int(os.getenv("PORTAL_PASSWORD_RESET_REQUEST_LIMIT", "5"))
PORTAL_PASSWORD_RESET_REQUEST_WINDOW_SECONDS = int(
    os.getenv("PORTAL_PASSWORD_RESET_REQUEST_WINDOW_SECONDS", "3600")
)
PORTAL_PASSWORD_RESET_CONFIRM_LIMIT = int(os.getenv("PORTAL_PASSWORD_RESET_CONFIRM_LIMIT", "10"))
PORTAL_PASSWORD_RESET_CONFIRM_WINDOW_SECONDS = int(
    os.getenv("PORTAL_PASSWORD_RESET_CONFIRM_WINDOW_SECONDS", "3600")
)
PORTAL_VERIFY_CODE_PEPPER = os.getenv("PORTAL_VERIFY_CODE_PEPPER", "").strip()
if _is_insecure_secret(PORTAL_VERIFY_CODE_PEPPER):
    if IS_PRODUCTION:
        raise RuntimeError("PORTAL_VERIFY_CODE_PEPPER must be set to a strong random secret in production.")
    PORTAL_VERIFY_CODE_PEPPER = os.getenv(
        "PORTAL_VERIFY_CODE_PEPPER_DEV_FALLBACK",
        _DEV_PORTAL_CODE_PEPPER_FALLBACK,
    ).strip() or _DEV_PORTAL_CODE_PEPPER_FALLBACK
    logger.warning(
        "PORTAL_VERIFY_CODE_PEPPER is missing or insecure; using a deterministic development fallback."
    )

# SMTP / Email verification
SMTP_HOST = os.getenv("SMTP_HOST", "smtp-relay.brevo.com").strip() or "smtp-relay.brevo.com"
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Blackbook").strip() or "Blackbook"
PORTAL_CAPTCHA_ENABLED = os.getenv("PORTAL_CAPTCHA_ENABLED", "false").strip().lower() == "true"
PORTAL_TURNSTILE_SITE_KEY = os.getenv("PORTAL_TURNSTILE_SITE_KEY", "").strip()
PORTAL_TURNSTILE_SECRET_KEY = os.getenv("PORTAL_TURNSTILE_SECRET_KEY", "").strip()

if (SMTP_USERNAME and not SMTP_PASSWORD) or (SMTP_PASSWORD and not SMTP_USERNAME):
    logger.warning("SMTP credentials are incomplete; email verification delivery may fail.")
if PORTAL_CAPTCHA_ENABLED and (not PORTAL_TURNSTILE_SITE_KEY or not PORTAL_TURNSTILE_SECRET_KEY):
    logger.warning(
        "PORTAL_CAPTCHA_ENABLED is true but Turnstile keys are missing; captcha checks will fail."
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
ADMIN_METRICS_TOKEN = os.getenv("ADMIN_METRICS_TOKEN", "").strip()

# ==================== OBJECT STORAGE (CLOUDFLARE R2) ====================
ENABLE_CLOUDFLARE_R2_UPLOADS = (
    os.getenv("ENABLE_CLOUDFLARE_R2_UPLOADS", "false").strip().lower() == "true"
)
CF_R2_ACCOUNT_ID = os.getenv("CF_R2_ACCOUNT_ID", "").strip()
CF_R2_ACCESS_KEY_ID = os.getenv("CF_R2_ACCESS_KEY_ID", "").strip()
CF_R2_SECRET_ACCESS_KEY = os.getenv("CF_R2_SECRET_ACCESS_KEY", "").strip()
CF_R2_BUCKET = os.getenv("CF_R2_BUCKET", "").strip()
CF_R2_REGION = os.getenv("CF_R2_REGION", "auto").strip() or "auto"
CF_R2_ENDPOINT = (
    os.getenv("CF_R2_ENDPOINT", "").strip()
    or (f"https://{CF_R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if CF_R2_ACCOUNT_ID else "")
)
CF_R2_PUBLIC_BASE_URL = os.getenv("CF_R2_PUBLIC_BASE_URL", "").strip().rstrip("/")
CF_R2_UPLOAD_PREFIX = os.getenv("CF_R2_UPLOAD_PREFIX", "providers").strip().strip("/")

# Web specific payment seed endpoint (from old config)
ENABLE_SEED_ENDPOINT = os.getenv("ENABLE_SEED_ENDPOINT", "false").strip().lower() == "true"
LOCALHOSTS = {"127.0.0.1", "::1", "localhost"}
_trusted_proxy_env = os.getenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32,::1/128")
TRUSTED_PROXY_CIDRS = []
for raw_cidr in _trusted_proxy_env.split(","):
    cidr = raw_cidr.strip()
    if not cidr:
        continue
    try:
        TRUSTED_PROXY_CIDRS.append(ip_network(cidr, strict=False))
    except ValueError:
        logger.warning(f"Ignoring invalid TRUSTED_PROXY_CIDRS entry: {cidr}")
if not TRUSTED_PROXY_CIDRS:
    TRUSTED_PROXY_CIDRS = [ip_network("127.0.0.1/32"), ip_network("::1/128")]

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

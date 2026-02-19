import os
import logging
import json
import hmac
import hashlib
import secrets
import uuid
from collections import OrderedDict
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
from urllib.parse import quote
from starlette.middleware.sessions import SessionMiddleware
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Blackbook Directory", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("PROVIDER_PORTAL_SESSION_SECRET", "replace-this-portal-secret"),
    same_site="lax",
    https_only=os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() == "true",
)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Database connection
db = Database()

# Telegram Bot Token for sending notifications
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
MEGAPAY_CALLBACK_SECRET = os.getenv("MEGAPAY_CALLBACK_SECRET")
ENABLE_SEED_ENDPOINT = os.getenv("ENABLE_SEED_ENDPOINT", "false").strip().lower() == "true"
LOCALHOSTS = {"127.0.0.1", "::1", "localhost"}
VALID_PACKAGE_DAYS = {0, 3, 7, 30, 90}
BOOST_DURATION_HOURS = int(os.getenv("BOOST_DURATION_HOURS", "12"))
BOOST_PRICE = int(os.getenv("BOOST_PRICE", "100"))
PACKAGE_PRICES = {
    3: int(os.getenv("PACKAGE_PRICE_3", "300")),
    7: int(os.getenv("PACKAGE_PRICE_7", "600")),
    30: int(os.getenv("PACKAGE_PRICE_30", "1500")),
    90: int(os.getenv("PACKAGE_PRICE_90", "4000")),
}
PUBLIC_BASE_URL = os.getenv("PUBLIC_WEB_BASE_URL", "https://innbucks.org").rstrip("/")
PORTAL_ADMIN_WHATSAPP = os.getenv("PORTAL_ADMIN_WHATSAPP", "")
PORTAL_MAX_PROFILE_PHOTOS = int(os.getenv("PORTAL_MAX_PROFILE_PHOTOS", "8"))
PORTAL_MIN_PROFILE_PHOTOS = max(
    1,
    min(PORTAL_MAX_PROFILE_PHOTOS, int(os.getenv("PORTAL_MIN_PROFILE_PHOTOS", "5"))),
)
PORTAL_MAX_UPLOAD_BYTES = int(os.getenv("PORTAL_MAX_UPLOAD_BYTES", str(6 * 1024 * 1024)))
ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Photo file-path cache (in-memory for now, consider Redis for production)
MAX_PHOTO_CACHE_ITEMS = int(os.getenv("MAX_PHOTO_CACHE_ITEMS", "2000"))
photo_url_cache = OrderedDict()

FALLBACK_PROFILE_IMAGES = [
    "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&q=80&w=900",
]


def _to_string_list(value) -> list[str]:
    """Normalizes a DB value to a flat string list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        if "," in text:
            return [item.strip() for item in text.split(",") if item.strip()]
        return [text]
    return []


def _fallback_image(seed: int, offset: int = 0) -> str:
    index = (seed + offset) % len(FALLBACK_PROFILE_IMAGES)
    return FALLBACK_PROFILE_IMAGES[index]


def _sanitize_phone(value: Optional[str]) -> str:
    if not value:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) >= 9:
        digits = "254" + digits[1:]
    return digits


def _normalize_portal_phone(value: str) -> str:
    """Normalizes and validates provider phone numbers for portal auth."""
    digits = _sanitize_phone(value)
    if not digits.startswith("254"):
        return ""
    if len(digits) < 12:
        return ""
    return digits[:12]


def _hash_password(password: str) -> str:
    """Hashes password with PBKDF2 for provider portal auth."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"{salt}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verifies password against stored PBKDF2 hash."""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, existing = stored_hash.split("$", 1)
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return hmac.compare_digest(existing, candidate)


def _portal_session_provider_id(request: Request) -> Optional[int]:
    """Gets provider ID from portal session cookie."""
    value = request.session.get("provider_portal_id")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _portal_generate_whatsapp_code() -> str:
    """Generates short manual verification code for WhatsApp confirmation."""
    return f"BB-{secrets.randbelow(9000) + 1000}"


def _to_int_or_none(value) -> Optional[int]:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


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


def _normalize_onboarding_step(raw_step) -> int:
    """Coerces onboarding step to a valid range."""
    try:
        step = int(raw_step)
    except (TypeError, ValueError):
        step = 1
    return max(1, min(step, ONBOARDING_TOTAL_STEPS))


def _parse_csv_values(raw_text: str) -> list[str]:
    """Normalizes comma-separated text to a clean list."""
    if not raw_text:
        return []
    return [item.strip() for item in str(raw_text).split(",") if item.strip()]


def _portal_onboarding_base_draft(provider: dict) -> dict:
    """Builds onboarding draft defaults from an existing provider profile."""
    return {
        "display_name": str(provider.get("display_name") or "").strip(),
        "city": str(provider.get("city") or "").strip(),
        "neighborhood": str(provider.get("neighborhood") or "").strip(),
        "age": str(provider.get("age") or "").strip(),
        "height_cm": str(provider.get("height_cm") or "").strip(),
        "weight_kg": str(provider.get("weight_kg") or "").strip(),
        "build": str(provider.get("build") or "").strip(),
        "bio": str(provider.get("bio") or "").strip(),
        "nearby_places": str(provider.get("nearby_places") or "").strip(),
        "availability_type": str(provider.get("availability_type") or "").strip(),
        "services_text": ", ".join(_to_string_list(provider.get("services"))),
        "languages_text": ", ".join(_to_string_list(provider.get("languages"))),
        "rate_30min": str(provider.get("rate_30min") or "").strip(),
        "rate_1hr": str(provider.get("rate_1hr") or "").strip(),
        "rate_2hr": str(provider.get("rate_2hr") or "").strip(),
        "rate_3hr": str(provider.get("rate_3hr") or "").strip(),
        "rate_overnight": str(provider.get("rate_overnight") or "").strip(),
    }


def _portal_get_onboarding_draft(request: Request, provider: dict) -> dict:
    """Returns current onboarding draft from session merged with DB defaults."""
    draft = _portal_onboarding_base_draft(provider)
    session_draft = request.session.get("provider_onboarding_draft")
    if isinstance(session_draft, dict):
        for key in draft:
            if key in session_draft:
                draft[key] = str(session_draft.get(key) or "").strip()
    return draft


def _portal_set_onboarding_draft(request: Request, draft: dict) -> None:
    """Persists onboarding draft in the session cookie."""
    request.session["provider_onboarding_draft"] = dict(draft)


def _portal_clear_onboarding_draft(request: Request) -> None:
    """Removes onboarding draft from session."""
    request.session.pop("provider_onboarding_draft", None)


def _portal_build_preview(draft: dict, photo_urls: list[str], has_verification_photo: bool) -> dict:
    """Builds compact preview values shown on each onboarding step."""
    rate_chunks = []
    rate_labels = {
        "rate_30min": "30m",
        "rate_1hr": "1h",
        "rate_2hr": "2h",
        "rate_3hr": "3h",
        "rate_overnight": "Overnight",
    }
    for key, label in rate_labels.items():
        amount = _to_int_or_none(draft.get(key))
        if amount is not None:
            rate_chunks.append(f"{label}: KES {amount:,}")

    return {
        "name": draft.get("display_name") or "Your stage name",
        "location": ", ".join(
            [item for item in [draft.get("neighborhood"), draft.get("city")] if item]
        ) or "Location not set",
        "stats": " | ".join(
            [
                part
                for part in [
                    f"Age {draft.get('age')}" if draft.get("age") else "",
                    f"{draft.get('height_cm')}cm" if draft.get("height_cm") else "",
                    f"{draft.get('weight_kg')}kg" if draft.get("weight_kg") else "",
                    draft.get("build") or "",
                ]
                if part
            ]
        ) or "Add your stats",
        "bio": draft.get("bio") or "Your bio will appear here.",
        "services": _parse_csv_values(draft.get("services_text", "")),
        "languages": _parse_csv_values(draft.get("languages_text", "")),
        "rates": rate_chunks,
        "photo_count": len(photo_urls),
        "verification_ready": bool(has_verification_photo),
    }


async def _save_provider_upload(provider_id: int, upload, prefix: str) -> Optional[str]:
    """Saves portal-uploaded image under static/uploads and returns public URL."""
    if not upload or not getattr(upload, "filename", None):
        return None
    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        ext = ".jpg"
    data = await upload.read()
    if not data:
        return None
    if len(data) > PORTAL_MAX_UPLOAD_BYTES:
        return None
    target_dir = Path("static/uploads/providers") / str(provider_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex}{ext}"
    target_path = target_dir / filename
    with open(target_path, "wb") as handle:
        handle.write(data)
    relative_url = f"/static/uploads/providers/{provider_id}/{filename}"
    return f"{PUBLIC_BASE_URL}{relative_url}"


def _extract_client_ip(request: Request) -> str:
    """Best-effort client IP extraction behind reverse proxies."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _detect_device_type(user_agent: str) -> str:
    """Simple device classification for lead analytics."""
    ua = (user_agent or "").lower()
    if not ua:
        return "unknown"
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    mobile_markers = ["android", "iphone", "mobile", "opera mini", "windows phone"]
    if any(marker in ua for marker in mobile_markers):
        return "mobile"
    return "desktop"


def _build_gallery_urls(provider_id: int, photo_ids: list[str]) -> list[str]:
    urls = []
    for file_id in photo_ids:
        if not file_id:
            continue
        file_id_str = str(file_id).strip()
        if not file_id_str:
            continue
        if file_id_str.startswith("http://") or file_id_str.startswith("https://") or file_id_str.startswith("/"):
            urls.append(file_id_str)
        else:
            urls.append(f"/photo/{file_id_str}")
    if urls:
        return urls[:5]
    # Keep a single fallback only when provider has no uploaded photos at all.
    return [_fallback_image(provider_id)]


def _normalize_provider(provider: dict) -> dict:
    """Builds a stable profile payload for the template."""
    profile = dict(provider)
    services_list = _to_string_list(profile.get("services"))
    languages_list = _to_string_list(profile.get("languages"))
    photo_ids = _to_string_list(profile.get("profile_photos"))

    profile["services_list"] = services_list
    profile["languages_list"] = languages_list
    profile["primary_location"] = profile.get("neighborhood") or profile.get("city") or "Nairobi"
    profile["photo_urls"] = _build_gallery_urls(profile.get("id", 0), photo_ids)
    profile["availability_label"] = profile.get("availability_type") or (
        "Available now" if profile.get("is_online") else "By booking"
    )
    profile["response_hint"] = (
        "Usually replies in under 15 minutes"
        if profile.get("is_online")
        else "Usually replies in under 1 hour"
    )
    profile["last_active_hint"] = "Online now" if profile.get("is_online") else "Active today"
    phone_digits = _sanitize_phone(profile.get("phone"))
    profile["phone_digits"] = phone_digits

    rate_fields = [
        ("30 min", "rate_30min"),
        ("1 hour", "rate_1hr"),
        ("2 hours", "rate_2hr"),
        ("3 hours", "rate_3hr"),
        ("Overnight", "rate_overnight"),
    ]
    rate_cards = []
    for label, field in rate_fields:
        amount = profile.get(field)
        if isinstance(amount, (int, float)) and amount > 0:
            rate_cards.append({"label": label, "amount": int(amount)})
    profile["rate_cards"] = rate_cards
    provider_id = profile.get("id")
    profile["call_url"] = f"/connect/{provider_id}?channel=call&mode=direct"
    profile["whatsapp_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=direct"
    profile["connect_direct_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=direct"
    profile["connect_stealth_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=stealth"
    profile["has_phone"] = bool(phone_digits)
    return profile


def _normalize_recommendation(provider: dict) -> dict:
    card = dict(provider)
    photo_ids = _to_string_list(card.get("profile_photos"))
    if photo_ids:
        first = str(photo_ids[0]).strip()
        if first.startswith("http://") or first.startswith("https://") or first.startswith("/"):
            card["photo_url"] = first
        else:
            card["photo_url"] = f"/photo/{first}"
    else:
        card["photo_url"] = _fallback_image(card.get("id", 0))
    card["location"] = card.get("neighborhood") or card.get("city") or "Nairobi"
    card["services_list"] = _to_string_list(card.get("services"))[:2]
    return card


def _telegram_contact_redirect(provider: dict, is_stealth: bool) -> RedirectResponse:
    """Fallback contact redirect using Telegram when phone is unavailable."""
    telegram_id = provider.get("telegram_id")
    username = provider.get("telegram_username")
    name = provider.get("display_name", "")
    if is_stealth:
        message = "Hi, is this a good time to talk?"
    else:
        message = f"Hi {name}, I found you on Blackbook. Are you available?"

    if username:
        return RedirectResponse(url=f"https://t.me/{username}?text={quote(message)}", status_code=302)
    if telegram_id:
        return RedirectResponse(url=f"tg://openmessage?user_id={telegram_id}", status_code=302)
    return RedirectResponse(url="/", status_code=302)


def _is_valid_callback_signature(raw_body: bytes, signature: Optional[str]) -> bool:
    """Validates callback signature using HMAC SHA256."""
    if not MEGAPAY_CALLBACK_SECRET:
        return False
    if not signature:
        return False
    if signature.startswith("sha256="):
        signature = signature.split("=", 1)[1]
    expected = hmac.new(
        MEGAPAY_CALLBACK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def _cache_photo_path(file_id: str, file_path: str) -> None:
    """Caches Telegram file paths with a bounded in-memory size."""
    if file_id in photo_url_cache:
        photo_url_cache.move_to_end(file_id)
    photo_url_cache[file_id] = file_path
    if len(photo_url_cache) > MAX_PHOTO_CACHE_ITEMS:
        photo_url_cache.popitem(last=False)


@app.get("/photo/{file_id}")
async def get_photo(file_id: str):
    """
    Proxy endpoint to serve Telegram photos.
    Fetches file path from Telegram API and streams the photo bytes.
    Caches results to minimize API calls.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN not set, cannot fetch photo")
        # Return a placeholder image
        return RedirectResponse(
            url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
            status_code=302
        )

    try:
        file_path = photo_url_cache.get(file_id)
        async with httpx.AsyncClient(timeout=30.0) as client:
            if not file_path:
                meta = await client.get(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile",
                    params={"file_id": file_id}
                )
                data = meta.json()
                if not data.get("ok") or not data.get("result", {}).get("file_path"):
                    logger.warning(f"⚠️ Failed to get file path for {file_id}: {data}")
                    return RedirectResponse(
                        url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
                        status_code=302
                    )
                file_path = data["result"]["file_path"]
                _cache_photo_path(file_id, file_path)

            photo_response = await client.get(
                f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            )
            if photo_response.status_code != 200:
                logger.warning(f"⚠️ Failed to fetch photo bytes for {file_id}: {photo_response.status_code}")
                return RedirectResponse(
                    url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
                    status_code=302
                )

            return Response(
                content=photo_response.content,
                media_type=photo_response.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": "public, max-age=3600"},
            )
    except Exception as e:
        logger.error(f"❌ Error fetching photo {file_id}: {e}")
        return RedirectResponse(
            url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
            status_code=302
        )


# Available cities and neighborhoods
CITIES = ["Nairobi", "Eldoret", "Mombasa"]

# Neighborhoods per city (Comprehensive coverage)
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


@app.get("/provider", response_class=HTMLResponse)
async def provider_portal_auth(request: Request, error: Optional[str] = None, success: Optional[str] = None):
    """Provider portal auth page (phone + password)."""
    provider_id = _portal_session_provider_id(request)
    if provider_id:
        return RedirectResponse(url="/provider/dashboard", status_code=302)
    return templates.TemplateResponse(
        "provider_auth.html",
        {
            "request": request,
            "error": error,
            "success": success,
        },
    )


@app.post("/provider/register")
async def provider_portal_register(request: Request):
    """Creates a new non-Telegram provider account."""
    form = await request.form()
    display_name = str(form.get("display_name", "")).strip()
    phone = _normalize_portal_phone(str(form.get("phone", "")).strip())
    password = str(form.get("password", ""))
    confirm_password = str(form.get("confirm_password", ""))

    if len(display_name) < 2:
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": "Display name must be at least 2 characters.", "success": None},
            status_code=400,
        )
    if not phone:
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": "Use a valid Kenyan phone number (e.g. 2547XXXXXXXX).", "success": None},
            status_code=400,
        )
    if len(password) < 6:
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": "Password must be at least 6 characters.", "success": None},
            status_code=400,
        )
    if password != confirm_password:
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": "Passwords do not match.", "success": None},
            status_code=400,
        )

    created = db.create_portal_provider_account(
        phone=phone,
        password_hash=_hash_password(password),
        display_name=display_name,
    )
    if not created:
        return templates.TemplateResponse(
            "provider_auth.html",
            {
                "request": request,
                "error": "This phone is already registered. Please log in instead.",
                "success": None,
            },
            status_code=400,
        )

    provider_id = int(created["id"])
    request.session["provider_portal_id"] = provider_id
    verify_code = _portal_generate_whatsapp_code()
    db.set_portal_phone_verification_code(provider_id, verify_code)
    await send_admin_alert(
        f"New portal signup: {display_name} ({phone}) provider_id={provider_id}. "
        f"Manual WhatsApp verification code: {verify_code}"
    )
    return RedirectResponse(url="/provider/onboarding", status_code=303)


@app.post("/provider/login")
async def provider_portal_login(request: Request):
    """Logs in an existing portal provider account."""
    form = await request.form()
    phone = _normalize_portal_phone(str(form.get("phone", "")).strip())
    password = str(form.get("password", ""))

    provider = db.get_portal_provider_by_phone(phone) if phone else None
    stored_hash = provider.get("portal_password_hash") if provider else None
    if not provider or not _verify_password(password, stored_hash):
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": "Invalid phone or password.", "success": None},
            status_code=401,
        )

    request.session["provider_portal_id"] = int(provider["id"])
    return RedirectResponse(url="/provider/dashboard", status_code=303)


@app.post("/provider/logout")
async def provider_portal_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/provider?success=Logged+out+successfully", status_code=303)


def _render_provider_onboarding_template(
    request: Request,
    provider: dict,
    draft: dict,
    step: int,
    error: Optional[str] = None,
):
    """Renders the multi-step portal onboarding screen."""
    photo_urls = _to_string_list(provider.get("profile_photos"))
    preview = _portal_build_preview(
        draft=draft,
        photo_urls=photo_urls,
        has_verification_photo=bool(provider.get("verification_photo_id")),
    )
    return templates.TemplateResponse(
        "provider_onboarding.html",
        {
            "request": request,
            "provider": provider,
            "draft": draft,
            "step": step,
            "total_steps": ONBOARDING_TOTAL_STEPS,
            "step_meta": ONBOARDING_STEP_META.get(step, ONBOARDING_STEP_META[1]),
            "step_numbers": list(range(1, ONBOARDING_TOTAL_STEPS + 1)),
            "error": error,
            "cities": CITIES,
            "neighborhood_map": NEIGHBORHOODS,
            "photo_urls": photo_urls,
            "max_photos": PORTAL_MAX_PROFILE_PHOTOS,
            "min_photos": PORTAL_MIN_PROFILE_PHOTOS,
            "preview": preview,
        },
    )


@app.get("/provider/onboarding", response_class=HTMLResponse)
async def provider_portal_onboarding(request: Request, step: Optional[int] = 1):
    """Multi-step onboarding wizard for non-Telegram providers."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)
    current_step = _normalize_onboarding_step(step)
    draft = _portal_get_onboarding_draft(request, provider)
    _portal_set_onboarding_draft(request, draft)
    return _render_provider_onboarding_template(
        request=request,
        provider=provider,
        draft=draft,
        step=current_step,
    )


@app.post("/provider/onboarding")
async def provider_portal_onboarding_submit(request: Request):
    """Handles step navigation and final onboarding submission."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    form = await request.form()
    step = _normalize_onboarding_step(form.get("step"))
    action = str(form.get("action", "next")).strip().lower()
    draft = _portal_get_onboarding_draft(request, provider)

    if step == 1:
        draft["display_name"] = str(form.get("display_name", "")).strip()
        draft["city"] = str(form.get("city", "")).strip()
        draft["neighborhood"] = str(form.get("neighborhood", "")).strip()
        draft["age"] = str(form.get("age", "")).strip()
        draft["height_cm"] = str(form.get("height_cm", "")).strip()
        draft["weight_kg"] = str(form.get("weight_kg", "")).strip()
        draft["build"] = str(form.get("build", "")).strip()
        _portal_set_onboarding_draft(request, draft)
        if action != "back" and (not draft["display_name"] or not draft["city"] or not draft["neighborhood"]):
            return _render_provider_onboarding_template(
                request=request,
                provider=provider,
                draft=draft,
                step=step,
                error="Please set display name, city, and neighborhood before continuing.",
            )
    elif step == 2:
        draft["bio"] = str(form.get("bio", "")).strip()
        draft["nearby_places"] = str(form.get("nearby_places", "")).strip()
        draft["availability_type"] = str(form.get("availability_type", "")).strip()
        _portal_set_onboarding_draft(request, draft)
        if action != "back" and len(draft["bio"]) < 20:
            return _render_provider_onboarding_template(
                request=request,
                provider=provider,
                draft=draft,
                step=step,
                error="Please write a richer bio (at least 20 characters).",
            )
    elif step == 3:
        draft["services_text"] = str(form.get("services_text", "")).strip()
        draft["languages_text"] = str(form.get("languages_text", "")).strip()
        draft["rate_30min"] = str(form.get("rate_30min", "")).strip()
        draft["rate_1hr"] = str(form.get("rate_1hr", "")).strip()
        draft["rate_2hr"] = str(form.get("rate_2hr", "")).strip()
        draft["rate_3hr"] = str(form.get("rate_3hr", "")).strip()
        draft["rate_overnight"] = str(form.get("rate_overnight", "")).strip()
        _portal_set_onboarding_draft(request, draft)
        if action != "back" and not _parse_csv_values(draft["services_text"]):
            return _render_provider_onboarding_template(
                request=request,
                provider=provider,
                draft=draft,
                step=step,
                error="Please add at least one service before continuing.",
            )

    if action == "back":
        return RedirectResponse(
            url=f"/provider/onboarding?step={max(1, step - 1)}",
            status_code=303,
        )

    if step < ONBOARDING_TOTAL_STEPS:
        return RedirectResponse(url=f"/provider/onboarding?step={step + 1}", status_code=303)

    # Final step: save to DB and submit.
    existing_photo_urls = _to_string_list(provider.get("profile_photos"))
    upload_items = form.getlist("photos")
    for upload in upload_items:
        if len(existing_photo_urls) >= PORTAL_MAX_PROFILE_PHOTOS:
            break
        saved_url = await _save_provider_upload(provider_id, upload, "profile")
        if saved_url:
            existing_photo_urls.append(saved_url)

    verification_photo_upload = form.get("verification_photo")
    verification_photo_url = await _save_provider_upload(provider_id, verification_photo_upload, "verify")
    effective_verification_photo = verification_photo_url or provider.get("verification_photo_id")

    if len(existing_photo_urls) < PORTAL_MIN_PROFILE_PHOTOS:
        return _render_provider_onboarding_template(
            request=request,
            provider=provider,
            draft=draft,
            step=ONBOARDING_TOTAL_STEPS,
            error=(
                f"Please upload at least {PORTAL_MIN_PROFILE_PHOTOS} profile photos "
                "before submitting."
            ),
        )
    if not effective_verification_photo:
        return _render_provider_onboarding_template(
            request=request,
            provider=provider,
            draft=draft,
            step=ONBOARDING_TOTAL_STEPS,
            error="Please upload a verification selfie or ID photo to submit.",
        )

    display_name = draft.get("display_name") or provider.get("display_name")
    city = draft.get("city", "")
    neighborhood = draft.get("neighborhood", "")
    bio = draft.get("bio", "")
    services = _parse_csv_values(draft.get("services_text", ""))
    languages = _parse_csv_values(draft.get("languages_text", ""))

    update_data = {
        "display_name": display_name,
        "city": city,
        "neighborhood": neighborhood,
        "age": _to_int_or_none(draft.get("age")),
        "height_cm": _to_int_or_none(draft.get("height_cm")),
        "weight_kg": _to_int_or_none(draft.get("weight_kg")),
        "build": draft.get("build", ""),
        "services": services,
        "bio": bio,
        "nearby_places": draft.get("nearby_places", ""),
        "availability_type": draft.get("availability_type", ""),
        "languages": languages,
        "profile_photos": existing_photo_urls,
        "rate_30min": _to_int_or_none(draft.get("rate_30min")),
        "rate_1hr": _to_int_or_none(draft.get("rate_1hr")),
        "rate_2hr": _to_int_or_none(draft.get("rate_2hr")),
        "rate_3hr": _to_int_or_none(draft.get("rate_3hr")),
        "rate_overnight": _to_int_or_none(draft.get("rate_overnight")),
        "is_online": False,
        "portal_onboarding_complete": bool(
            display_name
            and city
            and neighborhood
            and bio
            and len(existing_photo_urls) >= PORTAL_MIN_PROFILE_PHOTOS
        ),
    }
    if effective_verification_photo:
        update_data["verification_photo_id"] = effective_verification_photo

    saved = db.update_portal_provider_profile(provider_id, update_data)
    if not saved:
        return _render_provider_onboarding_template(
            request=request,
            provider=provider,
            draft=draft,
            step=ONBOARDING_TOTAL_STEPS,
            error="Could not save your profile right now. Please try again.",
        )

    provider_after = db.get_portal_provider_by_id(provider_id) or {}
    if not provider_after.get("phone_verify_code"):
        db.set_portal_phone_verification_code(provider_id, _portal_generate_whatsapp_code())

    if verification_photo_url:
        await send_admin_alert(
            "Portal verification submitted: "
            f"provider_id={provider_id}, name={display_name or provider.get('display_name', 'Unknown')}, "
            f"phone={provider.get('phone', '')}, photo={verification_photo_url}"
        )

    _portal_clear_onboarding_draft(request)
    return RedirectResponse(url="/provider/dashboard?saved=1", status_code=303)


@app.get("/provider/dashboard", response_class=HTMLResponse)
async def provider_portal_dashboard(request: Request, saved: Optional[int] = 0):
    """Provider dashboard for non-Telegram onboarding users."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    phone_code = provider.get("phone_verify_code")
    if not phone_code:
        phone_code = _portal_generate_whatsapp_code()
        db.set_portal_phone_verification_code(provider_id, phone_code)
        provider = db.get_portal_provider_by_id(provider_id) or provider

    return templates.TemplateResponse(
        "provider_dashboard.html",
        {
            "request": request,
            "provider": provider,
            "photo_urls": _to_string_list(provider.get("profile_photos")),
            "services_list": _to_string_list(provider.get("services")),
            "languages_list": _to_string_list(provider.get("languages")),
            "saved": bool(saved),
            "admin_whatsapp": PORTAL_ADMIN_WHATSAPP,
            "phone_verify_code": phone_code,
        },
    )


@app.get("/provider/verify-phone", response_class=HTMLResponse)
async def provider_portal_verify_phone(request: Request):
    """Manual WhatsApp-based phone verification instructions page."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    phone_code = provider.get("phone_verify_code")
    if not phone_code:
        phone_code = _portal_generate_whatsapp_code()
        db.set_portal_phone_verification_code(provider_id, phone_code)
    return templates.TemplateResponse(
        "provider_verify_phone.html",
        {
            "request": request,
            "provider": provider,
            "admin_whatsapp": PORTAL_ADMIN_WHATSAPP,
            "phone_verify_code": phone_code,
        },
    )


@app.post("/provider/verify-phone/regenerate")
async def provider_portal_regenerate_verify_code(request: Request):
    """Regenerates manual WhatsApp verification code."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    new_code = _portal_generate_whatsapp_code()
    db.set_portal_phone_verification_code(provider_id, new_code)
    provider = db.get_portal_provider_by_id(provider_id)
    if provider:
        await send_admin_alert(
            f"Portal verification code regenerated: provider_id={provider_id}, "
            f"phone={provider.get('phone', '')}, code={new_code}"
        )
    return RedirectResponse(url="/provider/verify-phone", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request, 
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """Main directory page with optional city and neighborhood filter."""
    from datetime import datetime
    
    # Default to Nairobi if no city selected
    if not city:
        city = "Nairobi"

    providers = db.get_active_providers(city, neighborhood)
    city_counts = db.get_city_counts()
    total_count = sum(city_counts.values())
    
    # Get stats for hero section
    total_verified = db.get_total_verified_count()
    total_online = db.get_online_count()
    total_premium = db.get_premium_count()
    
    # Get neighborhoods for selected city
    neighborhoods = NEIGHBORHOODS.get(city, []) if city else []
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "providers": providers,
        "cities": CITIES,
        "selected_city": city,
        "selected_neighborhood": neighborhood,
        "neighborhoods": neighborhoods,
        "neighborhood_map": NEIGHBORHOODS,
        "city_counts": city_counts,
        "total_count": total_count,
        "total_verified": total_verified,
        "total_online": total_online,
        "total_premium": total_premium,
        "now": datetime.now  # Pass datetime for template calculations
    })


@app.get("/api/grid", response_class=HTMLResponse)
async def api_grid(
    request: Request,
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """
    HTMX endpoint - returns only the provider grid HTML.
    Used for seamless filtering without full page reload.
    """
    from datetime import datetime
    
    providers = db.get_active_providers(city, neighborhood)
    
    return templates.TemplateResponse("_grid.html", {
        "request": request,
        "providers": providers,
        "selected_city": city,
        "now": datetime.now  # Pass datetime for template calculations
    })


@app.get("/api/recommendations", response_class=HTMLResponse)
async def api_recommendations(
    request: Request,
    city: str,
    exclude_id: int
):
    """
    HTMX endpoint - returns smart recommended providers HTML with relevance indicators.
    """
    recommendations = db.get_recommendations(city, exclude_id, limit=4)
    
    # Get source provider for comparison
    source_provider = db.get_provider_by_id(exclude_id)
    
    # Add relevance hints to each recommendation
    enriched_recommendations = []
    for rec in recommendations:
        rec_dict = dict(rec)
        hints = []
        
        if source_provider:
            # Same neighborhood
            if rec.get('neighborhood') == source_provider.get('neighborhood'):
                hints.append("From your area")
            # Same build
            elif rec.get('build') and rec.get('build') == source_provider.get('build'):
                hints.append("Similar style")
            # Recently verified
            elif rec.get('created_at'):
                from datetime import datetime, timedelta
                if rec['created_at'] > datetime.now() - timedelta(days=30):
                    hints.append("Recently verified")
            # Online
            if rec.get('is_online'):
                if not hints:
                    hints.append("Available now")
        
        rec_dict['relevance_hint'] = hints[0] if hints else None
        enriched_recommendations.append(rec_dict)
    
    return templates.TemplateResponse("_recommendations.html", {
        "request": request,
        "providers": enriched_recommendations,
        "selected_city": city
    })


@app.get("/seed")
async def seed_data(request: Request):
    """Seeds the database with test data."""
    if not ENABLE_SEED_ENDPOINT:
        return JSONResponse({"status": "error", "message": "Not found"}, status_code=404)
    client_host = request.client.host if request.client else None
    if client_host not in LOCALHOSTS:
        return JSONResponse({"status": "error", "message": "Forbidden"}, status_code=403)
    db.seed_test_providers()
    return {"status": "seeded", "message": "Test providers added."}


@app.get("/api/status/{provider_id}", response_class=HTMLResponse)
async def get_provider_status(provider_id: int):
    """
    Real-time status endpoint for HTMX polling.
    Returns the Live badge HTML if provider is online.
    """
    provider = db.get_provider_by_id(provider_id)
    
    if provider and provider.get("is_online"):
        return f'''
        <div id="live-badge-{provider_id}"
             hx-get="/api/status/{provider_id}"
             hx-trigger="every 30s"
             hx-swap="outerHTML"
             class="glass px-2 py-1 rounded-full flex items-center gap-1">
            <span class="h-2 w-2 bg-green-500 rounded-full animate-pulse"></span>
            <span class="text-[10px] text-green-400 font-bold uppercase">Live</span>
        </div>
        '''
    else:
        # Provider is offline - return empty badge that still polls
        return f'''
        <div id="live-badge-{provider_id}"
             hx-get="/api/status/{provider_id}"
             hx-trigger="every 30s"
             hx-swap="outerHTML">
        </div>
        '''


@app.get("/contact/{provider_id}", response_class=HTMLResponse)
async def contact_page(request: Request, provider_id: int):
    """
    Contact page - shows Direct vs Discreet messaging options.
    Preserves client privacy with stealth mode.
    """
    provider = db.get_provider_by_id(provider_id)
    
    if not provider:
        return RedirectResponse(url="/", status_code=302)

    profile = _normalize_provider(provider)
    recommendations = db.get_recommendations(profile.get("city") or "Nairobi", provider_id, limit=4)
    recommendation_cards = [_normalize_recommendation(item) for item in recommendations]
    
    # Log the contact click
    logger.info(f"📲 Contact page: Provider ID {provider_id} ({provider.get('display_name', 'Unknown')})")
    
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "provider": profile,
        "recommendations": recommendation_cards,
    })


@app.get("/connect/{provider_id}")
async def connect_provider(
    request: Request,
    provider_id: int,
    mode: str = Query("direct"),
    channel: str = Query("whatsapp"),
):
    """
    Tracking bridge for outbound contact actions.
    Logs lead analytics before redirecting to WhatsApp or phone app.
    """
    provider = db.get_provider_by_id(provider_id)
    if not provider:
        return RedirectResponse(url="/", status_code=302)

    profile = _normalize_provider(provider)
    mode_value = (mode or "direct").strip().lower()
    is_stealth = mode_value == "stealth"
    contact_method = "call" if (channel or "").strip().lower() == "call" else "whatsapp"
    name = profile.get("display_name", "there")
    phone_digits = profile.get("phone_digits", "")

    client_ip = _extract_client_ip(request)
    device_type = _detect_device_type(request.headers.get("user-agent", ""))
    db.log_lead_analytics(
        provider_id=provider_id,
        client_ip=client_ip,
        device_type=device_type,
        contact_method=contact_method,
        is_stealth=is_stealth,
    )

    if contact_method == "call":
        if phone_digits:
            logger.info(f"Call lead: provider={provider_id} mode={mode_value} ip={client_ip}")
            return RedirectResponse(url=f"tel:+{phone_digits}", status_code=302)
        logger.info(f"Call lead fallback to direct contact: provider={provider_id} ip={client_ip}")
        return _telegram_contact_redirect(provider, is_stealth=False)

    if is_stealth:
        message = (
            "Hello, I am interested in the lifestyle management services we discussed. "
            "Please let me know your availability for a consultation."
        )
    else:
        message = f"Hi {name}, I saw your profile on Blackbook. Are you available?"

    if phone_digits:
        wa_url = f"https://wa.me/{phone_digits}?text={quote(message)}"
        logger.info(f"WhatsApp lead: provider={provider_id} mode={mode_value} ip={client_ip}")
        return RedirectResponse(url=wa_url, status_code=302)

    logger.info(f"WhatsApp lead fallback to Telegram route: provider={provider_id} mode={mode_value}")
    return _telegram_contact_redirect(provider, is_stealth=is_stealth)


@app.get("/contact/{provider_id}/direct")
async def contact_direct(provider_id: int):
    """Direct message - opens Telegram with a clear first message."""
    provider = db.get_provider_by_id(provider_id)
    if not provider:
        return RedirectResponse(url="/", status_code=302)
    return _telegram_contact_redirect(provider, is_stealth=False)


@app.get("/contact/{provider_id}/discreet")
async def contact_discreet(provider_id: int):
    """Discreet message - opens Telegram with a vague, safe message."""
    provider = db.get_provider_by_id(provider_id)
    if not provider:
        return RedirectResponse(url="/", status_code=302)
    return _telegram_contact_redirect(provider, is_stealth=True)


# ==================== PAYMENT CALLBACK ====================

@app.post("/payments/callback")
async def megapay_callback(request: Request):
    """
    Handle MegaPay payment callback.
    When payment succeeds, activates the provider's subscription.
    """
    try:
        if not MEGAPAY_CALLBACK_SECRET:
            logger.error("❌ MEGAPAY_CALLBACK_SECRET not configured. Rejecting callback.")
            return JSONResponse({"status": "error", "message": "Callback secret not configured"}, status_code=503)

        raw_body = await request.body()
        signature = request.headers.get("X-MegaPay-Signature") or request.headers.get("X-Signature")
        if not _is_valid_callback_signature(raw_body, signature):
            logger.warning("⚠️ Invalid or missing callback signature.")
            return JSONResponse({"status": "error", "message": "Invalid signature"}, status_code=403)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return JSONResponse({"status": "error", "message": "Invalid JSON payload"}, status_code=400)

        logger.info(f"💳 Payment callback received (verified): {payload}")

        # Extract data from MegaPay response
        status = payload.get("status") or payload.get("ResultCode")
        reference = payload.get("MpesaReceiptNumber") or payload.get("TransactionId") or payload.get("reference")
        amount_raw = payload.get("Amount") or payload.get("amount")
        account_ref = (
            payload.get("AccountReference")
            or payload.get("account_reference")
            or (reference if isinstance(reference, str) and reference.startswith("BB_") else "")
        )

        if not reference:
            logger.error("❌ Missing payment reference in callback payload.")
            return JSONResponse({"status": "error", "message": "Missing payment reference"}, status_code=400)

        # Parse telegram_id and package_days from account reference.
        # Supports both BB_<tg>_<days> and BB_<tg>_<days>_<nonce>.
        parts = account_ref.split("_")
        if len(parts) >= 3 and parts[0] == "BB":
            try:
                telegram_id = int(parts[1])
                package_days = int(parts[2])
            except ValueError:
                logger.error(f"❌ Invalid account reference values: {account_ref}")
                return JSONResponse({"status": "error", "message": "Invalid account reference"}, status_code=400)
        else:
            logger.error(f"❌ Invalid account reference format: {account_ref}")
            return JSONResponse({"status": "error", "message": "Invalid account reference"}, status_code=400)

        if package_days not in VALID_PACKAGE_DAYS:
            logger.error(f"❌ Invalid package_days value from callback: {package_days}")
            return JSONResponse({"status": "error", "message": "Invalid package days"}, status_code=400)

        try:
            amount = int(float(amount_raw))
        except (TypeError, ValueError):
            logger.error(f"❌ Invalid amount in callback payload: {amount_raw}")
            return JSONResponse({"status": "error", "message": "Invalid amount"}, status_code=400)

        expected_amount = BOOST_PRICE if package_days == 0 else PACKAGE_PRICES.get(package_days)
        if expected_amount is None or amount != expected_amount:
            logger.error(
                f"❌ Amount mismatch for {reference}: expected {expected_amount}, got {amount}"
            )
            return JSONResponse({"status": "error", "message": "Invalid payment amount"}, status_code=400)

        # Idempotency: already-processed successful transaction
        if db.has_successful_payment(reference):
            logger.info(f"ℹ️ Duplicate callback ignored for reference {reference}")
            return JSONResponse({"status": "success", "message": "Already processed"})

        # Check if payment was successful
        success_markers = {"0", "200", "success", "completed", "succeeded", "ok"}
        success = str(status).strip().lower() in success_markers

        if success:
            provider_data = db.get_provider_by_telegram_id(telegram_id)
            if not provider_data:
                logger.warning(f"⚠️ Callback references unknown provider: {telegram_id}")
                db.log_payment(telegram_id, amount, reference, "FAILED_NO_PROVIDER", package_days)
                return JSONResponse({"status": "error", "message": "Provider not found"}, status_code=404)

            if not provider_data.get("is_verified"):
                logger.warning(f"⚠️ Callback rejected for unverified provider: {telegram_id}")
                db.log_payment(telegram_id, amount, reference, "REJECTED_UNVERIFIED", package_days)
                return JSONResponse({"status": "error", "message": "Provider not verified"}, status_code=403)

            # Boost transaction
            if package_days == 0:
                if not db.boost_provider(telegram_id, BOOST_DURATION_HOURS):
                    logger.error(f"❌ Failed to boost provider {telegram_id}")
                    await send_admin_alert(
                        f"Web callback error: failed boost activation for provider {telegram_id}, reference {reference}."
                    )
                    return JSONResponse({"status": "error", "message": "Failed to activate boost"}, status_code=400)
                if not db.log_payment(telegram_id, amount, reference, "SUCCESS", package_days):
                    logger.error(f"❌ Failed to log successful boost payment for {telegram_id}")
                    await send_admin_alert(
                        f"Web callback error: failed to log boost payment for provider {telegram_id}, reference {reference}."
                    )
                    return JSONResponse({"status": "error", "message": "Failed to log payment"}, status_code=500)

                from datetime import datetime, timedelta
                boost_until = datetime.now() + timedelta(hours=BOOST_DURATION_HOURS)
                await send_telegram_notification(
                    telegram_id,
                    f"🚀 **Boost Activated!**\n\n"
                    f"💰 Amount: {amount} KES\n"
                    f"⏱️ Duration: {BOOST_DURATION_HOURS} hours\n"
                    f"📈 Active until: **{boost_until.strftime('%Y-%m-%d %H:%M')}**\n\n"
                    f"Your profile is now prioritized in results."
                )
                db.log_funnel_event(
                    telegram_id,
                    "boost_purchased",
                    {"amount": amount, "hours": BOOST_DURATION_HOURS, "reference": reference},
                )
                logger.info(f"✅ Boost SUCCESS: Provider {telegram_id} boosted for {BOOST_DURATION_HOURS} hours")
                return JSONResponse({"status": "success", "message": "Boost activated"})

            # Subscription transaction
            if not db.activate_subscription(telegram_id, package_days):
                logger.error(f"❌ Failed to activate subscription for {telegram_id}")
                await send_admin_alert(
                    f"Web callback error: failed subscription activation for provider {telegram_id}, reference {reference}."
                )
                return JSONResponse({"status": "error", "message": "Failed to activate subscription"}, status_code=500)
            if not db.log_payment(telegram_id, amount, reference, "SUCCESS", package_days):
                logger.error(f"❌ Failed to log successful payment for {telegram_id}")
                await send_admin_alert(
                    f"Web callback error: failed to log successful payment for provider {telegram_id}, reference {reference}."
                )
                return JSONResponse({"status": "error", "message": "Failed to log payment"}, status_code=500)
            db.log_funnel_event(
                telegram_id,
                "paid_success",
                {"amount": amount, "days": package_days, "reference": reference},
            )
            db.log_funnel_event(
                telegram_id,
                "active_live",
                {"source": "payment", "days": package_days},
            )

            # === REFERRAL REWARD ===
            # If this provider was referred, reward the referrer
            referrer_id = provider_data.get("referred_by") if provider_data else None
            if referrer_id:
                try:
                    commission = int(float(amount or 0) * 0.20)  # 20% commission as credit
                    if commission > 0:
                        db.add_referral_credits(referrer_id, commission)
                    # Also give 1 free day
                    db.extend_subscription(referrer_id, 1)
                    await send_telegram_notification(
                        referrer_id,
                        f"🎁 **Referral Reward!**\n\n"
                        f"Someone you referred just subscribed!\n"
                        f"💰 +{commission} KES credit added\n"
                        f"📅 +1 bonus day added\n\n"
                        f"Keep sharing your link to earn more! 🤝"
                    )
                    logger.info(f"🤝 Referral reward: {commission} KES credit + 1 day to {referrer_id}")
                except Exception as ref_err:
                    logger.error(f"⚠️ Referral reward error (non-fatal): {ref_err}")

            neighborhood = provider_data.get("neighborhood", "your area")

            # Calculate expiry date
            from datetime import datetime, timedelta
            expiry_date = datetime.now() + timedelta(days=package_days)
            expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M")

            # Send enhanced Telegram notification to provider
            await send_telegram_notification(
                telegram_id,
                f"✅ **Payment Confirmed!**\n\n"
                f"💰 Amount: {amount} KES\n"
                f"📅 Package: {package_days} Day(s)\n\n"
                f"🎉 Your profile is now **LIVE** in **{neighborhood}** until **{expiry_str}**.\n\n"
                f"Go get them! 🚀"
            )

            logger.info(f"✅ Payment SUCCESS: Provider {telegram_id} activated for {package_days} days")
            return JSONResponse({"status": "success", "message": "Subscription activated"})

        db.log_payment(telegram_id, amount, reference, "FAILED", package_days)
        logger.warning(f"❌ Payment FAILED for {telegram_id}: {status}")
        return JSONResponse({"status": "failed", "message": "Payment failed"})

    except Exception as e:
        logger.error(f"❌ Payment callback error: {e}")
        await send_admin_alert(f"Web callback crashed with exception: {e}")
        return JSONResponse({"status": "error", "message": "Internal callback error"}, status_code=500)


async def send_telegram_notification(
    chat_id: int,
    message: str,
    parse_mode: Optional[str] = "Markdown",
    bot_token: Optional[str] = None,
):
    """Sends a notification to a user via Telegram Bot API."""
    token = bot_token or TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("⚠️ TELEGRAM_TOKEN not set, cannot send notification")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                logger.info(f"📨 Notification sent to {chat_id}")
            else:
                logger.warning(f"⚠️ Notification failed: {response.text}")
    except Exception as e:
        logger.error(f"❌ Telegram notification error: {e}")


async def send_admin_alert(message: str):
    """Sends basic operational alerts to admin via Telegram."""
    if not ADMIN_CHAT_ID or not ADMIN_BOT_TOKEN:
        return
    try:
        await send_telegram_notification(
            int(ADMIN_CHAT_ID),
            f"ALERT:\n{message}",
            parse_mode=None,
            bot_token=ADMIN_BOT_TOKEN,
        )
    except Exception as e:
        logger.error(f"❌ Failed to send admin alert: {e}")


# ==================== OTHER ROUTES ====================

@app.get("/safety", response_class=HTMLResponse)
async def safety(request: Request):
    """Safety page - shows blacklist and verification info."""
    return templates.TemplateResponse("safety.html", {"request": request})


@app.get("/api/providers")
async def api_providers(
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """JSON API endpoint for providers."""
    providers = db.get_public_active_providers(city, neighborhood)
    return {"providers": providers, "count": len(providers)}


@app.post("/api/analytics")
async def api_analytics(request: Request):
    """Receives lightweight frontend analytics events."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

    event = str(payload.get("event", "")).strip()
    event_payload = payload.get("payload", {})
    if not event:
        return JSONResponse({"status": "error", "message": "Missing event"}, status_code=400)
    if not isinstance(event_payload, dict):
        event_payload = {"value": str(event_payload)}

    ok = db.log_analytics_event(event_name=event, event_payload=event_payload)
    if not ok:
        return JSONResponse({"status": "error", "message": "Failed"}, status_code=500)
    return {"status": "ok"}


@app.get("/health")
async def health():
    """Readiness health endpoint (checks DB)."""
    db_ok = db.healthcheck()
    status_code = 200 if db_ok else 503
    return JSONResponse(
        {"status": "healthy" if db_ok else "unhealthy", "database": "up" if db_ok else "down"},
        status_code=status_code,
    )


@app.get("/health/live")
async def health_live():
    """Liveness endpoint."""
    return {"status": "alive"}

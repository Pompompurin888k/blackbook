import os
import logging
import uuid
import json
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote
from typing import Optional
from starlette.middleware.sessions import SessionMiddleware
from database import Database

# ── Config ──────────────────────────────────────────────────
from config import (
    TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, ADMIN_BOT_TOKEN,
    MEGAPAY_CALLBACK_SECRET, ENABLE_SEED_ENDPOINT,
    LOCALHOSTS, VALID_PACKAGE_DAYS,
    BOOST_DURATION_HOURS, BOOST_PRICE, PACKAGE_PRICES,
    PORTAL_ADMIN_WHATSAPP,
    PORTAL_MAX_PROFILE_PHOTOS, PORTAL_MIN_PROFILE_PHOTOS,
    PORTAL_RECOMMENDED_PROFILE_PHOTOS,
    PORTAL_MAX_UPLOAD_BYTES, ALLOWED_UPLOAD_EXTENSIONS,
    PORTAL_VERIFY_CODE_TTL_MINUTES, PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY,
    PORTAL_LOGIN_MAX_ATTEMPTS, PORTAL_LOGIN_LOCK_MINUTES,
    PORTAL_LOGIN_RATE_LIMIT_ATTEMPTS, PORTAL_LOGIN_RATE_WINDOW_SECONDS,
    PORTAL_VERIFY_REGEN_WINDOW_SECONDS,
    PORTAL_ACCOUNT_APPROVED, PORTAL_ACCOUNT_PENDING,
    PORTAL_ACCOUNT_REJECTED, PORTAL_ACCOUNT_SUSPENDED,
    ENABLE_REDIS_PAGE_CACHE, HOME_PAGE_CACHE_TTL_SECONDS,
    GRID_CACHE_TTL_SECONDS, RECOMMENDATIONS_CACHE_TTL_SECONDS,
    INTERNAL_TASK_TOKEN,
    FALLBACK_PROFILE_IMAGES, photo_url_cache,
    ONBOARDING_TOTAL_STEPS, ONBOARDING_STEP_META,
    CITIES, NEIGHBORHOODS,
)

# ── Services ────────────────────────────────────────────────
from services.redis_service import (
    _rate_limit_key_suffix,
    _redis_consume_limit,
    _redis_reset_limit,
    _cache_key,
    _redis_get_text,
    _redis_set_text,
    _enqueue_payment_callback,
)
from services.telegram_service import (
    send_telegram_notification,
    send_admin_alert,
)
from services.storage_service import upload_provider_photo

# ── Utils ───────────────────────────────────────────────────
from utils.auth import (
    _sanitize_phone,
    _normalize_portal_phone,
    _hash_password,
    _verify_password,
    _portal_session_provider_id,
    _portal_generate_whatsapp_code,
    _portal_hash_verification_code,
    _portal_account_state,
    _portal_is_locked,
    _portal_admin_review_keyboard,
    _to_int_or_none,
    _extract_client_ip,
    _detect_device_type,
    _is_valid_callback_signature,
)
from utils.providers import (
    _to_string_list,
    _fallback_image,
    _build_gallery_urls,
    _normalize_provider,
    _normalize_recommendation,
    _telegram_contact_redirect,
    _cache_photo_path,
)
from utils.onboarding import (
    _normalize_onboarding_step,
    _parse_csv_values,
    _portal_onboarding_base_draft,
    _portal_get_onboarding_draft,
    _portal_set_onboarding_draft,
    _portal_clear_onboarding_draft,
    _portal_build_preview,
    _portal_compute_profile_strength,
    _portal_build_ranking_tips,
)
from payment_queue_utils import extract_callback_reference

# ── App Setup ───────────────────────────────────────────────
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


# ── File Upload Helper ──────────────────────────────────────

async def _save_provider_upload(provider_id: int, upload, prefix: str) -> Optional[str]:
    """Saves portal-uploaded image under static/uploads and returns app-local URL."""
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

    uploaded_url = upload_provider_photo(
        provider_id=provider_id,
        data=data,
        extension=ext,
        prefix=prefix,
        content_type=getattr(upload, "content_type", None),
    )
    if uploaded_url:
        return uploaded_url

    target_dir = Path("static/uploads/providers") / str(provider_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex}{ext}"
    target_path = target_dir / filename
    with open(target_path, "wb") as handle:
        handle.write(data)
    relative_url = f"/static/uploads/providers/{provider_id}/{filename}"
    return relative_url


# ── Photo Proxy ─────────────────────────────────────────────

@app.get("/photo/{file_id}")
async def get_photo(file_id: str):
    """
    Proxy endpoint to serve Telegram photos.
    Fetches file path from Telegram API and streams the photo bytes.
    Caches results to minimize API calls.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN not set, cannot fetch photo")
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


# ==================== ROUTES ====================

from routes.public import router as public_router
from routes.portal_auth import router as portal_auth_router
from routes.portal_onboarding import router as portal_onboarding_router
from routes.portal_dashboard import router as portal_dashboard_router
from routes.portal_actions import router as portal_actions_router
from routes.payments import router as payments_router
from routes.api import router as api_router

app.include_router(public_router)
app.include_router(portal_auth_router)
app.include_router(portal_onboarding_router)
app.include_router(portal_dashboard_router)
app.include_router(portal_actions_router)
app.include_router(payments_router)
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Run database migrations on startup."""
    try:
        from config import SUPPRESS_MIGRATIONS
        if not SUPPRESS_MIGRATIONS:
            db._run_startup_migrations()
            logger.info("Database migrations completed.")
    except Exception as e:
        logger.error(f"Error during database startup: {e}")

"""
Portal Dashboard Routes — Verifying phone, dashboard view, code regenerate.
"""
import logging
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    PORTAL_ADMIN_WHATSAPP,
    PORTAL_VERIFY_CODE_TTL_MINUTES,
    PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY,
    PORTAL_VERIFY_REGEN_WINDOW_SECONDS,
    PORTAL_ACCOUNT_APPROVED,
)
from database import Database
from services.redis_service import _redis_consume_limit, _get_redis_client
from services.telegram_service import send_admin_alert
from utils.auth import (
    _sanitize_phone, _portal_session_provider_id,
    _portal_account_state, _portal_admin_review_keyboard,
    _portal_generate_whatsapp_code, _portal_hash_verification_code,
)
from utils.providers import _to_string_list
from utils.onboarding import _portal_compute_profile_strength, _portal_onboarding_base_draft

db = Database()
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/provider/dashboard", response_class=HTMLResponse)
async def provider_portal_dashboard(request: Request, saved: Optional[int] = 0):
    """Provider dashboard for non-Telegram onboarding users."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)
    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url=f"/provider/verify-phone?status={_portal_account_state(provider)}", status_code=302)

    phone_code = provider.get("phone_verify_code")
    if not phone_code:
        phone_code = _portal_generate_whatsapp_code()
        db.set_portal_phone_verification_code(
            provider_id,
            phone_code,
            _portal_hash_verification_code(phone_code),
            ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
            mark_pending=False,
        )
        provider = db.get_portal_provider_by_id(provider_id) or provider

    photo_urls = _to_string_list(provider.get("profile_photos"))
    services_list = _to_string_list(provider.get("services"))
    languages_list = _to_string_list(provider.get("languages"))
    profile_strength = _portal_compute_profile_strength(
        draft=_portal_onboarding_base_draft(provider),
        photo_count=len(photo_urls),
    )

    return templates.TemplateResponse(
        "provider_dashboard.html",
        {
            "request": request,
            "provider": provider,
            "photo_urls": photo_urls,
            "services_list": services_list,
            "languages_list": languages_list,
            "saved": bool(saved),
            "admin_whatsapp": PORTAL_ADMIN_WHATSAPP,
            "phone_verify_code": phone_code,
            "profile_strength": profile_strength,
            "photo_count": len(photo_urls),
            "services_count": len(services_list),
            "languages_count": len(languages_list),
        },
    )


@router.get("/provider/verify-phone", response_class=HTMLResponse)
async def provider_portal_verify_phone(
    request: Request,
    status: Optional[str] = None,
    registered: Optional[int] = 0,
    regenerated: Optional[int] = 0,
    rate_limited: Optional[int] = 0,
):
    """Manual WhatsApp-based phone verification instructions page."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    state = _portal_account_state(provider)
    if state == PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url="/provider/dashboard", status_code=302)

    phone_code = provider.get("phone_verify_code")
    if not phone_code:
        phone_code = _portal_generate_whatsapp_code()
        db.set_portal_phone_verification_code(
            provider_id,
            phone_code,
            _portal_hash_verification_code(phone_code),
            ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
            mark_pending=True,
        )
        db.log_provider_verification_event(
            provider_id,
            "code_issued",
            payload={"ttl_minutes": PORTAL_VERIFY_CODE_TTL_MINUTES, "source": "verify_phone_page"},
        )
    return templates.TemplateResponse(
        "provider_verify_phone.html",
        {
            "request": request,
            "provider": provider,
            "admin_whatsapp": PORTAL_ADMIN_WHATSAPP,
            "phone_verify_code": phone_code,
            "account_state": state,
            "status": status or state,
            "registered": bool(registered),
            "regenerated": bool(regenerated),
            "rate_limited": bool(rate_limited),
            "admin_whatsapp_link": (
                f"https://wa.me/{_sanitize_phone(PORTAL_ADMIN_WHATSAPP)}?text={quote(phone_code)}"
                if _sanitize_phone(PORTAL_ADMIN_WHATSAPP)
                else None
            ),
        },
    )


@router.post("/provider/verify-phone/regenerate")
async def provider_portal_regenerate_verify_code(request: Request):
    """Regenerates manual WhatsApp verification code."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)
    if _portal_account_state(provider) == PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url="/provider/dashboard", status_code=302)
    allowed_regen, _ = _redis_consume_limit(
        key=f"rl:provider_verify_regen:{provider_id}",
        limit=PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY,
        window_seconds=PORTAL_VERIFY_REGEN_WINDOW_SECONDS,
    )
    if not allowed_regen:
        return RedirectResponse(url="/provider/verify-phone?rate_limited=1", status_code=303)
    if _get_redis_client() is None:
        regen_count = db.count_provider_verification_events(provider_id, "code_regenerated", hours=24)
        if regen_count >= PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY:
            return RedirectResponse(url="/provider/verify-phone?rate_limited=1", status_code=303)

    new_code = _portal_generate_whatsapp_code()
    db.set_portal_phone_verification_code(
        provider_id,
        new_code,
        _portal_hash_verification_code(new_code),
        ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
        mark_pending=True,
    )
    provider = db.get_portal_provider_by_id(provider_id)
    db.log_provider_verification_event(
        provider_id,
        "code_regenerated",
        payload={"ttl_minutes": PORTAL_VERIFY_CODE_TTL_MINUTES},
    )
    if provider:
        await send_admin_alert(
            (
                "♻️ PORTAL CODE REGENERATED\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📞 Phone: {provider.get('phone', '')}\n"
                f"🆔 Provider ID: {provider_id}\n"
                f"🔐 New Code: {new_code}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "Use this latest code for WhatsApp verification."
            ),
            reply_markup=_portal_admin_review_keyboard(int(provider.get("telegram_id"))),
        )
    return RedirectResponse(url="/provider/verify-phone?regenerated=1", status_code=303)

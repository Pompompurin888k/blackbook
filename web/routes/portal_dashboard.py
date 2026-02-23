"""
Portal Dashboard Routes - Email verification, dashboard view, and provider hub pages.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    BOOST_DURATION_HOURS,
    BOOST_PRICE,
    FREE_TRIAL_DAYS,
    PACKAGE_PRICES,
    PORTAL_ACCOUNT_APPROVED,
    PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY,
    PORTAL_VERIFY_CODE_TTL_MINUTES,
    PORTAL_VERIFY_REGEN_WINDOW_SECONDS,
    TELEGRAM_BOT_USERNAME,
)
from database import Database
from services.email_service import send_portal_verification_email
from services.redis_service import _get_redis_client, _redis_consume_limit
from utils.auth import (
    _mask_email,
    _normalize_portal_email,
    _portal_account_state,
    _portal_generate_email_code,
    _portal_hash_verification_code,
    _portal_is_verification_code_match,
    _portal_session_provider_id,
)
from utils.db_async import db_call
from utils.onboarding import _portal_compute_profile_strength, _portal_onboarding_base_draft
from utils.providers import _normalize_photo_sources, _to_string_list

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter()
db = Database()
logger = logging.getLogger(__name__)


def _verification_code_is_active(provider: dict) -> bool:
    if not provider:
        return False
    code_hash = provider.get("verification_code_hash")
    expires_at = provider.get("verification_code_expires_at")
    used_at = provider.get("verification_code_used_at")
    if not code_hash or used_at or not expires_at:
        return False
    now = datetime.now(expires_at.tzinfo) if getattr(expires_at, "tzinfo", None) else datetime.now()
    return expires_at > now


async def _send_verification_code(provider: dict, provider_id: int, event_type: str, source: str) -> bool:
    email = _normalize_portal_email(provider.get("email") or "")
    if not email:
        return False

    code = _portal_generate_email_code()
    code_hash = _portal_hash_verification_code(code)
    saved = await db_call(
        db.set_portal_email_verification_code,
        provider_id,
        code_hash,
        ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
        mark_pending=True,
    )
    if not saved:
        return False

    sent = await send_portal_verification_email(
        recipient=email,
        code=code,
        ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
        display_name=provider.get("display_name") or "",
    )
    await db_call(
        db.log_provider_verification_event,
        provider_id,
        event_type,
        payload={
            "ttl_minutes": PORTAL_VERIFY_CODE_TTL_MINUTES,
            "source": source,
            "delivery": "email",
            "sent": bool(sent),
        },
    )
    return sent


@router.get("/provider/dashboard", response_class=HTMLResponse)
async def provider_portal_dashboard(
    request: Request,
    saved: Optional[int] = 0,
    notice: Optional[str] = None,
    error: Optional[str] = None,
):
    """Provider dashboard for portal users."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED or provider.get("email_verified") is not True:
        return RedirectResponse(url=f"/provider/verify-email?status={_portal_account_state(provider)}", status_code=302)

    photo_urls = _normalize_photo_sources(provider.get("profile_photos"))[:5]
    services_list = _to_string_list(provider.get("services"))
    languages_list = _to_string_list(provider.get("languages"))
    profile_strength = _portal_compute_profile_strength(
        draft=_portal_onboarding_base_draft(provider),
        photo_count=len(photo_urls),
    )
    tg_id = int(provider.get("telegram_id") or 0)
    trial_eligible = (
        provider.get("is_verified") is True
        and provider.get("is_active") is False
        and not provider.get("trial_used")
        and not await db_call(db.has_successful_payment_for_provider, tg_id)
    ) if tg_id else False

    return templates.TemplateResponse(
        "provider_dashboard.html",
        {
            "request": request,
            "provider": provider,
            "photo_urls": photo_urls,
            "services_list": services_list,
            "languages_list": languages_list,
            "saved": bool(saved),
            "profile_strength": profile_strength,
            "photo_count": len(photo_urls),
            "services_count": len(services_list),
            "languages_count": len(languages_list),
            "notice": notice,
            "error": error,
            "free_trial_days": FREE_TRIAL_DAYS,
            "trial_eligible": trial_eligible,
        },
    )


@router.get("/provider/verify-email", response_class=HTMLResponse)
async def provider_portal_verify_email(
    request: Request,
    status: Optional[str] = None,
    registered: Optional[int] = 0,
    regenerated: Optional[int] = 0,
    rate_limited: Optional[int] = 0,
    invalid: Optional[int] = 0,
    expired: Optional[int] = 0,
    email_failed: Optional[int] = 0,
):
    """Email-based verification page for pending portal accounts."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    state = _portal_account_state(provider)
    if state == PORTAL_ACCOUNT_APPROVED and provider.get("email_verified") is True:
        return RedirectResponse(url="/provider/dashboard", status_code=302)

    email = _normalize_portal_email(provider.get("email") or "")
    if email and not _verification_code_is_active(provider):
        sent = await _send_verification_code(
            provider=provider,
            provider_id=provider_id,
            event_type="code_issued",
            source="verify_email_page",
        )
        if not sent:
            email_failed = 1
        provider = await db_call(db.get_portal_provider_by_id, provider_id) or provider

    return templates.TemplateResponse(
        "provider_verify_email.html",
        {
            "request": request,
            "provider": provider,
            "masked_email": _mask_email(email),
            "account_state": state,
            "status": status or state,
            "registered": bool(registered),
            "regenerated": bool(regenerated),
            "rate_limited": bool(rate_limited),
            "invalid": bool(invalid),
            "expired": bool(expired),
            "email_failed": bool(email_failed),
            "email_missing": not bool(email),
        },
    )


@router.post("/provider/verify-email/confirm")
async def provider_portal_confirm_email_code(request: Request):
    """Validates submitted email verification code and unlocks account."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    state = _portal_account_state(provider)
    if state == PORTAL_ACCOUNT_APPROVED and provider.get("email_verified") is True:
        return RedirectResponse(url="/provider/dashboard", status_code=302)

    form = await request.form()
    submitted_code = str(form.get("code", "")).strip().replace(" ", "")
    if not submitted_code:
        return RedirectResponse(url="/provider/verify-email?invalid=1", status_code=303)

    code_hash = str(provider.get("verification_code_hash") or "")
    expires_at = provider.get("verification_code_expires_at")
    used_at = provider.get("verification_code_used_at")

    if not code_hash or used_at or not expires_at:
        return RedirectResponse(url="/provider/verify-email?expired=1", status_code=303)

    now = datetime.now(expires_at.tzinfo) if getattr(expires_at, "tzinfo", None) else datetime.now()
    if expires_at <= now:
        return RedirectResponse(url="/provider/verify-email?expired=1", status_code=303)

    if not _portal_is_verification_code_match(submitted_code, code_hash):
        await db_call(
            db.log_provider_verification_event,
            provider_id,
            "code_failed",
            payload={"source": "verify_email_confirm"},
        )
        return RedirectResponse(url="/provider/verify-email?invalid=1", status_code=303)

    verified = await db_call(db.mark_portal_email_verified, provider_id)
    if not verified:
        return RedirectResponse(url="/provider/verify-email?email_failed=1", status_code=303)

    await db_call(
        db.log_provider_verification_event,
        provider_id,
        "email_verified",
        payload={"source": "verify_email_confirm"},
    )
    return RedirectResponse(url="/provider/dashboard?saved=1", status_code=303)


@router.post("/provider/verify-email/regenerate")
async def provider_portal_regenerate_verify_code(request: Request):
    """Regenerates and delivers a new email verification code."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    if _portal_account_state(provider) == PORTAL_ACCOUNT_APPROVED and provider.get("email_verified") is True:
        return RedirectResponse(url="/provider/dashboard", status_code=302)

    allowed_regen, _ = _redis_consume_limit(
        key=f"rl:provider_verify_regen:{provider_id}",
        limit=PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY,
        window_seconds=PORTAL_VERIFY_REGEN_WINDOW_SECONDS,
    )
    if not allowed_regen:
        return RedirectResponse(url="/provider/verify-email?rate_limited=1", status_code=303)

    if _get_redis_client() is None:
        regen_count = await db_call(
            db.count_provider_verification_events,
            provider_id,
            "code_regenerated",
            hours=24,
        )
        if regen_count >= PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY:
            return RedirectResponse(url="/provider/verify-email?rate_limited=1", status_code=303)

    sent = await _send_verification_code(
        provider=provider,
        provider_id=provider_id,
        event_type="code_regenerated",
        source="verify_email_regenerate",
    )

    if not sent:
        return RedirectResponse(url="/provider/verify-email?email_failed=1", status_code=303)
    return RedirectResponse(url="/provider/verify-email?regenerated=1", status_code=303)


@router.get("/provider/verify-phone", response_class=HTMLResponse)
async def provider_verify_phone_legacy_redirect():
    """Legacy route retained for backward compatibility."""
    return RedirectResponse(url="/provider/verify-email", status_code=302)


@router.post("/provider/verify-phone/regenerate")
async def provider_verify_phone_regen_legacy_redirect():
    """Legacy route retained for backward compatibility."""
    return RedirectResponse(url="/provider/verify-email/regenerate", status_code=307)


@router.get("/provider/analytics", response_class=HTMLResponse)
async def provider_portal_analytics(request: Request):
    """Provider analytics page showing profile views and clicks."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED or provider.get("email_verified") is not True:
        return RedirectResponse(url=f"/provider/verify-email?status={_portal_account_state(provider)}", status_code=302)

    stats = await db_call(db.get_provider_analytics_stats, provider_id)
    return templates.TemplateResponse(
        "provider_analytics.html",
        {
            "request": request,
            "provider": provider,
            "stats": stats,
        },
    )


@router.get("/provider/wallet", response_class=HTMLResponse)
async def provider_portal_wallet(
    request: Request,
    notice: Optional[str] = None,
    error: Optional[str] = None,
):
    """Provider wallet page showing subscription status and options."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED or provider.get("email_verified") is not True:
        return RedirectResponse(url=f"/provider/verify-email?status={_portal_account_state(provider)}", status_code=302)

    tg_id = int(provider.get("telegram_id") or 0)
    latest_payment = await db_call(db.get_latest_payment_for_provider, tg_id) if tg_id else None
    trial_eligible = (
        provider.get("is_verified") is True
        and provider.get("is_active") is False
        and not provider.get("trial_used")
        and not await db_call(db.has_successful_payment_for_provider, tg_id)
    ) if tg_id else False

    return templates.TemplateResponse(
        "provider_wallet.html",
        {
            "request": request,
            "provider": provider,
            "notice": notice,
            "error": error,
            "package_prices": PACKAGE_PRICES,
            "boost_price": BOOST_PRICE,
            "boost_duration_hours": BOOST_DURATION_HOURS,
            "free_trial_days": FREE_TRIAL_DAYS,
            "trial_eligible": trial_eligible,
            "latest_payment": latest_payment,
            "now": datetime.now,
            "bot_username": TELEGRAM_BOT_USERNAME,
        },
    )


@router.get("/provider/referrals", response_class=HTMLResponse)
async def provider_portal_referrals(
    request: Request,
    notice: Optional[str] = None,
    error: Optional[str] = None,
):
    """Provider referrals hub page."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED or provider.get("email_verified") is not True:
        return RedirectResponse(url=f"/provider/verify-email?status={_portal_account_state(provider)}", status_code=302)

    tg_id = provider.get("telegram_id")
    stats = {"referral_code": None, "total_referred": 0, "credits": 0}
    history = []

    try:
        actual_tg_id = int(tg_id) if tg_id is not None else 0
    except (TypeError, ValueError):
        actual_tg_id = 0

    if actual_tg_id != 0:
        stats = await db_call(db.get_referral_stats, actual_tg_id)
        history = await db_call(db.get_referral_history, actual_tg_id)

        if not stats.get("referral_code"):
            await db_call(db.generate_referral_code, actual_tg_id)
            stats = await db_call(db.get_referral_stats, actual_tg_id)

    return templates.TemplateResponse(
        "provider_referrals.html",
        {
            "request": request,
            "provider": provider,
            "stats": stats,
            "history": history,
            "bot_username": TELEGRAM_BOT_USERNAME,
            "notice": notice,
            "error": error,
        },
    )

"""
Portal Dashboard Routes — Verifying phone, dashboard view, code regenerate.
"""
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    PORTAL_ADMIN_WHATSAPP,
    PORTAL_VERIFY_CODE_TTL_MINUTES,
    PORTAL_VERIFY_CODE_REGEN_LIMIT_PER_DAY,
    PORTAL_VERIFY_REGEN_WINDOW_SECONDS,
    PORTAL_ACCOUNT_APPROVED,
    PACKAGE_PRICES,
    BOOST_PRICE,
    BOOST_DURATION_HOURS,
    FREE_TRIAL_DAYS,
    TELEGRAM_BOT_USERNAME,
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
async def provider_portal_dashboard(
    request: Request,
    saved: Optional[int] = 0,
    notice: Optional[str] = None,
    error: Optional[str] = None,
):
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

    photo_ids = _to_string_list(provider.get("profile_photos"))
    photo_urls = [
        item if item.startswith(("http://", "https://", "/")) else f"/photo/{item}"
        for item in photo_ids
    ][:5]
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
            "photo_count": len(photo_ids),
            "services_count": len(services_list),
            "languages_count": len(languages_list),
            "notice": notice,
            "error": error,
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


@router.get("/provider/analytics", response_class=HTMLResponse)
async def provider_portal_analytics(request: Request):
    """Provider Analytics page showing profile views and clicks."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
        
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)
        
    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url=f"/provider/verify-phone?status={_portal_account_state(provider)}", status_code=302)

    # Fetch stats
    stats = db.get_provider_analytics_stats(provider_id)

    return templates.TemplateResponse(
        "provider_analytics.html",
        {
            "request": request,
            "provider": provider,
            "stats": stats
        }
    )


@router.get("/provider/wallet", response_class=HTMLResponse)
async def provider_portal_wallet(
    request: Request,
    notice: Optional[str] = None,
    error: Optional[str] = None,
):
    """Provider Wallet page showing subscription status, renewal options, and boost info."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
        
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)
        
    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url=f"/provider/verify-phone?status={_portal_account_state(provider)}", status_code=302)

    tg_id = int(provider.get("telegram_id") or 0)
    latest_payment = db.get_latest_payment_for_provider(tg_id) if tg_id else None
    trial_eligible = (
        provider.get("is_verified") is True
        and provider.get("is_active") is False
        and not provider.get("trial_used")
        and not db.has_successful_payment_for_provider(tg_id)
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
        }
    )

@router.get("/provider/referrals", response_class=HTMLResponse)
async def provider_portal_referrals(
    request: Request,
    notice: Optional[str] = None,
    error: Optional[str] = None,
):
    """Provider Referrals Hub page."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
        
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)
        
    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url=f"/provider/verify-phone?status={_portal_account_state(provider)}", status_code=302)

    tg_id = provider.get("telegram_id")
    # In case tg_id is somehow missing or not an integer (though it should be)
    stats = {"referral_code": None, "total_referred": 0, "credits": 0}
    history = []
    
    try:
        actual_tg_id = int(tg_id) if tg_id is not None else 0
    except (TypeError, ValueError):
        actual_tg_id = 0

    if actual_tg_id != 0:
        stats = db.get_referral_stats(actual_tg_id)
        history = db.get_referral_history(actual_tg_id)
        
        # If they don't have a referral code yet, generate one.
        if not stats.get("referral_code"):
            db.generate_referral_code(actual_tg_id)
            stats = db.get_referral_stats(actual_tg_id)

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
        }
    )



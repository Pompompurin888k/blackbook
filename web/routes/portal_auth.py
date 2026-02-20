"""
Portal Auth Routes — Login, registration, and logout for providers.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    PORTAL_VERIFY_CODE_TTL_MINUTES,
    PORTAL_LOGIN_MAX_ATTEMPTS, PORTAL_LOGIN_LOCK_MINUTES,
    PORTAL_LOGIN_RATE_LIMIT_ATTEMPTS, PORTAL_LOGIN_RATE_WINDOW_SECONDS,
    PORTAL_ACCOUNT_APPROVED, PORTAL_ACCOUNT_PENDING,
    PORTAL_ACCOUNT_REJECTED, PORTAL_ACCOUNT_SUSPENDED,
)
from database import Database
from services.redis_service import _rate_limit_key_suffix, _redis_consume_limit, _redis_reset_limit
from services.telegram_service import send_admin_alert
from utils.auth import (
    _normalize_portal_phone, _hash_password, _verify_password,
    _portal_session_provider_id, _portal_generate_whatsapp_code,
    _portal_hash_verification_code, _portal_account_state,
    _portal_is_locked, _portal_admin_review_keyboard,
    _extract_client_ip,
)

db = Database()
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/provider", response_class=HTMLResponse)
async def provider_portal_auth(request: Request, error: Optional[str] = None, success: Optional[str] = None):
    """Provider portal auth page (phone + password)."""
    provider_id = _portal_session_provider_id(request)
    if provider_id:
        provider = db.get_portal_provider_by_id(provider_id)
        if not provider:
            request.session.clear()
        else:
            state = _portal_account_state(provider)
            if state == PORTAL_ACCOUNT_APPROVED:
                return RedirectResponse(url="/provider/dashboard", status_code=302)
            return RedirectResponse(url=f"/provider/verify-phone?status={state}", status_code=302)
    return templates.TemplateResponse(
        "provider_auth.html",
        {
            "request": request,
            "error": error,
            "success": success,
        },
    )


@router.post("/provider/register")
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
    provider_tg_id = int(created["telegram_id"])
    request.session["provider_portal_id"] = provider_id
    verify_code = _portal_generate_whatsapp_code()
    code_hash = _portal_hash_verification_code(verify_code)
    db.set_portal_phone_verification_code(
        provider_id,
        verify_code,
        code_hash,
        ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
        mark_pending=True,
    )
    db.log_provider_verification_event(
        provider_id,
        "account_created",
        payload={"phone": phone, "display_name": display_name},
    )
    db.log_provider_verification_event(
        provider_id,
        "code_issued",
        payload={"ttl_minutes": PORTAL_VERIFY_CODE_TTL_MINUTES},
    )
    await send_admin_alert(
        (
            "🆕 PORTAL SIGNUP - PENDING REVIEW\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Name: {display_name}\n"
            f"📞 Phone: {phone}\n"
            f"🆔 Provider ID: {provider_id}\n"
            f"🔐 WhatsApp Code: {verify_code}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Next step:\n"
            "1. Confirm sender number + code on WhatsApp\n"
            "2. Tap Approve or Reject below"
        ),
        reply_markup=_portal_admin_review_keyboard(provider_tg_id),
    )
    return RedirectResponse(url="/provider/verify-phone?registered=1", status_code=303)


@router.post("/provider/login")
async def provider_portal_login(request: Request):
    """Logs in an existing portal provider account."""
    form = await request.form()
    phone = _normalize_portal_phone(str(form.get("phone", "")).strip())
    password = str(form.get("password", ""))
    client_ip = _extract_client_ip(request)
    login_rate_key = (
        f"rl:provider_login:{_rate_limit_key_suffix(client_ip)}:"
        f"{_rate_limit_key_suffix(phone or 'unknown')}"
    )
    allowed_attempt, _ = _redis_consume_limit(
        key=login_rate_key,
        limit=PORTAL_LOGIN_RATE_LIMIT_ATTEMPTS,
        window_seconds=PORTAL_LOGIN_RATE_WINDOW_SECONDS,
    )
    if not allowed_attempt:
        wait_minutes = max(1, PORTAL_LOGIN_RATE_WINDOW_SECONDS // 60)
        return templates.TemplateResponse(
            "provider_auth.html",
            {
                "request": request,
                "error": f"Too many login attempts from this network. Try again in about {wait_minutes} minutes.",
                "success": None,
            },
            status_code=429,
        )

    provider = db.get_portal_provider_by_phone(phone) if phone else None
    if not provider:
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": "Invalid phone or password.", "success": None},
            status_code=401,
        )
    if _portal_is_locked(provider):
        locked_until = provider.get("locked_until")
        locked_text = (
            locked_until.strftime("%H:%M")
            if hasattr(locked_until, "strftime")
            else "later"
        )
        return templates.TemplateResponse(
            "provider_auth.html",
            {
                "request": request,
                "error": f"Too many failed logins. Try again after {locked_text}.",
                "success": None,
            },
            status_code=423,
        )
    stored_hash = provider.get("portal_password_hash")
    if not _verify_password(password, stored_hash):
        failure = db.register_portal_login_failure(
            int(provider["id"]),
            max_attempts=PORTAL_LOGIN_MAX_ATTEMPTS,
            lock_minutes=PORTAL_LOGIN_LOCK_MINUTES,
        )
        db.log_provider_verification_event(
            int(provider["id"]),
            "login_failed",
            payload={"phone": phone},
        )
        if failure and failure.get("locked_until"):
            locked_until = failure.get("locked_until")
            locked_text = (
                locked_until.strftime("%H:%M")
                if hasattr(locked_until, "strftime")
                else "later"
            )
            message = f"Too many failed logins. Try again after {locked_text}."
        else:
            message = "Invalid phone or password."
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": message, "success": None},
            status_code=401,
        )

    db.reset_portal_login_failures(int(provider["id"]))
    _redis_reset_limit(login_rate_key)
    db.log_provider_verification_event(
        int(provider["id"]),
        "login_success",
        payload={"phone": phone},
    )

    request.session["provider_portal_id"] = int(provider["id"])
    state = _portal_account_state(provider)
    if state == PORTAL_ACCOUNT_SUSPENDED:
        return templates.TemplateResponse(
            "provider_auth.html",
            {
                "request": request,
                "error": "This account is suspended. Contact support/admin.",
                "success": None,
            },
            status_code=403,
        )
    if state != PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url=f"/provider/verify-phone?status={state}", status_code=303)
    return RedirectResponse(url="/provider/dashboard", status_code=303)


@router.post("/provider/logout")
async def provider_portal_logout(request: Request):
    """Disconnects the provider."""
    request.session.clear()
    return RedirectResponse(url="/provider?success=Logged+out+successfully", status_code=303)

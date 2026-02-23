"""
Portal Auth Routes - Login, registration, and logout for providers.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    PORTAL_VERIFY_CODE_TTL_MINUTES,
    PORTAL_LOGIN_MAX_ATTEMPTS,
    PORTAL_LOGIN_LOCK_MINUTES,
    PORTAL_LOGIN_RATE_LIMIT_ATTEMPTS,
    PORTAL_LOGIN_RATE_WINDOW_SECONDS,
    PORTAL_PASSWORD_RESET_CODE_TTL_MINUTES,
    PORTAL_PASSWORD_RESET_REQUEST_LIMIT,
    PORTAL_PASSWORD_RESET_REQUEST_WINDOW_SECONDS,
    PORTAL_ACCOUNT_APPROVED,
    PORTAL_ACCOUNT_SUSPENDED,
)
from database import Database
from services.email_service import send_portal_password_reset_email, send_portal_verification_email
from services.redis_service import _rate_limit_key_suffix, _redis_consume_limit, _redis_reset_limit
from utils.db_async import db_call
from utils.auth import (
    _extract_client_ip,
    _hash_password,
    _normalize_portal_email,
    _normalize_portal_phone,
    _portal_account_state,
    _portal_generate_email_code,
    _portal_hash_verification_code,
    _portal_is_verification_code_match,
    _portal_is_locked,
    _portal_session_provider_id,
    _verify_password,
)

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter()
db = Database()
logger = logging.getLogger(__name__)


@router.get("/provider", response_class=HTMLResponse)
async def provider_portal_auth(request: Request, error: Optional[str] = None, success: Optional[str] = None):
    """Provider portal auth page (email + password)."""
    provider_id = _portal_session_provider_id(request)
    if provider_id:
        provider = await db_call(db.get_portal_provider_by_id, provider_id)
        if not provider:
            request.session.clear()
        else:
            state = _portal_account_state(provider)
            if state == PORTAL_ACCOUNT_APPROVED and provider.get("email_verified") is True:
                return RedirectResponse(url="/provider/dashboard", status_code=302)
            return RedirectResponse(url=f"/provider/verify-email?status={state}", status_code=302)
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
    """Creates a new non-Telegram provider account and sends email verification code."""
    form = await request.form()
    display_name = str(form.get("display_name", "")).strip()
    phone = _normalize_portal_phone(str(form.get("phone", "")).strip())
    email = _normalize_portal_email(str(form.get("email", "")).strip())
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
    if not email:
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": "Enter a valid email address.", "success": None},
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

    created = await db_call(
        db.create_portal_provider_account,
        phone=phone,
        email=email,
        password_hash=_hash_password(password),
        display_name=display_name,
    )
    if not created:
        return templates.TemplateResponse(
            "provider_auth.html",
            {
                "request": request,
                "error": "This phone or email is already registered. Please log in instead.",
                "success": None,
            },
            status_code=400,
        )

    provider_id = int(created["id"])
    request.session["provider_portal_id"] = provider_id

    verify_code = _portal_generate_email_code()
    code_hash = _portal_hash_verification_code(verify_code)
    code_saved = await db_call(
        db.set_portal_email_verification_code,
        provider_id,
        code_hash,
        ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
        mark_pending=True,
    )
    if not code_saved:
        return templates.TemplateResponse(
            "provider_auth.html",
            {
                "request": request,
                "error": "Account created, but verification setup failed. Please try logging in again.",
                "success": None,
            },
            status_code=500,
        )

    await db_call(
        db.log_provider_verification_event,
        provider_id,
        "account_created",
        payload={"phone": phone, "email": email, "display_name": display_name},
    )

    email_sent = await send_portal_verification_email(
        recipient=email,
        code=verify_code,
        ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
        display_name=display_name,
    )

    await db_call(
        db.log_provider_verification_event,
        provider_id,
        "code_issued",
        payload={
            "ttl_minutes": PORTAL_VERIFY_CODE_TTL_MINUTES,
            "source": "register",
            "delivery": "email",
            "sent": bool(email_sent),
        },
    )

    if not email_sent:
        return RedirectResponse(url="/provider/verify-email?registered=1&email_failed=1", status_code=303)
    return RedirectResponse(url="/provider/verify-email?registered=1", status_code=303)


@router.post("/provider/login")
async def provider_portal_login(request: Request):
    """Logs in an existing portal provider account."""
    form = await request.form()
    email = _normalize_portal_email(str(form.get("email", "")).strip())
    password = str(form.get("password", ""))
    client_ip = _extract_client_ip(request)
    login_rate_key = (
        f"rl:provider_login:{_rate_limit_key_suffix(client_ip)}:"
        f"{_rate_limit_key_suffix(email or 'unknown')}"
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

    provider = await db_call(db.get_portal_provider_by_email, email) if email else None
    if not provider:
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": "Invalid email or password.", "success": None},
            status_code=401,
        )

    if _portal_is_locked(provider):
        locked_until = provider.get("locked_until")
        locked_text = locked_until.strftime("%H:%M") if hasattr(locked_until, "strftime") else "later"
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
        failure = await db_call(
            db.register_portal_login_failure,
            int(provider["id"]),
            max_attempts=PORTAL_LOGIN_MAX_ATTEMPTS,
            lock_minutes=PORTAL_LOGIN_LOCK_MINUTES,
        )
        await db_call(
            db.log_provider_verification_event,
            int(provider["id"]),
            "login_failed",
            payload={"email": email},
        )
        if failure and failure.get("locked_until"):
            locked_until = failure.get("locked_until")
            locked_text = locked_until.strftime("%H:%M") if hasattr(locked_until, "strftime") else "later"
            message = f"Too many failed logins. Try again after {locked_text}."
        else:
            message = "Invalid email or password."
        return templates.TemplateResponse(
            "provider_auth.html",
            {"request": request, "error": message, "success": None},
            status_code=401,
        )

    await db_call(db.reset_portal_login_failures, int(provider["id"]))
    _redis_reset_limit(login_rate_key)
    await db_call(
        db.log_provider_verification_event,
        int(provider["id"]),
        "login_success",
        payload={"email": email},
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

    if state != PORTAL_ACCOUNT_APPROVED or provider.get("email_verified") is not True:
        return RedirectResponse(url=f"/provider/verify-email?status={state}", status_code=303)
    return RedirectResponse(url="/provider/dashboard", status_code=303)


@router.get("/provider/password-reset", response_class=HTMLResponse)
async def provider_portal_password_reset(
    request: Request,
    sent: Optional[int] = 0,
    invalid: Optional[int] = 0,
    expired: Optional[int] = 0,
    rate_limited: Optional[int] = 0,
):
    """Renders provider password-reset page."""
    return templates.TemplateResponse(
        "provider_password_reset.html",
        {
            "request": request,
            "sent": bool(sent),
            "invalid": bool(invalid),
            "expired": bool(expired),
            "rate_limited": bool(rate_limited),
        },
    )


@router.post("/provider/password-reset/request")
async def provider_portal_password_reset_request(request: Request):
    """Issues and sends a one-time password-reset code to provider email."""
    form = await request.form()
    email = _normalize_portal_email(str(form.get("email", "")).strip())
    client_ip = _extract_client_ip(request)
    reset_rate_key = (
        f"rl:provider_password_reset:{_rate_limit_key_suffix(client_ip)}:"
        f"{_rate_limit_key_suffix(email or 'unknown')}"
    )
    allowed_attempt, _ = _redis_consume_limit(
        key=reset_rate_key,
        limit=PORTAL_PASSWORD_RESET_REQUEST_LIMIT,
        window_seconds=PORTAL_PASSWORD_RESET_REQUEST_WINDOW_SECONDS,
    )
    if not allowed_attempt:
        return RedirectResponse(url="/provider/password-reset?rate_limited=1", status_code=303)

    provider = await db_call(db.get_portal_provider_by_email, email) if email else None
    if provider:
        provider_id = int(provider["id"])
        reset_code = _portal_generate_email_code()
        reset_hash = _portal_hash_verification_code(reset_code)
        code_saved = await db_call(
            db.set_portal_password_reset_code,
            provider_id,
            reset_hash,
            ttl_minutes=PORTAL_PASSWORD_RESET_CODE_TTL_MINUTES,
        )
        email_sent = False
        if code_saved:
            email_sent = await send_portal_password_reset_email(
                recipient=email,
                code=reset_code,
                ttl_minutes=PORTAL_PASSWORD_RESET_CODE_TTL_MINUTES,
                display_name=provider.get("display_name") or "",
            )

        await db_call(
            db.log_provider_verification_event,
            provider_id,
            "password_reset_requested",
            payload={
                "delivery": "email",
                "ttl_minutes": PORTAL_PASSWORD_RESET_CODE_TTL_MINUTES,
                "code_saved": bool(code_saved),
                "sent": bool(email_sent),
            },
        )

    # Always use the same response to prevent account-enumeration signals.
    return RedirectResponse(url="/provider/password-reset?sent=1", status_code=303)


@router.post("/provider/password-reset/confirm")
async def provider_portal_password_reset_confirm(request: Request):
    """Validates reset code and updates provider password."""
    form = await request.form()
    email = _normalize_portal_email(str(form.get("email", "")).strip())
    submitted_code = str(form.get("code", "")).strip().replace(" ", "")
    password = str(form.get("password", ""))
    confirm_password = str(form.get("confirm_password", ""))

    if not email or not submitted_code or len(password) < 6 or password != confirm_password:
        return RedirectResponse(url="/provider/password-reset?invalid=1", status_code=303)

    provider = await db_call(db.get_portal_provider_by_email, email)
    if not provider:
        return RedirectResponse(url="/provider/password-reset?invalid=1", status_code=303)

    provider_id = int(provider["id"])
    code_hash = str(provider.get("password_reset_code_hash") or "")
    expires_at = provider.get("password_reset_code_expires_at")
    used_at = provider.get("password_reset_code_used_at")

    if not code_hash or used_at or not expires_at:
        return RedirectResponse(url="/provider/password-reset?expired=1", status_code=303)

    now = datetime.now(expires_at.tzinfo) if getattr(expires_at, "tzinfo", None) else datetime.now()
    if expires_at <= now:
        return RedirectResponse(url="/provider/password-reset?expired=1", status_code=303)

    if not _portal_is_verification_code_match(submitted_code, code_hash):
        await db_call(
            db.log_provider_verification_event,
            provider_id,
            "password_reset_code_failed",
            payload={"email": email},
        )
        return RedirectResponse(url="/provider/password-reset?invalid=1", status_code=303)

    updated = await db_call(
        db.reset_portal_password,
        provider_id,
        _hash_password(password),
    )
    if not updated:
        return RedirectResponse(url="/provider/password-reset?invalid=1", status_code=303)

    await db_call(
        db.log_provider_verification_event,
        provider_id,
        "password_reset_completed",
        payload={"email": email},
    )
    request.session.clear()
    return RedirectResponse(
        url="/provider?success=Password+updated.+Log+in+with+your+new+password",
        status_code=303,
    )


@router.post("/provider/logout")
async def provider_portal_logout(request: Request):
    """Disconnects the provider."""
    request.session.clear()
    return RedirectResponse(url="/provider?success=Logged+out+successfully", status_code=303)

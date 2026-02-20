"""
Portal action routes for provider parity with Telegram flows.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import (
    ADMIN_CHAT_ID,
    BOOST_DURATION_HOURS,
    BOOST_PRICE,
    FREE_TRIAL_DAYS,
    PACKAGE_PRICES,
    PORTAL_ACCOUNT_APPROVED,
    VALID_PACKAGE_DAYS,
)
from database import Database
from services.metapay import initiate_stk_push
from services.telegram_service import send_admin_alert
from utils.auth import _portal_account_state, _portal_session_provider_id, _sanitize_phone
from utils.providers import _to_string_list

router = APIRouter()
db = Database()
templates = Jinja2Templates(directory="templates")


def _portal_redirect(path: str, **params: object) -> RedirectResponse:
    safe = {k: v for k, v in params.items() if v not in (None, "", False)}
    if safe:
        return RedirectResponse(url=f"{path}?{urlencode(safe)}", status_code=303)
    return RedirectResponse(url=path, status_code=303)


def _get_provider_or_redirect(request: Request) -> tuple[Optional[dict], Optional[RedirectResponse]]:
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return None, RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return None, RedirectResponse(url="/provider?error=Session+expired", status_code=302)
    state = _portal_account_state(provider)
    if state != PORTAL_ACCOUNT_APPROVED:
        return None, RedirectResponse(url=f"/provider/verify-phone?status={state}", status_code=302)
    return provider, None


def _is_trial_eligible(provider: dict) -> bool:
    if not provider:
        return False
    return (
        provider.get("is_verified") is True
        and provider.get("is_active") is False
        and not provider.get("trial_used")
    )


def _normalize_mpesa_phone(phone: str) -> str:
    clean = _sanitize_phone(phone)
    return clean if clean.startswith("254") and len(clean) >= 12 else ""


@router.post("/provider/status/toggle")
async def provider_toggle_status(request: Request):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)
    if tg_id == 0:
        return _portal_redirect("/provider/dashboard", error="Provider account missing Telegram ID.")
    if not provider.get("is_active"):
        return _portal_redirect("/provider/dashboard", error="Activate a package before toggling visibility.")

    is_online = db.toggle_online_status(tg_id)
    notice = "You are now online and visible with a Live badge." if is_online else "You are now offline and hidden."
    return _portal_redirect("/provider/dashboard", notice=notice)


@router.post("/provider/photos/delete/{photo_index}")
async def provider_delete_photo(request: Request, photo_index: int):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)
    if tg_id == 0:
        return _portal_redirect("/provider/onboarding", step=4, error="Provider account missing Telegram ID.")
    photos = _to_string_list(provider.get("profile_photos"))
    if photo_index < 0 or photo_index >= len(photos):
        return _portal_redirect("/provider/onboarding", step=4, error="Photo not found.")
    photos.pop(photo_index)
    db.save_provider_photos(tg_id, photos)
    return _portal_redirect("/provider/onboarding", step=4, saved=1)


@router.post("/provider/photos/primary/{photo_index}")
async def provider_set_primary_photo(request: Request, photo_index: int):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)
    if tg_id == 0:
        return _portal_redirect("/provider/onboarding", step=4, error="Provider account missing Telegram ID.")
    photos = _to_string_list(provider.get("profile_photos"))
    if photo_index <= 0 or photo_index >= len(photos):
        return _portal_redirect("/provider/onboarding", step=4, error="Invalid photo selection.")
    selected = photos.pop(photo_index)
    photos.insert(0, selected)
    db.save_provider_photos(tg_id, photos)
    return _portal_redirect("/provider/onboarding", step=4, saved=1)


@router.post("/provider/wallet/trial-activate")
async def provider_activate_trial(request: Request):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)

    if not _is_trial_eligible(provider):
        return _portal_redirect(
            "/provider/wallet",
            error="Trial unavailable. Eligibility requires verified, inactive, and unused trial status.",
        )
    if db.has_successful_payment_for_provider(tg_id):
        return _portal_redirect("/provider/wallet", error="Trial is only available before first successful payment.")

    activated = db.activate_free_trial(tg_id, FREE_TRIAL_DAYS)
    if not activated:
        return _portal_redirect("/provider/wallet", error="Could not activate trial right now.")

    db.log_funnel_event(tg_id, "trial_started", {"days": FREE_TRIAL_DAYS, "source": "portal"})
    db.log_funnel_event(tg_id, "active_live", {"source": "portal_trial"})
    return _portal_redirect("/provider/wallet", notice=f"Free trial activated for {FREE_TRIAL_DAYS} days.")


@router.post("/provider/wallet/pay")
async def provider_wallet_pay(
    request: Request,
    package_days: int = Form(...),
    phone: str = Form(""),
):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect

    tg_id = int(provider.get("telegram_id") or 0)
    if package_days not in VALID_PACKAGE_DAYS:
        return _portal_redirect("/provider/wallet", error="Invalid package selected.")

    if package_days != 0 and not provider.get("is_verified"):
        return _portal_redirect("/provider/wallet", error="Profile must be verified before payment.")
    if package_days == 0 and not provider.get("is_active"):
        return _portal_redirect("/provider/wallet", error="Boost requires an active package.")

    amount = BOOST_PRICE if package_days == 0 else PACKAGE_PRICES.get(package_days)
    if not amount:
        return _portal_redirect("/provider/wallet", error="Package pricing unavailable.")

    normalized_phone = _normalize_mpesa_phone(phone or str(provider.get("phone") or ""))
    if not normalized_phone:
        return _portal_redirect("/provider/wallet", error="Enter a valid M-Pesa phone number.")

    db.update_provider_profile(tg_id, {"phone": normalized_phone})
    result = await initiate_stk_push(normalized_phone, int(amount), tg_id, package_days)
    if not result.get("success"):
        return _portal_redirect("/provider/wallet", error=result.get("message") or "Payment initiation failed.")

    reference = result.get("reference")
    if reference:
        db.log_payment(tg_id, int(amount), str(reference), "PENDING", package_days)
    db.log_funnel_event(
        tg_id,
        "paid_intent",
        {
            "source": "portal_wallet",
            "days": package_days,
            "amount": amount,
            "reference": reference,
            "is_boost": package_days == 0,
        },
    )
    item_label = f"{BOOST_DURATION_HOURS}h boost" if package_days == 0 else f"{package_days}-day package"
    return _portal_redirect(
        "/provider/wallet",
        notice=f"STK prompt sent to {normalized_phone} for {item_label}. Ref: {reference}",
    )


@router.get("/provider/safety", response_class=HTMLResponse)
async def provider_safety_page(
    request: Request,
    notice: Optional[str] = None,
    error: Optional[str] = None,
    check_phone: Optional[str] = None,
    check_status: Optional[str] = None,
    check_reason: Optional[str] = None,
):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)
    active_session = db.get_active_session(tg_id)
    return templates.TemplateResponse(
        "provider_safety.html",
        {
            "request": request,
            "provider": provider,
            "active_session": active_session,
            "notice": notice,
            "error": error,
            "check_phone": check_phone,
            "check_status": check_status,
            "check_reason": check_reason,
            "now": datetime.now,
        },
    )


@router.post("/provider/safety/check")
async def provider_safety_check(request: Request, phone: str = Form(...)):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    normalized_phone = _normalize_mpesa_phone(phone)
    if not normalized_phone:
        return _portal_redirect("/provider/safety", error="Enter a valid phone number.")

    result = db.check_blacklist(normalized_phone)
    if result.get("blacklisted"):
        return _portal_redirect(
            "/provider/safety",
            check_phone=normalized_phone,
            check_status="blacklisted",
            check_reason=result.get("reason", "Reported risk"),
        )
    return _portal_redirect("/provider/safety", check_phone=normalized_phone, check_status="clear")


@router.post("/provider/safety/report")
async def provider_safety_report(
    request: Request,
    phone: str = Form(...),
    reason: str = Form(...),
):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)
    normalized_phone = _normalize_mpesa_phone(phone)
    if not normalized_phone:
        return _portal_redirect("/provider/safety", error="Enter a valid phone number.")
    reason_text = (reason or "").strip()
    if len(reason_text) < 3:
        return _portal_redirect("/provider/safety", error="Provide a clear report reason.")

    ok = db.add_to_blacklist(normalized_phone, reason_text, tg_id)
    if not ok:
        return _portal_redirect("/provider/safety", error="Could not save report. Try again.")

    if ADMIN_CHAT_ID:
        await send_admin_alert(
            (
                "NEW PORTAL BLACKLIST REPORT\n"
                f"Provider: {provider.get('display_name', 'Unknown')} ({tg_id})\n"
                f"Phone: {normalized_phone}\n"
                f"Reason: {reason_text}"
            )
        )
    return _portal_redirect("/provider/safety", notice="Client number reported and saved to blacklist.")


@router.post("/provider/safety/session/start")
async def provider_safety_start_session(request: Request, minutes: int = Form(...)):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)

    duration = int(minutes)
    if duration < 15 or duration > 480:
        return _portal_redirect("/provider/safety", error="Session duration must be 15-480 minutes.")
    session_id = db.start_session(tg_id, duration)
    if not session_id:
        return _portal_redirect("/provider/safety", error="Could not start safety session.")
    return _portal_redirect("/provider/safety", notice=f"Safety session started for {duration} minutes.")


@router.post("/provider/safety/session/checkin")
async def provider_safety_checkin(request: Request):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)
    success = db.end_session(tg_id)
    if not success:
        return _portal_redirect("/provider/safety", error="No active session found.")
    return _portal_redirect("/provider/safety", notice="Check-in confirmed. Session closed.")


@router.get("/provider/support", response_class=HTMLResponse)
async def provider_support_page(request: Request):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    admin_contact = ADMIN_CHAT_ID if ADMIN_CHAT_ID else "Admin"
    if admin_contact and str(admin_contact).isdigit():
        contact_line = f"Telegram ID: {admin_contact}"
    elif admin_contact:
        contact_line = f"Telegram: @{str(admin_contact).lstrip('@')}"
    else:
        contact_line = "Contact: Admin"
    return templates.TemplateResponse(
        "provider_support.html",
        {"request": request, "provider": provider, "contact_line": contact_line},
    )


@router.get("/provider/rules", response_class=HTMLResponse)
async def provider_rules_page(request: Request):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("provider_rules.html", {"request": request, "provider": provider})


@router.post("/provider/referrals/reward/{reward_id}")
async def provider_claim_referral_reward(
    request: Request,
    reward_id: int,
    choice: str = Form(...),
):
    provider, redirect = _get_provider_or_redirect(request)
    if redirect:
        return redirect
    tg_id = int(provider.get("telegram_id") or 0)
    reward = db.get_referral_reward(reward_id)
    if not reward:
        return _portal_redirect("/provider/referrals", error="Reward not found.")
    if int(reward.get("referrer_tg_id") or 0) != tg_id:
        return _portal_redirect("/provider/referrals", error="This reward does not belong to your account.")
    if reward.get("is_claimed"):
        return _portal_redirect("/provider/referrals", error="Reward already claimed.")

    if choice == "credit":
        ok = db.add_referral_credits(tg_id, int(reward.get("reward_credit") or 0))
        if not ok:
            return _portal_redirect("/provider/referrals", error="Could not add reward credit.")
        db.mark_referral_reward_claimed(reward_id, "credit")
        return _portal_redirect("/provider/referrals", notice=f"Reward claimed: +{reward.get('reward_credit', 0)} KES.")

    if choice == "days":
        ok = db.extend_subscription(tg_id, int(reward.get("reward_days") or 0))
        if not ok:
            return _portal_redirect("/provider/referrals", error="Could not extend subscription.")
        db.mark_referral_reward_claimed(reward_id, "days")
        return _portal_redirect("/provider/referrals", notice=f"Reward claimed: +{reward.get('reward_days', 0)} days.")

    return _portal_redirect("/provider/referrals", error="Invalid reward choice.")

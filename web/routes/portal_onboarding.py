"""
Portal Onboarding Routes — Multi-step profile completion wizard.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    PORTAL_MAX_PROFILE_PHOTOS, PORTAL_MIN_PROFILE_PHOTOS,
    PORTAL_RECOMMENDED_PROFILE_PHOTOS,
    PORTAL_VERIFY_CODE_TTL_MINUTES,
    PORTAL_ACCOUNT_APPROVED,
    CITIES, NEIGHBORHOODS,
    ONBOARDING_TOTAL_STEPS, ONBOARDING_STEP_META,
)
from database import Database
from services.telegram_service import send_admin_alert
from utils.auth import (
    _portal_session_provider_id, _to_int_or_none,
    _portal_account_state, _portal_admin_review_keyboard,
    _portal_generate_whatsapp_code, _portal_hash_verification_code,
)
from utils.providers import _to_string_list
from utils.onboarding import (
    _normalize_onboarding_step, _parse_csv_values,
    _portal_get_onboarding_draft, _portal_set_onboarding_draft,
    _portal_clear_onboarding_draft, _portal_build_preview,
    _portal_compute_profile_strength, _portal_build_ranking_tips,
)

# Shared upload handler logic resides in main.py, but can be imported if extracted.
# For now, we import `_save_provider_upload`, meaning we should put it in `utils/providers.py`
# or a new `utils/uploads.py`. Let's import it from main since it's there, but actually
# we wrote it in the new main.py string. I'll import from `main`.
from main import _save_provider_upload

db = Database()
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

router = APIRouter()
logger = logging.getLogger(__name__)


def _render_provider_onboarding_template(
    request: Request,
    provider: dict,
    draft: dict,
    step: int,
    error: Optional[str] = None,
    show_saved_toast: bool = False,
):
    """Renders the multi-step portal onboarding screen."""
    photo_ids = _to_string_list(provider.get("profile_photos"))
    photo_urls = [
        item if item.startswith(("http://", "https://", "/")) else f"/photo/{item}"
        for item in photo_ids
    ][:PORTAL_MAX_PROFILE_PHOTOS]
    preview = _portal_build_preview(
        draft=draft,
        photo_urls=photo_urls,
    )
    profile_strength = _portal_compute_profile_strength(
        draft=draft,
        photo_count=len(photo_urls),
    )
    ranking_tips = _portal_build_ranking_tips(draft=draft, photo_count=len(photo_urls))
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
            "recommended_photos": PORTAL_RECOMMENDED_PROFILE_PHOTOS,
            "photo_slot_count": min(PORTAL_MAX_PROFILE_PHOTOS, max(5, PORTAL_RECOMMENDED_PROFILE_PHOTOS)),
            "preview": preview,
            "profile_strength": profile_strength,
            "ranking_tips": ranking_tips,
            "show_saved_toast": show_saved_toast,
        },
    )


@router.get("/provider/onboarding", response_class=HTMLResponse)
async def provider_portal_onboarding(
    request: Request,
    step: Optional[int] = 1,
    saved: Optional[int] = 0,
    error: Optional[str] = None,
):
    """Multi-step onboarding wizard for non-Telegram providers."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)
    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url=f"/provider/verify-phone?status={_portal_account_state(provider)}", status_code=302)
    current_step = _normalize_onboarding_step(step)
    draft = _portal_get_onboarding_draft(request, provider)
    _portal_set_onboarding_draft(request, draft)
    return _render_provider_onboarding_template(
        request=request,
        provider=provider,
        draft=draft,
        step=current_step,
        error=error,
        show_saved_toast=bool(saved),
    )


@router.post("/provider/onboarding")
async def provider_portal_onboarding_submit(request: Request):
    """Handles step navigation and final onboarding submission."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)
    provider = db.get_portal_provider_by_id(provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)
    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED:
        return RedirectResponse(url=f"/provider/verify-phone?status={_portal_account_state(provider)}", status_code=302)

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
            url=f"/provider/onboarding?step={max(1, step - 1)}&saved=1",
            status_code=303,
        )

    if step < ONBOARDING_TOTAL_STEPS:
        return RedirectResponse(url=f"/provider/onboarding?step={step + 1}&saved=1", status_code=303)

    # Final step: save to DB and submit.
    existing_photo_urls = _to_string_list(provider.get("profile_photos"))
    upload_items = form.getlist("photos")
    for upload in upload_items:
        if len(existing_photo_urls) >= PORTAL_MAX_PROFILE_PHOTOS:
            break
        saved_url = await _save_provider_upload(provider_id, upload, "profile")
        if saved_url:
            existing_photo_urls.append(saved_url)

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
    phone_code = provider_after.get("phone_verify_code")
    if not phone_code:
        phone_code = _portal_generate_whatsapp_code()
        db.set_portal_phone_verification_code(
            provider_id,
            phone_code,
            _portal_hash_verification_code(phone_code),
            ttl_minutes=PORTAL_VERIFY_CODE_TTL_MINUTES,
            mark_pending=False,
        )

    await send_admin_alert(
        (
            "📝 PORTAL PROFILE SUBMITTED\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Name: {display_name or provider.get('display_name', 'Unknown')}\n"
            f"📞 Phone: {provider.get('phone', '')}\n"
            f"🆔 Provider ID: {provider_id}\n"
            f"🔐 Active Code: {phone_code}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Review profile quality, then approve/reject in admin bot."
        ),
    )
    db.log_provider_verification_event(
        provider_id,
        "profile_submitted",
        payload={"photo_count": len(existing_photo_urls), "city": city, "neighborhood": neighborhood},
    )

    _portal_clear_onboarding_draft(request)
    return RedirectResponse(url="/provider/dashboard?saved=1", status_code=303)

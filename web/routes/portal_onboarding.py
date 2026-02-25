"""
Portal Onboarding Routes - Multi-step profile completion wizard.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    FREE_TRIAL_DAYS,
    NEIGHBORHOODS,
    ONBOARDING_STEP_META,
    ONBOARDING_TOTAL_STEPS,
    PORTAL_ACCOUNT_APPROVED,
    PORTAL_CITY_COUNTY_OPTIONS,
    PORTAL_MAX_PROFILE_PHOTOS,
    PORTAL_MIN_PROFILE_PHOTOS,
    PORTAL_RECOMMENDED_PROFILE_PHOTOS,
)
from database import Database
from services.redis_service import _invalidate_provider_listing_cache
from services.telegram_service import send_admin_alert
from utils.auth import _normalize_portal_phone, _portal_account_state, _portal_session_provider_id, _to_int_or_none
from utils.db_async import db_call
from utils.onboarding import (
    _canonical_city_name,
    _canonical_neighborhood_names,
    _normalize_onboarding_step,
    _parse_csv_values,
    _portal_build_preview,
    _portal_build_ranking_tips,
    _portal_clear_onboarding_draft,
    _portal_compute_profile_strength,
    _portal_get_onboarding_draft,
    _portal_set_onboarding_draft,
)
from utils.providers import _normalize_photo_sources
from utils.uploads import _save_provider_upload

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter()
db = Database()
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
    photo_urls = _normalize_photo_sources(provider.get("profile_photos"))[:PORTAL_MAX_PROFILE_PHOTOS]
    preview = _portal_build_preview(draft=draft, photo_urls=photo_urls)
    profile_strength = _portal_compute_profile_strength(draft=draft, photo_count=len(photo_urls))
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
            "cities": PORTAL_CITY_COUNTY_OPTIONS,
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
    """Multi-step onboarding wizard for portal providers."""
    provider_id = _portal_session_provider_id(request)
    if not provider_id:
        return RedirectResponse(url="/provider", status_code=302)

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED or provider.get("email_verified") is not True:
        return RedirectResponse(url=f"/provider/verify-email?status={_portal_account_state(provider)}", status_code=302)

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

    provider = await db_call(db.get_portal_provider_by_id, provider_id)
    if not provider:
        request.session.clear()
        return RedirectResponse(url="/provider?error=Session+expired", status_code=302)

    if _portal_account_state(provider) != PORTAL_ACCOUNT_APPROVED or provider.get("email_verified") is not True:
        return RedirectResponse(url=f"/provider/verify-email?status={_portal_account_state(provider)}", status_code=302)

    form = await request.form()
    step = _normalize_onboarding_step(form.get("step"))
    action = str(form.get("action", "next")).strip().lower()
    draft = _portal_get_onboarding_draft(request, provider)

    if step == 1:
        draft["display_name"] = str(form.get("display_name", "")).strip()
        phone_input = str(form.get("phone", "")).strip()
        draft["phone"] = _normalize_portal_phone(phone_input) if phone_input else ""
        raw_city = str(form.get("city", "")).strip()
        draft["city"] = _canonical_city_name(raw_city, PORTAL_CITY_COUNTY_OPTIONS)
        raw_neighborhood = str(form.get("neighborhood", "")).strip()
        draft["neighborhood"] = _canonical_neighborhood_names(raw_neighborhood, draft["city"], NEIGHBORHOODS)
        draft["age"] = str(form.get("age", "")).strip()
        draft["height_cm"] = str(form.get("height_cm", "")).strip()
        draft["weight_kg"] = str(form.get("weight_kg", "")).strip()
        draft["build"] = str(form.get("build", "")).strip()
        draft["gender"] = str(form.get("gender", "")).strip()
        draft["sexual_orientation"] = str(form.get("sexual_orientation", "")).strip()
        draft["nationality"] = str(form.get("nationality", "")).strip()
        draft["county"] = str(form.get("county", "")).strip()
        _portal_set_onboarding_draft(request, draft)
        if action != "back" and not draft["phone"]:
            return _render_provider_onboarding_template(
                request=request,
                provider=provider,
                draft=draft,
                step=step,
                error="Add a valid phone number (e.g. 2547XXXXXXXX) for your Call button.",
            )
        if action != "back" and raw_city and draft["city"] not in PORTAL_CITY_COUNTY_OPTIONS:
            return _render_provider_onboarding_template(
                request=request,
                provider=provider,
                draft=draft,
                step=step,
                error="Select a valid city/county from the suggestions list.",
            )
        if action != "back" and (not draft["display_name"] or not draft["city"] or not draft["neighborhood"]):
            return _render_provider_onboarding_template(
                request=request,
                provider=provider,
                draft=draft,
                step=step,
                error="Please set display name, city, and at least one neighborhood before continuing.",
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
        draft["incalls_from"] = str(form.get("incalls_from", "")).strip()
        draft["outcalls_from"] = str(form.get("outcalls_from", "")).strip()
        _portal_set_onboarding_draft(request, draft)
        if action != "back" and not _parse_csv_values(draft["services_text"]):
            return _render_provider_onboarding_template(
                request=request,
                provider=provider,
                draft=draft,
                step=step,
                error="Please add at least one service before continuing.",
            )

    elif step == ONBOARDING_TOTAL_STEPS:
        draft["video_url"] = str(form.get("video_url", "")).strip()
        _portal_set_onboarding_draft(request, draft)

    if action == "back":
        return RedirectResponse(url=f"/provider/onboarding?step={max(1, step - 1)}&saved=1", status_code=303)

    if step < ONBOARDING_TOTAL_STEPS:
        return RedirectResponse(url=f"/provider/onboarding?step={step + 1}&saved=1", status_code=303)

    existing_photo_urls = _normalize_photo_sources(provider.get("profile_photos"))
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
            error=f"Please upload at least {PORTAL_MIN_PROFILE_PHOTOS} profile photos before submitting.",
        )

    display_name = draft.get("display_name") or provider.get("display_name")
    normalized_phone = _normalize_portal_phone(draft.get("phone", ""))
    if not normalized_phone:
        return _render_provider_onboarding_template(
            request=request,
            provider=provider,
            draft=draft,
            step=1,
            error="Add a valid phone number (e.g. 2547XXXXXXXX) for your Call button.",
        )
    city = draft.get("city", "")
    neighborhood = draft.get("neighborhood", "")
    bio = draft.get("bio", "")
    services = _parse_csv_values(draft.get("services_text", ""))
    languages = _parse_csv_values(draft.get("languages_text", ""))

    update_data = {
        "display_name": display_name,
        "phone": normalized_phone,
        "city": city,
        "neighborhood": neighborhood,
        "age": _to_int_or_none(draft.get("age")),
        "height_cm": _to_int_or_none(draft.get("height_cm")),
        "weight_kg": _to_int_or_none(draft.get("weight_kg")),
        "build": draft.get("build", ""),
        "gender": draft.get("gender", ""),
        "sexual_orientation": draft.get("sexual_orientation", ""),
        "nationality": draft.get("nationality", ""),
        "county": draft.get("county", ""),
        "services": services,
        "bio": bio,
        "nearby_places": draft.get("nearby_places", ""),
        "availability_type": draft.get("availability_type", ""),
        "languages": languages,
        "profile_photos": existing_photo_urls,
        "incalls_from": _to_int_or_none(draft.get("incalls_from")),
        "outcalls_from": _to_int_or_none(draft.get("outcalls_from")),
        "video_url": draft.get("video_url", ""),
        "rate_30min": _to_int_or_none(draft.get("rate_30min")),
        "rate_1hr": _to_int_or_none(draft.get("rate_1hr")),
        "rate_2hr": _to_int_or_none(draft.get("rate_2hr")),
        "rate_3hr": _to_int_or_none(draft.get("rate_3hr")),
        "rate_overnight": _to_int_or_none(draft.get("rate_overnight")),
        "is_online": False,
        "portal_onboarding_complete": bool(
            display_name
            and normalized_phone
            and city
            and neighborhood
            and bio
            and len(existing_photo_urls) >= PORTAL_MIN_PROFILE_PHOTOS
        ),
    }
    saved = await db_call(db.update_portal_provider_profile, provider_id, update_data)
    if not saved:
        return _render_provider_onboarding_template(
            request=request,
            provider=provider,
            draft=draft,
            step=ONBOARDING_TOTAL_STEPS,
            error="Could not save your profile right now. Please try again.",
        )

    tg_id = int(provider.get("telegram_id") or 0)
    auto_trial_activated = False
    if tg_id:
        await db_call(db.update_provider_profile, tg_id, {"is_verified": True})
        if not await db_call(db.has_successful_payment_for_provider, tg_id):
            auto_trial_activated = await db_call(db.activate_free_trial, tg_id, FREE_TRIAL_DAYS)
            if auto_trial_activated:
                await db_call(
                    db.log_funnel_event,
                    tg_id,
                    "trial_started",
                    {"days": FREE_TRIAL_DAYS, "source": "portal_onboarding_complete"},
                )
                await db_call(db.log_funnel_event, tg_id, "active_live", {"source": "portal_onboarding_complete"})

    _invalidate_provider_listing_cache()

    await send_admin_alert(
        (
            "PORTAL PROFILE SUBMITTED\n"
            "-----------------------\n"
            f"Name: {display_name or provider.get('display_name', 'Unknown')}\n"
            f"Phone: {normalized_phone}\n"
            f"Provider ID: {provider_id}\n"
            "Review profile quality in admin bot."
        )
    )
    await db_call(
        db.log_provider_verification_event,
        provider_id,
        "profile_submitted",
        payload={"photo_count": len(existing_photo_urls), "city": city, "neighborhood": neighborhood},
    )

    _portal_clear_onboarding_draft(request)
    if auto_trial_activated:
        return RedirectResponse(url="/provider/dashboard?saved=1&trial_auto=1", status_code=303)
    return RedirectResponse(url="/provider/dashboard?saved=1", status_code=303)

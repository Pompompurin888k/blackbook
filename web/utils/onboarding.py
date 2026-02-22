"""
Onboarding Utilities — draft management, profile strength, ranking tips, CSV parsing.
"""
from typing import Optional

from fastapi import Request

from config import (
    ONBOARDING_TOTAL_STEPS,
    PORTAL_RECOMMENDED_PROFILE_PHOTOS,
)
from utils.auth import _to_int_or_none
from utils.providers import _to_string_list


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
        "gender": str(provider.get("gender") or "").strip(),
        "sexual_orientation": str(provider.get("sexual_orientation") or "").strip(),
        "nationality": str(provider.get("nationality") or "").strip(),
        "county": str(provider.get("county") or "").strip(),
        "bio": str(provider.get("bio") or "").strip(),
        "nearby_places": str(provider.get("nearby_places") or "").strip(),
        "availability_type": str(provider.get("availability_type") or "").strip(),
        "services_text": ", ".join(_to_string_list(provider.get("services"))),
        "languages_text": ", ".join(_to_string_list(provider.get("languages"))),
        "incalls_from": str(provider.get("incalls_from") or "").strip(),
        "outcalls_from": str(provider.get("outcalls_from") or "").strip(),
        "video_url": str(provider.get("video_url") or "").strip(),
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


def _portal_build_preview(draft: dict, photo_urls: list[str]) -> dict:
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
    }


def _portal_compute_profile_strength(
    draft: dict,
    photo_count: int,
) -> dict:
    """Builds a 0-100 quality score with focused missing-item guidance."""
    services_count = len(_parse_csv_values(draft.get("services_text", "")))
    languages_count = len(_parse_csv_values(draft.get("languages_text", "")))
    rates_count = sum(
        1
        for key in ["rate_30min", "rate_1hr", "rate_2hr", "rate_3hr", "rate_overnight"]
        if _to_int_or_none(draft.get(key)) is not None
    )
    bio_len = len((draft.get("bio") or "").strip())

    checks = [
        (
            8,
            bool((draft.get("display_name") or "").strip()),
            "Set a memorable display name",
        ),
        (6, bool((draft.get("city") or "").strip()), "Select your city"),
        (
            6,
            bool((draft.get("neighborhood") or "").strip()),
            "Add your neighborhood",
        ),
        (4, bool((draft.get("age") or "").strip()), "Add your age"),
        (4, bool((draft.get("height_cm") or "").strip()), "Add your height"),
        (4, bool((draft.get("weight_kg") or "").strip()), "Add your weight"),
        (4, bool((draft.get("build") or "").strip()), "Add your build/body type"),
        (12, bio_len >= 80, "Write a richer bio (80+ characters)"),
        (
            4,
            bool((draft.get("nearby_places") or "").strip()),
            "Add a nearby landmark",
        ),
        (
            4,
            bool((draft.get("availability_type") or "").strip()),
            "Set clear availability",
        ),
        (10, services_count >= 3, "List at least 3 services"),
        (8, languages_count >= 2, "Add at least 2 languages"),
        (10, rates_count >= 3, "Set at least 3 rate options"),
        (
            12,
            photo_count >= PORTAL_RECOMMENDED_PROFILE_PHOTOS,
            (
                "Upload at least "
                f"{PORTAL_RECOMMENDED_PROFILE_PHOTOS} profile photos"
            ),
        ),
    ]

    total_possible = sum(weight for weight, _, _ in checks)
    achieved = sum(weight for weight, passed, _ in checks if passed)
    score = int(round((achieved / total_possible) * 100)) if total_possible else 0

    if score >= 85:
        label = "Excellent"
    elif score >= 65:
        label = "Strong"
    elif score >= 45:
        label = "Good start"
    else:
        label = "Needs work"

    missing = [hint for _, passed, hint in checks if not passed][:4]
    return {
        "score": score,
        "label": label,
        "missing": missing,
        "completed": len([1 for _, passed, _ in checks if passed]),
        "total": len(checks),
    }


def _portal_build_ranking_tips(draft: dict, photo_count: int) -> list[dict]:
    """Builds lightweight ranking guidance for the final review step."""
    services_count = len(_parse_csv_values(draft.get("services_text", "")))
    languages_count = len(_parse_csv_values(draft.get("languages_text", "")))
    rates_count = sum(
        1
        for key in ["rate_30min", "rate_1hr", "rate_2hr", "rate_3hr", "rate_overnight"]
        if _to_int_or_none(draft.get(key)) is not None
    )
    bio_len = len((draft.get("bio") or "").strip())

    tips = [
        {
            "title": f"Upload {PORTAL_RECOMMENDED_PROFILE_PHOTOS} clear photos",
            "done": photo_count >= PORTAL_RECOMMENDED_PROFILE_PHOTOS,
        },
        {"title": "Write a bio with personality (80+ chars)", "done": bio_len >= 80},
        {"title": "List at least 3 services", "done": services_count >= 3},
        {"title": "Set at least 3 rates", "done": rates_count >= 3},
        {"title": "Add at least 2 languages", "done": languages_count >= 2},
        {
            "title": "Add nearby landmark + availability for trust",
            "done": bool(
                (draft.get("nearby_places") or "").strip()
                and (draft.get("availability_type") or "").strip()
            ),
        },
    ]
    return tips

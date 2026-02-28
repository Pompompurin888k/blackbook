"""
Provider Utilities — template payload normalization, photo URLs, fallback images.
"""
import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote
from urllib.parse import urlparse

from fastapi.responses import RedirectResponse

from config import FALLBACK_PROFILE_IMAGES, MAX_PHOTO_CACHE_ITEMS, photo_url_cache
from utils.auth import _sanitize_phone


def _to_string_list(value) -> list[str]:
    """Normalizes a DB value to a flat string list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        if "," in text:
            return [item.strip() for item in text.split(",") if item.strip()]
        return [text]
    return []


def _fallback_image(seed: int, offset: int = 0) -> str:
    index = (seed + offset) % len(FALLBACK_PROFILE_IMAGES)
    return FALLBACK_PROFILE_IMAGES[index]


def _normalize_photo_source(photo_ref: str) -> Optional[str]:
    """
    Normalizes a stored photo reference to a URL the current app host can serve.

    - Telegram file IDs become `/photo/{file_id}`
    - Absolute uploads like `https://domain/static/uploads/...` become `/static/uploads/...`
    - Relative `/...` paths are kept as-is
    """
    value = str(photo_ref or "").strip()
    if not value:
        return None
    if value.startswith("/"):
        if value.startswith("/uploads/"):
            return f"/static{value}"
        return value
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        if parsed.path.startswith("/static/uploads/"):
            return parsed.path
        if "/static/uploads/" in parsed.path:
            return parsed.path[parsed.path.index("/static/uploads/") :]
        if parsed.path.startswith("/uploads/"):
            return f"/static{parsed.path}"
        if "/uploads/providers/" in parsed.path:
            trimmed = parsed.path[parsed.path.index("/uploads/providers/") :]
            return f"/static{trimmed}"
        return value
    normalized_slashes = value.replace("\\", "/")
    if normalized_slashes.startswith("static/uploads/"):
        return f"/{normalized_slashes}"
    if normalized_slashes.startswith("uploads/"):
        return f"/static/{normalized_slashes}"
    return f"/photo/{value}"


def _normalize_photo_sources(value) -> list[str]:
    """Normalizes a DB photo collection to browser-ready URLs."""
    normalized: list[str] = []
    for raw in _to_string_list(value):
        source = _normalize_photo_source(raw)
        if source:
            normalized.append(source)
    return normalized


def _build_gallery_urls(provider_id: int, photo_ids: list[str]) -> list[str]:
    urls = _normalize_photo_sources(photo_ids)
    if urls:
        return urls[:5]
    # Keep a single fallback only when provider has no uploaded photos at all.
    return [_fallback_image(provider_id)]


def _slugify_segment(value: Optional[str], fallback: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return fallback
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return slug or fallback


def _build_public_profile_url(provider: dict) -> str:
    """Builds the canonical public profile URL for a provider."""
    provider_id = provider.get("id")
    if provider_id in (None, "", 0):
        return "/"

    safe_id = int(provider_id)
    city = _slugify_segment(provider.get("city"), "nairobi")
    neighborhood_values = _to_string_list(provider.get("neighborhood"))
    primary_neighborhood = neighborhood_values[0] if neighborhood_values else provider.get("city")
    neighborhood = _slugify_segment(primary_neighborhood, city)
    name_slug = _slugify_segment(provider.get("display_name"), f"provider-{safe_id}")
    return f"/{city}/{neighborhood}/escorts/{safe_id}/{name_slug}"


def _build_short_profile_url(provider: dict) -> str:
    """Builds a compact share URL that redirects to the canonical profile path."""
    provider_id = provider.get("id")
    if provider_id in (None, "", 0):
        return "/"
    return f"/p/{int(provider_id)}"


def _format_last_active_label(
    last_active_at: Optional[datetime],
    is_online: bool,
    now: Optional[datetime] = None,
) -> str:
    """Formats a compact, human-readable last-active label."""
    if is_online:
        return "Online now"
    if not isinstance(last_active_at, datetime):
        return "Recently active"

    reference_now = now
    if reference_now is None:
        if getattr(last_active_at, "tzinfo", None):
            reference_now = datetime.now(last_active_at.tzinfo)
        else:
            reference_now = datetime.now()

    delta_seconds = max(0, int((reference_now - last_active_at).total_seconds()))
    minutes = delta_seconds // 60
    if minutes < 1:
        return "Active just now"
    if minutes < 60:
        return f"Active {minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"Active {hours}h ago"
    days = hours // 24
    return f"Active {days}d ago"


def _format_response_rate_label(response_rate_pct) -> str:
    """Formats response-rate trust label for public profile badges."""
    if response_rate_pct is None:
        return "Response tracking"
    try:
        pct = int(round(float(response_rate_pct)))
    except (TypeError, ValueError):
        return "Response tracking"
    pct = max(0, min(99, pct))
    if pct == 0:
        return "New profile"
    return f"{pct}% response rate"


def _normalize_provider(provider: dict) -> dict:
    """Builds a stable profile payload for the template."""
    profile = dict(provider)
    services_list = _to_string_list(profile.get("services"))
    languages_list = _to_string_list(profile.get("languages"))
    photo_urls = _normalize_photo_sources(profile.get("profile_photos"))

    profile["services_list"] = services_list
    profile["languages_list"] = languages_list
    profile["primary_location"] = profile.get("neighborhood") or profile.get("city") or "Nairobi"
    profile["profile_photos"] = photo_urls
    profile["photo_urls"] = _build_gallery_urls(profile.get("id", 0), photo_urls)
    profile["availability_label"] = profile.get("availability_type") or (
        "Available now" if profile.get("is_online") else "By booking"
    )
    profile["response_hint"] = (
        "Usually replies in under 15 minutes"
        if profile.get("is_online")
        else "Usually replies in under 1 hour"
    )
    last_active_at = profile.get("updated_at") or profile.get("created_at")
    profile["last_active_hint"] = _format_last_active_label(last_active_at, bool(profile.get("is_online")))
    profile["email_verified_badge"] = bool(profile.get("email_verified"))
    profile["response_rate_label"] = _format_response_rate_label(profile.get("response_rate_pct"))
    phone_digits = _sanitize_phone(profile.get("phone"))
    profile["phone_digits"] = phone_digits

    rate_fields = [
        ("30 min", "rate_30min"),
        ("1 hour", "rate_1hr"),
        ("2 hours", "rate_2hr"),
        ("3 hours", "rate_3hr"),
        ("Overnight", "rate_overnight"),
    ]
    rate_cards = []
    for label, field in rate_fields:
        amount = profile.get(field)
        if isinstance(amount, (int, float)) and amount > 0:
            rate_cards.append({"label": label, "amount": int(amount)})
    profile["rate_cards"] = rate_cards
    provider_id = profile.get("id")
    profile["public_profile_url"] = _build_public_profile_url(profile)
    profile["short_profile_url"] = _build_short_profile_url(profile)
    profile["call_url"] = f"/connect/{provider_id}?channel=call&mode=direct"
    profile["whatsapp_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=direct"
    profile["connect_direct_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=direct"
    profile["connect_stealth_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=stealth"
    profile["has_phone"] = bool(phone_digits)
    return profile


def _normalize_recommendation(provider: dict) -> dict:
    card = dict(provider)
    photo_urls = _normalize_photo_sources(card.get("profile_photos"))
    if photo_urls:
        card["photo_url"] = photo_urls[0]
    else:
        card["photo_url"] = _fallback_image(card.get("id", 0))
    card["public_profile_url"] = _build_public_profile_url(card)
    card["short_profile_url"] = _build_short_profile_url(card)
    card["location"] = card.get("neighborhood") or card.get("city") or "Nairobi"
    card["services_list"] = _to_string_list(card.get("services"))[:2]
    return card


def _telegram_contact_redirect(provider: dict, is_stealth: bool) -> RedirectResponse:
    """Fallback contact redirect using Telegram when phone is unavailable."""
    telegram_id = provider.get("telegram_id")
    username = provider.get("telegram_username")
    name = provider.get("display_name", "")
    if is_stealth:
        message = "Hi, is this a good time to talk?"
    else:
        message = f"Hi {name}, I found you on Ace Girls. Are you available?"

    if username:
        return RedirectResponse(url=f"https://t.me/{username}?text={quote(message)}", status_code=302)
    if telegram_id:
        return RedirectResponse(url=f"tg://openmessage?user_id={telegram_id}", status_code=302)
    return RedirectResponse(url="/", status_code=302)


def _cache_photo_path(file_id: str, file_path: str) -> None:
    """Caches Telegram file paths with a bounded in-memory size."""
    if file_id in photo_url_cache:
        photo_url_cache.move_to_end(file_id)
    photo_url_cache[file_id] = file_path
    if len(photo_url_cache) > MAX_PHOTO_CACHE_ITEMS:
        photo_url_cache.popitem(last=False)

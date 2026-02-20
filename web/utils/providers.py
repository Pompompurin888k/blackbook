"""
Provider Utilities — template payload normalization, photo URLs, fallback images.
"""
import json
from typing import Optional
from urllib.parse import quote

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


def _build_gallery_urls(provider_id: int, photo_ids: list[str]) -> list[str]:
    urls = []
    for file_id in photo_ids:
        if not file_id:
            continue
        file_id_str = str(file_id).strip()
        if not file_id_str:
            continue
        if file_id_str.startswith("http://") or file_id_str.startswith("https://") or file_id_str.startswith("/"):
            urls.append(file_id_str)
        else:
            urls.append(f"/photo/{file_id_str}")
    if urls:
        return urls[:5]
    # Keep a single fallback only when provider has no uploaded photos at all.
    return [_fallback_image(provider_id)]


def _normalize_provider(provider: dict) -> dict:
    """Builds a stable profile payload for the template."""
    profile = dict(provider)
    services_list = _to_string_list(profile.get("services"))
    languages_list = _to_string_list(profile.get("languages"))
    photo_ids = _to_string_list(profile.get("profile_photos"))

    profile["services_list"] = services_list
    profile["languages_list"] = languages_list
    profile["primary_location"] = profile.get("neighborhood") or profile.get("city") or "Nairobi"
    profile["photo_urls"] = _build_gallery_urls(profile.get("id", 0), photo_ids)
    profile["availability_label"] = profile.get("availability_type") or (
        "Available now" if profile.get("is_online") else "By booking"
    )
    profile["response_hint"] = (
        "Usually replies in under 15 minutes"
        if profile.get("is_online")
        else "Usually replies in under 1 hour"
    )
    profile["last_active_hint"] = "Online now" if profile.get("is_online") else "Active today"
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
    profile["call_url"] = f"/connect/{provider_id}?channel=call&mode=direct"
    profile["whatsapp_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=direct"
    profile["connect_direct_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=direct"
    profile["connect_stealth_url"] = f"/connect/{provider_id}?channel=whatsapp&mode=stealth"
    profile["has_phone"] = bool(phone_digits)
    return profile


def _normalize_recommendation(provider: dict) -> dict:
    card = dict(provider)
    photo_ids = _to_string_list(card.get("profile_photos"))
    if photo_ids:
        first = str(photo_ids[0]).strip()
        if first.startswith("http://") or first.startswith("https://") or first.startswith("/"):
            card["photo_url"] = first
        else:
            card["photo_url"] = f"/photo/{first}"
    else:
        card["photo_url"] = _fallback_image(card.get("id", 0))
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
        message = f"Hi {name}, I found you on Blackbook. Are you available?"

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

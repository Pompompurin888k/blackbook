"""
Public Routes — Homepage, photo proxy, contact, connecting, safety.
"""
import logging
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request, Query, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    TELEGRAM_BOT_TOKEN,
    CITIES, NEIGHBORHOODS,
    ENABLE_REDIS_PAGE_CACHE, HOME_PAGE_CACHE_TTL_SECONDS,
    RECOMMENDATIONS_CACHE_TTL_SECONDS,
    photo_url_cache,
)
from database import Database
from services.redis_service import _cache_key, _redis_get_text, _redis_set_text
from utils.auth import _extract_client_ip, _detect_device_type
from utils.providers import (
    _cache_photo_path,
    _normalize_photo_sources,
    _normalize_provider,
    _normalize_recommendation,
    _telegram_contact_redirect,
)

# We use the router and expect the main app to provide `templates` and `db`
# A cleaner way is to import them or inject them. For now, we instantiate a local DB reference
# or rely on a shared one. We'll instantiate a local one since it's just a postgres connection pool.
db = Database()
# For templates, we can create a local Jinja2Templates instance since it's stateless.
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/photo/{file_id}")
async def get_photo(file_id: str):
    """
    Proxy endpoint to serve Telegram photos.
    Fetches file path from Telegram API and streams the photo bytes.
    Caches results to minimize API calls.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN not set, cannot fetch photo")
        return RedirectResponse(
            url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
            status_code=302
        )

    try:
        file_path = photo_url_cache.get(file_id)
        async with httpx.AsyncClient(timeout=30.0) as client:
            if not file_path:
                meta = await client.get(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile",
                    params={"file_id": file_id}
                )
                data = meta.json()
                if not data.get("ok") or not data.get("result", {}).get("file_path"):
                    logger.warning(f"⚠️ Failed to get file path for {file_id}: {data}")
                    return RedirectResponse(
                        url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
                        status_code=302
                    )
                file_path = data["result"]["file_path"]
                _cache_photo_path(file_id, file_path)

            photo_response = await client.get(
                f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            )
            if photo_response.status_code != 200:
                logger.warning(f"⚠️ Failed to fetch photo bytes for {file_id}: {photo_response.status_code}")
                return RedirectResponse(
                    url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
                    status_code=302
                )

            return Response(
                content=photo_response.content,
                media_type=photo_response.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": "public, max-age=3600"},
            )
    except Exception as e:
        logger.error(f"❌ Error fetching photo {file_id}: {e}")
        return RedirectResponse(
            url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
            status_code=302
        )


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request, 
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """Main directory page with optional city and neighborhood filter."""
    from datetime import datetime

    # Default to Nairobi if no city selected
    if not city:
        city = "Nairobi"
    normalized_city = city
    normalized_neighborhood = (neighborhood or "").strip() or "all"

    cache_key = _cache_key("home", normalized_city, normalized_neighborhood)
    if ENABLE_REDIS_PAGE_CACHE:
        cached_html = _redis_get_text(cache_key)
        if cached_html:
            return HTMLResponse(content=cached_html)

    raw_providers = db.get_active_providers(city, neighborhood)
    providers = []
    for item in raw_providers:
        row = dict(item)
        row["profile_photos"] = _normalize_photo_sources(row.get("profile_photos"))
        providers.append(row)
    city_counts = db.get_city_counts()
    total_count = sum(city_counts.values())

    # Get stats for hero section
    total_verified = db.get_total_verified_count()
    total_online = db.get_online_count()
    total_premium = db.get_premium_count()

    # Get neighborhoods for selected city
    neighborhoods = NEIGHBORHOODS.get(city, []) if city else []

    context = {
        "request": request,
        "providers": providers,
        "cities": CITIES,
        "selected_city": city,
        "selected_neighborhood": neighborhood,
        "neighborhoods": neighborhoods,
        "neighborhood_map": NEIGHBORHOODS,
        "city_counts": city_counts,
        "total_count": total_count,
        "total_verified": total_verified,
        "total_online": total_online,
        "total_premium": total_premium,
        "now": datetime.now  # Pass datetime for template calculations
    }
    if ENABLE_REDIS_PAGE_CACHE:
        html = templates.get_template("index.html").render(context)
        _redis_set_text(cache_key, html, HOME_PAGE_CACHE_TTL_SECONDS)
        return HTMLResponse(content=html)
    return templates.TemplateResponse("index.html", context)


@router.get("/{city}/{neighborhood}/escorts/{provider_id}", response_class=HTMLResponse)
async def public_profile_page(request: Request, city: str, neighborhood: str, provider_id: int):
    """
    SEO-friendly public profile route.
    Maps to the provider dashboard 'View Public Profile' link.
    """
    return await contact_page(request, provider_id)


@router.get("/contact/{provider_id}", response_class=HTMLResponse)
async def contact_page(request: Request, provider_id: int):
    """
    Contact page - shows Direct vs Discreet messaging options.
    Preserves client privacy with stealth mode.
    """
    provider = db.get_provider_by_id(provider_id)
    
    if not provider:
        return RedirectResponse(url="/", status_code=302)

    profile = _normalize_provider(provider)
    recommendations = db.get_recommendations(profile.get("city") or "Nairobi", provider_id, limit=4)
    recommendation_cards = [_normalize_recommendation(item) for item in recommendations]
    
    # Log the contact click
    logger.info(f"📲 Contact page: Provider ID {provider_id} ({provider.get('display_name', 'Unknown')})")
    
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "provider": profile,
        "recommendations": recommendation_cards,
    })


@router.get("/connect/{provider_id}")
async def connect_provider(
    request: Request,
    provider_id: int,
    mode: str = Query("direct"),
    channel: str = Query("whatsapp"),
):
    """
    Tracking bridge for outbound contact actions.
    Logs lead analytics before redirecting to WhatsApp or phone app.
    """
    provider = db.get_provider_by_id(provider_id)
    if not provider:
        return RedirectResponse(url="/", status_code=302)

    profile = _normalize_provider(provider)
    mode_value = (mode or "direct").strip().lower()
    is_stealth = mode_value == "stealth"
    contact_method = "call" if (channel or "").strip().lower() == "call" else "whatsapp"
    name = profile.get("display_name", "there")
    phone_digits = profile.get("phone_digits", "")

    client_ip = _extract_client_ip(request)
    device_type = _detect_device_type(request.headers.get("user-agent", ""))
    db.log_lead_analytics(
        provider_id=provider_id,
        client_ip=client_ip,
        device_type=device_type,
        contact_method=contact_method,
        is_stealth=is_stealth,
    )

    if contact_method == "call":
        if phone_digits:
            logger.info(f"Call lead: provider={provider_id} mode={mode_value} ip={client_ip}")
            return RedirectResponse(url=f"tel:+{phone_digits}", status_code=302)
        logger.info(f"Call lead fallback to direct contact: provider={provider_id} ip={client_ip}")
        return _telegram_contact_redirect(provider, is_stealth=False)

    if is_stealth:
        message = (
            "Hello, I am interested in the lifestyle management services we discussed. "
            "Please let me know your availability for a consultation."
        )
    else:
        message = f"Hi {name}, I saw your profile on Blackbook. Are you available?"

    if phone_digits:
        wa_url = f"https://wa.me/{phone_digits}?text={quote(message)}"
        logger.info(f"WhatsApp lead: provider={provider_id} mode={mode_value} ip={client_ip}")
        return RedirectResponse(url=wa_url, status_code=302)

    logger.info(f"WhatsApp lead fallback to Telegram route: provider={provider_id} mode={mode_value}")
    return _telegram_contact_redirect(provider, is_stealth=is_stealth)


@router.get("/contact/{provider_id}/direct")
async def contact_direct(request: Request, provider_id: int):
    """Direct contact shortcut using the normal connect flow."""
    return await connect_provider(request, provider_id, mode="direct", channel="whatsapp")


@router.get("/contact/{provider_id}/discreet")
async def contact_discreet(request: Request, provider_id: int):
    """Discreet contact shortcut using the normal connect flow."""
    return await connect_provider(request, provider_id, mode="stealth", channel="whatsapp")


@router.get("/safety", response_class=HTMLResponse)
async def safety(request: Request):
    """Safety page - shows blacklist and verification info."""
    return templates.TemplateResponse("safety.html", {"request": request})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    """Public privacy policy page."""
    return templates.TemplateResponse("privacy.html", {"request": request})


@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    """Public terms of service page."""
    return templates.TemplateResponse("terms.html", {"request": request})

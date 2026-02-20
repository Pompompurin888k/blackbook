"""
API Routes — Data fetching, HTMX endpoints, and healthchecks.
"""
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse

from config import (
    ENABLE_REDIS_PAGE_CACHE, GRID_CACHE_TTL_SECONDS,
    RECOMMENDATIONS_CACHE_TTL_SECONDS, ENABLE_SEED_ENDPOINT,
    LOCALHOSTS
)
from database import Database
from services.redis_service import _cache_key, _redis_get_text, _redis_set_text
from utils.providers import _normalize_photo_sources

db = Database()
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

router = APIRouter()


@router.get("/api/grid", response_class=HTMLResponse)
async def api_grid(
    request: Request,
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """
    HTMX endpoint - returns only the provider grid HTML.
    Used for seamless filtering without full page reload.
    """
    from datetime import datetime

    normalized_city = (city or "all").strip() or "all"
    normalized_neighborhood = (neighborhood or "").strip() or "all"
    cache_key = _cache_key("grid", normalized_city, normalized_neighborhood)
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

    context = {
        "request": request,
        "providers": providers,
        "selected_city": city,
        "now": datetime.now  # Pass datetime for template calculations
    }
    if ENABLE_REDIS_PAGE_CACHE:
        html = templates.get_template("_grid.html").render(context)
        _redis_set_text(cache_key, html, GRID_CACHE_TTL_SECONDS)
        return HTMLResponse(content=html)
    return templates.TemplateResponse("_grid.html", context)


@router.get("/api/recommendations", response_class=HTMLResponse)
async def api_recommendations(
    request: Request,
    city: str,
    exclude_id: int
):
    """
    HTMX endpoint - returns smart recommended providers HTML with relevance indicators.
    """
    normalized_city = (city or "nairobi").strip() or "nairobi"
    cache_key = _cache_key("recommendations", normalized_city, exclude_id)
    if ENABLE_REDIS_PAGE_CACHE:
        cached_html = _redis_get_text(cache_key)
        if cached_html:
            return HTMLResponse(content=cached_html)

    recommendations = db.get_recommendations(city, exclude_id, limit=4)
    
    # Get source provider for comparison
    source_provider = db.get_provider_by_id(exclude_id)
    
    # Add relevance hints to each recommendation
    enriched_recommendations = []
    for rec in recommendations:
        rec_dict = dict(rec)
        hints = []
        
        if source_provider:
            # Same neighborhood
            if rec.get('neighborhood') == source_provider.get('neighborhood'):
                hints.append("From your area")
            # Same build
            elif rec.get('build') and rec.get('build') == source_provider.get('build'):
                hints.append("Similar style")
            # Recently verified
            elif rec.get('created_at'):
                from datetime import datetime, timedelta
                if rec['created_at'] > datetime.now() - timedelta(days=30):
                    hints.append("Recently verified")
            # Online
            if rec.get('is_online'):
                if not hints:
                    hints.append("Available now")
        
        rec_dict['relevance_hint'] = hints[0] if hints else None
        enriched_recommendations.append(rec_dict)
    
    context = {
        "request": request,
        "providers": enriched_recommendations,
        "selected_city": city
    }
    if ENABLE_REDIS_PAGE_CACHE:
        html = templates.get_template("_recommendations.html").render(context)
        _redis_set_text(cache_key, html, RECOMMENDATIONS_CACHE_TTL_SECONDS)
        return HTMLResponse(content=html)
    return templates.TemplateResponse("_recommendations.html", context)


@router.get("/api/status/{provider_id}", response_class=HTMLResponse)
async def get_provider_status(provider_id: int):
    """
    Real-time status endpoint for HTMX polling.
    Returns the Live badge HTML if provider is online.
    """
    provider = db.get_provider_by_id(provider_id)
    
    if provider and provider.get("is_online"):
        return f'''
        <div id="live-badge-{provider_id}"
             hx-get="/api/status/{provider_id}"
             hx-trigger="every 30s"
             hx-swap="outerHTML"
             class="glass px-2 py-1 rounded-full flex items-center gap-1">
            <span class="h-2 w-2 bg-green-500 rounded-full animate-pulse"></span>
            <span class="text-[10px] text-green-400 font-bold uppercase">Live</span>
        </div>
        '''
    else:
        # Provider is offline - return empty badge that still polls
        return f'''
        <div id="live-badge-{provider_id}"
             hx-get="/api/status/{provider_id}"
             hx-trigger="every 30s"
             hx-swap="outerHTML">
        </div>
        '''


@router.get("/api/providers")
async def api_providers(
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """JSON API endpoint for providers."""
    providers = db.get_public_active_providers(city, neighborhood)
    return {"providers": providers, "count": len(providers)}


@router.post("/api/analytics")
async def api_analytics(request: Request):
    """Receives lightweight frontend analytics events."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

    event = str(payload.get("event", "")).strip()
    event_payload = payload.get("payload", {})
    if not event:
        return JSONResponse({"status": "error", "message": "Missing event"}, status_code=400)
    if not isinstance(event_payload, dict):
        event_payload = {"value": str(event_payload)}

    ok = db.log_analytics_event(event_name=event, event_payload=event_payload)
    if not ok:
        return JSONResponse({"status": "error", "message": "Failed"}, status_code=500)
    return {"status": "ok"}


@router.get("/seed")
async def seed_data(request: Request):
    """Seeds the database with test data."""
    if not ENABLE_SEED_ENDPOINT:
        return JSONResponse({"status": "error", "message": "Not found"}, status_code=404)
    client_host = request.client.host if request.client else None
    if client_host not in LOCALHOSTS:
        return JSONResponse({"status": "error", "message": "Forbidden"}, status_code=403)
    db.seed_test_providers()
    return {"status": "seeded", "message": "Test providers added."}


@router.get("/health")
async def health():
    """Readiness health endpoint (checks DB)."""
    db_ok = db.healthcheck()
    status_code = 200 if db_ok else 503
    return JSONResponse(
        {"status": "healthy" if db_ok else "unhealthy", "database": "up" if db_ok else "down"},
        status_code=status_code,
    )


@router.get("/health/live")
async def health_live():
    """Liveness endpoint."""
    return {"status": "alive"}

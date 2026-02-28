"""
Admin Ops Routes - token-protected operational metrics dashboard.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import ADMIN_METRICS_TOKEN
from database import Database
from utils.db_async import db_call

router = APIRouter()
templates = Jinja2Templates(directory="templates")
db = Database()


def _authorized_admin_request(request: Request) -> bool:
    if not ADMIN_METRICS_TOKEN:
        return False
    supplied = (
        str(request.headers.get("x-admin-token", "")).strip()
        or str(request.query_params.get("token", "")).strip()
    )
    if not supplied:
        return False
    return secrets.compare_digest(supplied, ADMIN_METRICS_TOKEN)


def _unauthorized_payload(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"ok": False, "detail": detail})


def _admin_token_from_request(request: Request) -> str:
    return str(request.query_params.get("token", "")).strip()


def _normalize_status_filter(value: str) -> str:
    normalized = (value or "").strip().lower()
    allowed = {"unverified", "verified", "active", "inactive", "all"}
    return normalized if normalized in allowed else "all"


@router.get("/admin/ops/metrics", response_class=HTMLResponse)
async def admin_ops_metrics(request: Request):
    """Renders portal operational metrics in a simple dashboard view."""
    if not ADMIN_METRICS_TOKEN:
        return HTMLResponse(
            status_code=503,
            content=(
                "<h1>Admin metrics disabled</h1>"
                "<p>Set ADMIN_METRICS_TOKEN in .env to enable this page.</p>"
            ),
        )
    if not _authorized_admin_request(request):
        return HTMLResponse(status_code=403, content="<h1>Forbidden</h1>")

    metrics = await db_call(db.get_portal_ops_metrics)
    generated_at = metrics.get("generated_at")
    if isinstance(generated_at, datetime):
        metrics["generated_at_iso"] = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        metrics["generated_at_iso"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return templates.TemplateResponse(
        "admin_ops_metrics.html",
        {
            "request": request,
            "metrics": metrics,
        },
    )


@router.get("/admin/ops/metrics.json")
async def admin_ops_metrics_json(request: Request):
    """Returns portal operational metrics as JSON for quick checks."""
    if not ADMIN_METRICS_TOKEN:
        return _unauthorized_payload(503, "ADMIN_METRICS_TOKEN is not configured")
    if not _authorized_admin_request(request):
        return _unauthorized_payload(403, "Forbidden")

    metrics = await db_call(db.get_portal_ops_metrics)
    generated_at = metrics.get("generated_at")
    if isinstance(generated_at, datetime):
        metrics["generated_at"] = generated_at.astimezone(timezone.utc).isoformat()
    return {"ok": True, "metrics": metrics}


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    status: str = Query("all"),
    pending_limit: int = Query(50),
):
    """Token-protected admin dashboard for portal reviews + provider actions."""
    if not _authorized_admin_request(request):
        return HTMLResponse(status_code=403, content="<h1>Forbidden</h1>")

    token = _admin_token_from_request(request)
    status_filter = _normalize_status_filter(status)
    safe_limit = max(1, min(int(pending_limit), 200))

    pending_accounts = await db_call(db.get_portal_pending_accounts, safe_limit, 0)
    pending_count = await db_call(db.get_portal_pending_count)
    providers = await db_call(db.get_providers_by_status, status_filter, 100, 0)

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "token": token,
            "status_filter": status_filter,
            "pending_accounts": pending_accounts,
            "pending_count": pending_count,
            "providers": providers,
        },
    )


@router.get("/admin/providers/{tg_id}", response_class=HTMLResponse)
async def admin_provider_detail(request: Request, tg_id: int):
    """Admin view for a single provider by Telegram ID."""
    if not _authorized_admin_request(request):
        return HTMLResponse(status_code=403, content="<h1>Forbidden</h1>")

    token = _admin_token_from_request(request)
    provider = await db_call(db.get_provider, tg_id)
    if not provider:
        return HTMLResponse(status_code=404, content="<h1>Provider not found</h1>")

    return templates.TemplateResponse(
        "admin_provider_detail.html",
        {
            "request": request,
            "token": token,
            "provider": provider,
        },
    )


@router.post("/admin/actions/verify")
async def admin_verify_provider(
    request: Request,
    telegram_id: int = Form(...),
    decision: str = Form(...),
    reason: str = Form(""),
    token: str = Form(""),
):
    """Approve or reject a provider (portal or Telegram)."""
    if not _authorized_admin_request(request):
        return HTMLResponse(status_code=403, content="<h1>Forbidden</h1>")

    normalized = (decision or "").strip().lower()
    verified = normalized == "approve"
    rejection_reason = (reason or "").strip() if not verified else None
    await db_call(db.verify_provider, telegram_id, verified, None, rejection_reason)

    redirect_token = token or _admin_token_from_request(request)
    return RedirectResponse(url=f"/admin?token={redirect_token}", status_code=303)


@router.post("/admin/actions/active")
async def admin_toggle_active(
    request: Request,
    telegram_id: int = Form(...),
    is_active: str = Form(...),
    token: str = Form(""),
):
    """List or unlist a provider from the public directory."""
    if not _authorized_admin_request(request):
        return HTMLResponse(status_code=403, content="<h1>Forbidden</h1>")

    desired_state = str(is_active or "").strip().lower() in {"1", "true", "yes", "on"}
    await db_call(db.set_provider_active_status, telegram_id, desired_state)

    redirect_token = token or _admin_token_from_request(request)
    return RedirectResponse(url=f"/admin?token={redirect_token}", status_code=303)

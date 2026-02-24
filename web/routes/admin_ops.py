"""
Admin Ops Routes - token-protected operational metrics dashboard.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
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

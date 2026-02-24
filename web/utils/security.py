"""
Security Utilities - captcha validation and shared auth-hardening helpers.
"""
from __future__ import annotations

import logging

import httpx

from config import (
    PORTAL_CAPTCHA_ENABLED,
    PORTAL_TURNSTILE_SECRET_KEY,
    PORTAL_TURNSTILE_SITE_KEY,
)

logger = logging.getLogger(__name__)

_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _captcha_template_context() -> dict:
    """Builds template flags for optional Turnstile rendering."""
    return {
        "captcha_enabled": bool(PORTAL_CAPTCHA_ENABLED),
        "turnstile_site_key": PORTAL_TURNSTILE_SITE_KEY,
    }


async def _verify_portal_captcha(token: str, remote_ip: str = "") -> bool:
    """
    Validates Cloudflare Turnstile token.
    Returns True when captcha is disabled so existing flows keep working.
    """
    if not PORTAL_CAPTCHA_ENABLED:
        return True
    if not PORTAL_TURNSTILE_SECRET_KEY:
        logger.error("Captcha verification failed: missing Turnstile secret key.")
        return False
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return False

    payload = {
        "secret": PORTAL_TURNSTILE_SECRET_KEY,
        "response": normalized_token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(_TURNSTILE_VERIFY_URL, data=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.error(f"Captcha verification request failed: {exc}")
        return False

    if bool(data.get("success")):
        return True

    error_codes = data.get("error-codes") or []
    logger.warning(f"Captcha verification rejected token: {error_codes}")
    return False

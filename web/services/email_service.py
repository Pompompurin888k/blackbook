"""
Email Service - Brevo HTTP API for provider portal verification.
Uses the Brevo transactional email API (HTTPS) instead of SMTP,
which avoids port 587 being blocked on Render's free tier.
"""
from __future__ import annotations

import logging

import httpx

from config import (
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_PASSWORD,
)

logger = logging.getLogger(__name__)

_BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _recipient_domain(recipient: str) -> str:
    address = str(recipient or "").strip()
    if "@" not in address:
        return "unknown"
    return address.rsplit("@", 1)[-1].lower() or "unknown"


def _mask_recipient(recipient: str) -> str:
    address = str(recipient or "").strip()
    if "@" not in address:
        return "***"
    local, domain = address.split("@", 1)
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


async def _send_email_via_brevo(recipient: str, subject: str, body: str) -> None:
    """Sends an email via the Brevo transactional API over HTTPS."""
    payload = {
        "sender": {"name": SMTP_FROM_NAME, "email": SMTP_FROM_EMAIL},
        "to": [{"email": recipient}],
        "subject": subject,
        "textContent": body,
    }
    headers = {
        "api-key": SMTP_PASSWORD,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(_BREVO_API_URL, json=payload, headers=headers)
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Brevo API error {response.status_code}: {response.text[:200]}"
            )


async def send_portal_verification_email(
    recipient: str,
    code: str,
    ttl_minutes: int,
    display_name: str = "",
) -> bool:
    """Sends the portal email verification code."""
    if not (SMTP_PASSWORD and SMTP_FROM_EMAIL):
        logger.error(
            "Brevo API key or sender email not configured; cannot send verification email."
        )
        return False

    safe_name = (display_name or "there").strip() or "there"
    subject = "Verify your Ace Girls provider account"
    body = (
        f"Hi {safe_name},\n\n"
        "Your Ace Girls provider verification code is:\n\n"
        f"{code}\n\n"
        f"This code expires in {ttl_minutes} minutes.\n"
        "If you did not request this, you can ignore this email.\n\n"
        "Ace Girls"
    )

    try:
        await _send_email_via_brevo(recipient, subject, body)
        logger.info(
            f"Verification email sent to {_mask_recipient(recipient)} "
            f"(domain={_recipient_domain(recipient)})"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed sending verification email to {_mask_recipient(recipient)} "
            f"(domain={_recipient_domain(recipient)}): {type(e).__name__}: {e}"
        )
        return False


async def send_portal_password_reset_email(
    recipient: str,
    code: str,
    ttl_minutes: int,
    display_name: str = "",
) -> bool:
    """Sends the portal password-reset code."""
    if not (SMTP_PASSWORD and SMTP_FROM_EMAIL):
        logger.error(
            "Brevo API key or sender email not configured; cannot send password-reset email."
        )
        return False

    safe_name = (display_name or "there").strip() or "there"
    subject = "Reset your Ace Girls provider password"
    body = (
        f"Hi {safe_name},\n\n"
        "Your Ace Girls password reset code is:\n\n"
        f"{code}\n\n"
        f"This code expires in {ttl_minutes} minutes.\n"
        "If you did not request this, you can ignore this email.\n\n"
        "Ace Girls"
    )

    try:
        await _send_email_via_brevo(recipient, subject, body)
        logger.info(
            f"Password-reset email sent to {_mask_recipient(recipient)} "
            f"(domain={_recipient_domain(recipient)})"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed sending password-reset email to {_mask_recipient(recipient)} "
            f"(domain={_recipient_domain(recipient)}): {type(e).__name__}: {e}"
        )
        return False

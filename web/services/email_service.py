"""
Email Service - SMTP helpers for provider portal verification.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from fastapi.concurrency import run_in_threadpool

from config import (
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)

logger = logging.getLogger(__name__)


def _build_from_header() -> str:
    if SMTP_FROM_NAME and SMTP_FROM_EMAIL:
        return f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    return SMTP_FROM_EMAIL


def _send_email_sync(recipient: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _build_from_header()
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)


async def send_portal_verification_email(
    recipient: str,
    code: str,
    ttl_minutes: int,
    display_name: str = "",
) -> bool:
    """Sends the portal email verification code."""
    if not (SMTP_HOST and SMTP_PORT and SMTP_USERNAME and SMTP_PASSWORD and SMTP_FROM_EMAIL):
        logger.error("SMTP is not fully configured; cannot send verification email.")
        return False

    safe_name = (display_name or "there").strip() or "there"
    subject = "Verify your Blackbook provider account"
    body = (
        f"Hi {safe_name},\n\n"
        "Your Blackbook provider verification code is:\n\n"
        f"{code}\n\n"
        f"This code expires in {ttl_minutes} minutes.\n"
        "If you did not request this, you can ignore this email.\n\n"
        "Blackbook"
    )

    try:
        await run_in_threadpool(_send_email_sync, recipient, subject, body)
        return True
    except Exception as e:
        logger.error(f"Failed sending verification email to {recipient}: {e}")
        return False


async def send_portal_password_reset_email(
    recipient: str,
    code: str,
    ttl_minutes: int,
    display_name: str = "",
) -> bool:
    """Sends the portal password-reset code."""
    if not (SMTP_HOST and SMTP_PORT and SMTP_USERNAME and SMTP_PASSWORD and SMTP_FROM_EMAIL):
        logger.error("SMTP is not fully configured; cannot send password-reset email.")
        return False

    safe_name = (display_name or "there").strip() or "there"
    subject = "Reset your Blackbook provider password"
    body = (
        f"Hi {safe_name},\n\n"
        "Your Blackbook password reset code is:\n\n"
        f"{code}\n\n"
        f"This code expires in {ttl_minutes} minutes.\n"
        "If you did not request this, you can ignore this email.\n\n"
        "Blackbook"
    )

    try:
        await run_in_threadpool(_send_email_sync, recipient, subject, body)
        return True
    except Exception as e:
        logger.error(f"Failed sending password-reset email to {recipient}: {e}")
        return False

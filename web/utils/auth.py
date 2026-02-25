"""
Auth Utilities — password hashing, session helpers, phone normalization, lockout checks.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime
from ipaddress import ip_address
from typing import Optional

from fastapi import Request

from config import (
    PORTAL_VERIFY_CODE_PEPPER,
    PORTAL_ACCOUNT_APPROVED,
    PORTAL_ACCOUNT_PENDING,
    PORTAL_ACCOUNT_REJECTED,
    PORTAL_ACCOUNT_SUSPENDED,
    TRUSTED_PROXY_CIDRS,
)


def _sanitize_phone(value: Optional[str]) -> str:
    if not value:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) >= 9:
        digits = "254" + digits[1:]
    return digits


def _normalize_portal_phone(value: str) -> str:
    """Normalizes and validates provider phone numbers for portal auth."""
    digits = _sanitize_phone(value)
    if not digits.startswith("254"):
        return ""
    if len(digits) < 12:
        return ""
    return digits[:12]


def _normalize_portal_email(value: str) -> str:
    """Normalizes and validates email for portal auth."""
    email = str(value or "").strip().lower()
    if not email or len(email) > 254:
        return ""
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return email if re.match(pattern, email) else ""


def _normalize_portal_username(value: str) -> str:
    """Normalizes and validates a portal username."""
    username = str(value or "").strip().lower().lstrip("@")
    if not username:
        return ""
    if len(username) < 3 or len(username) > 32:
        return ""
    pattern = r"^[a-z0-9_]+$"
    return username if re.match(pattern, username) else ""


def _hash_password(password: str) -> str:
    """Hashes password with PBKDF2 for provider portal auth."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"{salt}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verifies password against stored PBKDF2 hash."""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, existing = stored_hash.split("$", 1)
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return hmac.compare_digest(existing, candidate)


def _build_portal_login_failure_message(
    login_failed_attempts: Optional[int],
    max_attempts: int,
) -> str:
    """Returns a user-safe login failure message with remaining attempts when available."""
    base_message = "Invalid email or password."
    if login_failed_attempts is None:
        return base_message
    try:
        attempts = int(login_failed_attempts)
        limit = max(1, int(max_attempts))
    except (TypeError, ValueError):
        return base_message

    remaining = max(0, limit - attempts)
    if remaining <= 0:
        return base_message
    suffix = "attempt" if remaining == 1 else "attempts"
    return f"{base_message} {remaining} {suffix} left before a temporary lock."


def _portal_session_provider_id(request: Request) -> Optional[int]:
    """Gets provider ID from portal session cookie."""
    value = request.session.get("provider_portal_id")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _portal_generate_whatsapp_code() -> str:
    """Generates strong manual verification code for WhatsApp confirmation."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "BB-" + "".join(secrets.choice(alphabet) for _ in range(8))


def _portal_generate_email_code() -> str:
    """Generates a 6-digit email verification code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _portal_hash_verification_code(code: str) -> str:
    """Hashes verification code with an app-level pepper."""
    base = f"{PORTAL_VERIFY_CODE_PEPPER}:{code}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()


def _portal_is_verification_code_match(submitted_code: str, stored_hash: str) -> bool:
    """Compares submitted verification code against stored hash."""
    if not submitted_code or not stored_hash:
        return False
    candidate = _portal_hash_verification_code(submitted_code)
    return hmac.compare_digest(candidate, stored_hash)


def _mask_email(value: str) -> str:
    """Masks email for safe UI display."""
    email = _normalize_portal_email(value)
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "*" * max(1, len(local) - 1)
    else:
        masked_local = local[:2] + "*" * (len(local) - 2)
    return f"{masked_local}@{domain}"


def _portal_account_state(provider: Optional[dict]) -> str:
    """Normalizes provider account_state to a known value."""
    if not provider:
        return PORTAL_ACCOUNT_PENDING
    state = str(provider.get("account_state") or "").strip().lower()
    if state in {
        PORTAL_ACCOUNT_APPROVED,
        PORTAL_ACCOUNT_PENDING,
        PORTAL_ACCOUNT_REJECTED,
        PORTAL_ACCOUNT_SUSPENDED,
    }:
        return state
    return PORTAL_ACCOUNT_APPROVED if provider.get("is_verified") else PORTAL_ACCOUNT_PENDING


def _portal_is_locked(provider: dict) -> bool:
    """Checks whether login is currently locked for this provider."""
    locked_until = provider.get("locked_until")
    if not locked_until:
        return False
    try:
        now = datetime.now(locked_until.tzinfo) if getattr(locked_until, "tzinfo", None) else datetime.now()
        return locked_until > now
    except TypeError:
        return False


def _portal_admin_review_keyboard(telegram_id: int) -> dict:
    """Inline admin actions for portal signup approval workflow."""
    return {
        "inline_keyboard": [
            [{"text": "✅ Approve", "callback_data": f"verify_approve_{telegram_id}"}],
            [
                {"text": "❌ Photo Quality", "callback_data": f"verify_reject_{telegram_id}_photo"},
                {"text": "❌ Identity Mismatch", "callback_data": f"verify_reject_{telegram_id}_mismatch"},
            ],
            [{"text": "❌ Incomplete Profile", "callback_data": f"verify_reject_{telegram_id}_incomplete"}],
        ]
    }


def _to_int_or_none(value) -> Optional[int]:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_ip(value: Optional[str]):
    text = (value or "").strip()
    if not text:
        return None
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        return ip_address(text)
    except ValueError:
        return None


def _is_trusted_proxy(host: Optional[str]) -> bool:
    candidate = _parse_ip(host)
    if candidate is None:
        return False
    return any(candidate in network for network in TRUSTED_PROXY_CIDRS)


def _extract_client_ip(request: Request) -> str:
    """Extracts client IP, trusting forwarding headers only from trusted proxies."""
    remote_host = request.client.host if request.client else ""

    if _is_trusted_proxy(remote_host):
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            for item in forwarded_for.split(","):
                candidate = _parse_ip(item)
                if candidate is not None:
                    return str(candidate)

        real_ip = _parse_ip(request.headers.get("x-real-ip", ""))
        if real_ip is not None:
            return str(real_ip)

    remote_ip = _parse_ip(remote_host)
    if remote_ip is not None:
        return str(remote_ip)
    return "unknown"


def _detect_device_type(user_agent: str) -> str:
    """Simple device classification for lead analytics."""
    ua = (user_agent or "").lower()
    if not ua:
        return "unknown"
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    mobile_markers = ["android", "iphone", "mobile", "opera mini", "windows phone"]
    if any(marker in ua for marker in mobile_markers):
        return "mobile"
    return "desktop"


def _is_valid_callback_signature(raw_body: bytes, signature: Optional[str]) -> bool:
    """Validates callback signature using HMAC SHA256."""
    from config import MEGAPAY_CALLBACK_SECRET
    if not MEGAPAY_CALLBACK_SECRET:
        return False
    if not signature:
        return False
    if signature.startswith("sha256="):
        signature = signature.split("=", 1)[1]
    expected = hmac.new(
        MEGAPAY_CALLBACK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip())

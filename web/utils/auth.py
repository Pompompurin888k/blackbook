"""
Auth Utilities — password hashing, session helpers, phone normalization, lockout checks.
"""
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Optional

from fastapi import Request

from config import PORTAL_VERIFY_CODE_PEPPER, PORTAL_ACCOUNT_APPROVED, PORTAL_ACCOUNT_PENDING, PORTAL_ACCOUNT_REJECTED, PORTAL_ACCOUNT_SUSPENDED


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


def _portal_hash_verification_code(code: str) -> str:
    """Hashes verification code with an app-level pepper."""
    base = f"{PORTAL_VERIFY_CODE_PEPPER}:{code}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()


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


def _extract_client_ip(request: Request) -> str:
    """Best-effort client IP extraction behind reverse proxies."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
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

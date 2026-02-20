from __future__ import annotations

from typing import Any, Optional


def extract_callback_reference(payload: dict[str, Any]) -> Optional[str]:
    """Extracts MegaPay callback reference from known fields."""
    if not isinstance(payload, dict):
        return None
    reference = payload.get("MpesaReceiptNumber") or payload.get("TransactionId") or payload.get("reference")
    if reference is None:
        return None
    text = str(reference).strip()
    return text or None


def build_payment_callback_job_id(reference: Optional[str]) -> Optional[str]:
    """Builds a stable ARQ job id for idempotent callback queueing."""
    if not reference:
        return None
    return f"paycb:{reference.strip()}"

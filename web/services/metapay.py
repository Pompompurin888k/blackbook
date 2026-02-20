"""
MegaPay STK push service for web portal initiated payments.
"""
from __future__ import annotations

import logging
import uuid

import httpx

from config import MEGAPAY_API_KEY, MEGAPAY_EMAIL, MEGAPAY_STK_ENDPOINT

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str:
    value = (phone or "").strip().replace(" ", "").replace("-", "")
    if value.startswith("+"):
        value = value[1:]
    if value.startswith("0"):
        value = "254" + value[1:]
    return value


async def initiate_stk_push(phone: str, amount: int, telegram_id: int, package_days: int) -> dict:
    """
    Initiate STK push and return a normalized result payload.
    """
    normalized_phone = _normalize_phone(phone)
    reference = f"BB_{telegram_id}_{package_days}_{uuid.uuid4().hex[:10]}"
    payload = {
        "api_key": MEGAPAY_API_KEY,
        "email": MEGAPAY_EMAIL,
        "amount": str(amount),
        "msisdn": normalized_phone,
        "reference": reference,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(MEGAPAY_STK_ENDPOINT, json=payload)
            if response.status_code != 200:
                logger.error("STK push failed status=%s body=%s", response.status_code, response.text)
                return {
                    "success": False,
                    "message": "Payment request failed. Please try again.",
                    "reference": reference,
                    "error": response.text,
                }

            data = response.json()
            success = data.get("success") == "200" or data.get("ResponseCode") == 0
            if not success:
                return {
                    "success": False,
                    "message": data.get("message", data.get("ResponseDescription", "Payment request failed.")),
                    "reference": reference,
                    "error": data,
                }

            return {
                "success": True,
                "message": "STK prompt sent. Complete payment on your phone.",
                "reference": reference,
                "data": data,
            }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "Payment request timed out. Please try again.",
            "reference": reference,
        }
    except Exception as err:
        logger.error("STK push error: %s", err)
        return {
            "success": False,
            "message": "Payment service unavailable. Please try again.",
            "reference": reference,
        }

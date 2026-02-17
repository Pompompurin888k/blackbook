"""
MegaPay STK Push Service
Handles M-Pesa payments via MegaPay API
"""
import httpx
import logging
import uuid

from config import (
    MEGAPAY_API_KEY,
    MEGAPAY_EMAIL,
    MEGAPAY_STK_ENDPOINT,
    PACKAGES,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def initiate_stk_push(phone: str, amount: int, telegram_id: int, package_days: int) -> dict:
    """
    Initiates an M-Pesa STK Push via MegaPay.
    
    Args:
        phone: Provider's phone number (format: 254XXXXXXXXX)
        amount: Amount in KES
        telegram_id: Provider's Telegram ID (used as account reference)
        package_days: Number of days for the package
    
    Returns:
        dict with success status and message
    """
    # Format phone number (ensure it starts with 254)
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("+"):
        phone = phone[1:]
    
    # Prepare payload per MegaPay API documentation.
    # Reference is unique per transaction to support idempotency safely.
    reference = f"BB_{telegram_id}_{package_days}_{uuid.uuid4().hex[:10]}"
    payload = {
        "api_key": MEGAPAY_API_KEY,
        "email": MEGAPAY_EMAIL,
        "amount": str(amount),
        "msisdn": phone,
        "reference": reference,  # BB_123456789_3_ab12cd34ef
    }
    
    logger.info(f"📱 Initiating STK Push: {phone} - {amount} KES - {package_days} days")
    logger.info(f"📡 Endpoint: {MEGAPAY_STK_ENDPOINT}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(MEGAPAY_STK_ENDPOINT, json=payload)
            
            logger.info(f"📬 Response status: {response.status_code}")
            logger.info(f"📬 Response body: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                # Check if MegaPay returned success
                if data.get("success") == "200" or data.get("ResponseCode") == 0:
                    logger.info(f"✅ STK Push sent successfully: {data}")
                    return {
                        "success": True,
                        "message": "STK Push sent! Check your phone for the M-Pesa prompt.",
                        "reference": reference,
                        "data": data
                    }
                else:
                    logger.error(f"❌ STK Push API error: {data}")
                    return {
                        "success": False,
                        "message": f"Payment request failed: {data.get('message', data.get('ResponseDescription', 'Unknown error'))}",
                        "reference": reference,
                        "error": data
                    }
            else:
                logger.error(f"❌ STK Push failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": f"Payment request failed. Please try again.",
                    "reference": reference,
                    "error": response.text
                }
                
    except httpx.TimeoutException:
        logger.error("❌ STK Push timeout")
        return {
            "success": False,
            "message": "Payment request timed out. Please try again.",
            "reference": reference,
        }
    except Exception as e:
        logger.error(f"❌ STK Push error: {e}")
        return {
            "success": False,
            "message": "Payment service unavailable. Please try again later.",
            "reference": reference,
        }


def get_package_price(days: int) -> int:
    """Gets the price for a package."""
    return PACKAGES.get(days, 0)


def get_available_packages() -> dict:
    """Returns available packages with pricing."""
    return PACKAGES

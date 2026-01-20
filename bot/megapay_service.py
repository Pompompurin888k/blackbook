"""
MegaPay STK Push Service
Handles M-Pesa payments via MegaPay API
"""
import os
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MegaPay Configuration (loaded from .env)
MEGAPAY_API_KEY = os.getenv("MEGAPAY_API_KEY", "YOUR_API_KEY_HERE")
MEGAPAY_MERCHANT_ID = os.getenv("MEGAPAY_MERCHANT_ID", "YOUR_MERCHANT_ID_HERE")
MEGAPAY_CALLBACK_URL = os.getenv("MEGAPAY_CALLBACK_URL", "https://yourdomain.com/payments/callback")
MEGAPAY_STK_ENDPOINT = os.getenv("MEGAPAY_STK_ENDPOINT", "https://api.megapay.co.ke/v1/stk/push")

# Package pricing
PACKAGES = {
    3: 400,   # 3 days = 400 KES
    7: 800,   # 7 days = 800 KES
}


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
    
    # Prepare payload
    payload = {
        "api_key": MEGAPAY_API_KEY,
        "merchant_id": MEGAPAY_MERCHANT_ID,
        "phone_number": phone,
        "amount": amount,
        "account_reference": f"BB_{telegram_id}_{package_days}",  # BB_123456789_3
        "transaction_desc": f"Blackbook {package_days} Day Listing",
        "callback_url": MEGAPAY_CALLBACK_URL,
    }
    
    logger.info(f"📱 Initiating STK Push: {phone} - {amount} KES - {package_days} days")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(MEGAPAY_STK_ENDPOINT, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ STK Push sent successfully: {data}")
                return {
                    "success": True,
                    "message": "STK Push sent! Check your phone for the M-Pesa prompt.",
                    "data": data
                }
            else:
                logger.error(f"❌ STK Push failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": f"Payment request failed. Please try again.",
                    "error": response.text
                }
                
    except httpx.TimeoutException:
        logger.error("❌ STK Push timeout")
        return {
            "success": False,
            "message": "Payment request timed out. Please try again."
        }
    except Exception as e:
        logger.error(f"❌ STK Push error: {e}")
        return {
            "success": False,
            "message": "Payment service unavailable. Please try again later."
        }


def get_package_price(days: int) -> int:
    """Gets the price for a package."""
    return PACKAGES.get(days, 0)


def get_available_packages() -> dict:
    """Returns available packages with pricing."""
    return PACKAGES

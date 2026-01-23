import os
import logging
import httpx
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Blackbook Directory", docs_url=None, redoc_url=None)

# Templates
templates = Jinja2Templates(directory="templates")

# Database connection
db = Database()

# Telegram Bot Token for sending notifications
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Available cities and neighborhoods
CITIES = ["Nairobi", "Eldoret", "Mombasa"]

# Neighborhoods per city (High-Value Focus)
NEIGHBORHOODS = {
    "Nairobi": ["Westlands", "Lower Kabete", "Kilimani", "Lavington", "Karen", "Roysambu"],
    "Eldoret": ["Town Centre", "Elgon View", "Langas", "Kapsoya"],
    "Mombasa": ["Nyali", "Bamburi", "Mtwapa", "Diani", "Town Centre"]
}


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request, 
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """Main directory page with optional city and neighborhood filter."""
    providers = db.get_active_providers(city, neighborhood)
    city_counts = db.get_city_counts()
    total_count = sum(city_counts.values())
    
    # Get neighborhoods for selected city
    neighborhoods = NEIGHBORHOODS.get(city, []) if city else []
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "providers": providers,
        "cities": CITIES,
        "selected_city": city,
        "selected_neighborhood": neighborhood,
        "neighborhoods": neighborhoods,
        "city_counts": city_counts,
        "total_count": total_count,
    })


@app.get("/contact/{provider_id}", response_class=HTMLResponse)
async def contact_page(request: Request, provider_id: int):
    """
    Contact page - shows Direct vs Discreet messaging options.
    Preserves client privacy with stealth mode.
    """
    provider = db.get_provider_by_id(provider_id)
    
    if not provider:
        return RedirectResponse(url="/", status_code=302)
    
    # Log the contact click
    logger.info(f"📲 Contact page: Provider ID {provider_id} ({provider.get('display_name', 'Unknown')})")
    
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "provider": provider,
    })


@app.get("/contact/{provider_id}/direct")
async def contact_direct(provider_id: int):
    """Direct message - opens Telegram with a clear first message."""
    provider = db.get_provider_by_id(provider_id)
    
    if not provider:
        return RedirectResponse(url="/", status_code=302)
    
    telegram_id = provider.get("telegram_id")
    name = provider.get("display_name", "")
    message = f"Hi {name}, I found you on Blackbook. Are you available?"
    
    logger.info(f"📲 Direct contact: {provider_id} ({name})")
    return RedirectResponse(url=f"https://t.me/{telegram_id}?text={message.replace(' ', '%20')}", status_code=302)


@app.get("/contact/{provider_id}/discreet")
async def contact_discreet(provider_id: int):
    """Discreet message - opens Telegram with a vague, safe message."""
    provider = db.get_provider_by_id(provider_id)
    
    if not provider:
        return RedirectResponse(url="/", status_code=302)
    
    telegram_id = provider.get("telegram_id")
    name = provider.get("display_name", "")
    # Discreet message that doesn't mention Blackbook or the nature of service
    message = "Hi, is this a good time to talk?"
    
    logger.info(f"🔒 Discreet contact: {provider_id} ({name})")
    return RedirectResponse(url=f"https://t.me/{telegram_id}?text={message.replace(' ', '%20')}", status_code=302)


# ==================== PAYMENT CALLBACK ====================

@app.post("/payments/callback")
async def megapay_callback(request: Request):
    """
    Handle MegaPay payment callback.
    When payment succeeds, activates the provider's subscription.
    """
    try:
        payload = await request.json()
        logger.info(f"💳 Payment callback received: {payload}")
        
        # Extract data from MegaPay response
        # Note: Adjust field names based on actual MegaPay API response format
        status = payload.get("status") or payload.get("ResultCode")
        reference = payload.get("MpesaReceiptNumber") or payload.get("TransactionId") or payload.get("reference")
        amount = payload.get("Amount") or payload.get("amount")
        account_ref = payload.get("AccountReference") or payload.get("account_reference") or ""
        
        # Parse telegram_id and package_days from account reference (format: BB_123456789_3)
        parts = account_ref.split("_")
        if len(parts) >= 3 and parts[0] == "BB":
            telegram_id = int(parts[1])
            package_days = int(parts[2])
        else:
            logger.error(f"❌ Invalid account reference format: {account_ref}")
            return JSONResponse({"status": "error", "message": "Invalid reference"}, status_code=400)
        
        # Check if payment was successful
        # MegaPay typically uses "0" or "Success" for successful payments
        success = str(status) in ["0", "Success", "COMPLETED", "success"]
        
        if success:
            # Activate subscription
            db.activate_subscription(telegram_id, package_days)
            db.log_payment(telegram_id, amount, reference, "SUCCESS", package_days)
            
            # Fetch provider info for enhanced notification
            provider = db.get_provider_by_telegram_id(telegram_id)
            neighborhood = provider.get("neighborhood", "your area") if provider else "your area"
            
            # Calculate expiry date
            from datetime import datetime, timedelta
            expiry_date = datetime.now() + timedelta(days=package_days)
            expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M")
            
            # Send enhanced Telegram notification to provider
            await send_telegram_notification(
                telegram_id,
                f"✅ **Payment Confirmed!**\n\n"
                f"💰 Amount: {amount} KES\n"
                f"📅 Package: {package_days} Day(s)\n\n"
                f"🎉 Your profile is now **LIVE** in **{neighborhood}** until **{expiry_str}**.\n\n"
                f"Go get them! 🚀"
            )
            
            logger.info(f"✅ Payment SUCCESS: Provider {telegram_id} activated for {package_days} days")
            return JSONResponse({"status": "success", "message": "Subscription activated"})
        else:
            # Log failed payment
            db.log_payment(telegram_id, amount, reference, "FAILED", package_days)
            logger.warning(f"❌ Payment FAILED for {telegram_id}: {status}")
            return JSONResponse({"status": "failed", "message": "Payment failed"})
            
    except Exception as e:
        logger.error(f"❌ Payment callback error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def send_telegram_notification(chat_id: int, message: str):
    """Sends a notification to a user via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN not set, cannot send notification")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                logger.info(f"📨 Notification sent to {chat_id}")
            else:
                logger.warning(f"⚠️ Notification failed: {response.text}")
    except Exception as e:
        logger.error(f"❌ Telegram notification error: {e}")


# ==================== OTHER ROUTES ====================

@app.get("/safety", response_class=HTMLResponse)
async def safety(request: Request):
    """Safety page - shows blacklist and verification info."""
    return templates.TemplateResponse("safety.html", {"request": request})


@app.get("/api/providers")
async def api_providers(
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """JSON API endpoint for providers."""
    providers = db.get_active_providers(city, neighborhood)
    return {"providers": providers, "count": len(providers)}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

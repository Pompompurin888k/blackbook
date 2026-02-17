import os
import logging
import json
import hmac
import hashlib
from collections import OrderedDict
import httpx
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
from urllib.parse import quote
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Blackbook Directory", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Database connection
db = Database()

# Telegram Bot Token for sending notifications
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
MEGAPAY_CALLBACK_SECRET = os.getenv("MEGAPAY_CALLBACK_SECRET")
ENABLE_SEED_ENDPOINT = os.getenv("ENABLE_SEED_ENDPOINT", "false").strip().lower() == "true"
LOCALHOSTS = {"127.0.0.1", "::1", "localhost"}
VALID_PACKAGE_DAYS = {0, 3, 7, 30, 90}
BOOST_DURATION_HOURS = int(os.getenv("BOOST_DURATION_HOURS", "12"))
BOOST_PRICE = int(os.getenv("BOOST_PRICE", "100"))
PACKAGE_PRICES = {
    3: int(os.getenv("PACKAGE_PRICE_3", "300")),
    7: int(os.getenv("PACKAGE_PRICE_7", "600")),
    30: int(os.getenv("PACKAGE_PRICE_30", "1500")),
    90: int(os.getenv("PACKAGE_PRICE_90", "4000")),
}

# Photo file-path cache (in-memory for now, consider Redis for production)
MAX_PHOTO_CACHE_ITEMS = int(os.getenv("MAX_PHOTO_CACHE_ITEMS", "2000"))
photo_url_cache = OrderedDict()

FALLBACK_PROFILE_IMAGES = [
    "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&q=80&w=900",
    "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&q=80&w=900",
]


def _to_string_list(value) -> list[str]:
    """Normalizes a DB value to a flat string list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        if "," in text:
            return [item.strip() for item in text.split(",") if item.strip()]
        return [text]
    return []


def _fallback_image(seed: int, offset: int = 0) -> str:
    index = (seed + offset) % len(FALLBACK_PROFILE_IMAGES)
    return FALLBACK_PROFILE_IMAGES[index]


def _sanitize_phone(value: Optional[str]) -> str:
    if not value:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) >= 9:
        digits = "254" + digits[1:]
    return digits


def _build_gallery_urls(provider_id: int, photo_ids: list[str]) -> list[str]:
    urls = [f"/photo/{file_id}" for file_id in photo_ids if file_id]
    while len(urls) < 5:
        urls.append(_fallback_image(provider_id, len(urls)))
    return urls


def _normalize_provider(provider: dict) -> dict:
    """Builds a stable profile payload for the template."""
    profile = dict(provider)
    services_list = _to_string_list(profile.get("services"))
    languages_list = _to_string_list(profile.get("languages"))
    photo_ids = _to_string_list(profile.get("profile_photos"))

    profile["services_list"] = services_list
    profile["languages_list"] = languages_list
    profile["primary_location"] = profile.get("neighborhood") or profile.get("city") or "Nairobi"
    profile["photo_urls"] = _build_gallery_urls(profile.get("id", 0), photo_ids)
    profile["availability_label"] = profile.get("availability_type") or (
        "Available now" if profile.get("is_online") else "By booking"
    )
    profile["response_hint"] = (
        "Usually replies in under 15 minutes"
        if profile.get("is_online")
        else "Usually replies in under 1 hour"
    )
    profile["last_active_hint"] = "Online now" if profile.get("is_online") else "Active today"
    phone_digits = _sanitize_phone(profile.get("phone"))
    profile["phone_digits"] = phone_digits

    rate_fields = [
        ("30 min", "rate_30min"),
        ("1 hour", "rate_1hr"),
        ("2 hours", "rate_2hr"),
        ("3 hours", "rate_3hr"),
        ("Overnight", "rate_overnight"),
    ]
    rate_cards = []
    for label, field in rate_fields:
        amount = profile.get(field)
        if isinstance(amount, (int, float)) and amount > 0:
            rate_cards.append({"label": label, "amount": int(amount)})
    profile["rate_cards"] = rate_cards
    default_message = quote(f"Hi {profile.get('display_name', '')}, are you available?")
    profile["call_url"] = f"tel:+{phone_digits}" if phone_digits else f"/contact/{profile.get('id')}/direct"
    profile["whatsapp_url"] = (
        f"https://wa.me/{phone_digits}?text={default_message}"
        if phone_digits
        else f"/contact/{profile.get('id')}/direct"
    )
    profile["has_phone"] = bool(phone_digits)
    return profile


def _normalize_recommendation(provider: dict) -> dict:
    card = dict(provider)
    photo_ids = _to_string_list(card.get("profile_photos"))
    card["photo_url"] = f"/photo/{photo_ids[0]}" if photo_ids else _fallback_image(card.get("id", 0))
    card["location"] = card.get("neighborhood") or card.get("city") or "Nairobi"
    card["services_list"] = _to_string_list(card.get("services"))[:2]
    return card


def _is_valid_callback_signature(raw_body: bytes, signature: Optional[str]) -> bool:
    """Validates callback signature using HMAC SHA256."""
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


def _cache_photo_path(file_id: str, file_path: str) -> None:
    """Caches Telegram file paths with a bounded in-memory size."""
    if file_id in photo_url_cache:
        photo_url_cache.move_to_end(file_id)
    photo_url_cache[file_id] = file_path
    if len(photo_url_cache) > MAX_PHOTO_CACHE_ITEMS:
        photo_url_cache.popitem(last=False)


@app.get("/photo/{file_id}")
async def get_photo(file_id: str):
    """
    Proxy endpoint to serve Telegram photos.
    Fetches file path from Telegram API and streams the photo bytes.
    Caches results to minimize API calls.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN not set, cannot fetch photo")
        # Return a placeholder image
        return RedirectResponse(
            url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
            status_code=302
        )

    try:
        file_path = photo_url_cache.get(file_id)
        async with httpx.AsyncClient(timeout=30.0) as client:
            if not file_path:
                meta = await client.get(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile",
                    params={"file_id": file_id}
                )
                data = meta.json()
                if not data.get("ok") or not data.get("result", {}).get("file_path"):
                    logger.warning(f"⚠️ Failed to get file path for {file_id}: {data}")
                    return RedirectResponse(
                        url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
                        status_code=302
                    )
                file_path = data["result"]["file_path"]
                _cache_photo_path(file_id, file_path)

            photo_response = await client.get(
                f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            )
            if photo_response.status_code != 200:
                logger.warning(f"⚠️ Failed to fetch photo bytes for {file_id}: {photo_response.status_code}")
                return RedirectResponse(
                    url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
                    status_code=302
                )

            return Response(
                content=photo_response.content,
                media_type=photo_response.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": "public, max-age=3600"},
            )
    except Exception as e:
        logger.error(f"❌ Error fetching photo {file_id}: {e}")
        return RedirectResponse(
            url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=800",
            status_code=302
        )


# Available cities and neighborhoods
CITIES = ["Nairobi", "Eldoret", "Mombasa"]

# Neighborhoods per city (Comprehensive coverage)
NEIGHBORHOODS = {
    "Nairobi": [
        "Allsops", "Athi River", "Banana", "Buru Buru", "Chokaa", "Dagoretti", 
        "Dandora", "Donholm", "Eastlands", "Eastleigh", "Embakasi", "Garden City",
        "Githurai 44", "Githurai 45", "Homeland", "Hurlingham", "Huruma", "Imara Daima",
        "Jamhuri", "Joska", "Juja", "Kabete", "Kahawa Sukari", "Kahawa Wendani", 
        "Kahawa West", "Kamulu", "Kangemi", "Karen", "Kariobangi", "Kasarani",
        "Kawangware", "Kayole", "Kenyatta Road", "Kibera", "Kikuyu", "Kileleshwa",
        "Kilimani", "Kitengela", "Kitisuru", "Komarock", "Langata", "Lavington",
        "Loresho", "Madaraka", "Makadara", "Malaa", "Mathare", "Milimani",
        "Mlolongo", "Muthaiga", "Muthangari", "Muthurwa", "Mwiki", "Nairobi Town",
        "Nairobi West", "Ndenderu", "Ngara", "Ngong", "Ngumba", "Njiru",
        "Ongata Rongai", "Pangani", "Parklands", "Roasters", "Roysambu", "Ruai",
        "Ruaka", "Ruaraka", "Ruiru", "Runda", "Saika", "South B", "South C",
        "Syokimau", "Thika", "Thogoto", "Thome", "Umoja", "Upper Hill",
        "Utawala", "Uthiru", "Westlands"
    ],
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
    from datetime import datetime
    
    # Default to Nairobi if no city selected
    if not city:
        city = "Nairobi"

    providers = db.get_active_providers(city, neighborhood)
    city_counts = db.get_city_counts()
    total_count = sum(city_counts.values())
    
    # Get stats for hero section
    total_verified = db.get_total_verified_count()
    total_online = db.get_online_count()
    total_premium = db.get_premium_count()
    
    # Get neighborhoods for selected city
    neighborhoods = NEIGHBORHOODS.get(city, []) if city else []
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "providers": providers,
        "cities": CITIES,
        "selected_city": city,
        "selected_neighborhood": neighborhood,
        "neighborhoods": neighborhoods,
        "neighborhood_map": NEIGHBORHOODS,
        "city_counts": city_counts,
        "total_count": total_count,
        "total_verified": total_verified,
        "total_online": total_online,
        "total_premium": total_premium,
        "now": datetime.now  # Pass datetime for template calculations
    })


@app.get("/api/grid", response_class=HTMLResponse)
async def api_grid(
    request: Request,
    city: Optional[str] = Query(None),
    neighborhood: Optional[str] = Query(None)
):
    """
    HTMX endpoint - returns only the provider grid HTML.
    Used for seamless filtering without full page reload.
    """
    from datetime import datetime
    
    providers = db.get_active_providers(city, neighborhood)
    
    return templates.TemplateResponse("_grid.html", {
        "request": request,
        "providers": providers,
        "selected_city": city,
        "now": datetime.now  # Pass datetime for template calculations
    })


@app.get("/api/recommendations", response_class=HTMLResponse)
async def api_recommendations(
    request: Request,
    city: str,
    exclude_id: int
):
    """
    HTMX endpoint - returns smart recommended providers HTML with relevance indicators.
    """
    recommendations = db.get_recommendations(city, exclude_id, limit=4)
    
    # Get source provider for comparison
    source_provider = db.get_provider_by_id(exclude_id)
    
    # Add relevance hints to each recommendation
    enriched_recommendations = []
    for rec in recommendations:
        rec_dict = dict(rec)
        hints = []
        
        if source_provider:
            # Same neighborhood
            if rec.get('neighborhood') == source_provider.get('neighborhood'):
                hints.append("From your area")
            # Same build
            elif rec.get('build') and rec.get('build') == source_provider.get('build'):
                hints.append("Similar style")
            # Recently verified
            elif rec.get('created_at'):
                from datetime import datetime, timedelta
                if rec['created_at'] > datetime.now() - timedelta(days=30):
                    hints.append("Recently verified")
            # Online
            if rec.get('is_online'):
                if not hints:
                    hints.append("Available now")
        
        rec_dict['relevance_hint'] = hints[0] if hints else None
        enriched_recommendations.append(rec_dict)
    
    return templates.TemplateResponse("_recommendations.html", {
        "request": request,
        "providers": enriched_recommendations,
        "selected_city": city
    })


@app.get("/seed")
async def seed_data(request: Request):
    """Seeds the database with test data."""
    if not ENABLE_SEED_ENDPOINT:
        return JSONResponse({"status": "error", "message": "Not found"}, status_code=404)
    client_host = request.client.host if request.client else None
    if client_host not in LOCALHOSTS:
        return JSONResponse({"status": "error", "message": "Forbidden"}, status_code=403)
    db.seed_test_providers()
    return {"status": "seeded", "message": "Test providers added."}


@app.get("/api/status/{provider_id}", response_class=HTMLResponse)
async def get_provider_status(provider_id: int):
    """
    Real-time status endpoint for HTMX polling.
    Returns the Live badge HTML if provider is online.
    """
    provider = db.get_provider_by_id(provider_id)
    
    if provider and provider.get("is_online"):
        return f'''
        <div id="live-badge-{provider_id}"
             hx-get="/api/status/{provider_id}"
             hx-trigger="every 30s"
             hx-swap="outerHTML"
             class="glass px-2 py-1 rounded-full flex items-center gap-1">
            <span class="h-2 w-2 bg-green-500 rounded-full animate-pulse"></span>
            <span class="text-[10px] text-green-400 font-bold uppercase">Live</span>
        </div>
        '''
    else:
        # Provider is offline - return empty badge that still polls
        return f'''
        <div id="live-badge-{provider_id}"
             hx-get="/api/status/{provider_id}"
             hx-trigger="every 30s"
             hx-swap="outerHTML">
        </div>
        '''


@app.get("/contact/{provider_id}", response_class=HTMLResponse)
async def contact_page(request: Request, provider_id: int):
    """
    Contact page - shows Direct vs Discreet messaging options.
    Preserves client privacy with stealth mode.
    """
    provider = db.get_provider_by_id(provider_id)
    
    if not provider:
        return RedirectResponse(url="/", status_code=302)

    profile = _normalize_provider(provider)
    recommendations = db.get_recommendations(profile.get("city") or "Nairobi", provider_id, limit=4)
    recommendation_cards = [_normalize_recommendation(item) for item in recommendations]
    
    # Log the contact click
    logger.info(f"📲 Contact page: Provider ID {provider_id} ({provider.get('display_name', 'Unknown')})")
    
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "provider": profile,
        "recommendations": recommendation_cards,
    })


@app.get("/contact/{provider_id}/direct")
async def contact_direct(provider_id: int):
    """Direct message - opens Telegram with a clear first message."""
    provider = db.get_provider_by_id(provider_id)
    
    if not provider:
        return RedirectResponse(url="/", status_code=302)
    
    telegram_id = provider.get("telegram_id")
    username = provider.get("telegram_username")
    name = provider.get("display_name", "")
    message = f"Hi {name}, I found you on Blackbook. Are you available?"
    
    logger.info(f"📲 Direct contact: {provider_id} ({name})")
    
    if username:
        return RedirectResponse(url=f"https://t.me/{username}?text={quote(message)}", status_code=302)
    else:
        # Fallback: tg://user deep link (works on mobile/desktop Telegram)
        return RedirectResponse(url=f"tg://openmessage?user_id={telegram_id}", status_code=302)


@app.get("/contact/{provider_id}/discreet")
async def contact_discreet(provider_id: int):
    """Discreet message - opens Telegram with a vague, safe message."""
    provider = db.get_provider_by_id(provider_id)
    
    if not provider:
        return RedirectResponse(url="/", status_code=302)
    
    telegram_id = provider.get("telegram_id")
    username = provider.get("telegram_username")
    name = provider.get("display_name", "")
    # Discreet message that doesn't mention Blackbook or the nature of service
    message = "Hi, is this a good time to talk?"
    
    logger.info(f"🔒 Discreet contact: {provider_id} ({name})")
    
    if username:
        return RedirectResponse(url=f"https://t.me/{username}?text={quote(message)}", status_code=302)
    else:
        return RedirectResponse(url=f"tg://openmessage?user_id={telegram_id}", status_code=302)


# ==================== PAYMENT CALLBACK ====================

@app.post("/payments/callback")
async def megapay_callback(request: Request):
    """
    Handle MegaPay payment callback.
    When payment succeeds, activates the provider's subscription.
    """
    try:
        if not MEGAPAY_CALLBACK_SECRET:
            logger.error("❌ MEGAPAY_CALLBACK_SECRET not configured. Rejecting callback.")
            return JSONResponse({"status": "error", "message": "Callback secret not configured"}, status_code=503)

        raw_body = await request.body()
        signature = request.headers.get("X-MegaPay-Signature") or request.headers.get("X-Signature")
        if not _is_valid_callback_signature(raw_body, signature):
            logger.warning("⚠️ Invalid or missing callback signature.")
            return JSONResponse({"status": "error", "message": "Invalid signature"}, status_code=403)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return JSONResponse({"status": "error", "message": "Invalid JSON payload"}, status_code=400)

        logger.info(f"💳 Payment callback received (verified): {payload}")

        # Extract data from MegaPay response
        status = payload.get("status") or payload.get("ResultCode")
        reference = payload.get("MpesaReceiptNumber") or payload.get("TransactionId") or payload.get("reference")
        amount_raw = payload.get("Amount") or payload.get("amount")
        account_ref = (
            payload.get("AccountReference")
            or payload.get("account_reference")
            or (reference if isinstance(reference, str) and reference.startswith("BB_") else "")
        )

        if not reference:
            logger.error("❌ Missing payment reference in callback payload.")
            return JSONResponse({"status": "error", "message": "Missing payment reference"}, status_code=400)

        # Parse telegram_id and package_days from account reference.
        # Supports both BB_<tg>_<days> and BB_<tg>_<days>_<nonce>.
        parts = account_ref.split("_")
        if len(parts) >= 3 and parts[0] == "BB":
            try:
                telegram_id = int(parts[1])
                package_days = int(parts[2])
            except ValueError:
                logger.error(f"❌ Invalid account reference values: {account_ref}")
                return JSONResponse({"status": "error", "message": "Invalid account reference"}, status_code=400)
        else:
            logger.error(f"❌ Invalid account reference format: {account_ref}")
            return JSONResponse({"status": "error", "message": "Invalid account reference"}, status_code=400)

        if package_days not in VALID_PACKAGE_DAYS:
            logger.error(f"❌ Invalid package_days value from callback: {package_days}")
            return JSONResponse({"status": "error", "message": "Invalid package days"}, status_code=400)

        try:
            amount = int(float(amount_raw))
        except (TypeError, ValueError):
            logger.error(f"❌ Invalid amount in callback payload: {amount_raw}")
            return JSONResponse({"status": "error", "message": "Invalid amount"}, status_code=400)

        expected_amount = BOOST_PRICE if package_days == 0 else PACKAGE_PRICES.get(package_days)
        if expected_amount is None or amount != expected_amount:
            logger.error(
                f"❌ Amount mismatch for {reference}: expected {expected_amount}, got {amount}"
            )
            return JSONResponse({"status": "error", "message": "Invalid payment amount"}, status_code=400)

        # Idempotency: already-processed successful transaction
        if db.has_successful_payment(reference):
            logger.info(f"ℹ️ Duplicate callback ignored for reference {reference}")
            return JSONResponse({"status": "success", "message": "Already processed"})

        # Check if payment was successful
        success_markers = {"0", "200", "success", "completed", "succeeded", "ok"}
        success = str(status).strip().lower() in success_markers

        if success:
            provider_data = db.get_provider_by_telegram_id(telegram_id)
            if not provider_data:
                logger.warning(f"⚠️ Callback references unknown provider: {telegram_id}")
                db.log_payment(telegram_id, amount, reference, "FAILED_NO_PROVIDER", package_days)
                return JSONResponse({"status": "error", "message": "Provider not found"}, status_code=404)

            if not provider_data.get("is_verified"):
                logger.warning(f"⚠️ Callback rejected for unverified provider: {telegram_id}")
                db.log_payment(telegram_id, amount, reference, "REJECTED_UNVERIFIED", package_days)
                return JSONResponse({"status": "error", "message": "Provider not verified"}, status_code=403)

            # Boost transaction
            if package_days == 0:
                if not db.boost_provider(telegram_id, BOOST_DURATION_HOURS):
                    logger.error(f"❌ Failed to boost provider {telegram_id}")
                    return JSONResponse({"status": "error", "message": "Failed to activate boost"}, status_code=400)
                if not db.log_payment(telegram_id, amount, reference, "SUCCESS", package_days):
                    logger.error(f"❌ Failed to log successful boost payment for {telegram_id}")
                    return JSONResponse({"status": "error", "message": "Failed to log payment"}, status_code=500)

                from datetime import datetime, timedelta
                boost_until = datetime.now() + timedelta(hours=BOOST_DURATION_HOURS)
                await send_telegram_notification(
                    telegram_id,
                    f"🚀 **Boost Activated!**\n\n"
                    f"💰 Amount: {amount} KES\n"
                    f"⏱️ Duration: {BOOST_DURATION_HOURS} hours\n"
                    f"📈 Active until: **{boost_until.strftime('%Y-%m-%d %H:%M')}**\n\n"
                    f"Your profile is now prioritized in results."
                )
                logger.info(f"✅ Boost SUCCESS: Provider {telegram_id} boosted for {BOOST_DURATION_HOURS} hours")
                return JSONResponse({"status": "success", "message": "Boost activated"})

            # Subscription transaction
            if not db.activate_subscription(telegram_id, package_days):
                logger.error(f"❌ Failed to activate subscription for {telegram_id}")
                return JSONResponse({"status": "error", "message": "Failed to activate subscription"}, status_code=500)
            if not db.log_payment(telegram_id, amount, reference, "SUCCESS", package_days):
                logger.error(f"❌ Failed to log successful payment for {telegram_id}")
                return JSONResponse({"status": "error", "message": "Failed to log payment"}, status_code=500)

            # === REFERRAL REWARD ===
            # If this provider was referred, reward the referrer
            referrer_id = provider_data.get("referred_by") if provider_data else None
            if referrer_id:
                try:
                    commission = int(float(amount or 0) * 0.20)  # 20% commission as credit
                    if commission > 0:
                        db.add_referral_credits(referrer_id, commission)
                    # Also give 1 free day
                    db.extend_subscription(referrer_id, 1)
                    await send_telegram_notification(
                        referrer_id,
                        f"🎁 **Referral Reward!**\n\n"
                        f"Someone you referred just subscribed!\n"
                        f"💰 +{commission} KES credit added\n"
                        f"📅 +1 bonus day added\n\n"
                        f"Keep sharing your link to earn more! 🤝"
                    )
                    logger.info(f"🤝 Referral reward: {commission} KES credit + 1 day to {referrer_id}")
                except Exception as ref_err:
                    logger.error(f"⚠️ Referral reward error (non-fatal): {ref_err}")

            neighborhood = provider_data.get("neighborhood", "your area")

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

        db.log_payment(telegram_id, amount, reference, "FAILED", package_days)
        logger.warning(f"❌ Payment FAILED for {telegram_id}: {status}")
        return JSONResponse({"status": "failed", "message": "Payment failed"})

    except Exception as e:
        logger.error(f"❌ Payment callback error: {e}")
        return JSONResponse({"status": "error", "message": "Internal callback error"}, status_code=500)


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
    providers = db.get_public_active_providers(city, neighborhood)
    return {"providers": providers, "count": len(providers)}


@app.post("/api/analytics")
async def api_analytics(request: Request):
    """Receives lightweight frontend analytics events."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

    event = str(payload.get("event", "")).strip()
    event_payload = payload.get("payload", {})
    if not event:
        return JSONResponse({"status": "error", "message": "Missing event"}, status_code=400)
    if not isinstance(event_payload, dict):
        event_payload = {"value": str(event_payload)}

    ok = db.log_analytics_event(event_name=event, event_payload=event_payload)
    if not ok:
        return JSONResponse({"status": "error", "message": "Failed"}, status_code=500)
    return {"status": "ok"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

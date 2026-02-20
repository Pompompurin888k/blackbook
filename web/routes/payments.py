"""
Payment Routes — Webhook endpoint for MegaPay.
"""
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import (
    INTERNAL_TASK_TOKEN, MEGAPAY_CALLBACK_SECRET,
    VALID_PACKAGE_DAYS, BOOST_PRICE, PACKAGE_PRICES,
    BOOST_DURATION_HOURS,
)
from database import Database
from services.redis_service import _enqueue_payment_callback
from services.telegram_service import send_admin_alert, send_telegram_notification
from utils.auth import _is_valid_callback_signature
from payment_queue_utils import extract_callback_reference

db = Database()
router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/payments/callback")
async def megapay_callback(request: Request):
    """
    Handle MegaPay payment callback.
    When payment succeeds, activates the provider's subscription.
    """
    try:
        internal_token = request.headers.get("X-Internal-Task-Token", "")
        internal_mode = bool(INTERNAL_TASK_TOKEN and internal_token == INTERNAL_TASK_TOKEN)
        if not internal_mode and not MEGAPAY_CALLBACK_SECRET:
            logger.error("❌ MEGAPAY_CALLBACK_SECRET not configured. Rejecting callback.")
            return JSONResponse({"status": "error", "message": "Callback secret not configured"}, status_code=503)

        raw_body = await request.body()
        signature = None if internal_mode else (request.headers.get("X-MegaPay-Signature") or request.headers.get("X-Signature"))
        if not internal_mode and not _is_valid_callback_signature(raw_body, signature):
            logger.warning("⚠️ Invalid or missing callback signature.")
            return JSONResponse({"status": "error", "message": "Invalid signature"}, status_code=403)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return JSONResponse({"status": "error", "message": "Invalid JSON payload"}, status_code=400)

        if not internal_mode and not extract_callback_reference(payload):
            logger.error("❌ Missing payment reference in callback payload.")
            return JSONResponse({"status": "error", "message": "Missing payment reference"}, status_code=400)

        if not internal_mode and await _enqueue_payment_callback(payload):
            logger.info("Queued payment callback for background processing.")
            return JSONResponse({"status": "success", "message": "Callback queued"}, status_code=200)

        logger.info(f"💳 Payment callback processing payload: {payload}")

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

            is_first_payment = not db.has_successful_payment_for_provider(telegram_id)

            # Boost transaction
            if package_days == 0:
                if not db.boost_provider(telegram_id, BOOST_DURATION_HOURS):
                    logger.error(f"❌ Failed to boost provider {telegram_id}")
                    await send_admin_alert(
                        f"Web callback error: failed boost activation for provider {telegram_id}, reference {reference}."
                    )
                    return JSONResponse({"status": "error", "message": "Failed to activate boost"}, status_code=400)
                if not db.log_payment(telegram_id, amount, reference, "SUCCESS", package_days):
                    logger.error(f"❌ Failed to log successful boost payment for {telegram_id}")
                    await send_admin_alert(
                        f"Web callback error: failed to log boost payment for provider {telegram_id}, reference {reference}."
                    )
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
                db.log_funnel_event(
                    telegram_id,
                    "boost_purchased",
                    {"amount": amount, "hours": BOOST_DURATION_HOURS, "reference": reference},
                )
                logger.info(f"✅ Boost SUCCESS: Provider {telegram_id} boosted for {BOOST_DURATION_HOURS} hours")
                return JSONResponse({"status": "success", "message": "Boost activated"})

            # Subscription transaction
            if not db.activate_subscription(telegram_id, package_days):
                logger.error(f"❌ Failed to activate subscription for {telegram_id}")
                await send_admin_alert(
                    f"Web callback error: failed subscription activation for provider {telegram_id}, reference {reference}."
                )
                return JSONResponse({"status": "error", "message": "Failed to activate subscription"}, status_code=500)
            if not db.log_payment(telegram_id, amount, reference, "SUCCESS", package_days):
                logger.error(f"❌ Failed to log successful payment for {telegram_id}")
                await send_admin_alert(
                    f"Web callback error: failed to log successful payment for provider {telegram_id}, reference {reference}."
                )
                return JSONResponse({"status": "error", "message": "Failed to log payment"}, status_code=500)
            db.log_funnel_event(
                telegram_id,
                "paid_success",
                {"amount": amount, "days": package_days, "reference": reference},
            )
            db.log_funnel_event(
                telegram_id,
                "active_live",
                {"source": "payment", "days": package_days},
            )

            # === REFERRAL REWARD ===
            # If this provider was referred, reward the referrer on their first payment
            referrer_id = provider_data.get("referred_by") if provider_data else None
            if referrer_id and is_first_payment:
                try:
                    commission = int(float(amount or 0) * 0.20)  # 20% commission
                    if commission > 0:
                        reward_id = db.create_referral_reward(referrer_id, telegram_id, amount, commission, 3)
                        if reward_id:
                            reply_markup = {
                                "inline_keyboard": [
                                    [{"text": f"💰 {commission} KES Credit", "callback_data": f"ref_reward_{reward_id}_credit"}],
                                    [{"text": "📅 3 Free Days", "callback_data": f"ref_reward_{reward_id}_days"}]
                                ]
                            }
                            await send_telegram_notification(
                                referrer_id,
                                f"🎉 **Referral Success!**\n\n"
                                f"Someone you referred just made their first payment.\n"
                                f"Choose your reward below:",
                                reply_markup=reply_markup
                            )
                            logger.info(f"🤝 Created pending referral reward {reward_id} for {referrer_id}")
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
        await send_admin_alert(f"Web callback crashed with exception: {e}")
        return JSONResponse({"status": "error", "message": "Internal callback error"}, status_code=500)

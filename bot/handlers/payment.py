"""
Blackbook Bot - Payment Handlers
Handles: /topup, payment menu callbacks, STK push integration
"""
import logging
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import TOPUP_PHONE, TOPUP_CONFIRM, get_package_price
from utils.keyboards import (
    get_package_keyboard,
    get_menu_package_keyboard,
    get_phone_confirm_keyboard,
    get_topup_phone_confirm_keyboard,
    get_payment_failed_keyboard,
    get_back_button,
)
from services.metapay import initiate_stk_push

logger = logging.getLogger(__name__)


def get_db():
    """Gets the database instance from db_context module."""
    from db_context import get_db as _get_db
    return _get_db()


# ==================== MENU CALLBACKS ====================

async def payment_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles payment-related menu callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    action = query.data.replace("menu_", "")
    db = get_db()
    provider = db.get_provider(user.id)
    
    # === TOPUP / GO LIVE SCREEN ===
    if action == "topup":
        status_text = ""
        if provider and provider.get("is_active"):
            expiry = provider.get("expiry_date")
            if expiry:
                status_text = f"\n\n📅 Current subscription expires: {expiry.strftime('%Y-%m-%d')}"
        
        await query.edit_message_text(
            "💰 *LISTING MANAGEMENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Active listings receive *400% more engagement*.{status_text}\n\n"
            "Select your package:",
            reply_markup=get_menu_package_keyboard(),
            parse_mode="Markdown"
        )
    
    # === PAYMENT: USE SAVED PHONE ===
    elif action == "pay_confirm":
        saved_phone = db.get_provider_phone(user.id)
        days = context.user_data.get("topup_days", 3)
        price = context.user_data.get("topup_price", 400)
        
        await query.edit_message_text(
            "⏳ *Initiating Secure Payment...*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"A prompt will appear on `{saved_phone}`.\n"
            "Enter your M-Pesa PIN to authorize.",
            reply_markup=get_back_button(),
            parse_mode="Markdown"
        )
        
        result = await initiate_stk_push(saved_phone, price, user.id, days)
        
        if result["success"]:
            neighborhood = provider.get('neighborhood', 'your area') if provider else 'your area'
            await context.bot.send_message(
                chat_id=user.id,
                text="✅ *Transaction Initiated*\n\n"
                     f"📱 Check your phone: `{saved_phone}`\n"
                     f"💰 Amount: {price} KES\n\n"
                     f"_Your profile will appear in {neighborhood} once confirmed._",
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"❌ *Payment Failed*\n\n{result['message']}\n\nPlease try again.",
                reply_markup=get_payment_failed_keyboard(),
                parse_mode="Markdown"
            )
    
    # === PAYMENT: NEW PHONE NUMBER ===
    elif action == "pay_newphone":
        days = context.user_data.get("topup_days", 3)
        price = context.user_data.get("topup_price", 400)
        
        await query.edit_message_text(
            f"📦 *{days} Day Package — {price} KES*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Please type your M-Pesa phone number:\n"
            "_Format: 0712345678_",
            reply_markup=get_back_button("menu_topup"),
            parse_mode="Markdown"
        )
        context.user_data["awaiting_phone"] = True
    
    # === PAYMENT PACKAGE SELECTION ===
    elif action.startswith("pay_"):
        days = int(action.replace("pay_", ""))
        price = 400 if days == 3 else 800
        
        context.user_data["topup_days"] = days
        context.user_data["topup_price"] = price
        
        saved_phone = db.get_provider_phone(user.id) if provider else None
        
        if saved_phone:
            await query.edit_message_text(
                f"📦 *{days} Day Package — {price} KES*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"We have your M-Pesa number saved:\n"
                f"📱 `{saved_phone}`\n\n"
                "Use this number?",
                reply_markup=get_phone_confirm_keyboard(saved_phone),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"📦 *{days} Day Package — {price} KES*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Please type your M-Pesa phone number:\n"
                "_Format: 0712345678_",
                reply_markup=get_back_button("menu_topup"),
                parse_mode="Markdown"
            )
            context.user_data["awaiting_phone"] = True


# ==================== /TOPUP COMMAND ====================

async def topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the topup process - shows package selection."""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You need to /register first before topping up.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if not provider.get("is_verified"):
        await update.message.reply_text(
            "❌ You need to complete /verify first before topping up.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    status_text = ""
    if provider.get("is_active"):
        expiry = provider.get("expiry_date")
        if expiry:
            status_text = f"\n\n📅 Current subscription expires: {expiry.strftime('%Y-%m-%d %H:%M')}"
    
    await update.message.reply_text(
        "💰 *Listing Management*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Active listings receive *400% more engagement*.{status_text}\n\n"
        "⏰ *3 Days Package* — 300 KES\n"
        "🔥 *7 Days Package* — 600 KES (1 day FREE!)",
        reply_markup=get_package_keyboard(),
        parse_mode="Markdown"
    )
    return TOPUP_PHONE


async def topup_package_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles package selection and asks for phone number."""
    query = update.callback_query
    await query.answer()
    db = get_db()
    
    days = int(query.data.replace("topup_", ""))
    price = get_package_price(days)
    
    context.user_data["topup_days"] = days
    context.user_data["topup_price"] = price
    
    user = query.from_user
    saved_phone = db.get_provider_phone(user.id)
    
    if saved_phone:
        await query.edit_message_text(
            f"📦 **{days} Day Package - {price} KES**\n\n"
            f"We have your number saved:\n📱 `{saved_phone}`\n\n"
            "Use this number for M-Pesa?",
            reply_markup=get_topup_phone_confirm_keyboard(saved_phone),
            parse_mode="Markdown"
        )
        return TOPUP_CONFIRM
    else:
        await query.edit_message_text(
            f"📦 **{days} Day Package - {price} KES**\n\n"
            "Please enter your **M-Pesa phone number**:\n"
            "_Format: 0712345678 or 254712345678_",
            parse_mode="Markdown"
        )
        return TOPUP_PHONE


async def topup_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles phone number input for topup."""
    user = update.effective_user
    db = get_db()
    phone = update.message.text.strip()
    
    phone_clean = phone.replace(" ", "").replace("-", "").replace("+", "")
    if not phone_clean.isdigit() or len(phone_clean) < 9:
        await update.message.reply_text(
            "❌ Invalid phone number. Please enter a valid M-Pesa number:\n"
            "_Format: 0712345678 or 254712345678_",
            parse_mode="Markdown"
        )
        return TOPUP_PHONE
    
    db.update_provider_phone(user.id, phone_clean)
    context.user_data["topup_phone"] = phone_clean
    
    days = context.user_data.get("topup_days", 3)
    price = context.user_data.get("topup_price", 400)
    
    await update.message.reply_text(
        "⏳ *Initiating Secure Payment...*\n\n"
        f"A prompt will appear on your phone (`{phone_clean}`). "
        "Enter your PIN to authorize the listing.",
        parse_mode="Markdown"
    )
    
    result = await initiate_stk_push(phone_clean, price, user.id, days)
    
    if result["success"]:
        provider = db.get_provider(user.id)
        neighborhood = provider.get('neighborhood', 'your area') if provider else 'your area'
        await update.message.reply_text(
            "✅ *Transaction Initiated.*\n\n"
            f"📱 Check your phone: `{phone_clean}`\n"
            f"💰 Amount: {price} KES\n\n"
            "Enter your M-Pesa PIN to confirm.\n\n"
            f"_Your profile will be visible in the {neighborhood} section once confirmed._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ **Payment Request Failed**\n\n"
            f"{result['message']}\n\n"
            "Please try /topup again.",
            parse_mode="Markdown"
        )
    
    context.user_data.clear()
    return ConversationHandler.END


async def topup_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles confirmation of saved phone or new phone request."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db = get_db()
    
    if query.data == "topup_use_saved":
        phone = db.get_provider_phone(user.id)
        days = context.user_data.get("topup_days", 3)
        price = context.user_data.get("topup_price", 400)
        
        await query.edit_message_text(
            "⏳ **Sending M-Pesa prompt...**\n\n"
            "Please check your phone and enter your PIN.",
            parse_mode="Markdown"
        )
        
        result = await initiate_stk_push(phone, price, user.id, days)
        
        if result["success"]:
            await query.message.reply_text(
                "✅ **M-Pesa Request Sent!**\n\n"
                f"📱 Check your phone ({phone})\n"
                f"💰 Amount: {price} KES\n\n"
                "_Enter your M-Pesa PIN to complete payment._\n\n"
                "Your profile will go LIVE automatically once we confirm payment!",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(
                f"❌ **Payment Request Failed**\n\n"
                f"{result['message']}\n\n"
                "Please try /topup again.",
                parse_mode="Markdown"
            )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    elif query.data == "topup_new_phone":
        await query.edit_message_text(
            "Please enter your **M-Pesa phone number**:\n"
            "_Format: 0712345678 or 254712345678_",
            parse_mode="Markdown"
        )
        return TOPUP_PHONE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the topup conversation."""
    await update.message.reply_text("❌ Payment cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


# ==================== HANDLER REGISTRATION ====================

def register_handlers(application):
    """Registers all payment-related handlers with the application."""
    
    # Topup conversation
    topup_handler = ConversationHandler(
        entry_points=[CommandHandler("topup", topup)],
        states={
            TOPUP_PHONE: [
                CallbackQueryHandler(topup_package_callback, pattern="^topup_[0-9]+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, topup_phone_input),
            ],
            TOPUP_CONFIRM: [
                CallbackQueryHandler(topup_confirm_callback, pattern="^topup_(use_saved|new_phone)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(topup_handler)
    
    # Menu callback handler
    application.add_handler(CallbackQueryHandler(
        payment_menu_callback,
        pattern="^menu_(topup|pay_confirm|pay_newphone|pay_\\d+)$"
    ))

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import ContextTypes

from db_context import get_db
from utils.keyboards import (
    get_photo_management_keyboard,
    get_photo_delete_keyboard,
    get_photo_reorder_keyboard,
    get_photo_viewer_keyboard,
)

logger = logging.getLogger(__name__)

async def photos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /photos command for photo gallery management."""
    user = update.effective_user
    db = get_db()
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You're not registered yet. Use /register first.",
            parse_mode="Markdown"
        )
        return
    
    photos = provider.get("profile_photos") or []
    if isinstance(photos, str):
        import json
        try:
            photos = json.loads(photos)
        except (json.JSONDecodeError, TypeError):
            photos = []
    
    photo_count = len(photos)
    
    await update.message.reply_text(
        "📸 *Photo Gallery Manager*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"You have *{photo_count}* photos in your gallery.\n\n"
        "Manage your profile photos below:",
        reply_markup=get_photo_management_keyboard(photo_count),
        parse_mode="Markdown"
    )

async def photos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles photo management callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    db = get_db()
    data = query.data
    
    provider = db.get_provider(user.id)
    photos = provider.get("profile_photos") or []
    if isinstance(photos, str):
        import json
        try:
            photos = json.loads(photos)
        except (json.JSONDecodeError, TypeError):
            photos = []
    
    # View photos (first photo or specific index)
    if data == "photos_view" or data.startswith("photo_view_"):
        if not photos:
            await query.answer("No photos to view!", show_alert=True)
            return
        
        # Get photo index
        if data == "photos_view":
            idx = 0
        else:
            idx = int(data.replace("photo_view_", ""))
        
        if idx >= len(photos):
            idx = 0
        
        caption = f"📸 *Photo {idx + 1} of {len(photos)}*"
        try:
            # If we're already on a photo message, update in place for smoother mobile UX.
            if query.message and query.message.photo and data.startswith("photo_view_"):
                await query.edit_message_media(
                    media=InputMediaPhoto(
                        media=photos[idx],
                        caption=caption,
                        parse_mode="Markdown",
                    ),
                    reply_markup=get_photo_viewer_keyboard(idx, len(photos)),
                )
                return

            # First open from manager view.
            await context.bot.send_photo(
                chat_id=user.id,
                photo=photos[idx],
                caption=caption,
                reply_markup=get_photo_viewer_keyboard(idx, len(photos)),
                parse_mode="Markdown",
            )

            # Cleanup old manager message only after successful send.
            if query.message:
                try:
                    await query.message.delete()
                except Exception:
                    pass
            return
        except Exception as e:
            logger.error(f"❌ Failed to open photo viewer for {user.id}: {e}")
            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    "⚠️ Couldn't open this photo.\n\n"
                    "Some older photos may be invalid after bot-token changes.\n"
                    "Please re-upload from 👤 My Profile → 📸 Photos."
                ),
                reply_markup=get_photo_management_keyboard(len(photos)),
            )
        return
    
    # Delete photo menu
    if data == "photos_delete":
        if not photos:
            await query.answer("No photos to delete!", show_alert=True)
            return
        
        await query.edit_message_text(
            "🗑️ *Delete Photo*\n\n"
            "Select which photo to remove:",
            reply_markup=get_photo_delete_keyboard(photos),
            parse_mode="Markdown"
        )
        return
    
    # Reorder photos menu
    if data == "photos_reorder":
        if len(photos) < 2:
            await query.answer("Need at least 2 photos to reorder!", show_alert=True)
            return
        
        await query.edit_message_text(
            "🔄 *Reorder Photos*\n\n"
            "Select which photo to move to the first position\n"
            "(This will be your primary profile photo):",
            reply_markup=get_photo_reorder_keyboard(photos),
            parse_mode="Markdown"
        )
        return
    
    # Add photos
    if data == "photos_add":
        context.user_data["photo_add_mode"] = True
        await query.edit_message_text(
            "📸 *Add Photos*\n\n"
            "Send your photo(s) now.\n"
            "You can keep adding until you reach 5 total.\n\n"
            "Tap *Done* when finished.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Done", callback_data="photos_manage")]
            ]),
        )
        return
    
    # Back to photo management
    if data == "photos_manage":
        context.user_data.pop("photo_add_mode", None)
        await query.edit_message_text(
            "📸 *Photo Gallery Manager*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"You have *{len(photos)}* photos in your gallery.\n\n"
            "Manage your profile photos below:",
            reply_markup=get_photo_management_keyboard(len(photos)),
            parse_mode="Markdown"
        )
        return
    
    # Delete specific photo
    if data.startswith("photo_del_"):
        idx = int(data.replace("photo_del_", ""))
        if 0 <= idx < len(photos):
            photos.pop(idx)
            db.save_provider_photos(user.id, photos)
            await query.edit_message_text(
                f"✅ *Photo #{idx + 1} Deleted!*\n\n"
                f"You now have {len(photos)} photos.",
                reply_markup=get_photo_management_keyboard(len(photos)),
                parse_mode="Markdown"
            )
        return
    
    # Move photo to first position
    if data.startswith("photo_first_"):
        idx = int(data.replace("photo_first_", ""))
        if 0 < idx < len(photos):
            photo_to_move = photos.pop(idx)
            photos.insert(0, photo_to_move)
            db.save_provider_photos(user.id, photos)
            await query.edit_message_text(
                f"✅ *Photo #{idx + 1} is now your primary photo!*\n\n"
                "This will be the first photo visitors see.",
                reply_markup=get_photo_management_keyboard(len(photos)),
                parse_mode="Markdown"
            )
        return

async def handle_photo_add_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Accepts photo uploads while user is in gallery add mode."""
    if not context.user_data.get("photo_add_mode"):
        return

    user = update.effective_user
    db = get_db()
    provider = db.get_provider(user.id)
    if not provider:
        context.user_data.pop("photo_add_mode", None)
        return

    photos = provider.get("profile_photos") or []
    if isinstance(photos, str):
        import json
        try:
            photos = json.loads(photos)
        except (json.JSONDecodeError, TypeError):
            photos = []

    if not update.message.photo:
        await update.message.reply_text("⚠️ Please send a photo.")
        return

    if len(photos) >= 5:
        context.user_data.pop("photo_add_mode", None)
        await update.message.reply_text(
            "✅ You already have 5 photos (maximum).",
            reply_markup=get_photo_management_keyboard(len(photos)),
            parse_mode="Markdown",
        )
        return

    photo_file_id = update.message.photo[-1].file_id
    photos.append(photo_file_id)
    db.save_provider_photos(user.id, photos)

    if len(photos) >= 5:
        context.user_data.pop("photo_add_mode", None)
        await update.message.reply_text(
            "✅ *Photo added!* You now have 5/5 photos.",
            reply_markup=get_photo_management_keyboard(len(photos)),
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        f"✅ *Photo added!* You now have {len(photos)}/5 photos.\n\n"
        "Send another photo or tap *Done* in the previous message.",
        parse_mode="Markdown",
    )

def register_handlers(application):
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
    
    application.add_handler(CommandHandler("photos", photos_command))
    application.add_handler(CallbackQueryHandler(
        photos_callback,
        pattern="^(photos_|photo_del_|photo_first_|photo_view_)"
    ))
    application.add_handler(MessageHandler(
        filters.PHOTO,
        handle_photo_add_mode
    ), group=2)

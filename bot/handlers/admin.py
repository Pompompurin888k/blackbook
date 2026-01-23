"""
Blackbook Bot - Admin Handlers
Handles: /partner, /maintenance, /broadcast
"""
import logging
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from config import is_admin, is_authorized_partner

logger = logging.getLogger(__name__)


def get_db(context: ContextTypes.DEFAULT_TYPE):
    """Gets the database instance from bot_data."""
    return context.bot_data.get("db")


# ==================== /PARTNER DASHBOARD ====================

async def partner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Partner dashboard command - shows recruitment statistics."""
    user = update.effective_user
    db = get_db(context)
    
    if not is_authorized_partner(user.id):
        await update.message.reply_text(
            "🚫 *Access Denied*\n\n"
            "You are not authorized to view this dashboard.",
            parse_mode="Markdown"
        )
        logger.warning(f"⚠️ Unauthorized /partner access attempt by user {user.id}")
        return
    
    stats = db.get_recruitment_stats()
    
    # Build city breakdown string
    city_lines = []
    for city, count in stats["city_breakdown"].items():
        city_lines.append(f"📍 {city} Density: {count}")
    
    city_breakdown = "\n".join(city_lines) if city_lines else "  _No data yet_"
    
    total = stats["total_users"]
    verified = stats["verified_users"]
    online = stats.get("online_now", 0)
    revenue = stats.get("total_revenue", 0)
    
    # Build verification rate string
    if total > 0:
        verified_line = f"✔️ *Verified Assets:* {verified} ({(verified/total*100):.0f}%)\n"
    else:
        verified_line = f"✔️ *Verified Assets:* {verified}\n"
    
    report = (
        "📊 *BLACKBOOK OPERATIONAL OVERVIEW*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Network Size:* {total} Providers\n"
        f"{verified_line}"
        f"🟢 *Currently Live:* {online}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{city_breakdown}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *Total Revenue:* {revenue:,} KES"
    )
    
    await update.message.reply_text(report, parse_mode="Markdown")
    logger.info(f"📊 Partner dashboard accessed by user {user.id}")


# ==================== /MAINTENANCE ====================

async def maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles maintenance mode - Admin only."""
    import config
    
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "🚫 **Access Denied**\n\nAdmin only command.",
            parse_mode="Markdown"
        )
        logger.warning(f"⚠️ Unauthorized /maintenance attempt by user {user.id}")
        return
    
    # Toggle maintenance mode
    config.MAINTENANCE_MODE = not config.MAINTENANCE_MODE
    status = "🔴 ON" if config.MAINTENANCE_MODE else "🟢 OFF"
    
    await update.message.reply_text(
        f"🛠️ **Maintenance Mode: {status}**\n\n"
        f"{'New registrations are now BLOCKED.' if config.MAINTENANCE_MODE else 'Registrations are now OPEN.'}",
        parse_mode="Markdown"
    )
    logger.info(f"🛠️ Maintenance mode toggled to {config.MAINTENANCE_MODE} by admin")


# ==================== /BROADCAST ====================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcasts a message to all providers - Admin only."""
    user = update.effective_user
    db = get_db(context)
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "🚫 **Access Denied**\n\nAdmin only command.",
            parse_mode="Markdown"
        )
        logger.warning(f"⚠️ Unauthorized /broadcast attempt by user {user.id}")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **Broadcast Usage**\n\n"
            "`/broadcast Your message here`\n\n"
            "Example:\n"
            "`/broadcast Hello everyone! We have exciting updates coming soon.`",
            parse_mode="Markdown"
        )
        return
    
    message = ' '.join(context.args)
    provider_ids = db.get_all_provider_ids()
    
    if not provider_ids:
        await update.message.reply_text(
            "⚠️ No providers to broadcast to.",
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text(
        f"📡 **Broadcasting to {len(provider_ids)} providers...**",
        parse_mode="Markdown"
    )
    
    success_count = 0
    fail_count = 0
    
    broadcast_text = (
        "📢 **Platform Announcement**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{message}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "_— Blackbook Team_"
    )
    
    for provider_id in provider_ids:
        try:
            await context.bot.send_message(
                chat_id=provider_id,
                text=broadcast_text,
                parse_mode="Markdown"
            )
            success_count += 1
        except Exception as e:
            fail_count += 1
            logger.warning(f"Failed to send broadcast to {provider_id}: {e}")
    
    await update.message.reply_text(
        f"✅ **Broadcast Complete**\n\n"
        f"📨 Delivered: {success_count}\n"
        f"❌ Failed: {fail_count}",
        parse_mode="Markdown"
    )
    logger.info(f"📢 Broadcast sent by admin to {success_count} providers")


# ==================== HANDLER REGISTRATION ====================

def register_handlers(application):
    """Registers all admin-related handlers with the application."""
    
    application.add_handler(CommandHandler("partner", partner))
    application.add_handler(CommandHandler("maintenance", maintenance))
    application.add_handler(CommandHandler("broadcast", broadcast))

"""
Blackbook Bot - Admin Handlers
Handles: /partner, /maintenance, /broadcast, /portal_pending
"""
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from config import is_admin, is_authorized_partner, TELEGRAM_TOKEN

logger = logging.getLogger(__name__)

QUEUE_FILTER_LABELS = {
    "all_pending": "All Pending",
    "new_today": "New Today",
    "pending_2h": "Pending > 2h",
    "missing_fields": "Missing Fields",
}

REJECT_REASON_TEMPLATES = {
    "photo": "photo quality issue",
    "mismatch": "identity mismatch",
    "incomplete": "incomplete profile details",
}

PORTAL_PENDING_PAGE_SIZE = 5


def get_db():
    """Gets the database instance from db_context module."""
    from db_context import get_db as _get_db
    return _get_db()


async def _safe_edit_message_text(
    query,
    text: str,
    parse_mode: str = "Markdown",
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edits callback message and ignores harmless no-change edits."""
    try:
        await query.edit_message_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    except BadRequest as exc:
        if "message is not modified" in str(exc).lower():
            logger.debug("Skipped no-op admin message edit")
            return
        raise


async def send_provider_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> bool:
    """Sends provider-facing messages via client bot token."""
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN missing; cannot notify provider.")
        return False
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": int(chat_id),
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            if resp.status_code != 200:
                logger.warning(f"Failed provider notification ({chat_id}): {resp.text}")
                return False
        return True
    except Exception as e:
        logger.warning(f"Provider notification error ({chat_id}): {e}")
        return False


# ==================== /PARTNER DASHBOARD ====================

async def partner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Partner dashboard command - shows recruitment statistics."""
    user = update.effective_user
    db = get_db()
    
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

    lead_area_lines = []
    for area, count in stats.get("top_neighborhoods_by_leads", {}).items():
        lead_area_lines.append(f"🔥 {area}: {count} leads")
    lead_areas = "\n".join(lead_area_lines) if lead_area_lines else "_No lead analytics yet_"
    
    total = stats["total_users"]
    verified = stats["verified_users"]
    online = stats.get("online_now", 0)
    revenue = stats.get("total_revenue", 0)
    total_leads = stats.get("total_leads", 0)
    leads_7d = stats.get("leads_last_7d", 0)
    
    # Build verification rate string
    if total > 0:
        verified_line = f"✔️ *Verified Assets:* {verified} ({(verified/total*100):.0f}%)\n"
    else:
        verified_line = f"✔️ *Verified Assets:* {verified}\n"
    
    report = (
        "📊 *ACE GIRLS OPERATIONAL OVERVIEW*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Network Size:* {total} Providers\n"
        f"{verified_line}"
        f"🟢 *Currently Live:* {online}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{city_breakdown}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *Total Revenue:* {revenue:,} KES"
        f"\n📈 *Total Leads:* {total_leads}"
        f"\n🗓️ *Leads (Last 7d):* {leads_7d}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{lead_areas}"
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
            "🚫 *Access Denied*\n\nAdmin only command.",
            parse_mode="Markdown"
        )
        logger.warning(f"⚠️ Unauthorized /maintenance attempt by user {user.id}")
        return
    
    # Toggle maintenance mode
    config.MAINTENANCE_MODE = not config.MAINTENANCE_MODE
    status = "🔴 ON" if config.MAINTENANCE_MODE else "🟢 OFF"
    
    await update.message.reply_text(
        f"🛠️ *Maintenance Mode: {status}*\n\n"
        f"{'New registrations are now BLOCKED.' if config.MAINTENANCE_MODE else 'Registrations are now OPEN.'}",
        parse_mode="Markdown"
    )
    logger.info(f"🛠️ Maintenance mode toggled to {config.MAINTENANCE_MODE} by admin")


# ==================== /BROADCAST ====================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcasts a message to all providers - Admin only."""
    user = update.effective_user
    db = get_db()
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "🚫 *Access Denied*\n\nAdmin only command.",
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
        "_— Ace Girls Team_"
    )
    
    for provider_id in provider_ids:
        try:
            ok = await send_provider_message(
                chat_id=provider_id,
                text=broadcast_text,
                parse_mode="Markdown",
            )
            if ok:
                success_count += 1
            else:
                fail_count += 1
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


# ==================== /ADMIN PANEL ====================

def _admin_panel_keyboard(db) -> InlineKeyboardMarkup:
    """Builds admin panel keyboard with moderation queue entry."""
    unverified = db.get_provider_count_by_status("unverified")
    active = db.get_provider_count_by_status("active")
    inactive = db.get_provider_count_by_status("inactive")
    total = db.get_provider_count_by_status("all")
    queue_counts = db.get_verification_queue_counts()
    portal_pending = db.get_portal_pending_count()

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🧾 Verification Queue ({queue_counts.get('all_pending', 0)})", callback_data="admin_vq")],
        [InlineKeyboardButton(f"📱 Portal Pending ({portal_pending})", callback_data="admin_portal_pending")],
        [InlineKeyboardButton(f"❓ Unverified ({unverified})", callback_data="admin_list_unverified")],
        [InlineKeyboardButton(f"🟢 Listed/Active ({active})", callback_data="admin_list_active")],
        [InlineKeyboardButton(f"⚫ Unlisted ({inactive})", callback_data="admin_list_inactive")],
        [InlineKeyboardButton(f"📋 All Providers ({total})", callback_data="admin_list_all")],
    ])


def _verification_filter_keyboard(counts: dict, active_filter: str) -> InlineKeyboardMarkup:
    """Filter chips for verification queue."""
    rows = []
    for key in ("all_pending", "new_today", "pending_2h", "missing_fields"):
        marker = "• " if key == active_filter else ""
        rows.append([
            InlineKeyboardButton(
                f"{marker}{QUEUE_FILTER_LABELS[key]} ({counts.get(key, 0)})",
                callback_data=f"admin_vqf_{key}",
            )
        ])
    rows.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_back")])
    return InlineKeyboardMarkup(rows)


async def _show_verification_queue(update: Update, context: ContextTypes.DEFAULT_TYPE, queue_filter: str, page: int) -> None:
    """Renders verification queue list with filter and one-tap reject templates."""
    query = update.callback_query
    db = get_db()
    page_size = 3
    rows = db.get_verification_queue(queue_filter=queue_filter, limit=page_size, offset=page * page_size)
    total = db.get_verification_queue_count(queue_filter=queue_filter)
    counts = db.get_verification_queue_counts()

    context.user_data["admin_view"] = "vq"
    context.user_data["admin_vq_filter"] = queue_filter
    context.user_data["admin_vq_page"] = page

    header = (
        f"*Verification Queue - {QUEUE_FILTER_LABELS.get(queue_filter, 'All Pending')}*\n"
        f"Showing {page * page_size + 1}-{min((page + 1) * page_size, max(total, 1))} of {total}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not rows:
        await _safe_edit_message_text(
            query,
            header + "No providers in this queue filter.",
            reply_markup=_verification_filter_keyboard(counts, queue_filter),
        )
        return

    text = header
    keyboard = []
    for item in rows:
        pid = item.get("telegram_id")
        name = item.get("display_name") or "Unknown"
        city = item.get("city") or "?"
        neighborhood = item.get("neighborhood") or "?"
        pending_minutes = int(item.get("pending_minutes") or 0)
        pending_hours = round(pending_minutes / 60.0, 1)
        missing_count = int(item.get("missing_fields_count") or 0)

        text += (
            f"*{name}* (`{pid}`)\n"
            f"Location: {neighborhood}, {city}\n"
            f"Pending: {pending_hours}h\n"
            f"Missing fields: {missing_count}\n\n"
        )

        keyboard.append([InlineKeyboardButton(f"✅ Verify {name}", callback_data=f"admin_verify_{pid}")])
        keyboard.append([
            InlineKeyboardButton("❌ Photo Quality", callback_data=f"admin_reject_{pid}_photo"),
            InlineKeyboardButton("❌ Mismatch", callback_data=f"admin_reject_{pid}_mismatch"),
        ])
        keyboard.append([InlineKeyboardButton("❌ Incomplete", callback_data=f"admin_reject_{pid}_incomplete")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_vqpage_{queue_filter}_{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_vqpage_{queue_filter}_{page + 1}"))
    if nav:
        keyboard.append(nav)

    keyboard.extend(_verification_filter_keyboard(counts, queue_filter).inline_keyboard)
    await _safe_edit_message_text(
        query,
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _show_portal_pending(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0,
) -> None:
    """Shows portal accounts waiting for admin approval."""
    db = get_db()
    page = max(page, 0)
    rows = db.get_portal_pending_accounts(
        limit=PORTAL_PENDING_PAGE_SIZE,
        offset=page * PORTAL_PENDING_PAGE_SIZE,
    )
    total = db.get_portal_pending_count()

    context.user_data["admin_view"] = "portal_pending"
    context.user_data["admin_portal_page"] = page

    has_rows = bool(rows)
    start_index = (page * PORTAL_PENDING_PAGE_SIZE) + 1 if has_rows else 0
    end_index = min((page + 1) * PORTAL_PENDING_PAGE_SIZE, total) if has_rows else 0
    text = (
        "*Portal Pending Approvals*\n"
        f"Showing {start_index}-{end_index} of {total}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    keyboard = []
    if not rows:
        text += "No pending portal accounts right now."
    else:
        for item in rows:
            pid = item.get("telegram_id")
            name = item.get("display_name") or "Unnamed"
            phone = item.get("phone") or "-"
            city = item.get("city") or "?"
            neighborhood = item.get("neighborhood") or "?"
            pending_minutes = int(item.get("pending_minutes") or 0)
            pending_hours = round(pending_minutes / 60.0, 1)
            onboarding = "yes" if item.get("portal_onboarding_complete") else "no"

            text += (
                f"*{name}* (`{pid}`)\n"
                f"📞 {phone}\n"
                f"📍 {neighborhood}, {city}\n"
                f"⏱️ Pending: {pending_hours}h\n"
                f"🧾 Onboarding complete: {onboarding}\n\n"
            )
            keyboard.append([InlineKeyboardButton(f"✅ Approve {name}", callback_data=f"admin_verify_{pid}")])
            keyboard.append([
                InlineKeyboardButton("❌ Photo", callback_data=f"admin_reject_{pid}_photo"),
                InlineKeyboardButton("❌ Mismatch", callback_data=f"admin_reject_{pid}_mismatch"),
            ])
            keyboard.append([InlineKeyboardButton("❌ Incomplete", callback_data=f"admin_reject_{pid}_incomplete")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_portalpage_{page - 1}"))
    if (page + 1) * PORTAL_PENDING_PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_portalpage_{page + 1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"admin_portalpage_{page}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    if query:
        await _safe_edit_message_text(query, text, reply_markup=reply_markup)
        return
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def portal_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command: show pending portal approvals."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text(
            "🚫 *Access Denied*\n\nAdmin only command.",
            parse_mode="Markdown",
        )
        logger.warning(f"⚠️ Unauthorized /portal_pending attempt by user {user.id}")
        return
    await _show_portal_pending(update, context, page=0)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin panel - shows management options."""
    user = update.effective_user
    db = get_db()
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "🚫 *Access Denied*\n\nAdmin only.",
            parse_mode="Markdown"
        )
        return
    context.user_data["admin_view"] = "panel"
    
    keyboard = _admin_panel_keyboard(db)
    
    await update.message.reply_text(
        "🛠️ *Admin Panel*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select a category to manage:\n",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin panel callback queries."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    db = get_db()
    data = query.data
    
    if not is_admin(user.id):
        await query.answer("Access denied!", show_alert=True)
        return

    if data == "admin_vq":
        return await _show_verification_queue(update, context, queue_filter="all_pending", page=0)

    if data == "admin_portal_pending":
        return await _show_portal_pending(update, context, page=0)

    if data.startswith("admin_portalpage_"):
        page_raw = data.replace("admin_portalpage_", "", 1)
        try:
            page = int(page_raw)
        except ValueError:
            page = 0
        return await _show_portal_pending(update, context, page=page)

    if data.startswith("admin_vqf_"):
        queue_filter = data.replace("admin_vqf_", "")
        return await _show_verification_queue(update, context, queue_filter=queue_filter, page=0)

    if data.startswith("admin_vqpage_"):
        rest = data.replace("admin_vqpage_", "", 1)
        if "_" not in rest:
            return
        queue_filter, page_raw = rest.rsplit("_", 1)
        try:
            page = int(page_raw)
        except ValueError:
            page = 0
        return await _show_verification_queue(update, context, queue_filter=queue_filter, page=max(page, 0))
    
    # List providers by status
    if data.startswith("admin_list_"):
        status = data.replace("admin_list_", "")
        page = context.user_data.get("admin_page", 0)
        context.user_data["admin_view"] = "list"
        context.user_data["admin_list_status"] = status
        
        providers = db.get_providers_by_status(status, limit=5, offset=page * 5)
        total = db.get_provider_count_by_status(status)
        
        if not providers:
            await _safe_edit_message_text(
                query,
                f"📋 *No {status} providers found.*\n\n"
                "Use the button below to go back.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_back")]
                ]),
            )
            return
        
        status_labels = {
            'unverified': '❓ Unverified',
            'active': '🟢 Listed/Active',
            'inactive': '⚫ Unlisted',
            'all': '📋 All'
        }
        
        text = f"*{status_labels.get(status, status)} Providers*\n"
        text += f"Showing {page * 5 + 1}-{min((page + 1) * 5, total)} of {total}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        keyboard = []
        for p in providers:
            name = p.get('display_name', 'Unknown')
            city = p.get('city', '?')
            verified = "✔️" if p.get('is_verified') else "❓"
            listed = "🟢" if p.get('is_active') else "⚫"
            
            text += f"{verified}{listed} *{name}* ({city})\n"
            
            # Action buttons for each provider
            pid = p.get('telegram_id')
            actions = []
            if not p.get('is_verified'):
                actions.append(InlineKeyboardButton("✅ Verify", callback_data=f"admin_verify_{pid}"))
            if p.get('is_active'):
                actions.append(InlineKeyboardButton("⚫ Unlist", callback_data=f"admin_unlist_{pid}"))
            else:
                actions.append(InlineKeyboardButton("🟢 List", callback_data=f"admin_activate_{pid}"))
            
            if actions:
                keyboard.append(actions)
        
        # Pagination
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_page_{status}_{page - 1}"))
        if (page + 1) * 5 < total:
            nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_page_{status}_{page + 1}"))
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_back")])
        
        await _safe_edit_message_text(
            query,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return
    
    # Pagination
    if data.startswith("admin_page_"):
        parts = data.split("_")
        status = parts[2]
        page = int(parts[3])
        context.user_data["admin_page"] = page
        # Trigger the list again
        query.data = f"admin_list_{status}"
        return await admin_callback(update, context)

    if data.startswith("admin_reject_"):
        parts = data.split("_")
        if len(parts) != 4:
            await query.answer("Invalid reject action.", show_alert=True)
            return
        pid = int(parts[2])
        reason_code = parts[3]
        reason_text = REJECT_REASON_TEMPLATES.get(reason_code, "verification requirements not met")

        provider = db.get_provider(pid)
        if not provider:
            await query.answer("Provider not found.", show_alert=True)
            return
        display_name = provider.get("display_name", "Unknown")
        is_portal_account = str(provider.get("auth_channel") or "telegram").lower() == "portal"
        updated = db.verify_provider(pid, False, admin_tg_id=user.id, reason=reason_text)
        if not updated:
            await query.answer("Reject failed; try again.", show_alert=True)
            return
        if not is_portal_account:
            db.update_provider_profile(pid, {"verification_photo_id": None})
            db.log_funnel_event(pid, "verification_rejected", {"reason": reason_text, "source": "admin_queue"})
            try:
                await send_provider_message(
                    chat_id=pid,
                    text=(
                        "❌ *Verification Rejected*\n\n"
                        f"Reason: *{reason_text}*\n\n"
                        "Please update your profile/photos and submit verification again from your profile."
                    ),
                )
            except Exception as e:
                logger.warning(f"Failed to send reject template to {pid}: {e}")
        await query.answer(f"Rejected {display_name}: {reason_text}", show_alert=True)

        if context.user_data.get("admin_view") == "portal_pending":
            return await _show_portal_pending(
                update,
                context,
                page=context.user_data.get("admin_portal_page", 0),
            )
        if context.user_data.get("admin_view") == "vq":
            return await _show_verification_queue(
                update,
                context,
                queue_filter=context.user_data.get("admin_vq_filter", "all_pending"),
                page=context.user_data.get("admin_vq_page", 0),
            )
        query.data = "admin_list_unverified"
        return await admin_callback(update, context)
    
    # Verify provider
    if data.startswith("admin_verify_"):
        pid = int(data.replace("admin_verify_", ""))
        provider = db.get_provider(pid)
        if not provider:
            await query.answer("Provider not found.", show_alert=True)
            return
        is_portal_account = str(provider.get("auth_channel") or "telegram").lower() == "portal"
        updated = db.verify_provider(pid, True, admin_tg_id=user.id)
        if not updated:
            await query.answer("Verify failed; try again.", show_alert=True)
            return
        if not is_portal_account:
            db.log_funnel_event(pid, "verified")
            try:
                await send_provider_message(
                    chat_id=pid,
                    text="✅ *Verification Approved!*\n\n"
                         "🎉 You now have the Blue Tick ✔️\n\n"
                         "Your profile has been verified by admin.",
                )
            except Exception as e:
                logger.warning(f"Failed to send verify notification to {pid}: {e}")
        await query.answer(f"✅ Verified {provider.get('display_name', 'Unknown')}!", show_alert=True)

        if context.user_data.get("admin_view") == "portal_pending":
            return await _show_portal_pending(
                update,
                context,
                page=context.user_data.get("admin_portal_page", 0),
            )
        if context.user_data.get("admin_view") == "vq":
            return await _show_verification_queue(
                update,
                context,
                queue_filter=context.user_data.get("admin_vq_filter", "all_pending"),
                page=context.user_data.get("admin_vq_page", 0),
            )

        # Refresh the list
        query.data = "admin_list_unverified"
        return await admin_callback(update, context)
    
    # List/Activate provider (set active)
    if data.startswith("admin_activate_"):
        pid = int(data.replace("admin_activate_", ""))
        db.set_provider_active_status(pid, True)
        
        provider = db.get_provider(pid)
        try:
            await send_provider_message(
                chat_id=pid,
                text="🟢 *You're Now Listed!*\n\n"
                     "Your profile is now visible on the website.",
            )
        except:
            pass
        
        await query.answer(f"🟢 Listed {provider.get('display_name', 'Unknown')}!", show_alert=True)
        query.data = "admin_list_inactive"
        return await admin_callback(update, context)
    
    # Unlist provider
    if data.startswith("admin_unlist_"):
        pid = int(data.replace("admin_unlist_", ""))
        db.set_provider_active_status(pid, False)
        
        provider = db.get_provider(pid)
        try:
            await send_provider_message(
                chat_id=pid,
                text="⚫ *Profile Unlisted*\n\n"
                     "Your profile has been removed from the website by admin.",
            )
        except:
            pass
        
        await query.answer(f"⚫ Unlisted {provider.get('display_name', 'Unknown')}!", show_alert=True)
        query.data = "admin_list_active"
        return await admin_callback(update, context)
    
    # Back to panel
    if data == "admin_back":
        context.user_data["admin_page"] = 0
        context.user_data["admin_view"] = "panel"
        keyboard = _admin_panel_keyboard(db)

        await _safe_edit_message_text(
            query,
            "🛠️ *Admin Panel*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select a category to manage:\n",
            reply_markup=keyboard,
        )


# ==================== HANDLER REGISTRATION ====================

def register_handlers(application):
    """Registers all admin-related handlers with the application."""
    from telegram.ext import CallbackQueryHandler
    
    application.add_handler(CommandHandler("partner", partner))
    application.add_handler(CommandHandler("portal_pending", portal_pending))
    application.add_handler(CommandHandler("maintenance", maintenance))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # Admin callbacks
    application.add_handler(CallbackQueryHandler(
        admin_callback,
        pattern="^admin_"
    ))


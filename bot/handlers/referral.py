"""
Blackbook Bot - Referral Rewards Handlers
Handles referral reward choices (KES credit vs free days)
"""
import logging
from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

logger = logging.getLogger(__name__)

def get_db():
    from db_context import get_db as _get_db
    return _get_db()

async def referral_reward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the user's choice of referral reward."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    db = get_db()
    
    # Expected format: "ref_reward_{id}_{choice}"
    # Example: "ref_reward_15_credit" or "ref_reward_15_days"
    parts = data.split("_")
    if len(parts) != 4:
        await query.edit_message_text("❌ Invalid reward data.")
        return
        
    reward_id_str = parts[2]
    choice = parts[3]
    
    try:
        reward_id = int(reward_id_str)
    except ValueError:
        await query.edit_message_text("❌ Invalid reward ID.")
        return
        
    reward = db.get_referral_reward(reward_id)
    if not reward:
        await query.edit_message_text("❌ Reward not found or already processed.")
        return
        
    if reward.get("is_claimed"):
        await query.edit_message_text("⚠️ This reward has already been claimed.")
        return
        
    # Apply the reward based on choice
    if choice == "credit":
        credit_amount = reward["reward_credit"]
        success = db.add_referral_credits(reward["referrer_tg_id"], credit_amount)
        if success:
            db.mark_referral_reward_claimed(reward_id, "credit")
            await query.edit_message_text(f"✅ **Reward Claimed!**\n\n💰 {credit_amount} KES credit has been added to your balance.", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Failed to add credit. Please contact support.")
            
    elif choice == "days":
        days_amount = reward["reward_days"]
        success = db.extend_subscription(reward["referrer_tg_id"], days_amount)
        if success:
            db.mark_referral_reward_claimed(reward_id, "days")
            await query.edit_message_text(f"✅ **Reward Claimed!**\n\n📅 {days_amount} free days have been added to your subscription.", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Failed to extend subscription. Please contact support.")
            
    else:
        await query.edit_message_text("❌ Unknown reward choice.")

def register_handlers(application):
    """Registers referral reward handlers."""
    application.add_handler(CallbackQueryHandler(
        referral_reward_callback,
        pattern="^ref_reward_"
    ))

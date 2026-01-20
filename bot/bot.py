import os
import random
import string
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from database import Database
from megapay_service import initiate_stk_push, get_package_price, get_available_packages

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states for registration
STAGE_NAME, CITY, NEIGHBORHOOD = range(3)

# Verification state
AWAITING_PHOTO = 10

# Topup states
TOPUP_PHONE, TOPUP_CONFIRM = 20, 21

# Admin and Partner IDs from environment
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
PARTNER_TELEGRAM_ID = os.getenv("PARTNER_TELEGRAM_ID")

# Global maintenance mode flag
MAINTENANCE_MODE = False

# Initialize database
db = Database()


def is_admin(user_id: int) -> bool:
    """Checks if a user is the admin."""
    return ADMIN_CHAT_ID and user_id == int(ADMIN_CHAT_ID)


def generate_verification_code() -> str:
    """Generates a random 6-character verification code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command with premium welcome message."""
    user = update.effective_user
    
    # Check if existing user
    provider = db.get_provider(user.id)
    
    if provider:
        # Existing user - show status with menu
        status = "🟢 Active" if provider.get("is_active") else "⚫ Inactive"
        verified = "✔️ Verified" if provider.get("is_verified") else "❌ Unverified"
        expiry = provider.get("expiry_date")
        time_left = f"{expiry.strftime('%Y-%m-%d')}" if expiry else "No active subscription"
        
        # Build menu keyboard
        keyboard = [
            [
                InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"),
                InlineKeyboardButton("💰 Go Live", callback_data="menu_topup"),
            ],
            [
                InlineKeyboardButton("🟢 Toggle Status", callback_data="menu_status"),
                InlineKeyboardButton("🛡️ Safety Check", callback_data="menu_check"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Welcome back, *{provider.get('display_name', user.first_name)}*.\n\n"
            f"📱 *Current Status:* {status}\n"
            f"🛡️ *Trust Level:* {verified}\n"
            f"⏱️ *Expires:* {time_left}\n\n"
            "Use the menu below or type a command:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        # New user - full welcome
        await update.message.reply_text(
            "🎩 *BLACKBOOK: Private Concierge Network*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Welcome to the inner circle. This bot is your command center for managing "
            "your professional presence, safety, and earnings on the Blackbook directory.\n\n"
            "📜 *How to get started:*\n"
            "1️⃣ *Register* — Setup your stage name and location.\n"
            "2️⃣ *Verify* — Complete our anti-catfish protocol to get your Blue Tick ✔️.\n"
            "3️⃣ *Topup* — Activate your listing to appear on the \"Dark Room\" directory.\n\n"
            "🛠 *Your Command Reference:*\n\n"
            "👤 *IDENTITY*\n"
            "/register — Create or edit your profile.\n"
            "/verify — Submit proof of identity (Required for listing).\n"
            "/myprofile — View your status, rating, and expiry.\n\n"
            "💰 *VISIBILITY*\n"
            "/topup — Purchase listing credits (3 or 7 days).\n"
            "/status — Toggle your 'Live Now' 🟢 badge on the website.\n\n"
            "🛡 *SAFETY SUITE*\n"
            "/check <number> — Search the national blacklist.\n"
            "/report <number> <reason> — Flag a dangerous client.\n"
            "/session <mins> — Start a safety timer before a meeting.\n"
            "/checkin — Confirm you are safe after a session.\n\n"
            "🚫 Use /cancel at any time to stop a current process.\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "_Blackbook: Privacy is Power._",
            parse_mode="Markdown"
        )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all menu button navigation throughout the bot."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    action = query.data.replace("menu_", "")
    provider = db.get_provider(user.id)
    
    # === MAIN MENU ===
    if action == "main":
        if provider:
            status = "🟢 Active" if provider.get("is_active") else "⚫ Inactive"
            verified = "✔️ Verified" if provider.get("is_verified") else "❌ Unverified"
            expiry = provider.get("expiry_date")
            time_left = f"{expiry.strftime('%Y-%m-%d')}" if expiry else "No subscription"
            
            keyboard = [
                [
                    InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"),
                    InlineKeyboardButton("💰 Go Live", callback_data="menu_topup"),
                ],
                [
                    InlineKeyboardButton("🟢 Toggle Status", callback_data="menu_status"),
                    InlineKeyboardButton("🛡️ Safety Suite", callback_data="menu_safety"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🎩 *BLACKBOOK COMMAND CENTER*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 *Status:* {status}\n"
                f"🛡️ *Trust:* {verified}\n"
                f"⏱️ *Expires:* {time_left}\n\n"
                "Select an option below:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    # === PROFILE SCREEN ===
    elif action == "profile":
        if provider:
            name = provider.get("display_name", "Unknown")
            city = provider.get("city", "Not set")
            neighborhood = provider.get("neighborhood", "Not set")
            verified = "✔️ Verified" if provider.get("is_verified") else "❌ Not Verified"
            active = "🟢 Active" if provider.get("is_active") else "⚫ Inactive"
            online = "🟢 Live" if provider.get("is_online") else "⚫ Offline"
            expiry = provider.get("expiry_date")
            expiry_text = expiry.strftime("%Y-%m-%d %H:%M") if expiry else "No subscription"
            
            # Contextual buttons based on state
            buttons = []
            if not provider.get("is_verified"):
                buttons.append([InlineKeyboardButton("📸 Get Verified", callback_data="menu_verify_start")])
            if not provider.get("is_active"):
                buttons.append([InlineKeyboardButton("💰 Go Live Now", callback_data="menu_topup")])
            buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(
                f"👤 *YOUR PROFILE*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎭 *Stage Name:* {name}\n"
                f"📍 *Location:* {neighborhood}, {city}\n\n"
                f"🛡️ *Trust Level:* {verified}\n"
                f"📱 *Listing Status:* {active}\n"
                f"🌐 *Website Badge:* {online}\n\n"
                f"⏱️ *Expires:* {expiry_text}\n"
                "━━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    # === TOPUP / GO LIVE SCREEN ===
    elif action == "topup":
        keyboard = [
            [InlineKeyboardButton("⏰ 3 Days — 400 KES", callback_data="menu_pay_3")],
            [InlineKeyboardButton("🔥 7 Days — 800 KES", callback_data="menu_pay_7")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        status_text = ""
        if provider and provider.get("is_active"):
            expiry = provider.get("expiry_date")
            if expiry:
                status_text = f"\n\n📅 Current subscription expires: {expiry.strftime('%Y-%m-%d')}"
        
        await query.edit_message_text(
            "💰 *LISTING MANAGEMENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Active listings receive *400% more engagement*.{}\n\n"
            "Select your package:".format(status_text),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # === PAYMENT: USE SAVED PHONE (must be before generic pay_ check) ===
    elif action == "pay_confirm":
        saved_phone = db.get_provider_phone(user.id)
        days = context.user_data.get("topup_days", 3)
        price = context.user_data.get("topup_price", 400)
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⏳ *Initiating Secure Payment...*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"A prompt will appear on `{saved_phone}`.\n"
            "Enter your M-Pesa PIN to authorize.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Trigger STK push
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
            failed_keyboard = [
                [InlineKeyboardButton("🔄 Try Again", callback_data="menu_topup")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
            ]
            failed_markup = InlineKeyboardMarkup(failed_keyboard)
            await context.bot.send_message(
                chat_id=user.id,
                text=f"❌ *Payment Failed*\n\n{result['message']}\n\nPlease try again.",
                reply_markup=failed_markup,
                parse_mode="Markdown"
            )
    
    # === PAYMENT: NEW PHONE NUMBER (must be before generic pay_ check) ===
    elif action == "pay_newphone":
        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data="menu_topup")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        days = context.user_data.get("topup_days", 3)
        price = context.user_data.get("topup_price", 400)
        
        await query.edit_message_text(
            f"📦 *{days} Day Package — {price} KES*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Please type your M-Pesa phone number:\n"
            "_Format: 0712345678_",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        context.user_data["awaiting_phone"] = True
    
    # === PAYMENT PACKAGE SELECTION ===
    elif action.startswith("pay_"):
        days = int(action.replace("pay_", ""))
        price = 400 if days == 3 else 800
        
        # Store selection
        context.user_data["topup_days"] = days
        context.user_data["topup_price"] = price
        
        # Check for saved phone
        saved_phone = db.get_provider_phone(user.id) if provider else None
        
        if saved_phone:
            keyboard = [
                [InlineKeyboardButton(f"✅ Use {saved_phone}", callback_data="menu_pay_confirm")],
                [InlineKeyboardButton("📱 New Number", callback_data="menu_pay_newphone")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu_topup")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📦 *{days} Day Package — {price} KES*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"We have your M-Pesa number saved:\n"
                f"📱 `{saved_phone}`\n\n"
                "Use this number?",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            keyboard = [
                [InlineKeyboardButton("🔙 Back", callback_data="menu_topup")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📦 *{days} Day Package — {price} KES*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Please type your M-Pesa phone number:\n"
                "_Format: 0712345678_",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            context.user_data["awaiting_phone"] = True
    
    # === STATUS TOGGLE ===
    elif action == "status":
        if provider and provider.get("is_active"):
            new_status = db.toggle_online_status(user.id)
            neighborhood = provider.get('neighborhood', 'your area')
            
            keyboard = [
                [InlineKeyboardButton("🔄 Toggle Again", callback_data="menu_status")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if new_status:
                await query.edit_message_text(
                    "🟢 *Status: LIVE*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Your profile now shows the 'Available Now' badge.\n"
                    f"You are prioritized in {neighborhood} search results.",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "⚫ *Status: HIDDEN*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Your profile is still visible, but clients see you are unavailable.",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
        else:
            keyboard = [
                [InlineKeyboardButton("💰 Go Live", callback_data="menu_topup")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "❌ *Cannot Toggle Status*\n\n"
                "You need an active subscription to appear on the website.\n\n"
                "Get listed now:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    # === SAFETY SUITE MENU ===
    elif action == "safety":
        keyboard = [
            [InlineKeyboardButton("📞 Check Number", callback_data="menu_safety_check")],
            [InlineKeyboardButton("⏱️ Start Session", callback_data="menu_safety_session")],
            [InlineKeyboardButton("🚫 Report Client", callback_data="menu_safety_report")],
            [InlineKeyboardButton("✅ Check In", callback_data="menu_safety_checkin")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🛡️ *SAFETY SUITE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your protection tools:\n\n"
            "📞 *Check* — Screen client numbers\n"
            "⏱️ *Session* — Start safety timer\n"
            "🚫 *Report* — Flag dangerous clients\n"
            "✅ *Check In* — Confirm you're safe",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # === SAFETY: CHECK NUMBER ===
    elif action == "safety_check":
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Safety", callback_data="menu_safety")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📞 *CLIENT INTELLIGENCE CHECK*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Type the command:\n"
            "`/check 0712345678`\n\n"
            "We'll search our database for reports of:\n"
            "• Non-payment\n"
            "• Violence\n"
            "• Suspicious behavior",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # === SAFETY: START SESSION ===
    elif action == "safety_session":
        keyboard = [
            [
                InlineKeyboardButton("30 min", callback_data="menu_session_30"),
                InlineKeyboardButton("60 min", callback_data="menu_session_60"),
            ],
            [
                InlineKeyboardButton("90 min", callback_data="menu_session_90"),
                InlineKeyboardButton("120 min", callback_data="menu_session_120"),
            ],
            [InlineKeyboardButton("🔙 Back to Safety", callback_data="menu_safety")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⏱️ *SAFETY SESSION TIMER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select session duration:\n\n"
            "If you don't /checkin on time, an *Emergency Alert* "
            "will be sent to the Management Team.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # === SAFETY: SESSION DURATION SELECTED ===
    elif action.startswith("session_"):
        minutes = int(action.replace("session_", ""))
        session_id = db.start_session(user.id, minutes)
        
        if session_id:
            from datetime import datetime, timedelta
            check_back_time = datetime.now() + timedelta(minutes=minutes)
            
            keyboard = [
                [InlineKeyboardButton("✅ Check In Now", callback_data="menu_safety_checkin")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✅ *SAFETY TIMER ACTIVE*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏱️ Duration: {minutes} Minutes\n"
                f"⏰ Check-in Due: {check_back_time.strftime('%H:%M')}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "We are watching the clock.\n\n"
                "Tap *Check In Now* when you're safe.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    # === SAFETY: CHECK IN ===
    elif action == "safety_checkin":
        success = db.end_session(user.id)
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if success:
            await query.edit_message_text(
                "✅ *CHECK-IN CONFIRMED*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Glad you're safe! 💚\n\n"
                "Remember to start a new session before your next meeting.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "ℹ️ *No Active Session*\n\n"
                "You don't have an active safety timer.\n\n"
                "Use the Safety Suite to start one before your next meeting.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    # === SAFETY: REPORT ===
    elif action == "safety_report":
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Safety", callback_data="menu_safety")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🚫 *REPORT A CLIENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Type the command:\n"
            "`/report 0712345678 Reason here`\n\n"
            "Example:\n"
            "`/report 0712345678 Did not pay, aggressive`\n\n"
            "_Help protect your sisters. Only report genuine issues._",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # === VERIFY PROMPT ===
    elif action == "verify_start":
        keyboard = [
            [InlineKeyboardButton("📸 Start Verification", callback_data="menu_verify_go")],
            [InlineKeyboardButton("🔙 Back to Profile", callback_data="menu_profile")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📸 *BLUE TICK VERIFICATION*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "To get verified, you'll need to:\n\n"
            "1. Receive a unique code\n"
            "2. Write it on paper\n"
            "3. Take a live selfie with it\n\n"
            "Ready to begin?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # === VERIFY GO ===
    elif action == "verify_go":
        code = generate_verification_code()
        context.user_data["verification_code"] = code
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📸 *YOUR VERIFICATION CODE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Your code is: `{code}`\n\n"
            "*INSTRUCTIONS:*\n"
            "1. Write this code on paper\n"
            "2. Hold it next to your face\n"
            "3. Take a *live camera photo*\n"
            "4. Send it here\n\n"
            "⚠️ Gallery uploads will be rejected.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        # Set state to await photo
        context.user_data["awaiting_verification_photo"] = True


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the registration conversation and asks for Stage Name."""
    global MAINTENANCE_MODE
    user = update.effective_user
    
    # Check if maintenance mode is active
    if MAINTENANCE_MODE:
        await update.message.reply_text(
            "🛠️ **Maintenance Mode Active**\n\n"
            "We're currently performing system updates. "
            "Please try again later.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "👋 *Let's build your brand.*\n\n"
        "Please enter your *Stage Name* (The name clients will see on the website):",
        parse_mode="Markdown"
    )
    return STAGE_NAME


async def stage_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the stage name and asks for city selection."""
    user = update.effective_user
    stage_name_input = update.message.text.strip()
    
    # Store in context for later use
    context.user_data["stage_name"] = stage_name_input
    
    # Add provider to database with initial display name
    db.add_provider(user.id, stage_name_input)
    
    # Create inline keyboard for city selection
    keyboard = [
        [InlineKeyboardButton("🏙️ Nairobi", callback_data="city_Nairobi")],
        [InlineKeyboardButton("🌆 Eldoret", callback_data="city_Eldoret")],
        [InlineKeyboardButton("🏖️ Mombasa", callback_data="city_Mombasa")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Excellent, *{stage_name_input}*.\n\n"
        "Now, select your *Primary City* where you operate:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return CITY


async def city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles city button selection and asks for neighborhood."""
    query = update.callback_query
    await query.answer()
    
    # Extract city from callback data (format: "city_CityName")
    city = query.data.replace("city_", "")
    context.user_data["city"] = city
    
    await query.edit_message_text(
        f"📍 *{city} Selection Confirmed.*\n\n"
        "To help local high-value clients find you, please enter your specific "
        "*Neighborhood* (e.g., Westlands, Lower Kabete, Roysambu):",
        parse_mode="Markdown"
    )
    return NEIGHBORHOOD


async def neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the neighborhood and completes registration."""
    user = update.effective_user
    neighborhood_input = update.message.text.strip()
    
    # Get stored data
    city = context.user_data.get("city")
    stage_name = context.user_data.get("stage_name")
    
    # Save to database
    db.update_provider_profile(user.id, city, neighborhood_input)
    
    await update.message.reply_text(
        "✨ *Profile Initialized!*\n\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 Name: {stage_name}\n"
        f"📍 Area: {neighborhood_input}, {city}\n"
        "━━━━━━━━━━━━━━━\n\n"
        "⚠️ *Note:* Your profile is currently *HIDDEN*.\n"
        "Next step: Use /verify to prove your identity and unlock listing features.",
        parse_mode="Markdown"
    )
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current conversation."""
    await update.message.reply_text(
        "❌ Cancelled. Use /register or /verify to start again."
    )
    context.user_data.clear()
    return ConversationHandler.END


# ==================== VERIFICATION SYSTEM ====================

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the verification process by giving user a unique code."""
    user = update.effective_user
    
    # Check if user is registered
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You need to /register first before verification.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # Check if already verified
    if provider.get("is_verified"):
        await update.message.reply_text(
            "✅ You are already verified! ✔️",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # Generate unique verification code
    code = generate_verification_code()
    context.user_data["verification_code"] = code
    
    await update.message.reply_text(
        "📸 *Blue Tick Verification*\n\n"
        f"Your unique session code is: `{code}`\n\n"
        "*INSTRUCTIONS:*\n"
        "1. Write this code clearly on a piece of paper.\n"
        "2. Take a *Live Selfie* holding the paper.\n"
        "3. Ensure your face and the code are clearly visible.\n\n"
        "⚠️ *Security Note:* Gallery uploads and 'View Once' documents are "
        "automatically blocked to prevent fraud. Use your Telegram camera.",
        parse_mode="Markdown"
    )
    return AWAITING_PHOTO


async def handle_verification_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the verification photo submission."""
    user = update.effective_user
    
    # Check if it's a photo (not a document/file)
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send a **photo taken with your camera**, not a file or document.\n"
            "Use the camera icon 📷 to take a live photo.",
            parse_mode="Markdown"
        )
        return AWAITING_PHOTO
    
    # Get the highest resolution photo
    photo = update.message.photo[-1]
    photo_file_id = photo.file_id
    
    # Get verification code and provider info
    code = context.user_data.get("verification_code", "N/A")
    provider = db.get_provider(user.id)
    display_name = provider.get("display_name", "Unknown") if provider else "Unknown"
    
    # Save photo ID to database
    db.save_verification_photo(user.id, photo_file_id)
    
    # Check if ADMIN_CHAT_ID is set
    if not ADMIN_CHAT_ID:
        logger.error("❌ ADMIN_CHAT_ID not set!")
        await update.message.reply_text(
            "⚠️ Verification system error. Please contact support."
        )
        return ConversationHandler.END
    
    # Create admin approval buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"verify_approve_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"verify_reject_{user.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Forward photo to admin with details
    caption = (
        "🔍 *NEW VETTING REQUEST*\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 Provider: {display_name}\n"
        f"📍 City: {provider.get('city', 'N/A') if provider else 'N/A'}\n"
        f"🔑 Code: `{code}`\n"
    )
    
    await context.bot.send_photo(
        chat_id=int(ADMIN_CHAT_ID),
        photo=photo_file_id,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    await update.message.reply_text(
        "✅ *Encrypted Upload Complete.*\n\n"
        "Your verification is in the queue. Our team will review the match "
        "between your profile and live photo.\n\n"
        "_Review time: 15–120 minutes._",
        parse_mode="Markdown"
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def handle_document_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Rejects document uploads during verification (anti-catfish measure)."""
    await update.message.reply_text(
        "🚫 *Security Alert: Gallery Upload Detected.*\n\n"
        "For the safety of our clients and the integrity of the Blue Tick, "
        "we only accept *Live Camera Photos*.\n\n"
        "Please try /verify again using your camera.",
        parse_mode="Markdown"
    )
    return AWAITING_PHOTO


async def admin_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin approval/rejection of verification requests."""
    query = update.callback_query
    await query.answer()
    
    # Parse callback data
    data = query.data
    parts = data.split("_")
    
    if len(parts) != 3:
        return
    
    action = parts[1]  # "approve" or "reject"
    provider_id = int(parts[2])
    
    provider = db.get_provider(provider_id)
    display_name = provider.get("display_name", "Unknown") if provider else "Unknown"
    
    if action == "approve":
        # Update database
        db.verify_provider(provider_id, True)
        
        # Notify provider
        await context.bot.send_message(
            chat_id=provider_id,
            text="🎉 *Status: VERIFIED*\n\n"
                 "You now have the Blue Tick ✔️. Your trust score has increased.\n\n"
                 "Use /topup to appear in the 'Collection.'",
            parse_mode="Markdown"
        )
        
        # Update admin message
        await query.edit_message_caption(
            caption=f"✅ **APPROVED**\n\n"
                    f"Provider: {display_name}\n"
                    f"User ID: `{provider_id}`",
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ Provider {provider_id} ({display_name}) verified by admin")
        
    elif action == "reject":
        # Don't update is_verified, just notify
        await context.bot.send_message(
            chat_id=provider_id,
            text="❌ **Verification Rejected**\n\n"
                 "Your verification photo was not approved.\n"
                 "Please use /verify to try again with a clearer photo.",
            parse_mode="Markdown"
        )
        
        # Update admin message
        await query.edit_message_caption(
            caption=f"❌ **REJECTED**\n\n"
                    f"Provider: {display_name}\n"
                    f"User ID: `{provider_id}`",
            parse_mode="Markdown"
        )
        
        logger.info(f"❌ Provider {provider_id} ({display_name}) rejected by admin")


# ==================== PARTNER DASHBOARD ====================

def is_authorized_partner(user_id: int) -> bool:
    """Checks if a user is authorized to access the partner dashboard."""
    authorized_ids = []
    if ADMIN_CHAT_ID:
        authorized_ids.append(int(ADMIN_CHAT_ID))
    if PARTNER_TELEGRAM_ID:
        authorized_ids.append(int(PARTNER_TELEGRAM_ID))
    return user_id in authorized_ids


async def partner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Partner dashboard command - shows recruitment statistics."""
    user = update.effective_user
    
    # Security check
    if not is_authorized_partner(user.id):
        await update.message.reply_text(
            "🚫 *Access Denied*\n\n"
            "You are not authorized to view this dashboard.",
            parse_mode="Markdown"
        )
        logger.warning(f"⚠️ Unauthorized /partner access attempt by user {user.id}")
        return
    
    # Get stats from database
    stats = db.get_recruitment_stats()
    
    # Build city breakdown string
    city_lines = []
    for city, count in stats["city_breakdown"].items():
        city_lines.append(f"📍 {city} Density: {count}")
    
    city_breakdown = "\n".join(city_lines) if city_lines else "  _No data yet_"
    
    # Calculate verification rate
    total = stats["total_users"]
    verified = stats["verified_users"]
    active = stats.get("active_users", 0)
    online = stats.get("online_now", 0)
    revenue = stats.get("total_revenue", 0)
    
    # Build the report
    report = (
        "📊 *BLACKBOOK OPERATIONAL OVERVIEW*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Network Size:* {total} Providers\n"
        f"✔️ *Verified Assets:* {verified} ({(verified/total*100):.0f}%)\n" if total > 0 else f"� *Network Size:* {total} Providers\n✔️ *Verified Assets:* {verified}\n"
        f"🟢 *Currently Live:* {online}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{city_breakdown}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *Total Revenue:* {revenue:,} KES"
    )
    
    await update.message.reply_text(report, parse_mode="Markdown")
    logger.info(f"📊 Partner dashboard accessed by user {user.id}")


async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the provider's current profile status."""
    user = update.effective_user
    
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You're not registered yet. Use /register to get started.",
            parse_mode="Markdown"
        )
        return
    
    # Build status strings
    name = provider.get("display_name", "Unknown")
    city = provider.get("city", "Not set")
    neighborhood = provider.get("neighborhood", "Not set")
    verified = "✔️ Verified" if provider.get("is_verified") else "❌ Not Verified"
    active = "� Active" if provider.get("is_active") else "⚫ Inactive"
    online = "🟢 Live" if provider.get("is_online") else "⚫ Offline"
    
    expiry = provider.get("expiry_date")
    expiry_text = expiry.strftime("%Y-%m-%d %H:%M") if expiry else "No subscription"
    
    await update.message.reply_text(
        f"👤 *YOUR PROFILE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎭 *Stage Name:* {name}\n"
        f"📍 *Location:* {neighborhood}, {city}\n\n"
        f"🛡️ *Trust Level:* {verified}\n"
        f"📱 *Listing Status:* {active}\n"
        f"🌐 *Website Badge:* {online}\n\n"
        f"⏱️ *Subscription Expires:* {expiry_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "_Use /status to toggle your Live badge._\n"
        "_Use /topup to extend your subscription._",
        parse_mode="Markdown"
    )


# ==================== TOPUP / PAYMENT SYSTEM ====================

async def topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the topup process - shows package selection."""
    user = update.effective_user
    
    # Check if user is registered and verified
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
    
    # Show package selection
    keyboard = [
        [InlineKeyboardButton("⏰ 3 Days - 400 KES", callback_data="topup_3")],
        [InlineKeyboardButton("🔥 7 Days - 800 KES", callback_data="topup_7")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check current status
    status_text = ""
    if provider.get("is_active"):
        expiry = provider.get("expiry_date")
        if expiry:
            status_text = f"\n\n📅 Current subscription expires: {expiry.strftime('%Y-%m-%d %H:%M')}"
    
    await update.message.reply_text(
        "💰 *Listing Management*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Active listings receive *400% more engagement*.{}\n\n"
        "⏰ *3 Days Standard* — 400 KES\n"
        "🔥 *7 Days Premium* — 800 KES".format(status_text),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return TOPUP_PHONE


async def topup_package_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles package selection and asks for phone number."""
    query = update.callback_query
    await query.answer()
    
    # Extract package days from callback
    days = int(query.data.replace("topup_", ""))
    price = get_package_price(days)
    
    context.user_data["topup_days"] = days
    context.user_data["topup_price"] = price
    
    # Check if phone is already saved
    user = query.from_user
    saved_phone = db.get_provider_phone(user.id)
    
    if saved_phone:
        # Phone already exists - ask to confirm or change
        keyboard = [
            [InlineKeyboardButton(f"✅ Use {saved_phone}", callback_data="topup_use_saved")],
            [InlineKeyboardButton("📱 Enter New Number", callback_data="topup_new_phone")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📦 **{days} Day Package - {price} KES**\n\n"
            f"We have your number saved:\n📱 `{saved_phone}`\n\n"
            "Use this number for M-Pesa?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return TOPUP_CONFIRM
    else:
        # No phone saved - ask for it
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
    phone = update.message.text.strip()
    
    # Basic validation
    phone_clean = phone.replace(" ", "").replace("-", "").replace("+", "")
    if not phone_clean.isdigit() or len(phone_clean) < 9:
        await update.message.reply_text(
            "❌ Invalid phone number. Please enter a valid M-Pesa number:\n"
            "_Format: 0712345678 or 254712345678_",
            parse_mode="Markdown"
        )
        return TOPUP_PHONE
    
    # Save phone to database
    db.update_provider_phone(user.id, phone_clean)
    context.user_data["topup_phone"] = phone_clean
    
    # Proceed to payment
    days = context.user_data.get("topup_days", 3)
    price = context.user_data.get("topup_price", 400)
    
    # Initiate STK push
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
    
    if query.data == "topup_use_saved":
        # Use saved phone
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
        # Ask for new phone
        await query.edit_message_text(
            "Please enter your **M-Pesa phone number**:\n"
            "_Format: 0712345678 or 254712345678_",
            parse_mode="Markdown"
        )
        return TOPUP_PHONE


# ==================== SAFETY COMMANDS ====================

async def check_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks if a phone number is blacklisted. Usage: /check 0712345678"""
    user = update.effective_user
    
    # Check if registered
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text(
            "❌ You need to /register first.",
            parse_mode="Markdown"
        )
        return
    
    # Get phone number from command
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "📞 *Client Intelligence Check*\n\n"
            "Usage: `/check 0712345678`\n\n"
            "We check our national database for reports of non-payment, "
            "violence, or suspicious behavior.",
            parse_mode="Markdown"
        )
        return
    
    phone = context.args[0]
    result = db.check_blacklist(phone)
    
    if result.get("blacklisted"):
        await update.message.reply_text(
            "🚨 *SECURITY ALERT: BLACKLISTED*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 Client: `{phone}`\n"
            f"⚠️ Risk: {result.get('reason', 'Not specified')}\n"
            f"📅 Reported: {result.get('date', 'Unknown')}\n\n"
            "*Recommendation: ABORT CONNECTION. Do not meet this individual.*",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✅ *Security Check: PASSED*\n\n"
            f"No reports found for `{phone}`.\n\n"
            "_Note: Always use /session regardless of check results._",
            parse_mode="Markdown"
        )
    
    logger.info(f"🔍 Blacklist check by {user.id}: {phone} - {'FOUND' if result.get('blacklisted') else 'CLEAR'}")


async def report_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reports a phone number to the blacklist. Usage: /report 0712345678 Reason here"""
    user = update.effective_user
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🚫 **Report to Blacklist**\n\n"
            "Usage: `/report 0712345678 Reason for report`\n\n"
            "Example: `/report 0712345678 Did not pay, threatened me`",
            parse_mode="Markdown"
        )
        return
    
    phone = context.args[0]
    reason = " ".join(context.args[1:])
    
    success = db.add_to_blacklist(phone, reason, user.id)
    
    if success:
        await update.message.reply_text(
            "✅ **Number Reported**\n\n"
            f"📱 `{phone}` has been added to the blacklist.\n"
            f"📝 Reason: {reason}\n\n"
            "_Thank you for keeping our community safe._",
            parse_mode="Markdown"
        )
        
        # Alert admin
        if ADMIN_CHAT_ID:
            try:
                provider = db.get_provider(user.id)
                name = provider.get("display_name", "Unknown") if provider else "Unknown"
                await context.bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text=f"🚨 **New Blacklist Report**\n\n"
                         f"📱 Number: `{phone}`\n"
                         f"📝 Reason: {reason}\n"
                         f"👤 Reported by: {name}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to alert admin: {e}")
    else:
        await update.message.reply_text(
            "❌ Failed to add to blacklist. Please try again.",
            parse_mode="Markdown"
        )


async def start_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts a safety session timer. Usage: /session 60 (for 60 minutes)"""
    user = update.effective_user
    
    # Check if registered
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text("❌ You need to /register first.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "⏱️ **Safety Session Timer**\n\n"
            "Usage: `/session 60` (for 60 minutes)\n\n"
            "This starts a timer. If you don't send /checkin before the time is up, "
            "the admin will be alerted.\n\n"
            "**Always use this before meeting a client!**",
            parse_mode="Markdown"
        )
        return
    
    try:
        minutes = int(context.args[0])
        if minutes < 15 or minutes > 480:
            await update.message.reply_text(
                "⚠️ Session time must be between 15 and 480 minutes.",
                parse_mode="Markdown"
            )
            return
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number of minutes.")
        return
    
    session_id = db.start_session(user.id, minutes)
    
    if session_id:
        from datetime import datetime, timedelta
        check_back_time = datetime.now() + timedelta(minutes=minutes)
        
        await update.message.reply_text(
            "✅ *Safety Timer Active.*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏱️ Duration: {minutes} Minutes\n"
            f"⏰ Check-in Due: {check_back_time.strftime('%H:%M')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "We are watching the clock. You are expected to /checkin by the deadline.\n\n"
            "If you do not check in, an *Emergency Alert* including your last known "
            "location will be sent to the Management Team.",
            parse_mode="Markdown"
        )
        logger.info(f"⏱️ Session started by {user.id} for {minutes} minutes")
    else:
        await update.message.reply_text("❌ Failed to start session. Please try again.")


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks in after a session - confirms provider is safe."""
    user = update.effective_user
    
    success = db.end_session(user.id)
    
    if success:
        await update.message.reply_text(
            "✅ **Check-in Confirmed!**\n\n"
            "Glad you're safe! 💚\n\n"
            "_Remember to /session before your next meeting._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ℹ️ No active session to check in for.\n\n"
            "Use `/session <minutes>` to start a safety timer.",
            parse_mode="Markdown"
        )


async def toggle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles online/offline status for the website."""
    user = update.effective_user
    
    # Check if registered and active
    provider = db.get_provider(user.id)
    if not provider:
        await update.message.reply_text("❌ You need to /register first.")
        return
    
    if not provider.get("is_active"):
        await update.message.reply_text(
            "❌ You need an active subscription to go online.\n\n"
            "Use /topup to get listed on the website.",
            parse_mode="Markdown"
        )
        return
    
    new_status = db.toggle_online_status(user.id)
    neighborhood = provider.get('neighborhood', 'your area')
    
    if new_status:
        await update.message.reply_text(
            "🟢 *Status: LIVE*\n\n"
            f"Your profile now shows the 'Available Now' badge. "
            f"You will be prioritized in {neighborhood} search results.\n\n"
            "_Send /status again to go offline._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "⚫ *Status: HIDDEN*\n\n"
            "Your profile is still visible, but clients see you are currently unavailable.\n\n"
            "_Send /status again to go back online._",
            parse_mode="Markdown"
        )
    
    logger.info(f"📡 Status toggle by {user.id}: {'ONLINE' if new_status else 'OFFLINE'}")


# ==================== ADMIN EMERGENCY COMMANDS ====================


async def maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles maintenance mode - Admin only."""
    global MAINTENANCE_MODE
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "🚫 **Access Denied**\n\nAdmin only command.",
            parse_mode="Markdown"
        )
        logger.warning(f"⚠️ Unauthorized /maintenance attempt by user {user.id}")
        return
    
    # Toggle maintenance mode
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    status = "🔴 ON" if MAINTENANCE_MODE else "🟢 OFF"
    
    await update.message.reply_text(
        f"🛠️ **Maintenance Mode: {status}**\n\n"
        f"{'New registrations are now BLOCKED.' if MAINTENANCE_MODE else 'Registrations are now OPEN.'}",
        parse_mode="Markdown"
    )
    logger.info(f"🛠️ Maintenance mode toggled to {MAINTENANCE_MODE} by admin")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcasts a message to all providers - Admin only."""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "🚫 **Access Denied**\n\nAdmin only command.",
            parse_mode="Markdown"
        )
        logger.warning(f"⚠️ Unauthorized /broadcast attempt by user {user.id}")
        return
    
    # Get the message to broadcast (everything after /broadcast)
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
    
    # Get all provider IDs
    provider_ids = db.get_all_provider_ids()
    
    if not provider_ids:
        await update.message.reply_text(
            "⚠️ No providers to broadcast to.",
            parse_mode="Markdown"
        )
        return
    
    # Send confirmation before broadcasting
    await update.message.reply_text(
        f"📡 **Broadcasting to {len(provider_ids)} providers...**",
        parse_mode="Markdown"
    )
    
    # Broadcast message
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
    
    # Send summary
    await update.message.reply_text(
        f"✅ **Broadcast Complete**\n\n"
        f"📨 Delivered: {success_count}\n"
        f"❌ Failed: {fail_count}",
        parse_mode="Markdown"
    )
    logger.info(f"📢 Broadcast sent by admin to {success_count} providers")


def main() -> None:
    """Run the bot."""
    # Get token from environment variable
    token = os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        logger.error("❌ TELEGRAM_TOKEN environment variable not set!")
        raise ValueError("TELEGRAM_TOKEN environment variable is required")
    
    if not ADMIN_CHAT_ID:
        logger.warning("⚠️ ADMIN_CHAT_ID not set! Verification system will not work.")
    
    # Create the Application
    application = Application.builder().token(token).build()
    
    # Add /start command handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("partner", partner))
    application.add_handler(CommandHandler("myprofile", myprofile))
    
    # Admin emergency commands
    application.add_handler(CommandHandler("maintenance", maintenance))
    application.add_handler(CommandHandler("broadcast", broadcast))
    
    # Safety commands
    application.add_handler(CommandHandler("check", check_number))
    application.add_handler(CommandHandler("report", report_number))
    application.add_handler(CommandHandler("session", start_session))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("status", toggle_status))
    
    # Create the ConversationHandler for registration
    registration_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register)],
        states={
            STAGE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, stage_name)
            ],
            CITY: [
                CallbackQueryHandler(city_callback, pattern="^city_")
            ],
            NEIGHBORHOOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, neighborhood)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Create the ConversationHandler for verification
    verification_handler = ConversationHandler(
        entry_points=[CommandHandler("verify", verify)],
        states={
            AWAITING_PHOTO: [
                MessageHandler(filters.PHOTO, handle_verification_photo),
                MessageHandler(filters.Document.ALL, handle_document_rejection),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Create the ConversationHandler for topup
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
    
    # Add handlers
    application.add_handler(registration_handler)
    application.add_handler(verification_handler)
    application.add_handler(topup_handler)
    
    # Add admin callback handler for verification approvals
    application.add_handler(CallbackQueryHandler(
        admin_verification_callback, 
        pattern="^verify_(approve|reject)_"
    ))
    
    # Add menu callback handler for /start menu
    application.add_handler(CallbackQueryHandler(
        menu_callback,
        pattern="^menu_"
    ))
    
    # Start the bot
    logger.info("🚀 Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

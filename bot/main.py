"""
Blackbook Bot - Main Entry Point
Orchestrates the modular bot architecture with persistence and centralized logging.
"""
import os
from telegram import Update
from telegram.ext import Application, PicklePersistence

from config import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from database import Database
from handlers import register_all_handlers
from utils.logger import get_logger, configure_root_logger

# Setup centralized logging
configure_root_logger()
logger = get_logger(__name__)

# Persistence file path (keeps conversation state across restarts)
PERSISTENCE_FILE = os.path.join(os.path.dirname(__file__), "bot_persistence.pickle")


def main() -> None:
    """Run the bot."""
    # Validate required environment variables
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN environment variable not set!")
        raise ValueError("TELEGRAM_TOKEN environment variable is required")
    
    if not ADMIN_CHAT_ID:
        logger.warning("⚠️ ADMIN_CHAT_ID not set! Verification system will not work.")
    
    # Initialize database
    logger.info("🗄️ Initializing database connection...")
    db = Database()
    
    # Setup persistence (preserves conversation state across restarts)
    logger.info("💾 Loading conversation persistence...")
    persistence = PicklePersistence(filepath=PERSISTENCE_FILE)
    
    # Create the Application with persistence
    logger.info("🤖 Building Telegram application...")
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .persistence(persistence)
        .build()
    )
    
    # Register all handlers from modular structure
    logger.info("📦 Registering handlers...")
    register_all_handlers(application, db)
    
    # Start the bot
    logger.info("🚀 Blackbook Bot is starting...")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  Modules loaded:")
    logger.info("    ✓ handlers/auth.py")
    logger.info("    ✓ handlers/safety.py")
    logger.info("    ✓ handlers/payment.py")
    logger.info("    ✓ handlers/admin.py")
    logger.info("    ✓ services/metapay.py")
    logger.info("    ✓ utils/logger.py")
    logger.info("  Features:")
    logger.info("    ✓ PicklePersistence (conversation state survives restarts)")
    logger.info("    ✓ Centralized logging (module-aware)")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

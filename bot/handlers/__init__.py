"""
Blackbook Bot Handlers
All command and callback handlers organized by domain.
"""
from . import auth
from . import safety
from . import payment
from . import admin


def register_all_handlers(application, db):
    """
    Registers all handlers with the application.
    
    Args:
        application: The telegram Application instance
        db: The shared Database instance
    """
    # Store database in bot_data for access across handlers
    application.bot_data["db"] = db
    
    # Register handlers from each module
    auth.register_handlers(application)
    safety.register_handlers(application)
    payment.register_handlers(application)
    admin.register_handlers(application)

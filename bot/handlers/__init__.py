"""
Blackbook Bot Handlers
All command and callback handlers organized by domain.
"""
from . import auth
from . import safety
from . import payment
from . import admin
from . import profile
from . import photos
from . import online
from . import verification


def register_all_handlers(application, db):
    """
    Registers all handlers with the application.
    
    Args:
        application: The telegram Application instance
        db: The shared Database instance
    """
    # Register handlers from each module
    auth.register_handlers(application)
    profile.register_handlers(application)
    photos.register_handlers(application)
    online.register_handlers(application)
    verification.register_handlers(application)
    safety.register_handlers(application)
    payment.register_handlers(application)
    admin.register_handlers(application)


def register_admin_only_handlers(application, db):
    """
    Registers only moderation/admin handlers for dedicated admin bot.

    Args:
        application: The telegram Application instance
        db: The shared Database instance
    """
    auth.register_admin_verification_handlers(application)
    verification.register_admin_verification_handlers(application)
    admin.register_handlers(application)

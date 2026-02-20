"""
Blackbook Bot Configuration
Thin wrapper around shared config + bot-specific conversation states.
"""

from shared.config import *

# ==================== CONVERSATION STATES ====================
# Registration flow
STAGE_NAME, CITY, NEIGHBORHOOD = range(3)

# Payment/Topup flow
TOPUP_PHONE, TOPUP_CONFIRM = range(20, 22)

# Verification flow
AWAITING_PHOTO = 10

# Profile Completion flow
PROFILE_AGE, PROFILE_HEIGHT, PROFILE_WEIGHT, PROFILE_BUILD, PROFILE_AVAILABILITY, PROFILE_SERVICES, PROFILE_BIO, PROFILE_NEARBY, PROFILE_PHOTOS, PROFILE_RATES, PROFILE_LANGUAGES = range(30, 41)

# PACKAGES (bot previously used PACKAGES, shared sets PACKAGE_PRICES)
PACKAGES = PACKAGE_PRICES
TELEGRAM_TOKEN = TELEGRAM_BOT_TOKEN
CITIES = CITIES_RICH

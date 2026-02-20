"""
Smoke Tests for Blackbook Bot Service
Validates that all major modules can be imported and key helper/config
functions produce expected results. Runs WITHOUT Telegram or database.

Run from project root: python -m pytest bot/tests/test_smoke_bot.py -v
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock


# ──────────────────────────────────────────────────────────
# 1. Mock external dependencies
# ──────────────────────────────────────────────────────────

# Mock psycopg2
if "psycopg2" not in sys.modules:
    psycopg2 = types.ModuleType("psycopg2")

    class _Psycopg2Error(Exception):
        pass

    class _OperationalError(_Psycopg2Error):
        pass

    extras = types.ModuleType("psycopg2.extras")
    extensions = types.ModuleType("psycopg2.extensions")

    class _Json:
        def __init__(self, adapted: Any):
            self.adapted = adapted

    extras.Json = _Json
    extras.RealDictCursor = object
    extensions.TRANSACTION_STATUS_INERROR = 3
    extensions.TRANSACTION_STATUS_UNKNOWN = 0
    psycopg2.Error = _Psycopg2Error
    psycopg2.OperationalError = _OperationalError
    psycopg2.extras = extras
    psycopg2.extensions = extensions
    psycopg2.connect = MagicMock(return_value=MagicMock())
    sys.modules["psycopg2"] = psycopg2
    sys.modules["psycopg2.extras"] = extras
    sys.modules["psycopg2.extensions"] = extensions

# Mock telegram library — heavy C extensions we don't want to pull in
if "telegram" not in sys.modules:
    telegram = types.ModuleType("telegram")
    telegram.Update = MagicMock
    telegram.InlineKeyboardButton = MagicMock
    telegram.InlineKeyboardMarkup = MagicMock
    telegram.ReplyKeyboardMarkup = MagicMock
    telegram.KeyboardButton = MagicMock
    telegram.InputMediaPhoto = MagicMock
    telegram.helpers = types.ModuleType("telegram.helpers")
    telegram.helpers.escape_markdown = MagicMock(side_effect=lambda text, version=2: text)
    telegram.error = types.ModuleType("telegram.error")
    telegram.error.BadRequest = type("BadRequest", (Exception,), {})
    sys.modules["telegram"] = telegram
    sys.modules["telegram.helpers"] = telegram.helpers
    sys.modules["telegram.error"] = telegram.error

if "telegram.ext" not in sys.modules:
    telegram_ext = types.ModuleType("telegram.ext")
    telegram_ext.ContextTypes = MagicMock()
    telegram_ext.CommandHandler = MagicMock
    telegram_ext.MessageHandler = MagicMock
    telegram_ext.CallbackQueryHandler = MagicMock
    telegram_ext.ConversationHandler = MagicMock
    telegram_ext.ApplicationBuilder = MagicMock
    telegram_ext.filters = MagicMock()
    telegram_ext.Application = MagicMock
    sys.modules["telegram.ext"] = telegram_ext

if "httpx" not in sys.modules:
    httpx = types.ModuleType("httpx")
    httpx.AsyncClient = MagicMock
    sys.modules["httpx"] = httpx

# Ensure bot/ and root/ are on sys.path
BOT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BOT_DIR.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# ──────────────────────────────────────────────────────────
# 2. Config Module Tests
# ──────────────────────────────────────────────────────────


class TestConfigImport(unittest.TestCase):
    """Verify config module loads and has expected constants."""

    def test_import_config(self):
        import config
        self.assertIsNotNone(config)

    def test_cities_defined(self):
        from config import CITIES
        self.assertIsInstance(CITIES, list)
        self.assertGreater(len(CITIES), 0)
        # Each city should be (name, emoji, is_available)
        for city in CITIES:
            self.assertEqual(len(city), 3, f"City tuple should have 3 elements: {city}")

    def test_neighborhoods_defined(self):
        from config import NAIROBI_NEIGHBORHOODS, ELDORET_NEIGHBORHOODS
        self.assertIsInstance(NAIROBI_NEIGHBORHOODS, list)
        self.assertGreater(len(NAIROBI_NEIGHBORHOODS), 10)
        self.assertIsInstance(ELDORET_NEIGHBORHOODS, list)

    def test_packages_defined(self):
        from config import PACKAGES, TIERS
        self.assertIn(3, PACKAGES)
        self.assertIn(7, PACKAGES)
        self.assertIn(30, PACKAGES)
        self.assertIn(90, PACKAGES)
        # TIERS should have matching keys
        for days in PACKAGES:
            self.assertIn(days, TIERS, f"Missing tier for {days} days")

    def test_conversation_states(self):
        from config import STAGE_NAME, CITY, NEIGHBORHOOD, AWAITING_PHOTO
        # These should be distinct integers
        self.assertIsInstance(STAGE_NAME, int)
        self.assertIsInstance(CITY, int)
        self.assertIsInstance(NEIGHBORHOOD, int)
        self.assertIsInstance(AWAITING_PHOTO, int)

    def test_static_data(self):
        from config import BUILDS, AVAILABILITIES, SERVICES, LANGUAGES, SESSION_DURATIONS
        self.assertGreater(len(BUILDS), 0)
        self.assertGreater(len(AVAILABILITIES), 0)
        self.assertGreater(len(SERVICES), 0)
        self.assertGreater(len(LANGUAGES), 0)
        self.assertGreater(len(SESSION_DURATIONS), 0)

    def test_is_admin_function(self):
        from config import is_admin, ADMIN_CHAT_ID
        # Without ADMIN_CHAT_ID set, should return False
        if ADMIN_CHAT_ID is None:
            self.assertFalse(is_admin(12345))
        else:
            self.assertTrue(is_admin(int(ADMIN_CHAT_ID)))

    def test_get_package_price(self):
        from config import get_package_price, PACKAGES
        for days, price in PACKAGES.items():
            self.assertEqual(get_package_price(days), price)
        self.assertEqual(get_package_price(999), 0)

    def test_is_authorized_partner(self):
        from config import is_authorized_partner
        # With no env vars, should return False for random ID
        self.assertFalse(is_authorized_partner(999999999))


# ──────────────────────────────────────────────────────────
# 3. Database Module Tests
# ──────────────────────────────────────────────────────────


class TestBotDatabaseStructure(unittest.TestCase):
    """Verify Database class has all expected methods."""

    def setUp(self):
        from database import Database
        self.db = Database()

    def test_has_provider_methods(self):
        expected = [
            "get_provider",
            "add_provider",
            "update_provider_profile",
            "update_provider_phone",
            "get_provider_phone",
            "verify_provider",
            "toggle_online_status",
            "set_online_status",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_payment_methods(self):
        expected = [
            "log_payment",
            "get_payment_by_reference",
            "get_latest_payment_for_provider",
            "activate_subscription",
            "boost_provider",
            "is_boosted",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_safety_methods(self):
        expected = [
            "check_blacklist",
            "add_to_blacklist",
            "start_session",
            "end_session",
            "get_overdue_sessions",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_trial_methods(self):
        expected = [
            "activate_free_trial",
            "get_trial_reminder_candidates",
            "mark_trial_reminder_sent",
            "get_unnotified_expired_trials",
            "get_trial_winback_candidates",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_referral_methods(self):
        expected = [
            "generate_referral_code",
            "get_referrer_by_code",
            "set_referred_by",
            "add_referral_credits",
            "get_referral_stats",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_verification_methods(self):
        expected = [
            "save_verification_photo",
            "save_provider_photos",
            "get_verification_queue",
            "get_verification_queue_count",
            "log_provider_verification_event",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_admin_methods(self):
        expected = [
            "get_all_provider_ids",
            "get_recruitment_stats",
            "get_providers_by_status",
            "set_provider_active_status",
            "get_portal_pending_accounts",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")


# ──────────────────────────────────────────────────────────
# 4. db_context Module Tests
# ──────────────────────────────────────────────────────────


class TestDbContext(unittest.TestCase):
    """Verify db_context set/get pattern works."""

    def test_set_and_get_db(self):
        from db_context import set_db, get_db
        sentinel = object()
        set_db(sentinel)
        self.assertIs(get_db(), sentinel)
        # Reset
        set_db(None)
        self.assertIsNone(get_db())


# ──────────────────────────────────────────────────────────
# 5. Formatters Module Tests
# ──────────────────────────────────────────────────────────


class TestFormatters(unittest.TestCase):
    """Verify formatter utility functions."""

    def test_import_formatters(self):
        from utils.formatters import (
            generate_verification_code,
            format_welcome_message,
            format_profile_text,
            format_tier_badge,
            format_status_badge,
        )
        self.assertTrue(callable(generate_verification_code))
        self.assertTrue(callable(format_welcome_message))

    def test_generate_verification_code(self):
        from utils.formatters import generate_verification_code
        code = generate_verification_code()
        self.assertIsInstance(code, str)
        self.assertEqual(len(code), 6)

    def test_format_tier_badge(self):
        from utils.formatters import format_tier_badge
        self.assertIn("Platinum", format_tier_badge("platinum"))
        self.assertIn("Gold", format_tier_badge("gold"))

    def test_format_welcome_message(self):
        from utils.formatters import format_welcome_message
        msg = format_welcome_message()
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 50)

    def test_format_profile_text(self):
        from utils.formatters import format_profile_text
        provider = {
            "display_name": "Test Provider",
            "city": "Nairobi",
            "neighborhood": "Westlands",
            "phone": "0712345678",
            "is_verified": True,
            "is_active": True,
            "is_online": True,
            "subscription_tier": "gold",
            "expiry_date": None,
            "referral_code": "ABC123",
        }
        text = format_profile_text(provider)
        self.assertIn("Test Provider", text)
        self.assertIn("Nairobi", text)


# ──────────────────────────────────────────────────────────
# 6. Handlers Init Module Tests
# ──────────────────────────────────────────────────────────


class TestHandlersInit(unittest.TestCase):
    """Verify handler registration functions exist."""

    def test_import_handlers(self):
        from handlers import register_all_handlers, register_admin_only_handlers
        self.assertTrue(callable(register_all_handlers))
        self.assertTrue(callable(register_admin_only_handlers))


if __name__ == "__main__":
    unittest.main()

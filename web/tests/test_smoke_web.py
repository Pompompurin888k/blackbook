"""
Smoke Tests for Blackbook Web Service
Validates that all major modules can be imported and key helper functions
produce expected results. These run WITHOUT a database or Redis connection.

Run: python -m pytest tests/test_smoke_web.py -v
"""
from __future__ import annotations

import sys
import os
import types
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Any


# ──────────────────────────────────────────────────────────
# 1. Mock external dependencies that need live connections
# ──────────────────────────────────────────────────────────

# Mock psycopg2 so Database.__init__ doesn't try to connect.
# Guard carefully to avoid conflicts with test_database_unit.py mocks.
_psycopg2_mod = sys.modules.get("psycopg2")
if _psycopg2_mod is None:
    _psycopg2_mod = types.ModuleType("psycopg2")

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
    _psycopg2_mod.Error = _Psycopg2Error
    _psycopg2_mod.OperationalError = _OperationalError
    _psycopg2_mod.extras = extras
    _psycopg2_mod.extensions = extensions
    _psycopg2_mod.connect = MagicMock(return_value=MagicMock())
    sys.modules["psycopg2"] = _psycopg2_mod
    sys.modules["psycopg2.extras"] = extras
    sys.modules["psycopg2.extensions"] = extensions
elif not hasattr(_psycopg2_mod, "connect"):
    _psycopg2_mod.connect = MagicMock(return_value=MagicMock())


# Ensure web/ and root/ are on sys.path
WEB_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = WEB_DIR.parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Change to web directory so StaticFiles(directory="static") doesn't fail
_original_cwd = os.getcwd()
os.chdir(str(WEB_DIR))


# ──────────────────────────────────────────────────────────
# 2. Import Tests — verify all key modules can load
# ──────────────────────────────────────────────────────────


class TestWebImports(unittest.TestCase):
    """Verify that all major web modules can be imported."""

    def test_import_database(self):
        from database import Database
        db = Database()
        self.assertTrue(hasattr(db, "get_active_providers"))
        self.assertTrue(hasattr(db, "get_provider_by_id"))
        self.assertTrue(hasattr(db, "healthcheck"))

    def test_import_payment_queue_utils(self):
        from payment_queue_utils import extract_callback_reference, build_payment_callback_job_id
        self.assertIsNotNone(extract_callback_reference)
        self.assertIsNotNone(build_payment_callback_job_id)

    def test_import_main_app(self):
        import main
        self.assertTrue(hasattr(main, "app"))
        self.assertEqual(main.app.title, "Blackbook Directory")

    def test_import_main_helpers(self):
        from main import (
            _to_string_list,
            _sanitize_phone,
            _normalize_portal_phone,
            _hash_password,
            _verify_password,
            _fallback_image,
            _normalize_onboarding_step,
            _parse_csv_values,
            _to_int_or_none,
            _detect_device_type,
            _extract_client_ip,
            _normalize_provider,
            _normalize_recommendation,
            _portal_account_state,
            _portal_is_locked,
            _build_gallery_urls,
            _portal_compute_profile_strength,
            _portal_build_ranking_tips,
        )
        # Should all be callable
        for fn in [
            _to_string_list, _sanitize_phone, _normalize_portal_phone,
            _hash_password, _verify_password, _fallback_image,
            _normalize_onboarding_step, _parse_csv_values, _to_int_or_none,
            _detect_device_type, _normalize_provider, _normalize_recommendation,
            _portal_account_state, _portal_is_locked, _build_gallery_urls,
            _portal_compute_profile_strength, _portal_build_ranking_tips,
        ]:
            self.assertTrue(callable(fn), f"{fn} should be callable")

    def test_import_main_route_functions(self):
        from routes.public import home, safety, contact_page, connect_provider
        from routes.api import health, health_live, api_providers, api_grid, api_recommendations
        from routes.portal_auth import provider_portal_auth, provider_portal_login, provider_portal_register, provider_portal_logout
        from routes.portal_onboarding import provider_portal_onboarding, provider_portal_onboarding_submit
        from routes.portal_dashboard import provider_portal_dashboard
        from routes.portal_actions import (
            provider_toggle_status,
            provider_activate_trial,
            provider_wallet_pay,
            provider_safety_page,
            provider_support_page,
            provider_rules_page,
            provider_claim_referral_reward,
        )
        from routes.payments import megapay_callback

        # All should be callable
        self.assertTrue(callable(home))
        self.assertTrue(callable(safety))
        self.assertTrue(callable(health))
        self.assertTrue(callable(provider_toggle_status))
        self.assertTrue(callable(provider_activate_trial))
        self.assertTrue(callable(provider_wallet_pay))
        self.assertTrue(callable(provider_safety_page))
        self.assertTrue(callable(provider_support_page))
        self.assertTrue(callable(provider_rules_page))
        self.assertTrue(callable(provider_claim_referral_reward))


# ──────────────────────────────────────────────────────────
# 3. Helper Function Tests — verify pure logic works
# ──────────────────────────────────────────────────────────


class TestToStringList(unittest.TestCase):
    """Tests for _to_string_list helper."""

    def setUp(self):
        from main import _to_string_list
        self.fn = _to_string_list

    def test_none_returns_empty(self):
        self.assertEqual(self.fn(None), [])

    def test_list_passthrough(self):
        self.assertEqual(self.fn(["a", "b"]), ["a", "b"])

    def test_list_strips_whitespace(self):
        self.assertEqual(self.fn(["  a  ", " b "]), ["a", "b"])

    def test_list_filters_empty_strings(self):
        self.assertEqual(self.fn(["a", "", "  ", "b"]), ["a", "b"])

    def test_tuple_input(self):
        self.assertEqual(self.fn(("x", "y")), ["x", "y"])

    def test_json_string_list(self):
        self.assertEqual(self.fn('["foo", "bar"]'), ["foo", "bar"])

    def test_csv_string(self):
        self.assertEqual(self.fn("a, b, c"), ["a", "b", "c"])

    def test_single_string(self):
        self.assertEqual(self.fn("hello"), ["hello"])

    def test_empty_string(self):
        self.assertEqual(self.fn(""), [])

    def test_whitespace_string(self):
        self.assertEqual(self.fn("   "), [])


class TestSanitizePhone(unittest.TestCase):
    """Tests for _sanitize_phone helper."""

    def setUp(self):
        from main import _sanitize_phone
        self.fn = _sanitize_phone

    def test_empty_returns_empty(self):
        self.assertEqual(self.fn(""), "")
        self.assertEqual(self.fn(None), "")

    def test_local_format(self):
        self.assertEqual(self.fn("0712345678"), "254712345678")

    def test_intl_format(self):
        self.assertEqual(self.fn("254712345678"), "254712345678")

    def test_double_zero_prefix(self):
        self.assertEqual(self.fn("00254712345678"), "254712345678")

    def test_with_special_chars(self):
        self.assertEqual(self.fn("+254-712-345-678"), "254712345678")


class TestNormalizePortalPhone(unittest.TestCase):
    """Tests for _normalize_portal_phone helper."""

    def setUp(self):
        from main import _normalize_portal_phone
        self.fn = _normalize_portal_phone

    def test_valid_phone(self):
        self.assertEqual(self.fn("0712345678"), "254712345678")

    def test_too_short(self):
        self.assertEqual(self.fn("0712"), "")

    def test_non_254_prefix(self):
        self.assertEqual(self.fn("1234567890"), "")


class TestPasswordHashVerify(unittest.TestCase):
    """Tests for _hash_password / _verify_password helpers."""

    def setUp(self):
        from main import _hash_password, _verify_password
        self.hash_fn = _hash_password
        self.verify_fn = _verify_password

    def test_hash_produces_salt_hash_format(self):
        h = self.hash_fn("secret123")
        self.assertIn("$", h)
        parts = h.split("$")
        self.assertEqual(len(parts), 2)

    def test_verify_correct_password(self):
        h = self.hash_fn("mypassword")
        self.assertTrue(self.verify_fn("mypassword", h))

    def test_verify_wrong_password(self):
        h = self.hash_fn("mypassword")
        self.assertFalse(self.verify_fn("wrongpassword", h))

    def test_verify_empty_hash(self):
        self.assertFalse(self.verify_fn("test", ""))

    def test_verify_no_dollar_sign(self):
        self.assertFalse(self.verify_fn("test", "nodollarsign"))


class TestNormalizeOnboardingStep(unittest.TestCase):
    """Tests for _normalize_onboarding_step helper."""

    def setUp(self):
        from main import _normalize_onboarding_step, ONBOARDING_TOTAL_STEPS
        self.fn = _normalize_onboarding_step
        self.total = ONBOARDING_TOTAL_STEPS

    def test_valid_step(self):
        self.assertEqual(self.fn(1), 1)
        self.assertEqual(self.fn(2), 2)

    def test_below_range(self):
        self.assertEqual(self.fn(0), 1)
        self.assertEqual(self.fn(-5), 1)

    def test_above_range(self):
        self.assertEqual(self.fn(99), self.total)

    def test_invalid_type(self):
        self.assertEqual(self.fn("abc"), 1)
        self.assertEqual(self.fn(None), 1)


class TestDetectDeviceType(unittest.TestCase):
    """Tests for _detect_device_type helper."""

    def setUp(self):
        from main import _detect_device_type
        self.fn = _detect_device_type

    def test_mobile(self):
        self.assertEqual(self.fn("Mozilla/5.0 (iPhone; CPU)"), "mobile")

    def test_android(self):
        self.assertEqual(self.fn("Mozilla/5.0 (Linux; Android 12)"), "mobile")

    def test_desktop(self):
        self.assertEqual(self.fn("Mozilla/5.0 (Windows NT 10.0; Win64)"), "desktop")

    def test_tablet(self):
        self.assertEqual(self.fn("Mozilla/5.0 (iPad; CPU OS)"), "tablet")

    def test_empty(self):
        self.assertEqual(self.fn(""), "unknown")
        self.assertEqual(self.fn(None), "unknown")


class TestPortalAccountState(unittest.TestCase):
    """Tests for _portal_account_state helper."""

    def setUp(self):
        from main import _portal_account_state
        self.fn = _portal_account_state

    def test_none_provider(self):
        self.assertEqual(self.fn(None), "pending_review")

    def test_known_state(self):
        self.assertEqual(self.fn({"account_state": "approved"}), "approved")
        self.assertEqual(self.fn({"account_state": "rejected"}), "rejected")

    def test_unknown_state_verified(self):
        self.assertEqual(self.fn({"account_state": "bogus", "is_verified": True}), "approved")

    def test_unknown_state_not_verified(self):
        self.assertEqual(self.fn({"account_state": "bogus", "is_verified": False}), "pending_review")


class TestPortalIsLocked(unittest.TestCase):
    """Tests for _portal_is_locked helper."""

    def setUp(self):
        from main import _portal_is_locked
        from datetime import datetime, timedelta
        self.fn = _portal_is_locked
        self.datetime = datetime
        self.timedelta = timedelta

    def test_no_locked_until(self):
        self.assertFalse(self.fn({"locked_until": None}))

    def test_locked_in_future(self):
        future = self.datetime.now() + self.timedelta(hours=1)
        self.assertTrue(self.fn({"locked_until": future}))

    def test_locked_in_past(self):
        past = self.datetime.now() - self.timedelta(hours=1)
        self.assertFalse(self.fn({"locked_until": past}))


class TestNormalizeProvider(unittest.TestCase):
    """Tests for _normalize_provider helper — verifies template payload stability."""

    def setUp(self):
        from main import _normalize_provider
        self.fn = _normalize_provider

    def test_minimal_provider(self):
        provider = {
            "id": 1,
            "display_name": "Test",
            "city": "Nairobi",
            "services": None,
            "profile_photos": None,
            "phone": None,
            "is_online": False,
        }
        result = self.fn(provider)
        self.assertEqual(result["services_list"], [])
        self.assertIn("photo_urls", result)
        self.assertEqual(len(result["photo_urls"]), 1)  # fallback
        self.assertEqual(result["has_phone"], False)
        self.assertIn("rate_cards", result)

    def test_provider_with_data(self):
        provider = {
            "id": 42,
            "display_name": "Nia",
            "city": "Nairobi",
            "neighborhood": "Westlands",
            "services": ["GFE", "Massage"],
            "profile_photos": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
            "phone": "0712345678",
            "is_online": True,
            "rate_30min": 3000,
            "rate_1hr": 5000,
        }
        result = self.fn(provider)
        self.assertEqual(result["services_list"], ["GFE", "Massage"])
        self.assertEqual(len(result["photo_urls"]), 2)
        self.assertTrue(result["has_phone"])
        self.assertEqual(result["primary_location"], "Westlands")
        self.assertEqual(len(result["rate_cards"]), 2)


class TestBuildGalleryUrls(unittest.TestCase):
    """Tests for _build_gallery_urls helper."""

    def setUp(self):
        from main import _build_gallery_urls
        self.fn = _build_gallery_urls

    def test_empty_photos(self):
        result = self.fn(1, [])
        self.assertEqual(len(result), 1)  # fallback image

    def test_http_urls_passthrough(self):
        urls = ["https://example.com/a.jpg", "https://example.com/b.jpg"]
        result = self.fn(1, urls)
        self.assertEqual(result, urls)

    def test_telegram_file_ids(self):
        ids = ["AgACAgI_abc", "AgACAgI_def"]
        result = self.fn(1, ids)
        self.assertEqual(result, ["/photo/AgACAgI_abc", "/photo/AgACAgI_def"])

    def test_max_five_photos(self):
        ids = [f"https://example.com/{i}.jpg" for i in range(10)]
        result = self.fn(1, ids)
        self.assertEqual(len(result), 5)


class TestProfileStrength(unittest.TestCase):
    """Tests for _portal_compute_profile_strength helper."""

    def setUp(self):
        from main import _portal_compute_profile_strength
        self.fn = _portal_compute_profile_strength

    def test_empty_draft_scores_low(self):
        result = self.fn({}, 0)
        self.assertLess(result["score"], 20)
        self.assertEqual(result["label"], "Needs work")
        self.assertGreater(len(result["missing"]), 0)

    def test_full_draft_scores_high(self):
        draft = {
            "display_name": "Test",
            "city": "Nairobi",
            "neighborhood": "Westlands",
            "age": "25",
            "height_cm": "170",
            "weight_kg": "60",
            "build": "Slim",
            "bio": "x" * 100,
            "nearby_places": "Near Mall",
            "availability_type": "Both",
            "services_text": "GFE, Massage, Dinner Date",
            "languages_text": "English, Swahili",
            "rate_30min": "3000",
            "rate_1hr": "5000",
            "rate_2hr": "8000",
        }
        result = self.fn(draft, 5)
        self.assertGreaterEqual(result["score"], 85)
        self.assertEqual(result["label"], "Excellent")


class TestToIntOrNone(unittest.TestCase):
    """Tests for _to_int_or_none helper."""

    def setUp(self):
        from main import _to_int_or_none
        self.fn = _to_int_or_none

    def test_none(self):
        self.assertIsNone(self.fn(None))

    def test_valid_int(self):
        self.assertEqual(self.fn("42"), 42)

    def test_with_commas(self):
        self.assertEqual(self.fn("1,000"), 1000)

    def test_empty_string(self):
        self.assertIsNone(self.fn(""))

    def test_invalid(self):
        self.assertIsNone(self.fn("abc"))


class TestPortalActionHelpers(unittest.TestCase):
    """Tests for portal action helper logic."""

    def setUp(self):
        from routes.portal_actions import _normalize_mpesa_phone, _is_trial_eligible
        self.normalize_phone = _normalize_mpesa_phone
        self.is_trial_eligible = _is_trial_eligible

    def test_normalize_mpesa_phone(self):
        self.assertEqual(self.normalize_phone("0712345678"), "254712345678")
        self.assertEqual(self.normalize_phone("+254712345678"), "254712345678")
        self.assertEqual(self.normalize_phone("0712"), "")

    def test_trial_eligibility(self):
        self.assertTrue(self.is_trial_eligible({"is_verified": True, "is_active": False, "trial_used": False}))
        self.assertFalse(self.is_trial_eligible({"is_verified": False, "is_active": False, "trial_used": False}))
        self.assertFalse(self.is_trial_eligible({"is_verified": True, "is_active": True, "trial_used": False}))
        self.assertFalse(self.is_trial_eligible({"is_verified": True, "is_active": False, "trial_used": True}))


class TestParseCsvValues(unittest.TestCase):
    """Tests for _parse_csv_values helper."""

    def setUp(self):
        from main import _parse_csv_values
        self.fn = _parse_csv_values

    def test_empty(self):
        self.assertEqual(self.fn(""), [])

    def test_csv(self):
        self.assertEqual(self.fn("a, b, c"), ["a", "b", "c"])

    def test_strips_whitespace(self):
        self.assertEqual(self.fn("  x ,  y  "), ["x", "y"])


class TestFallbackImage(unittest.TestCase):
    """Tests for _fallback_image helper."""

    def setUp(self):
        from main import _fallback_image
        self.fn = _fallback_image

    def test_deterministic(self):
        self.assertEqual(self.fn(1), self.fn(1))

    def test_different_seeds(self):
        # Not strictly guaranteed, but should differ for adjacent seeds
        self.assertNotEqual(self.fn(0), self.fn(1))

    def test_returns_url(self):
        self.assertTrue(self.fn(0).startswith("https://"))


# ──────────────────────────────────────────────────────────
# 4. Database Class Structure Tests
# ──────────────────────────────────────────────────────────


class TestDatabaseStructure(unittest.TestCase):
    """Verify that Database class has all expected methods."""

    def setUp(self):
        from database import Database
        self.db = Database()

    def test_has_provider_methods(self):
        expected = [
            "get_active_providers",
            "get_public_active_providers",
            "get_city_counts",
            "get_provider_by_id",
            "get_provider_by_telegram_id",
            "get_total_verified_count",
            "get_online_count",
            "get_premium_count",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_portal_methods(self):
        expected = [
            "get_portal_provider_by_phone",
            "get_portal_provider_by_id",
            "create_portal_provider_account",
            "update_portal_provider_profile",
            "set_portal_phone_verification_code",
            "register_portal_login_failure",
            "reset_portal_login_failures",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_payment_methods(self):
        expected = [
            "activate_subscription",
            "has_successful_payment",
            "log_payment",
            "boost_provider",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")

    def test_has_analytics_methods(self):
        expected = [
            "log_analytics_event",
            "log_lead_analytics",
            "log_funnel_event",
        ]
        for method in expected:
            self.assertTrue(hasattr(self.db, method), f"Missing: {method}")


if __name__ == "__main__":
    unittest.main()

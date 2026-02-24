from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


WEB_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = WEB_DIR.parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.providers import _format_last_active_label  # noqa: E402
from utils.providers import _format_response_rate_label  # noqa: E402
from utils.providers import _normalize_provider  # noqa: E402


class TestProviderTrustSignals(unittest.TestCase):
    def test_last_active_online(self) -> None:
        label = _format_last_active_label(datetime.now(), is_online=True)
        self.assertEqual(label, "Online now")

    def test_last_active_relative_hours(self) -> None:
        now = datetime(2026, 2, 24, 18, 0, 0)
        last_active = now - timedelta(hours=2, minutes=5)
        label = _format_last_active_label(last_active, is_online=False, now=now)
        self.assertEqual(label, "Active 2h ago")

    def test_response_rate_label(self) -> None:
        self.assertEqual(_format_response_rate_label(None), "Response tracking")
        self.assertEqual(_format_response_rate_label(0), "New profile")
        self.assertEqual(_format_response_rate_label(87.4), "87% response rate")

    def test_normalize_provider_includes_trust_flags(self) -> None:
        provider = {
            "id": 59,
            "display_name": "Sara",
            "is_online": False,
            "email_verified": True,
            "updated_at": datetime(2026, 2, 24, 17, 55, 0),
            "created_at": datetime(2026, 2, 24, 17, 0, 0),
            "response_rate_pct": 63,
            "profile_photos": [],
        }
        normalized = _normalize_provider(provider)
        self.assertTrue(normalized["email_verified_badge"])
        self.assertEqual(normalized["response_rate_label"], "63% response rate")
        self.assertIn("Active", normalized["last_active_hint"])


if __name__ == "__main__":
    unittest.main()

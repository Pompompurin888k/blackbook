from __future__ import annotations

import sys
import unittest
from pathlib import Path


WEB_DIR = Path(__file__).resolve().parents[1]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from utils.auth import _build_portal_login_failure_message, _normalize_portal_username  # type: ignore  # noqa: E402


class PortalAuthUtilsUnitTests(unittest.TestCase):
    def test_normalize_portal_username_accepts_valid_username(self) -> None:
        self.assertEqual(_normalize_portal_username("Mathew_88"), "mathew_88")

    def test_normalize_portal_username_strips_at_prefix(self) -> None:
        self.assertEqual(_normalize_portal_username("@Innbucks"), "innbucks")

    def test_normalize_portal_username_rejects_short_username(self) -> None:
        self.assertEqual(_normalize_portal_username("ab"), "")

    def test_normalize_portal_username_rejects_invalid_characters(self) -> None:
        self.assertEqual(_normalize_portal_username("mathew.dev"), "")

    def test_normalize_portal_username_rejects_too_long_username(self) -> None:
        self.assertEqual(_normalize_portal_username("a" * 33), "")

    def test_build_login_failure_message_with_remaining_attempts(self) -> None:
        message = _build_portal_login_failure_message(login_failed_attempts=2, max_attempts=5)
        self.assertIn("3 attempts left", message)

    def test_build_login_failure_message_when_no_attempt_count(self) -> None:
        message = _build_portal_login_failure_message(login_failed_attempts=None, max_attempts=5)
        self.assertEqual(message, "Invalid email or password.")

    def test_build_login_failure_message_when_limit_reached(self) -> None:
        message = _build_portal_login_failure_message(login_failed_attempts=5, max_attempts=5)
        self.assertEqual(message, "Invalid email or password.")


if __name__ == "__main__":
    unittest.main()

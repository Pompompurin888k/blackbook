from __future__ import annotations

import sys
import unittest
from pathlib import Path


WEB_DIR = Path(__file__).resolve().parents[1]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from utils.auth import _normalize_portal_username  # type: ignore  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()

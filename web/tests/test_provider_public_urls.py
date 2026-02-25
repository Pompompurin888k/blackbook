from __future__ import annotations

import sys
import unittest
from pathlib import Path


WEB_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = WEB_DIR.parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.providers import _build_public_profile_url  # noqa: E402
from utils.providers import _build_short_profile_url  # noqa: E402


class TestProviderPublicUrls(unittest.TestCase):
    def test_builds_seo_url_from_profile_fields(self):
        url = _build_public_profile_url(
            {
                "id": 55,
                "display_name": "Wizo Weez",
                "city": "Nairobi",
                "neighborhood": "Westlands",
            }
        )
        self.assertEqual(url, "/nairobi/westlands/escorts/55/wizo-weez")

    def test_falls_back_when_fields_missing(self):
        url = _build_public_profile_url({"id": 12, "display_name": "", "city": "", "neighborhood": ""})
        self.assertEqual(url, "/nairobi/nairobi/escorts/12/provider-12")

    def test_uses_first_neighborhood_when_multiple_are_stored(self):
        url = _build_public_profile_url(
            {
                "id": 21,
                "display_name": "Nia",
                "city": "Nairobi",
                "neighborhood": "Westlands, Kilimani, Kileleshwa",
            }
        )
        self.assertEqual(url, "/nairobi/westlands/escorts/21/nia")

    def test_builds_short_profile_url(self):
        self.assertEqual(_build_short_profile_url({"id": 55}), "/p/55")


if __name__ == "__main__":
    unittest.main()

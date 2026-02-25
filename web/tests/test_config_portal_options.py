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

from config import PORTAL_CITY_COUNTY_OPTIONS  # noqa: E402


class TestPortalCityCountyOptions(unittest.TestCase):
    def test_contains_all_47_kenya_counties(self) -> None:
        self.assertEqual(len(PORTAL_CITY_COUNTY_OPTIONS), 47)
        self.assertEqual(len(set(PORTAL_CITY_COUNTY_OPTIONS)), 47)
        self.assertIn("Nairobi", PORTAL_CITY_COUNTY_OPTIONS)
        self.assertIn("Mombasa", PORTAL_CITY_COUNTY_OPTIONS)
        self.assertIn("Uasin Gishu", PORTAL_CITY_COUNTY_OPTIONS)


if __name__ == "__main__":
    unittest.main()

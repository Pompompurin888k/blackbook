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

from utils.onboarding import _portal_compute_profile_strength  # noqa: E402
from utils.onboarding import _canonical_city_name  # noqa: E402
from utils.onboarding import _canonical_neighborhood_name  # noqa: E402
from utils.onboarding import _canonical_neighborhood_names  # noqa: E402
from utils.onboarding import _portal_onboarding_base_draft  # noqa: E402


class TestOnboardingUtils(unittest.TestCase):
    def test_canonical_city_name_matches_case_insensitive(self) -> None:
        city = _canonical_city_name("nairobi", ["Nairobi", "Uasin Gishu"])
        self.assertEqual(city, "Nairobi")

    def test_canonical_city_name_keeps_unknown_city(self) -> None:
        city = _canonical_city_name("Naivasha", ["Nairobi", "Uasin Gishu"])
        self.assertEqual(city, "Naivasha")

    def test_canonical_city_name_handles_empty(self) -> None:
        city = _canonical_city_name("", ["Nairobi", "Uasin Gishu"])
        self.assertEqual(city, "")

    def test_canonical_neighborhood_name_matches_city_specific_case_insensitive(self) -> None:
        neighborhood = _canonical_neighborhood_name(
            "westlands",
            "nairobi",
            {
                "Nairobi": ["Westlands", "Kilimani"],
                "Mombasa": ["Nyali"],
            },
        )
        self.assertEqual(neighborhood, "Westlands")

    def test_canonical_neighborhood_name_matches_global_when_city_missing(self) -> None:
        neighborhood = _canonical_neighborhood_name(
            "nyali",
            "Kiambu",
            {
                "Nairobi": ["Westlands", "Kilimani"],
                "Mombasa": ["Nyali"],
            },
        )
        self.assertEqual(neighborhood, "Nyali")

    def test_canonical_neighborhood_name_keeps_unknown_value(self) -> None:
        neighborhood = _canonical_neighborhood_name(
            "Roysambu Annex",
            "Nairobi",
            {
                "Nairobi": ["Westlands", "Kilimani"],
            },
        )
        self.assertEqual(neighborhood, "Roysambu Annex")

    def test_canonical_neighborhood_names_normalizes_list_and_deduplicates(self) -> None:
        neighborhoods = _canonical_neighborhood_names(
            "westlands, nyali, WESTLANDS, Roysambu Annex",
            "Nairobi",
            {
                "Nairobi": ["Westlands", "Kilimani"],
                "Mombasa": ["Nyali"],
            },
        )
        self.assertEqual(neighborhoods, "Westlands, Nyali, Roysambu Annex")

    def test_base_draft_includes_phone(self) -> None:
        draft = _portal_onboarding_base_draft({"display_name": "Sara", "phone": "254712345678"})
        self.assertEqual(draft["phone"], "254712345678")

    def test_profile_strength_flags_missing_phone(self) -> None:
        draft = {
            "display_name": "Sara",
            "phone": "",
            "city": "Nairobi",
            "neighborhood": "Westlands",
            "age": "24",
            "height_cm": "170",
            "weight_kg": "56",
            "build": "Athletic",
            "bio": "A" * 100,
            "nearby_places": "Sarit",
            "availability_type": "Incall and outcall",
            "services_text": "Dinner date, Massage, Travel companion",
            "languages_text": "English, Swahili",
            "rate_30min": "5000",
            "rate_1hr": "10000",
            "rate_2hr": "18000",
            "rate_3hr": "",
            "rate_overnight": "",
        }
        strength = _portal_compute_profile_strength(draft=draft, photo_count=5)
        self.assertIn("Add your contact phone for Call button", strength["missing"])

    def test_profile_strength_passes_phone_check_when_present(self) -> None:
        draft = {
            "display_name": "Sara",
            "phone": "254712345678",
            "city": "Nairobi",
            "neighborhood": "Westlands",
            "age": "24",
            "height_cm": "170",
            "weight_kg": "56",
            "build": "Athletic",
            "bio": "A" * 100,
            "nearby_places": "Sarit",
            "availability_type": "Incall and outcall",
            "services_text": "Dinner date, Massage, Travel companion",
            "languages_text": "English, Swahili",
            "rate_30min": "5000",
            "rate_1hr": "10000",
            "rate_2hr": "18000",
            "rate_3hr": "",
            "rate_overnight": "",
        }
        strength = _portal_compute_profile_strength(draft=draft, photo_count=5)
        self.assertNotIn("Add your contact phone for Call button", strength["missing"])


if __name__ == "__main__":
    unittest.main()

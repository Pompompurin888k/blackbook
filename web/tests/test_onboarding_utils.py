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
from utils.onboarding import _portal_onboarding_base_draft  # noqa: E402


class TestOnboardingUtils(unittest.TestCase):
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

from __future__ import annotations

import sys
import unittest
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from payment_queue_utils import build_payment_callback_job_id, extract_callback_reference  # noqa: E402


class PaymentQueueUtilsTests(unittest.TestCase):
    def test_extract_callback_reference_prefers_mpesa_receipt(self) -> None:
        payload = {
            "MpesaReceiptNumber": "REF123",
            "TransactionId": "TXN456",
            "reference": "FALLBACK",
        }
        self.assertEqual(extract_callback_reference(payload), "REF123")

    def test_extract_callback_reference_uses_fallback_fields(self) -> None:
        payload = {"TransactionId": "TXN456"}
        self.assertEqual(extract_callback_reference(payload), "TXN456")

    def test_extract_callback_reference_returns_none_for_missing_or_blank(self) -> None:
        self.assertIsNone(extract_callback_reference({}))
        self.assertIsNone(extract_callback_reference({"reference": "   "}))

    def test_build_payment_callback_job_id(self) -> None:
        self.assertEqual(build_payment_callback_job_id("ABC123"), "paycb:ABC123")
        self.assertIsNone(build_payment_callback_job_id(""))


if __name__ == "__main__":
    unittest.main()

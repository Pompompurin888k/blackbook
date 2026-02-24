from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


WEB_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = WEB_DIR.parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.security import _captcha_template_context  # noqa: E402
from utils.security import _verify_portal_captcha  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return dict(self._payload)


class _FakeAsyncClient:
    def __init__(self, payload: dict):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *_args, **_kwargs):
        return _FakeResponse(self._payload)


class TestSecurityUtils(unittest.IsolatedAsyncioTestCase):
    async def test_captcha_disabled_returns_true(self) -> None:
        with patch("utils.security.PORTAL_CAPTCHA_ENABLED", False):
            result = await _verify_portal_captcha("", "127.0.0.1")
        self.assertTrue(result)

    async def test_captcha_enabled_missing_token_returns_false(self) -> None:
        with patch("utils.security.PORTAL_CAPTCHA_ENABLED", True), patch(
            "utils.security.PORTAL_TURNSTILE_SECRET_KEY", "secret"
        ):
            result = await _verify_portal_captcha("", "127.0.0.1")
        self.assertFalse(result)

    async def test_captcha_enabled_success_response_returns_true(self) -> None:
        with patch("utils.security.PORTAL_CAPTCHA_ENABLED", True), patch(
            "utils.security.PORTAL_TURNSTILE_SECRET_KEY", "secret"
        ), patch(
            "utils.security.httpx.AsyncClient",
            return_value=_FakeAsyncClient({"success": True}),
        ):
            result = await _verify_portal_captcha("token", "127.0.0.1")
        self.assertTrue(result)

    def test_template_context_has_expected_keys(self) -> None:
        context = _captcha_template_context()
        self.assertIn("captcha_enabled", context)
        self.assertIn("turnstile_site_key", context)


if __name__ == "__main__":
    unittest.main()

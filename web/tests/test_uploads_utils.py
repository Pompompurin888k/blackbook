from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


WEB_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = WEB_DIR.parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


if "psycopg2" not in sys.modules:
    psycopg2 = types.ModuleType("psycopg2")
    extras = types.ModuleType("psycopg2.extras")
    extensions = types.ModuleType("psycopg2.extensions")
    extras.RealDictCursor = object

    class _Json:
        def __init__(self, adapted):
            self.adapted = adapted

    extras.Json = _Json
    extensions.TRANSACTION_STATUS_INERROR = 3
    extensions.TRANSACTION_STATUS_UNKNOWN = 0
    psycopg2.extras = extras
    psycopg2.extensions = extensions
    sys.modules["psycopg2"] = psycopg2
    sys.modules["psycopg2.extras"] = extras
    sys.modules["psycopg2.extensions"] = extensions


class _FakeUpload:
    def __init__(self, filename: str, content: bytes, content_type: str = "image/jpeg"):
        self.filename = filename
        self._content = content
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._content


class UploadUtilsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._original_cwd = os.getcwd()
        os.chdir(str(WEB_DIR))

    def tearDown(self) -> None:
        os.chdir(self._original_cwd)

    async def test_save_provider_upload_returns_none_for_empty_filename(self) -> None:
        from utils.uploads import _save_provider_upload

        upload = _FakeUpload(filename="", content=b"img")
        result = await _save_provider_upload(provider_id=1, upload=upload, prefix="profile")
        self.assertIsNone(result)

    async def test_save_provider_upload_uses_fallback_extension_for_unknown_types(self) -> None:
        from utils.uploads import _save_provider_upload

        upload = _FakeUpload(filename="avatar.weird", content=b"img-bytes", content_type="image/weird")
        with patch("utils.uploads.upload_provider_photo", return_value="https://cdn.example.com/p.jpg") as mocked:
            result = await _save_provider_upload(provider_id=3, upload=upload, prefix="profile")

        self.assertEqual(result, "https://cdn.example.com/p.jpg")
        self.assertTrue(mocked.called)
        self.assertEqual(mocked.call_args.kwargs["extension"], ".jpg")

    async def test_save_provider_upload_rejects_oversized_payload(self) -> None:
        from config import PORTAL_MAX_UPLOAD_BYTES
        from utils.uploads import _save_provider_upload

        upload = _FakeUpload(filename="avatar.jpg", content=b"a" * (PORTAL_MAX_UPLOAD_BYTES + 1))
        with patch("utils.uploads.upload_provider_photo", return_value="https://cdn.example.com/p.jpg") as mocked:
            result = await _save_provider_upload(provider_id=7, upload=upload, prefix="profile")

        self.assertIsNone(result)
        self.assertFalse(mocked.called)


if __name__ == "__main__":
    unittest.main()

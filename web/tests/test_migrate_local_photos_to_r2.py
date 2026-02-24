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

from scripts.migrate_local_photos_to_r2 import (  # noqa: E402
    _local_ref_to_disk_path,
    _normalize_local_upload_url,
)


class TestNormalizeLocalUploadUrl(unittest.TestCase):
    def test_accepts_relative_static_path(self):
        self.assertEqual(
            _normalize_local_upload_url("static/uploads/providers/59/a.jpg"),
            "/static/uploads/providers/59/a.jpg",
        )

    def test_accepts_absolute_static_path(self):
        self.assertEqual(
            _normalize_local_upload_url("/static/uploads/providers/59/a.jpg"),
            "/static/uploads/providers/59/a.jpg",
        )

    def test_converts_uploads_prefix(self):
        self.assertEqual(
            _normalize_local_upload_url("/uploads/providers/59/a.jpg"),
            "/static/uploads/providers/59/a.jpg",
        )

    def test_extracts_static_path_from_absolute_url(self):
        self.assertEqual(
            _normalize_local_upload_url("https://innbucks.org/static/uploads/providers/59/a.jpg"),
            "/static/uploads/providers/59/a.jpg",
        )

    def test_rejects_non_local_url(self):
        self.assertIsNone(_normalize_local_upload_url("https://cdn.example.com/r2/providers/59/a.jpg"))

    def test_rejects_telegram_file_id(self):
        self.assertIsNone(_normalize_local_upload_url("AgACAgIAAxkBAAIBAm"))


class TestLocalRefToDiskPath(unittest.TestCase):
    def test_maps_to_static_folder(self):
        path = _local_ref_to_disk_path("/static/uploads/providers/59/photo.jpg")
        self.assertIsNotNone(path)
        self.assertTrue(path.as_posix().endswith("static/uploads/providers/59/photo.jpg"))

    def test_blocks_path_traversal(self):
        self.assertIsNone(_local_ref_to_disk_path("/static/uploads/providers/59/../../secret.txt"))


if __name__ == "__main__":
    unittest.main()

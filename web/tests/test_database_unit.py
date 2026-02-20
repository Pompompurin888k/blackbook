from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from typing import Any


if "psycopg2" not in sys.modules:
    psycopg2 = types.ModuleType("psycopg2")

    class Psycopg2Error(Exception):
        pass

    class OperationalError(Psycopg2Error):
        pass

    extras = types.ModuleType("psycopg2.extras")

    class Json:
        def __init__(self, adapted: Any):
            self.adapted = adapted

    extras.Json = Json
    extras.RealDictCursor = object
    psycopg2.Error = Psycopg2Error
    psycopg2.OperationalError = OperationalError
    psycopg2.extras = extras
    sys.modules["psycopg2"] = psycopg2
    sys.modules["psycopg2.extras"] = extras


WEB_DIR = Path(__file__).resolve().parents[1]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from database import Database, Json  # type: ignore  # noqa: E402


class FakeCursor:
    def __init__(self, rowcount: int = 1, fetchone_result: dict[str, Any] | None = None) -> None:
        self.rowcount = rowcount
        self.fetchone_result = fetchone_result
        self.executions: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> None:
        self.executions.append((query, params))

    def fetchone(self) -> dict[str, Any] | None:
        return self.fetchone_result

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.commit_calls = 0
        self.rollback_calls = 0

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def build_db(cursor: FakeCursor) -> Database:
    db = Database.__new__(Database)
    db.conn = FakeConnection(cursor)
    db._ensure_connection = lambda: None
    return db


class DatabaseUnitTests(unittest.TestCase):
    def test_update_portal_provider_profile_filters_fields_and_wraps_json_lists(self) -> None:
        cursor = FakeCursor(rowcount=1)
        db = build_db(cursor)

        result = db.update_portal_provider_profile(
            provider_id=12,
            data={
                "display_name": "Nia",
                "services": ["Massage", "Dinner"],
                "profile_photos": ["abc", "def"],
                "not_allowed": "drop me",
            },
        )

        self.assertTrue(result)
        self.assertEqual(db.conn.commit_calls, 1)
        self.assertEqual(len(cursor.executions), 1)
        query, params = cursor.executions[0]
        self.assertIn("display_name = %s", query)
        self.assertIn("services = %s", query)
        self.assertIn("profile_photos = %s", query)
        self.assertNotIn("not_allowed", query)
        self.assertIsNotNone(params)
        assert params is not None
        self.assertEqual(params[-1], 12)
        self.assertIsInstance(params[1], Json)
        self.assertIsInstance(params[2], Json)

    def test_update_portal_provider_profile_returns_false_for_empty_sanitized_payload(self) -> None:
        cursor = FakeCursor(rowcount=1)
        db = build_db(cursor)

        result = db.update_portal_provider_profile(provider_id=12, data={"unknown_field": "x"})

        self.assertFalse(result)
        self.assertEqual(db.conn.commit_calls, 0)
        self.assertEqual(cursor.executions, [])

    def test_set_portal_phone_verification_code_clamps_ttl_and_mark_pending_flag(self) -> None:
        cursor = FakeCursor(rowcount=1)
        db = build_db(cursor)

        result = db.set_portal_phone_verification_code(
            provider_id=7,
            code="BB-ABC12345",
            code_hash="hash",
            ttl_minutes=0,
            mark_pending=False,
        )

        self.assertTrue(result)
        self.assertEqual(db.conn.commit_calls, 1)
        query, params = cursor.executions[0]
        self.assertIn("verification_code_expires_at = NOW() + (%s || ' minutes')::INTERVAL", query)
        self.assertEqual(params, ("BB-ABC12345", "hash", "1", False, 7))

    def test_log_provider_verification_event_normalizes_event_type(self) -> None:
        cursor = FakeCursor(rowcount=1)
        db = build_db(cursor)

        result = db.log_provider_verification_event(
            provider_id=2,
            event_type="  APPROVED  ",
            payload={"reason": "ok"},
            admin_telegram_id=99,
        )

        self.assertTrue(result)
        query, params = cursor.executions[0]
        self.assertIn("INSERT INTO provider_verification_events", query)
        self.assertIsNotNone(params)
        assert params is not None
        self.assertEqual(params[0], 2)
        self.assertEqual(params[1], "approved")
        self.assertIsInstance(params[2], Json)
        self.assertEqual(params[3], 99)

    def test_log_provider_verification_event_rejects_blank_event_type(self) -> None:
        cursor = FakeCursor(rowcount=1)
        db = build_db(cursor)

        result = db.log_provider_verification_event(provider_id=2, event_type="   ")

        self.assertFalse(result)
        self.assertEqual(cursor.executions, [])
        self.assertEqual(db.conn.commit_calls, 0)

    def test_count_provider_verification_events_normalizes_event_type_and_clamps_hours(self) -> None:
        cursor = FakeCursor(fetchone_result={"count": 3})
        db = build_db(cursor)

        result = db.count_provider_verification_events(provider_id=4, event_type="  RejectED ", hours=0)

        self.assertEqual(result, 3)
        query, params = cursor.executions[0]
        self.assertIn("SELECT COUNT(*) AS count", query)
        self.assertEqual(params, (4, "rejected", "1"))

    def test_count_provider_verification_events_rejects_blank_event_type(self) -> None:
        cursor = FakeCursor(fetchone_result={"count": 99})
        db = build_db(cursor)

        result = db.count_provider_verification_events(provider_id=4, event_type="")

        self.assertEqual(result, 0)
        self.assertEqual(cursor.executions, [])


if __name__ == "__main__":
    unittest.main()

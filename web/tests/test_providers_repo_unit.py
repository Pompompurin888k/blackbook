from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from typing import Any


if "psycopg2" not in sys.modules:
    psycopg2 = types.ModuleType("psycopg2")
    extras = types.ModuleType("psycopg2.extras")
    extensions = types.ModuleType("psycopg2.extensions")
    extras.RealDictCursor = object
    extras.Json = object
    extensions.TRANSACTION_STATUS_INERROR = 3
    extensions.TRANSACTION_STATUS_UNKNOWN = 0
    psycopg2.extras = extras
    psycopg2.extensions = extensions
    sys.modules["psycopg2"] = psycopg2
    sys.modules["psycopg2.extras"] = extras
    sys.modules["psycopg2.extensions"] = extensions


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.database.providers import ProvidersRepository  # noqa: E402


class FakeCursor:
    def __init__(self, fetchone_result: dict[str, Any] | None = None) -> None:
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

    def cursor(self) -> FakeCursor:
        return self._cursor


class FakeManager:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    def ensure_connection(self) -> None:
        return None


class ProvidersRepositoryUnitTests(unittest.TestCase):
    def test_get_provider_by_id_uses_created_at_alias_for_updated_at(self) -> None:
        cursor = FakeCursor(fetchone_result={"id": 32})
        repo = ProvidersRepository(FakeManager(FakeConnection(cursor)))

        row = repo.get_provider_by_id(32)

        self.assertEqual(row, {"id": 32})
        self.assertEqual(len(cursor.executions), 1)
        query, params = cursor.executions[0]
        self.assertIn("created_at AS updated_at", query)
        self.assertEqual(params, (32,))


if __name__ == "__main__":
    unittest.main()

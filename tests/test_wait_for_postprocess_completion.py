import logging
from typing import Any

import pytest

from app_utils import azure_sql


def test_wait_for_postprocess_completion(monkeypatch, caplog):
    calls: list[tuple[str, tuple[Any, ...]]] = []

    class DummyCursor:
        def __init__(self) -> None:
            self._select_count = 0

        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if "SELECT" in self._last_sql:
                self._select_count += 1
                if self._select_count == 1:
                    return (None,)
                return ("2024-01-01",)
            return None

    class DummyConn:
        def __enter__(self) -> "DummyConn":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def commit(self) -> None:
            calls.append(("commit", ()))

    monkeypatch.setattr(azure_sql, "_connect", lambda: DummyConn())
    monkeypatch.setattr(azure_sql.time, "sleep", lambda s: calls.append(("sleep", (s,))))

    caplog.set_level(logging.INFO, logger="app_utils.azure_sql")
    azure_sql.wait_for_postprocess_completion("pg", "OP", poll_interval=1)

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    assert len(selects) == 2
    assert len(execs) == 1
    assert len(sleeps) == 1
    assert any("RFP_OBJECT_DATA_POST_PROCESS" in m for m in caplog.messages)


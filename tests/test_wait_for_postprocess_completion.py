"""Tests for :func:`app_utils.azure_sql.wait_for_postprocess_completion`."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app_utils import azure_sql


def test_wait_for_postprocess_completion_missing_lane_data(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Aborts when ``LANES_MISSING_DATA`` has rows for the client SCAC."""

    calls: list[tuple[str, tuple[Any, ...]]] = []

    class DummyCursor:
        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if "LANES_MISSING_DATA" in self._last_sql:
                return (1,)
            if "SELECT" in self._last_sql:
                return (None, None)
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
    process_guid = "pg"
    operation_cd = "ADSJ_VAN"
    with pytest.raises(RuntimeError, match="Missing lane data"):
        azure_sql.wait_for_postprocess_completion(process_guid, operation_cd, poll_interval=1)

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    commits = [c for c in calls if c[0] == "commit"]
    assert len(selects) == 1
    assert not execs
    assert not commits
    assert any("Missing lane data" in m for m in caplog.messages)


def test_wait_for_postprocess_completion_reexec(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Re-executes postprocess when still running."""

    calls: list[tuple[str, tuple[Any, ...]]] = []

    class DummyCursor:
        def __init__(self) -> None:
            self._select_count = 0

        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if "LANES_MISSING_DATA" in self._last_sql:
                return None
            if "SELECT" in self._last_sql:
                self._select_count += 1
                if self._select_count == 1:
                    return ("2024-01-01", None)
                return ("2024-01-01", "2024-01-02")
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
    process_guid = "pg"
    operation_cd = "OP"
    azure_sql.wait_for_postprocess_completion(process_guid, operation_cd, poll_interval=1)

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    assert len(selects) == 3
    assert len(execs) == 2
    assert len(sleeps) == 2
    assert all(params == (process_guid, operation_cd) for _, params in execs)
    assert any("still running" in m for m in caplog.messages)


def test_wait_for_postprocess_completion_missing_begin(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Raises when the postprocess never begins."""

    calls: list[tuple[str, tuple[Any, ...]]] = []

    class DummyCursor:
        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if "LANES_MISSING_DATA" in self._last_sql:
                return None
            if "SELECT" in self._last_sql:
                return (None, None)
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
    process_guid = "pg"
    operation_cd = "OP"
    with pytest.raises(RuntimeError, match="did not begin"):
        azure_sql.wait_for_postprocess_completion(process_guid, operation_cd, poll_interval=1)

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    assert len(selects) == 2
    assert len(execs) == 1
    assert len(sleeps) == 1
    assert execs[0][1] == (process_guid, operation_cd)
    assert any("did not begin" in m for m in caplog.messages)


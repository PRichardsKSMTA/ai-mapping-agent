"""Tests for :func:`app_utils.azure_sql.wait_for_postprocess_completion`."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app_utils import azure_sql


def test_wait_for_postprocess_completion_reexec(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Re-executes postprocess only after 5 minutes of polling."""

    calls: list[tuple[str, tuple[Any, ...]]] = []

    class DummyCursor:
        def __init__(self) -> None:
            self._select_count = 0

        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if self._last_sql.startswith("SELECT"):
                self._select_count += 1
                if self._select_count < 12:
                    return (None,)
                return ("2024-01-02",)
            return None

    class DummyConn:
        def __init__(self) -> None:
            self.commit_count = 0

        def __enter__(self) -> "DummyConn":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def commit(self) -> None:
            self.commit_count += 1
            calls.append(("commit", ()))

    conn = DummyConn()
    monkeypatch.setattr(azure_sql, "_connect", lambda: conn)
    monkeypatch.setattr(azure_sql.time, "sleep", lambda s: calls.append(("sleep", (s,))))

    caplog.set_level(logging.INFO, logger="app_utils.azure_sql")
    azure_sql.wait_for_postprocess_completion("pg", "OP", max_attempts=2)

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    commits = [c for c in calls if c[0] == "commit"]
    assert len(selects) == 12
    assert len(execs) == 2
    assert len(sleeps) == 12
    assert len(commits) == len(selects) + len(execs)
    exec_indices = [i for i, c in enumerate(calls) if c[0].startswith("EXEC")]
    commit_before_retry = (
        sum(1 for c in calls[:exec_indices[1]] if c[0] == "commit") - 1
    )
    assert commit_before_retry == 10
    assert any("Post-process complete" in m for m in caplog.messages)


def test_wait_for_postprocess_completion_max_attempts(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Stops after max attempts when postprocess never completes."""

    calls: list[tuple[str, tuple[Any, ...]]] = []

    class DummyCursor:
        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if self._last_sql.startswith("SELECT"):
                return (None,)
            return None

    class DummyConn:
        def __init__(self) -> None:
            self.commit_count = 0

        def __enter__(self) -> "DummyConn":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def commit(self) -> None:
            self.commit_count += 1
            calls.append(("commit", ()))

    conn = DummyConn()
    monkeypatch.setattr(azure_sql, "_connect", lambda: conn)
    monkeypatch.setattr(azure_sql.time, "sleep", lambda s: calls.append(("sleep", (s,))))

    caplog.set_level(logging.INFO, logger="app_utils.azure_sql")
    azure_sql.wait_for_postprocess_completion("pg", "OP", max_attempts=2)

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    commits = [c for c in calls if c[0] == "commit"]
    assert len(selects) == 20
    assert len(execs) == 2
    assert len(sleeps) == 20
    assert len(commits) == len(selects) + len(execs)
    assert any("did not complete" in m for m in caplog.messages)


def test_wait_for_postprocess_completion_exits_early(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Stops polling once completion timestamp appears."""

    calls: list[tuple[str, tuple[Any, ...]]] = []

    class DummyCursor:
        def __init__(self) -> None:
            self._select_count = 0

        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if self._last_sql.startswith("SELECT"):
                self._select_count += 1
                if self._select_count == 3:
                    return ("2024-01-02",)
                return (None,)
            return None

    class DummyConn:
        def __init__(self) -> None:
            self.commit_count = 0

        def __enter__(self) -> "DummyConn":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def commit(self) -> None:
            self.commit_count += 1
            calls.append(("commit", ()))

    conn = DummyConn()
    monkeypatch.setattr(azure_sql, "_connect", lambda: conn)
    monkeypatch.setattr(azure_sql.time, "sleep", lambda s: calls.append(("sleep", (s,))))

    caplog.set_level(logging.INFO, logger="app_utils.azure_sql")
    azure_sql.wait_for_postprocess_completion("pg", "OP", max_attempts=2)

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    commits = [c for c in calls if c[0] == "commit"]
    assert len(selects) == 3
    assert len(execs) == 1
    assert len(sleeps) == 3
    assert len(commits) == len(selects) + len(execs)
    assert any("Post-process complete" in m for m in caplog.messages)


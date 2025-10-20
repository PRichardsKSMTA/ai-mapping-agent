"""Tests for :func:`app_utils.azure_sql.wait_for_postprocess_completion`."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app_utils import azure_sql
from app_utils.azure_sql import PostprocessTimeoutError


def test_wait_for_postprocess_completion_reruns_on_flag(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Triggers a rerun as soon as the rerun flag is observed."""

    calls: list[tuple[str, tuple[Any, ...]]] = []
    select_responses = [
        (None, 0),
        (None, 1),
        ("2024-01-02", 0),
    ]

    class DummyCursor:
        def __init__(self) -> None:
            self._select_count = 0

        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if self._last_sql.startswith("SELECT"):
                response = select_responses[self._select_count]
                self._select_count += 1
                return response
            return None

    class DummyConn:
        def commit(self) -> None:
            calls.append(("commit", ()))

        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def __enter__(self) -> "DummyConn":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    conn = DummyConn()
    monkeypatch.setattr(azure_sql, "_connect", lambda: conn)
    monkeypatch.setattr(azure_sql.time, "sleep", lambda s: calls.append(("sleep", (s,))))

    caplog.set_level(logging.INFO, logger="app_utils.azure_sql")
    azure_sql.wait_for_postprocess_completion(
        "pg", "OP", poll_interval=90, max_attempts=1
    )

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    commits = [c for c in calls if c[0] == "commit"]
    assert len(selects) == 3
    assert len(execs) == 1
    assert len(sleeps) == 3
    assert len(commits) == len(selects) + len(execs)
    for idx, (sql, _) in enumerate(calls):
        if sql.startswith("SELECT") or sql.startswith("EXEC"):
            assert calls[idx + 1][0] == "commit"
    assert any("Rerun flag detected" in m for m in caplog.messages)
    assert any("Post-process complete" in m for m in caplog.messages)


def test_wait_for_postprocess_completion_skips_rerun_when_flag_false(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Avoids rerunning the stored procedure when the rerun bit stays false."""

    calls: list[tuple[str, tuple[Any, ...]]] = []
    select_responses = [
        (None, 0),
        (None, 0),
        ("2024-01-02", 0),
    ]

    class DummyCursor:
        def __init__(self) -> None:
            self._select_count = 0

        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if self._last_sql.startswith("SELECT"):
                response = select_responses[self._select_count]
                self._select_count += 1
                return response
            return None

    class DummyConn:
        def commit(self) -> None:
            calls.append(("commit", ()))

        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def __enter__(self) -> "DummyConn":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    conn = DummyConn()
    monkeypatch.setattr(azure_sql, "_connect", lambda: conn)
    monkeypatch.setattr(azure_sql.time, "sleep", lambda s: calls.append(("sleep", (s,))))

    caplog.set_level(logging.INFO, logger="app_utils.azure_sql")
    azure_sql.wait_for_postprocess_completion(
        "pg", "OP", poll_interval=90, max_attempts=1
    )

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    commits = [c for c in calls if c[0] == "commit"]
    assert len(selects) == 3
    assert execs == []
    assert len(sleeps) == 3
    assert len(commits) == len(selects)
    for idx, (sql, _) in enumerate(calls):
        if sql.startswith("SELECT"):
            assert calls[idx + 1][0] == "commit"
    assert all("Rerun flag detected" not in m for m in caplog.messages)
    assert any("Post-process complete" in m for m in caplog.messages)


def test_wait_for_postprocess_completion_timeout(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Raises a timeout after the full polling budget elapses."""

    calls: list[tuple[str, tuple[Any, ...]]] = []

    class DummyCursor:
        def execute(self, sql: str, *params: Any) -> None:
            calls.append((sql, params))
            self._last_sql = sql

        def fetchone(self) -> tuple[Any, ...] | None:
            if self._last_sql.startswith("SELECT"):
                return (None, 0)
            return None

    class DummyConn:
        def commit(self) -> None:
            calls.append(("commit", ()))

        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def __enter__(self) -> "DummyConn":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    conn = DummyConn()
    monkeypatch.setattr(azure_sql, "_connect", lambda: conn)
    monkeypatch.setattr(azure_sql.time, "sleep", lambda s: calls.append(("sleep", (s,))))

    caplog.set_level(logging.INFO, logger="app_utils.azure_sql")
    with pytest.raises(PostprocessTimeoutError) as exc:
        azure_sql.wait_for_postprocess_completion(
            "pg", "OP", poll_interval=60, max_attempts=1
        )

    selects = [c for c in calls if c[0].startswith("SELECT")]
    execs = [c for c in calls if c[0].startswith("EXEC")]
    sleeps = [c for c in calls if c[0] == "sleep"]
    commits = [c for c in calls if c[0] == "commit"]
    assert len(selects) == 5
    assert execs == []
    assert len(sleeps) == 5
    assert len(commits) == len(selects)
    for idx, (sql, _) in enumerate(calls):
        if sql.startswith("SELECT"):
            assert calls[idx + 1][0] == "commit"
    assert any("did not complete" in m for m in caplog.messages)
    assert "did not complete" in str(exc.value)


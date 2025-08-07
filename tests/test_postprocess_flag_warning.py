from __future__ import annotations

import streamlit as st

from app import warn_if_postprocess_missing


def test_warn_if_postprocess_missing(monkeypatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(st, "info", lambda msg: messages.append(msg))
    monkeypatch.setenv("ENABLE_POSTPROCESS", "0")
    warn_if_postprocess_missing()
    assert messages and "ENABLE_POSTPROCESS=1" in messages[0]

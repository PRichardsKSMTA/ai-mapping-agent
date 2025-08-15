import importlib
import sys
import types

import pytest
import streamlit as st


def _import_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AAD_CLIENT_ID", "cid")
    monkeypatch.setenv("AAD_CLIENT_SECRET", "sec")
    monkeypatch.setenv("AAD_TENANT_ID", "tid")
    monkeypatch.setenv("AAD_REDIRECT_URI", "http://localhost")
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    st.session_state.clear()
    sys.modules.pop("auth", None)
    return importlib.import_module("auth")


def test_render_login_button_no_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = _import_auth(monkeypatch)
    captured: dict[str, str] = {}

    def fake_markdown(html: str, *a, **k) -> None:
        captured["markdown"] = html

    class DummyV1:
        def html(self, html: str, *a, **k) -> None:  # pragma: no cover - simple stub
            captured["component"] = html

    monkeypatch.setattr(st, "markdown", fake_markdown)
    monkeypatch.setattr(st, "components", types.SimpleNamespace(v1=DummyV1()))

    auth.render_login_button("http://login")
    assert "target=\"_blank\"" not in captured["markdown"]
    assert "target=\"_blank\"" not in captured["component"]


def test_ensure_user_invokes_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = _import_auth(monkeypatch)
    called: dict[str, str | None] = {"url": None}

    monkeypatch.setattr(auth, "_complete_flow", lambda: None)
    monkeypatch.setattr(auth, "_initiate_flow", lambda: "http://login")

    def fake_render(url: str) -> None:
        called["url"] = url

    monkeypatch.setattr(auth, "render_login_button", fake_render)

    def stop() -> None:
        raise RuntimeError("stopped")

    monkeypatch.setattr(st, "stop", stop)

    with pytest.raises(RuntimeError):
        auth._ensure_user()
    assert called["url"] == "http://login"

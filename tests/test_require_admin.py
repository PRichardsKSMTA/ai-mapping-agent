import importlib
import sys
import types
import pytest


class StopCalled(Exception):
    pass


def setup_auth(monkeypatch: pytest.MonkeyPatch):
    def stop() -> None:
        raise StopCalled()

    dummy_st = types.SimpleNamespace(
        session_state={},
        secrets={},
        error=lambda *a, **k: None,
        stop=stop,
    )
    monkeypatch.setitem(sys.modules, "streamlit", dummy_st)
    monkeypatch.setitem(
        sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None)
    )
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    monkeypatch.setenv("AAD_CLIENT_ID", "x")
    monkeypatch.setenv("AAD_TENANT_ID", "x")
    monkeypatch.setenv("AAD_REDIRECT_URI", "http://localhost")
    sys.modules.pop("auth", None)
    auth = importlib.import_module("auth")
    monkeypatch.setattr(auth, "_ensure_user", lambda: None)
    return auth, dummy_st


def test_require_admin(monkeypatch: pytest.MonkeyPatch):
    auth, st = setup_auth(monkeypatch)

    @auth.require_admin
    def protected() -> str:
        return "ok"

    st.session_state["is_admin"] = False
    with pytest.raises(StopCalled):
        protected()

    st.session_state["is_admin"] = True
    assert protected() == "ok"
    sys.modules.pop("auth", None)

import importlib
import sys
import types
import pytest


class DummySidebar:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, dict[str, object]]] = []

    def __enter__(self) -> "DummySidebar":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def button(self, label: str, **kwargs: object) -> bool:
        self.calls.append(("button", label, kwargs))
        return True


def test_logout_clears_center_css_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    sidebar = DummySidebar()
    components_v1 = types.ModuleType("streamlit.components.v1")
    components_v1.html = lambda *a, **k: None
    components = types.ModuleType("streamlit.components")
    components.v1 = components_v1
    st = types.ModuleType("streamlit")
    st.sidebar = sidebar
    st.session_state = {"user_email": "x", "id_token": "tok", "_center_css_done": True}
    st.secrets = {}
    st.query_params = types.SimpleNamespace(clear=lambda: None)
    st.button = lambda label, **k: sidebar.button(label, **k)
    st.stop = lambda: None
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setitem(sys.modules, "streamlit.components", components)
    monkeypatch.setitem(sys.modules, "streamlit.components.v1", components_v1)
    monkeypatch.setitem(sys.modules, "msal", types.SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "msal_streamlit_t2",
        types.SimpleNamespace(msal_authentication=lambda **_: None),
    )
    monkeypatch.setenv("DISABLE_AUTH", "0")
    monkeypatch.setenv("AAD_CLIENT_ID", "x")
    monkeypatch.setenv("AAD_CLIENT_SECRET", "x")
    monkeypatch.setenv("AAD_TENANT_ID", "x")
    monkeypatch.setenv("AAD_REDIRECT_URI", "x")

    auth = importlib.import_module("auth")
    importlib.reload(auth)
    monkeypatch.setattr(auth, "_clear_storage_and_reload", lambda: None)

    auth.logout_button()

    assert "_center_css_done" not in st.session_state
    assert "user_email" not in st.session_state
    assert "id_token" not in st.session_state

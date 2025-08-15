import importlib
import sys
import types


class DummySidebar:
    def __init__(self):
        self.calls: list[tuple[str, str | None, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def markdown(self, text: str, **kwargs):
        self.calls.append(("markdown", text, kwargs))

    def button(self, label: str, **kwargs):
        self.calls.append(("button", label, kwargs))
        return False

def test_logout_button_adds_spacing(monkeypatch):
    sidebar = DummySidebar()
    st = types.SimpleNamespace(
        sidebar=sidebar,
        session_state={},
        secrets={},
        query_params=types.SimpleNamespace(clear=lambda: None),
        rerun=lambda: None,
        markdown=lambda text, **k: sidebar.markdown(text, **k),
        button=lambda label, **k: sidebar.button(label, **k),
    )
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setitem(sys.modules, "msal", types.SimpleNamespace())
    monkeypatch.setenv("DISABLE_AUTH", "0")
    monkeypatch.setenv("AAD_CLIENT_ID", "x")
    monkeypatch.setenv("AAD_CLIENT_SECRET", "x")
    monkeypatch.setenv("AAD_TENANT_ID", "x")
    monkeypatch.setenv("AAD_REDIRECT_URI", "x")

    auth = importlib.import_module("auth")
    importlib.reload(auth)

    auth.logout_button()

    assert sidebar.calls[0][0] == "markdown"
    assert "height" in sidebar.calls[0][1]
    assert sidebar.calls[1][0] == "button"
    assert sidebar.calls[1][1] == "Sign out"
    assert sidebar.calls[1][2].get("use_container_width") is True

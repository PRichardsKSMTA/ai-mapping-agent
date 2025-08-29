class DummySidebar:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def subheader(self, *a, **k):
        pass

    def error(self, msg, *a, **k):
        self.st.errors.append(msg)


class DummyStreamlit:
    def __init__(self):
        self.session_state = {}
        self.sidebar = DummySidebar(self)
        self.errors: list[str] = []
        self.secrets = {}

    def set_page_config(self, *a, **k):
        pass

    def title(self, *a, **k):
        pass

    def caption(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def subheader(self, *a, **k):
        pass

    def error(self, msg, *a, **k):
        self.errors.append(msg)

    def cache_data(self, *a, **k):
        def wrap(func):
            return func
        return wrap


def test_error_when_user_email_missing(monkeypatch):
    import importlib
    import sys

    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setenv("DISABLE_AUTH", "1")

    import auth
    import app_utils.azure_sql as azure_sql
    import app_utils.ui_utils as ui_utils

    monkeypatch.setattr(ui_utils, "apply_global_css", lambda: None)
    monkeypatch.setattr(auth, "require_login", lambda f: f)
    monkeypatch.setattr(auth, "logout_button", lambda: None)
    monkeypatch.setattr(auth, "get_user_email", lambda: None)
    monkeypatch.setattr(azure_sql, "_odbc_diag_log", lambda: None)

    called = {"count": 0}

    def fake_fetch_operation_codes(email):
        called["count"] += 1
        return []

    monkeypatch.setattr(azure_sql, "fetch_operation_codes", fake_fetch_operation_codes)

    sys.modules.pop("Home", None)
    import Home
    importlib.reload(Home)

    Home.main()

    assert called["count"] == 0
    assert any("sign in" in msg.lower() for msg in st.errors)


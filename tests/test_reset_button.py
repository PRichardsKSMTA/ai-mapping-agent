import importlib
import sys
import types

class DummyContainer:
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        pass
    def markdown(self, *a, **k):
        pass
    def progress(self, *a, **k):
        pass

class DummySidebar:
    def __init__(self, st):
        self.st = st
        self.reset_pressed = False
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        pass
    def subheader(self, *a, **k):
        pass
    def selectbox(self, label, options, index=0, key=None, **k):
        choice = options[index] if options else None
        if key:
            self.st.session_state[key] = choice
        return choice
    def empty(self):
        return DummyContainer()
    def write(self, *a, **k):
        pass
    def info(self, *a, **k):
        pass
    def button(self, label, on_click=None, *a, **k):
        if label == "Reset":
            if not self.reset_pressed:
                self.reset_pressed = True
                if on_click:
                    on_click()
                return True
            return False
        return False

class DummyStreamlit:
    def __init__(self):
        self.session_state = {}
        self.sidebar = DummySidebar(self)
        self.rerun_called = False
        self.secrets = {}
    def set_page_config(self, *a, **k):
        pass
    def title(self, *a, **k):
        pass
    header = subheader = success = error = write = warning = info = title
    def selectbox(self, label, options, index=0, key=None, **k):
        choice = options[index] if options else None
        if key:
            self.session_state[key] = choice
        return choice
    def file_uploader(self, label, *, key=None, **k):
        return self.session_state.get(key)
    def button(self, *a, **k):
        return False
    def spinner(self, *a, **k):
        return DummyContainer()
    def empty(self):
        return DummyContainer()
    def container(self):
        return DummyContainer()
    def rerun(self):
        self.rerun_called = True
    def markdown(self, *a, **k):
        pass
    def cache_data(self, *a, **k):
        def wrap(func):
            return func
        return wrap

def run_app(monkeypatch):
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
    monkeypatch.setattr("auth.logout_button", lambda: None)
    monkeypatch.setattr("app_utils.excel_utils.list_sheets", lambda _u: [])
    monkeypatch.setattr("app_utils.excel_utils.read_tabular_file", lambda _f, sheet_name=None: ([], []))
    monkeypatch.setattr(
        "app_utils.azure_sql.fetch_operation_codes", lambda email=None: ["DEK1_REF"]
    )
    upload_key = "uploader-key"
    st.session_state.update(
        {
            "selected_template_file": "demo.json",
            "uploaded_file": object(),
            "upload_data_file_key": upload_key,
            upload_key: object(),
            "template": {},
            "template_name": "Demo",
            "current_template": "Demo",
            "layer_confirmed_0": True,
            "export_complete": True,
            "header_mapping_0": {"A": {"src": "A"}},
        }
    )
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return st, app_mod, upload_key


def test_reset_button_triggers_rerun(monkeypatch):
    st, _app, old_key = run_app(monkeypatch)
    assert st.rerun_called is True
    assert "uploaded_file" not in st.session_state
    assert old_key not in st.session_state
    assert "export_complete" not in st.session_state
    assert "header_mapping_0" not in st.session_state


def test_uploader_cleared_after_rerun(monkeypatch):
    st, app_mod, old_key = run_app(monkeypatch)
    new_key = st.session_state["upload_data_file_key"]
    assert new_key != old_key
    app_mod.main()
    assert st.session_state["upload_data_file_key"] == new_key
    assert new_key not in st.session_state
    assert "uploaded_file" not in st.session_state

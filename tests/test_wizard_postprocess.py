import types
import importlib
import json
from pathlib import Path
import sys
import pandas as pd

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
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass
    def subheader(self, *a, **k):
        pass
    def selectbox(self, label, options, index=0, **k):
        return options[index]
    def empty(self):
        return DummyContainer()
    def write(self, *a, **k):
        pass
    def info(self, *a, **k):
        pass

class DummyStreamlit:
    def __init__(self):
        self.session_state = {}
        self.sidebar = DummySidebar()
    def set_page_config(self, *a, **k):
        pass
    def title(self, *a, **k):
        pass
    header = subheader = success = error = write = warning = info = title
    def selectbox(self, label, options, index=0, **k):
        return options[index]
    def file_uploader(self, *a, **k):
        return None
    def button(self, label, *a, **k):
        return label == "Run Postprocess"
    def spinner(self, *a, **k):
        return DummyContainer()
    def empty(self):
        return DummyContainer()
    def rerun(self):
        pass
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
    monkeypatch.setattr("app_utils.excel_utils.list_sheets", lambda _u: ["Sheet1"])
    monkeypatch.setattr(
        "app_utils.excel_utils.read_tabular_file",
        lambda _f, sheet_name=None: (pd.DataFrame({"A": [1]}), ["A"]),
    )
    called = {}
    monkeypatch.setattr(
        "app_utils.postprocess_runner.run_postprocess_if_configured",
        lambda tpl, df: called.setdefault("run", True),
    )
    tpl_path = Path("templates/pit-bid.json")
    tpl_data = json.loads(tpl_path.read_text())
    tpl_data["postprocess"] = {"type": "sql_insert"}
    orig_read = Path.read_text
    def fake_read(self, *a, **k):
        if self == tpl_path:
            return json.dumps(tpl_data)
        return orig_read(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", fake_read)
    st.session_state.update({
        "selected_template_file": tpl_path.name,
        "uploaded_file": object(),
        "template": tpl_data,
        "template_name": "PIT BID",
        "current_template": "PIT BID",
        "layer_confirmed_0": True,
    })
    sys.modules.pop("app", None)
    importlib.import_module("app")
    return called


def test_postprocess_runner_called(monkeypatch):
    called = run_app(monkeypatch)
    assert called.get("run") is True

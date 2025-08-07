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
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def subheader(self, *a, **k):
        pass

    def selectbox(self, label, options, index=0, key=None, **k):
        choice = options[index]
        if key:
            self.st.session_state[key] = choice
        return choice
    def empty(self):
        return DummyContainer()
    def write(self, *a, **k):
        pass
    def info(self, *a, **k):
        pass
    def button(self, *a, **k):
        return False

class DummyStreamlit:
    def __init__(self):
        self.session_state = {}
        self.sidebar = DummySidebar(self)
        self.json_calls: list[object] = []
        self.secrets = {}
    def set_page_config(self, *a, **k):
        pass
    def title(self, *a, **k):
        pass
    header = subheader = success = error = write = warning = info = title
    def selectbox(self, label, options, index=0, key=None, **k):
        choice = options[index]
        if key:
            self.session_state[key] = choice
        return choice
    def file_uploader(self, *a, **k):
        return None
    def button(self, label, *a, **k):
        return label == "Run Export" and not self.session_state.get("export_complete")
    def spinner(self, *a, **k):
        return DummyContainer()
    def empty(self):
        return DummyContainer()
    def rerun(self):
        pass
    def markdown(self, *a, **k):
        pass
    def download_button(self, *a, **k):
        pass
    def json(self, obj, *a, **k):  # type: ignore[override]
        self.json_calls.append(obj)
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
    monkeypatch.setattr(
        "app_utils.azure_sql.fetch_operation_codes", lambda email=None: ["ADSJ_VAN"]
    )
    monkeypatch.setattr("app_utils.azure_sql.fetch_customers", lambda scac: [])
    monkeypatch.setattr(
        "app_utils.azure_sql.insert_pit_bid_rows", lambda df, op, cust, guid: len(df)
    )
    called: dict[str, object] = {}

    def fake_runner(tpl, df, process_guid, *args):
        called["run"] = True
        called["guid"] = process_guid
        return ["ok"], {"p": 1}

    monkeypatch.setattr(
        "app_utils.postprocess_runner.run_postprocess_if_configured",
        fake_runner,
    )
    tpl_path = Path("templates/pit-bid.json")
    tpl_data = json.loads(tpl_path.read_text())
    tpl_data["postprocess"] = {"url": "https://example.com"}
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
    if st.session_state.get("export_complete"):
        importlib.reload(sys.modules["app"])
    return called, st.session_state, st


def test_postprocess_runner_called(monkeypatch):
    called, state, _st = run_app(monkeypatch)
    assert called.get("run") is True
    assert called.get("guid") is not None
    logs = state.get("export_logs")
    assert "Inserted" in logs[0]
    assert logs[1] == "ok"
    assert state.get("postprocess_payload") == {"p": 1}


def test_postprocess_payload_displayed(monkeypatch):
    _, _, st = run_app(monkeypatch)
    assert st.json_calls and st.json_calls[0] == {"p": 1}

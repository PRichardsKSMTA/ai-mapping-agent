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


class DummyColumn:
    def button(self, *a, **k):
        return False

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
        self.markdown_calls: list[str] = []
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
    def markdown(self, text, *a, **k):
        self.markdown_calls.append(text)
    def download_button(self, *a, **k):
        pass
    def json(self, *a, **k):  # type: ignore[override]
        pass
    def cache_data(self, *a, **k):
        def wrap(func):
            return func
        return wrap
    def multiselect(self, label, options, default=None, key=None, **k):
        if key and key in self.session_state:
            return self.session_state[key]
        sel = default or []
        if key:
            self.session_state[key] = sel
        return sel
    def columns(self, spec):
        n = len(spec) if isinstance(spec, (list, tuple)) else spec
        return [DummyColumn() for _ in range(n)]


def run_app(monkeypatch):
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setenv("CLIENT_DEST_SITE", "https://tenant.sharepoint.com/sites/demo")
    monkeypatch.setenv("CLIENT_DEST_FOLDER_PATH", "docs/folder")
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
    monkeypatch.setattr(
        "app_utils.azure_sql.fetch_customers",
        lambda scac: [{"BILLTO_NAME": "Cust", "BILLTO_ID": "1"}],
    )
    monkeypatch.setattr(
        "app_utils.azure_sql.insert_pit_bid_rows", lambda df, op, cust, guid, adhoc: len(df)
    )
    monkeypatch.setattr("app_utils.azure_sql.derive_adhoc_headers", lambda df: {})
    def fake_log(process_guid, template_name, friendly_name, user_email, file_name_string, process_json, template_guid, adhoc_headers=None):
        called["log_guid"] = process_guid
        called["log_template"] = template_name
        called["log_friendly"] = friendly_name
        called["log_email"] = user_email
        called["log_file"] = file_name_string
    monkeypatch.setattr("app_utils.azure_sql.log_mapping_process", fake_log)
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
        "customer_name": "Customer",
        "layer_confirmed_0": True,
        "customer_name": "Cust",
        "customer_ids": ["1"],
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
    assert called.get("log_guid") == called.get("guid")
    assert called.get("log_template") == "pit-bid"
    assert called.get("log_friendly") == "PIT BID"
    assert called.get("log_file") == "pit-bid.json"
    assert state["final_json"].get("process_guid") == called.get("guid")
    assert state.get("postprocess_payload") == {"p": 1}

def test_sharepoint_link_displayed(monkeypatch):
    _, _, st = run_app(monkeypatch)
    assert any(
        "https://tenant.sharepoint.com/sites/demo/docs/folder" in m
        for m in st.markdown_calls
    )


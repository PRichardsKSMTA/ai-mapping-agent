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
    def __init__(self, button_sequence: list[set[str]] | None = None):
        self.session_state = {}
        self.sidebar = DummySidebar(self)
        self.markdown_calls: list[str] = []
        self.spinner_messages: list[str] = []
        self.info_messages: list[str] = []
        self.success_messages: list[str] = []
        self.dataframe_calls: list[pd.DataFrame] = []
        self.secrets = {}
        self.button_sequence = button_sequence or []
        self.run_idx = 0
    def set_page_config(self, *a, **k):
        pass
    def title(self, *a, **k):
        pass
    header = subheader = error = write = warning = caption = title
    def info(self, msg, *a, **k):
        self.info_messages.append(msg)
    def success(self, msg, *a, **k):
        self.success_messages.append(msg)
    def selectbox(self, label, options, index=0, key=None, **k):
        choice = options[index] if options and index is not None else None
        if key:
            self.session_state[key] = choice
        return choice
    def file_uploader(self, *a, **k):
        return types.SimpleNamespace(name="upload.csv")
    def button(self, label, *a, **k):
        presses = (
            self.button_sequence[self.run_idx]
            if self.run_idx < len(self.button_sequence)
            else set()
        )
        return label in presses
    def spinner(self, msg, *a, **k):
        class _C(DummyContainer):
            def __enter__(self_inner):
                self.spinner_messages.append(msg)
                return self_inner
        return _C()
    def empty(self):
        return DummyContainer()
    def rerun(self):
        pass

    def next_run(self) -> None:
        self.run_idx += 1
    def markdown(self, text, *a, **k):
        self.markdown_calls.append(text)
    def download_button(self, *a, **k):
        pass
    def json(self, *a, **k):  # type: ignore[override]
        pass
    def dataframe(self, data, *a, **k):  # type: ignore[override]
        self.dataframe_calls.append(data)
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


def run_app(monkeypatch, button_sequence: list[set[str]] | None = None):
    st = DummyStreamlit(button_sequence or [{"Generate BID"}])
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
        "app_utils.azure_sql.insert_pit_bid_rows",
        lambda df, op, cust, ids, guid, adhoc: len(df),
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
        payload = {
            "p": 1,
            "CLIENT_DEST_SITE": "https://tenant.sharepoint.com/sites/demo",
            "DEST_FOLDER_PATH": "/Client Downloads/Pricing Tools/Customer Bids",
        }
        return ["ok"], payload

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
    st.next_run()
    if st.session_state.get("export_complete"):
        importlib.reload(sys.modules["app"])
        st.next_run()
    return called, st.session_state, st


def test_postprocess_runner_called(monkeypatch):
    called, state, _st = run_app(monkeypatch)
    assert called.get("run") is True
    assert called.get("guid") is not None
    assert called.get("log_guid") == called.get("guid")
    assert called.get("log_template") == "pit-bid"
    assert called.get("log_friendly") == "PIT BID"
    assert called.get("log_file") == "pit-bid.json"
    assert "final_json" not in state


def test_no_sharepoint_link_displayed(monkeypatch):
    _, _, st = run_app(monkeypatch)
    assert any("mileage and toll data" in m for m in st.spinner_messages)
    assert not st.markdown_calls


def test_back_before_export(monkeypatch):
    _, state, _ = run_app(monkeypatch, button_sequence=[{"Back to mappings"}])
    assert "export_complete" not in state
    assert "layer_confirmed_0" not in state


def test_back_after_export(monkeypatch):
    _, state, _ = run_app(
        monkeypatch,
        button_sequence=[{"Generate BID"}, {"Back to mappings"}],
    )
    for key in ["export_complete", "mapped_csv"]:
        assert key not in state
    assert "layer_confirmed_0" not in state


def test_preview_before_export(monkeypatch):
    _, state, st = run_app(monkeypatch, button_sequence=[set()])
    assert "export_complete" not in state
    assert len(st.dataframe_calls) >= 2
    assert "Lane ID" in st.dataframe_calls[1].columns


def test_dataframe_previews(monkeypatch):
    _, state, st = run_app(monkeypatch)
    assert state.get("export_complete")
    assert len(st.dataframe_calls) >= 2


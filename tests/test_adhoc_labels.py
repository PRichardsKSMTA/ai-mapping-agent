import importlib
import json
import sys
from pathlib import Path
import types
from typing import Dict, Tuple
import hashlib

import pandas as pd
from pytest import MonkeyPatch

from tests.test_wizard_postprocess import DummyStreamlit
from schemas.template_v2 import FieldSpec, HeaderLayer
from pages.steps import header as header_step


class HeaderDummyCol:
    def __init__(self, st: "HeaderDummyStreamlit") -> None:
        self.st = st

    def selectbox(self, label, options, index=0, key=None, **k):
        if key and key in self.st.session_state:
            return self.st.session_state[key]
        choice = options[index]
        if key:
            self.st.session_state[key] = choice
        return choice

    def button(self, *a, **k):
        return False

    def markdown(self, *a, **k):
        pass

    def text_input(self, label, value="", key=None, **k):
        key = key or label
        if key in self.st.session_state:
            return self.st.session_state[key]
        self.st.session_state[key] = value
        return value

    def columns(self, spec):
        n = len(spec) if isinstance(spec, (list, tuple)) else spec
        return [HeaderDummyCol(self.st) for _ in range(n)]


class HeaderDummyStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}

    def header(self, *a, **k):
        pass

    subheader = success = error = info = warning = header

    class Spinner:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    def spinner(self, *a, **k):
        return self.Spinner()

    def columns(self, spec):
        n = len(spec) if isinstance(spec, (list, tuple)) else spec
        return [HeaderDummyCol(self) for _ in range(n)]

    def rerun(self):
        pass

    def markdown(self, *a, **k):
        pass

    def button(self, *a, **k):
        return False

    def download_button(self, *a, **k):
        pass

    def caption(self, *a, **k):
        pass


def setup_header_env(monkeypatch: MonkeyPatch) -> HeaderDummyStreamlit:
    st = HeaderDummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setattr(header_step, "st", st)
    monkeypatch.setattr(
        header_step,
        "read_tabular_file",
        lambda _f, sheet_name=None: (pd.DataFrame(), ["A", "B"]),
    )
    monkeypatch.setattr(
        header_step,
        "suggest_header_mapping",
        lambda fields, cols: {k: {} for k in fields},
    )
    monkeypatch.setattr(
        header_step, "apply_gpt_header_fallback", lambda m, c, targets=None: m
    )
    monkeypatch.setattr(header_step, "get_suggestions", lambda *a, **k: [])
    monkeypatch.setattr(header_step, "add_suggestion", lambda *a, **k: None)
    import app_utils.ui.header_utils as header_utils

    monkeypatch.setattr(header_utils, "st", st)
    st.session_state.update({"uploaded_file": object(), "current_template": "demo"})
    return st


def run_app_with_labels(
    monkeypatch: MonkeyPatch,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    st = DummyStreamlit([{"Generate PIT"}])
    st.session_state.clear()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setitem(
        sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None)
    )
    monkeypatch.setattr("auth.logout_button", lambda: None)
    monkeypatch.setattr("auth.ensure_user_email", lambda: "test@example.com")
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
        "app_utils.azure_sql.get_pit_url_payload",
        lambda op_cd: {
            "item/In_dtInputData": [
                {
                    "CLIENT_DEST_SITE": "https://tenant.sharepoint.com/sites/demo",
                    "CLIENT_DEST_FOLDER_PATH": "/docs/folder",
                }
            ]
        },
    )

    captured: dict[str, object] = {}

    def fake_insert(df, op, cust, ids, guid, adhoc_headers):
        captured["insert_adhoc"] = adhoc_headers
        return len(df)

    monkeypatch.setattr("app_utils.azure_sql.insert_pit_bid_rows", fake_insert)

    def fake_log(
        process_guid,
        operation_cd,
        template_name,
        friendly_name,
        user_email,
        file_name_string,
        process_json,
        template_guid,
        adhoc_headers=None,
    ):
        captured["log_adhoc"] = adhoc_headers

    monkeypatch.setattr("app_utils.azure_sql.log_mapping_process", fake_log)
    monkeypatch.setattr(
        "app_utils.azure_sql.derive_adhoc_headers",
        lambda df: {"unexpected": "call"},
    )
    monkeypatch.setattr(
        "app_utils.excel_utils.dedupe_adhoc_headers", lambda h, cols: h
    )
    monkeypatch.setattr(
        "app_utils.postprocess_runner.run_postprocess_if_configured",
        lambda tpl, df, guid, customer_name=None, operation_cd=None, user_email=None, filename=None: (
            [],
            None,
            None,
        ),
    )

    tpl_path = Path("templates/pit-bid.json")
    tpl_data = json.loads(tpl_path.read_text())
    st.session_state.update(
        {
            "selected_template_file": tpl_path.name,
            "uploaded_file": object(),
            "template": tpl_data,
            "template_name": "PIT BID",
            "current_template": "PIT BID",
            "layer_confirmed_0": True,
            "header_adhoc_headers": {"ADHOC_INFO1": "Foo"},
            "customer_name": "Demo",
            "operation_code": "ADSJ_VAN",
            "customer_ids": ["1"],
        }
    )
    sys.modules.pop("app", None)
    importlib.import_module("app")
    if st.session_state.get("export_complete"):
        importlib.reload(sys.modules["app"])
    return captured, st.session_state


def test_adhoc_labels_propagate(monkeypatch: MonkeyPatch) -> None:
    captured, state = run_app_with_labels(monkeypatch)
    expected = {"ADHOC_INFO1": "Foo"}
    assert captured.get("insert_adhoc") == expected
    assert captured.get("log_adhoc") == expected
    assert state.get("header_adhoc_headers") == expected


def test_preset_mapping_populates_label(monkeypatch: MonkeyPatch) -> None:
    st = setup_header_env(monkeypatch)
    monkeypatch.setattr(
        header_step,
        "read_tabular_file",
        lambda _f, sheet_name=None: (pd.DataFrame(), ["Foo"]),
    )
    layer = HeaderLayer(
        type="header", fields=[FieldSpec(key="ADHOC_INFO1", required=False)]
    )
    cols_hash = hashlib.sha256("|".join(["Foo"]).encode()).hexdigest()
    st.session_state.update(
        {
            "header_mapping_0": {"ADHOC_INFO1": {"src": "Foo"}},
            "header_sheet_0": 0,
            "header_cols_0": cols_hash,
        }
    )
    header_step.render(layer, 0)
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == "Foo"


def test_default_label_updates_on_mapping(monkeypatch: MonkeyPatch) -> None:
    st = setup_header_env(monkeypatch)
    layer = HeaderLayer(
        type="header", fields=[FieldSpec(key="ADHOC_INFO1", required=False)]
    )
    st.session_state["src_ADHOC_INFO1"] = "A"
    header_step.render(layer, 0)
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == "A"
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] is True


def test_custom_label_persists(monkeypatch: MonkeyPatch) -> None:
    st = setup_header_env(monkeypatch)
    layer = HeaderLayer(
        type="header", fields=[FieldSpec(key="ADHOC_INFO1", required=False)]
    )
    st.session_state["src_ADHOC_INFO1"] = "A"
    header_step.render(layer, 0)
    st.session_state["adhoc_label_ADHOC_INFO1"] = "Custom"
    header_step.render(layer, 0)
    st.session_state["src_ADHOC_INFO1"] = "B"
    header_step.render(layer, 0)
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == "Custom"
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] is False


def test_label_updates_after_multiple_source_changes(monkeypatch: MonkeyPatch) -> None:
    st = setup_header_env(monkeypatch)
    layer = HeaderLayer(
        type="header", fields=[FieldSpec(key="ADHOC_INFO1", required=False)]
    )
    st.session_state["src_ADHOC_INFO1"] = "A"
    header_step.render(layer, 0)
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == "A"
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] is True
    st.session_state["src_ADHOC_INFO1"] = "B"
    header_step.render(layer, 0)
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == "B"
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] is True
    st.session_state["src_ADHOC_INFO1"] = "A"
    header_step.render(layer, 0)
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == "A"
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] is True

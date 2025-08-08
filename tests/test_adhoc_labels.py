import importlib
import json
import sys
from pathlib import Path
import types
from typing import Dict, Tuple

import pandas as pd
from pytest import MonkeyPatch

from tests.test_wizard_postprocess import DummyStreamlit


def run_app_with_labels(monkeypatch: MonkeyPatch) -> Tuple[Dict[str, object], Dict[str, object]]:
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

    captured: dict[str, object] = {}

    def fake_insert(df, op, cust, guid, adhoc_headers):
        captured["insert_adhoc"] = adhoc_headers
        return len(df)

    monkeypatch.setattr("app_utils.azure_sql.insert_pit_bid_rows", fake_insert)

    def fake_log(
        process_guid,
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
        "app_utils.postprocess_runner.run_postprocess_if_configured",
        lambda tpl, df, guid, op=None, cust=None: ([], None),
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

import hashlib
import pandas as pd
from pytest import MonkeyPatch

from schemas.template_v2 import FieldSpec, HeaderLayer
from pages.steps import header as header_step
from tests.test_adhoc_labels import setup_header_env


def test_new_upload_clears_adhoc_mapping_and_label(monkeypatch: MonkeyPatch) -> None:
    st = setup_header_env(monkeypatch)

    def fake_read(file, sheet_name=None):
        if file == "file1":
            return pd.DataFrame({"A": [1]}), ["A"]
        return pd.DataFrame({"B": [1]}), ["B"]

    monkeypatch.setattr(header_step, "read_tabular_file", fake_read)

    old_cols = ["A"]
    old_hash = hashlib.sha256("|".join(old_cols).encode()).hexdigest()
    st.session_state.update(
        {
            "uploaded_file": "file1",
            "upload_sheet": "Sheet1",
            "upload_sheets": ["Sheet1"],
            "current_template": "demo",
            "header_mapping_0": {"ADHOC_INFO1": {"src": "A"}},
            "header_sheet_0": "Sheet1",
            "header_cols_0": old_hash,
            "header_adhoc_headers": {"ADHOC_INFO1": "Custom"},
            "header_adhoc_autogen": {"ADHOC_INFO1": False},
        }
    )

    st.session_state["uploaded_file"] = "file2"

    layer = HeaderLayer(type="header", fields=[FieldSpec(key="ADHOC_INFO1", required=False)])
    header_step.render(layer, 0)

    assert st.session_state["header_mapping_0"]["ADHOC_INFO1"] == {}
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == "AdHoc1"
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] is True
    assert st.session_state["adhoc_label_ADHOC_INFO1"] == "AdHoc1"

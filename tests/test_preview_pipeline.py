import json
import tempfile
from pathlib import Path

from app_utils.excel_utils import read_tabular_file, save_mapped_csv
from app_utils.mapping.exporter import build_output_template
from schemas.template_v2 import Template


def test_preview_pipeline(tmp_path: Path) -> None:
    template = Template.model_validate(
        json.loads(Path("tests/fixtures/simple-template.json").read_text())
    )
    with open("tests/fixtures/simple.csv", "rb") as f:
        df, _ = read_tabular_file(f)
    state = {
        "header_mapping_0": {
            "Name": {"src": "Name"},
            "Value": {"src": "Value"},
        }
    }
    preview_json = build_output_template(template, state, "dummy-guid")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        mapped_df = save_mapped_csv(df, preview_json, tmp_path)
    tmp_path.unlink()
    assert list(mapped_df.columns) == ["Name", "Value"]
    assert mapped_df.iloc[0]["Value"] == "1"


def test_preview_pipeline_custom_label(tmp_path: Path) -> None:
    template = Template.model_validate(
        json.loads(Path("tests/fixtures/simple-template.json").read_text())
    )
    with open("tests/fixtures/simple.csv", "rb") as f:
        df, _ = read_tabular_file(f)
    state = {
        "header_mapping_0": {
            "Name": {"src": "Name"},
            "ADHOC_INFO1": {"src": "Value"},
        },
        "header_extra_fields_0": ["ADHOC_INFO1"],
        "header_adhoc_headers": {"ADHOC_INFO1": "Custom"},
    }
    preview_json = build_output_template(template, state, "dummy-guid")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        mapped_df = save_mapped_csv(df, preview_json, tmp_path)
    tmp_path.unlink()
    adhoc_headers = state["header_adhoc_headers"]
    display_df = mapped_df.rename(columns=adhoc_headers)
    assert list(display_df.columns) == ["Name", "Value", "Custom"]


def test_preview_pipeline_duplicate_mapping(tmp_path: Path) -> None:
    """Single source column can map to multiple destination fields."""
    template = Template.model_validate(
        {
            "template_name": "dup-template",
            "layers": [
                {
                    "type": "header",
                    "fields": [
                        {"key": "Name"},
                        {"key": "Value"},
                        {"key": "ValueCopy"},
                    ],
                }
            ],
        }
    )
    with open("tests/fixtures/simple.csv", "rb") as f:
        df, _ = read_tabular_file(f)
    state = {
        "header_mapping_0": {
            "Name": {"src": "Name"},
            "Value": {"src": "Value"},
            "ValueCopy": {"src": "Value"},
        }
    }
    preview_json = build_output_template(template, state, "dummy-guid")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        mapped_df = save_mapped_csv(df, preview_json, tmp_path)
    tmp_path.unlink()
    assert list(mapped_df.columns) == ["Name", "Value", "ValueCopy"]
    assert mapped_df["Value"].tolist() == mapped_df["ValueCopy"].tolist()


def test_preview_pipeline_expression_overrides_src(tmp_path: Path) -> None:
    template = Template.model_validate(
        json.loads(Path("tests/fixtures/simple-template.json").read_text())
    )
    with open("tests/fixtures/simple.csv", "rb") as f:
        df, _ = read_tabular_file(f)
    state = {
        "header_mapping_0": {
            "Name": {"src": "Name"},
            "Value": {"src": "Value", "expr": "df['Value'].astype(int) * 10"},
        }
    }
    preview_json = build_output_template(template, state, "dummy-guid")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        mapped_df = save_mapped_csv(df, preview_json, tmp_path)
    tmp_path.unlink()
    # Expression result should override the direct source copy
    assert mapped_df["Value"].tolist() == [10, 20]


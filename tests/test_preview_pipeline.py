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
    assert mapped_df.iloc[0]["Value"] == 1


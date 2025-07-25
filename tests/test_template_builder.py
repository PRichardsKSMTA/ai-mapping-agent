import io

from schemas.template_v2 import Template
from app_utils.excel_utils import read_tabular_file
from app_utils.template_builder import build_header_template


def test_scan_csv_columns():
    path = "tests/fixtures/simple.csv"
    with open(path, "rb") as f:
        _, cols = read_tabular_file(f)
    assert cols == ["Name", "Value"]


def test_build_header_template_valid():
    cols = ["A", "B"]
    required = {"A": True, "B": False}
    tpl = build_header_template("demo", cols, required)
    Template.model_validate(tpl)

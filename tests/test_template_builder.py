
from schemas.template_v2 import Template
from app_utils.excel_utils import read_tabular_file
from app_utils.template_builder import build_header_template
from app_utils.template_builder import load_template_json, save_template_file


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


def test_load_template_json_valid():
    with open('tests/fixtures/simple-template.json') as f:
        tpl = load_template_json(f)
    assert tpl['template_name'] == 'simple-template'


def test_save_template_file(tmp_path):
    tpl = {"template_name": "demo*temp", "layers": []}
    name = save_template_file(tpl, directory=tmp_path)
    assert (tmp_path / f"{name}.json").exists()


import pandas as pd
import app_utils.excel_utils as excel_utils
from pathlib import Path
from app_utils.excel_utils import list_sheets, read_tabular_file, save_mapped_csv


def test_list_sheets():
    with open('tests/fixtures/multi.xlsx', 'rb') as f:
        sheets = list_sheets(f)
    assert sheets == ['First', 'Second']


def test_list_sheets_filters_hidden():
    with open('tests/fixtures/multi_hidden.xlsx', 'rb') as f:
        sheets = list_sheets(f)
    assert sheets == ['First']


def test_read_tabular_file_excel():
    with open('tests/fixtures/multi.xlsx', 'rb') as f:
        df, cols = read_tabular_file(f, sheet_name='Second')
    assert cols == ['B']
    assert df.iloc[0]['B'] == 2


def test_read_tabular_file_drops_empty_columns():
    with open('tests/fixtures/blankcol.xlsx', 'rb') as f:
        df, cols = read_tabular_file(f, sheet_name='First')
    assert cols == ['A']


def test_read_tabular_file_header_only():
    with open('tests/fixtures/header_only.xlsx', 'rb') as f:
        df, cols = read_tabular_file(f)
    assert cols == ['A', 'B', 'C']
    assert df.empty


def test_read_tabular_file_multiple_reads():
    with open('tests/fixtures/simple.csv', 'rb') as f:
        df1, cols1 = read_tabular_file(f)
        df2, cols2 = read_tabular_file(f)
    assert cols1 == cols2 == ['Name', 'Value']
    assert df1.equals(df2)


def test_list_sheets_closes_temp(monkeypatch, tmp_path):
    path = tmp_path / "dummy.xlsx"
    excel_utils.pd.DataFrame({'A': [1]}).to_excel(path, index=False)

    def fake_copy(uploaded_file, suffix):
        return str(path)

    monkeypatch.setattr(excel_utils, "_copy_to_temp", fake_copy)

    closed = {"val": False}

    class DummyExcelFile:
        def __init__(self, *_args, **_kwargs):
            pass

        @property
        def worksheets(self):
            class DummySheet:
                title = "First"
                sheet_state = "visible"

            return [DummySheet()]

        def close(self):
            closed["val"] = True

    monkeypatch.setattr(excel_utils, "load_workbook", lambda *_args, **_kwargs: DummyExcelFile())

    import os

    def fake_unlink(_):
        assert closed["val"]

    monkeypatch.setattr(os, "unlink", fake_unlink)

    class DummyUpload:
        name = "dummy.xlsx"

        def getbuffer(self):
            return b""

        def read(self):
            return b""

        def seek(self, _pos):
            pass

    sheets = excel_utils.list_sheets(DummyUpload())
    assert sheets == ["First"]


def test_save_mapped_csv(tmp_path):
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    tpl = {
        "template_name": "t",
        "layers": [
            {
                "type": "header",
                "fields": [
                    {"key": "X", "source": "A"},
                    {"key": "Y", "source": "B"},
                ],
            }
        ],
    }
    out_path = tmp_path / "mapped.csv"
    mapped_df = save_mapped_csv(df, tpl, out_path)
    text = out_path.read_text().strip().splitlines()
    assert text[0] == "X,Y"
    assert text[1] == "1,2"
    assert list(mapped_df.columns) == ["X", "Y"]
    # Unmapped source column should be dropped
    assert "C" not in mapped_df.columns


def test_save_mapped_csv_extra_field(tmp_path):
    df = pd.DataFrame({"A": [1], "B": [2]})
    tpl = {
        "template_name": "t",
        "layers": [
            {
                "type": "header",
                "fields": [
                    {"key": "X", "source": "A"},
                    {"key": "Z", "source": "B"},
                ],
            }
        ],
        "header_extra_fields_0": ["Z"],
    }
    out_path = tmp_path / "mapped_extra.csv"
    mapped_df = save_mapped_csv(df, tpl, out_path)
    text = out_path.read_text().strip().splitlines()
    assert text[0] == "X,Z"
    assert text[1] == "1,2"
    assert list(mapped_df.columns) == ["X", "Z"]

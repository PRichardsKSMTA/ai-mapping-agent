import app_utils.excel_utils as excel_utils
from app_utils.excel_utils import list_sheets, read_tabular_file


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

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            closed["val"] = True

        @property
        def sheet_names(self):
            return ["First"]

    monkeypatch.setattr(excel_utils.pd, "ExcelFile", DummyExcelFile)

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

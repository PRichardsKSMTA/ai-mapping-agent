import pandas as pd
from app_utils.excel_utils import list_sheets, read_tabular_file


def test_list_sheets():
    with open('tests/fixtures/multi.xlsx', 'rb') as f:
        sheets = list_sheets(f)
    assert sheets == ['First', 'Second']


def test_read_tabular_file_excel():
    with open('tests/fixtures/multi.xlsx', 'rb') as f:
        df, cols = read_tabular_file(f, sheet_name='Second')
    assert cols == ['B']
    assert df.iloc[0]['B'] == 2
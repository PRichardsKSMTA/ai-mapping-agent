import json
import subprocess
from pathlib import Path
import sys

import cli
from app_utils import azure_sql


def test_cli_basic(tmp_path: Path):
    tpl = Path('tests/fixtures/simple-template.json')
    src = Path('tests/fixtures/simple.csv')
    out = tmp_path / 'out.json'

    subprocess.check_call(['python', 'cli.py', str(tpl), str(src), str(out)])

    data = json.loads(out.read_text())
    header_layer = data['layers'][0]
    fields = {f['key']: f.get('source') for f in header_layer['fields']}
    assert fields['Name'] == 'Name'
    assert fields['Value'] == 'Value'


def test_cli_csv_output(tmp_path: Path):
    tpl = Path('tests/fixtures/simple-template.json')
    src = Path('tests/fixtures/simple.csv')
    out_json = tmp_path / 'out.json'
    out_csv = tmp_path / 'out.csv'

    subprocess.check_call([
        'python',
        'cli.py',
        str(tpl),
        str(src),
        str(out_json),
        '--csv-output',
        str(out_csv),
    ])

    content = out_csv.read_text().strip().splitlines()
    assert content[0] == 'Name,Value'
    assert content[1] == 'Alice,1'


def test_cli_sql_insert(monkeypatch, tmp_path: Path, capsys):
    tpl = Path('templates/pit-bid.json')
    src = tmp_path / 'src.csv'
    src.write_text('Lane ID,Bid Volume\nL1,5\n')
    out_json = tmp_path / 'out.json'
    out_csv = tmp_path / 'out.csv'

    captured: dict[str, object] = {}

    def fake_insert(df, op, cust, guid):
        captured['cols'] = list(df.columns)
        captured['op'] = op
        captured['cust'] = cust
        captured['guid'] = guid
        return len(df)
    monkeypatch.setattr(azure_sql, 'insert_pit_bid_rows', fake_insert)
    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload', lambda op_cd: {}
    )
    monkeypatch.setattr(
        cli,
        'run_postprocess_if_configured',
        lambda tpl_obj, df, guid, operation_code=None, customer_name=None: ([], None),
    )
    monkeypatch.setattr(sys, 'argv', [
        'cli.py',
        str(tpl),
        str(src),
        str(out_json),
        '--csv-output',
        str(out_csv),
        '--operation-code',
        'OP',
        '--customer-name',
        'Cust',
    ])

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out_json.read_text())
    assert 'Inserted 1 rows into RFP_OBJECT_DATA' in out
    assert captured['op'] == 'OP'
    assert captured['cust'] == 'Cust'
    assert 'Lane ID' in captured['cols']
    assert captured['guid']
    assert data['process_guid'] == captured['guid']


def test_cli_postprocess_receives_codes(monkeypatch, tmp_path: Path, capsys):
    tpl = Path('templates/pit-bid.json')
    src = tmp_path / 'src.csv'
    src.write_text('Lane ID,Bid Volume\nL1,5\n')
    out_json = tmp_path / 'out.json'
    out_csv = tmp_path / 'out.csv'

    def fake_insert(df, op, cust, guid):
        return len(df)

    captured: dict[str, object] = {}

    def fake_postprocess(
        tpl_obj, df, process_guid, op_cd, cust_name
    ):
        captured['op'] = op_cd
        captured['cust'] = cust_name
        captured['guid'] = process_guid
        return ['POST https://example.com/hook', 'Done'], {'foo': 'bar'}

    monkeypatch.setattr(azure_sql, 'insert_pit_bid_rows', fake_insert)
    monkeypatch.setattr(cli, 'run_postprocess_if_configured', fake_postprocess)
    monkeypatch.setattr(sys, 'argv', [
        'cli.py',
        str(tpl),
        str(src),
        str(out_json),
        '--csv-output',
        str(out_csv),
        '--operation-code',
        'OP',
        '--customer-name',
        'Cust',
    ])

    cli.main()
    out = capsys.readouterr().out
    assert 'POST https://example.com/hook' in out
    assert json.dumps({'foo': 'bar'}, indent=2) in out
    data = json.loads(out_json.read_text())
    assert captured['op'] == 'OP'
    assert captured['cust'] == 'Cust'
    assert captured['guid']
    assert data['process_guid'] == captured['guid']


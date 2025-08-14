import json
import json
from pathlib import Path
import sys

import pytest

import cli
from app_utils import azure_sql


def test_cli_basic(monkeypatch, tmp_path: Path):
    tpl = Path('tests/fixtures/simple-template.json')
    src = Path('tests/fixtures/simple.csv')
    out = tmp_path / 'out.json'
    captured: dict[str, object] = {}

    def fake_log(process_guid, template_name, friendly_name, user_email, file_name_string, process_json, template_guid, adhoc_headers=None):
        captured.update(
            {
                'process_guid': process_guid,
                'template_name': template_name,
                'friendly_name': friendly_name,
                'user_email': user_email,
                'file_name_string': file_name_string,
                'process_json': process_json,
                'template_guid': template_guid,
                'adhoc_headers': adhoc_headers,
            }
        )

    monkeypatch.setattr(azure_sql, 'log_mapping_process', fake_log)
    monkeypatch.setattr(sys, 'argv', [
        'cli.py', str(tpl), str(src), str(out), '--user-email', 'user@example.com'
    ])
    cli.main()

    data = json.loads(out.read_text())
    header_layer = data['layers'][0]
    fields = {f['key']: f.get('source') for f in header_layer['fields']}
    assert fields['Name'] == 'Name'
    assert fields['Value'] == 'Value'
    assert data['process_guid'] == captured['process_guid']
    assert captured['template_name'] == tpl.stem
    assert captured['friendly_name'] == 'simple-template'
    assert captured['user_email'] == 'user@example.com'
    assert captured['file_name_string'] == tpl.name


def test_cli_csv_output(monkeypatch, tmp_path: Path):
    tpl = Path('tests/fixtures/simple-template.json')
    src = Path('tests/fixtures/simple.csv')
    out_json = tmp_path / 'out.json'
    out_csv = tmp_path / 'out.csv'

    monkeypatch.setattr(azure_sql, 'log_mapping_process', lambda *a, **k: None)
    monkeypatch.setattr(azure_sql, 'derive_adhoc_headers', lambda df: {})
    monkeypatch.setattr(sys, 'argv', [
        'cli.py',
        str(tpl),
        str(src),
        str(out_json),
        '--csv-output',
        str(out_csv),
    ])
    cli.main()

    data = json.loads(out_json.read_text())
    content = out_csv.read_text().strip().splitlines()
    assert content[0] == 'Name,Value'
    assert content[1] == 'Alice,1'
    assert data['process_guid']


def test_cli_sql_insert(monkeypatch, tmp_path: Path, capsys):
    tpl = Path('templates/pit-bid.json')
    src = tmp_path / 'src.csv'
    src.write_text('Lane ID,Bid Volume\nL1,5\n')
    out_json = tmp_path / 'out.json'
    out_csv = tmp_path / 'out.csv'

    captured: dict[str, object] = {}

    def fake_insert(df, op, cust, ids, guid, adhoc_headers):
        captured['cols'] = list(df.columns)
        captured['op'] = op
        captured['cust'] = cust
        captured['ids'] = ids
        captured['guid'] = guid
        captured['adhoc'] = adhoc_headers
        return len(df)
    monkeypatch.setattr(azure_sql, 'insert_pit_bid_rows', fake_insert)
    monkeypatch.setattr(azure_sql, 'derive_adhoc_headers', lambda df: {})
    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload', lambda op_cd: {}
    )
    monkeypatch.setattr(
        cli,
        'run_postprocess_if_configured',
        lambda tpl_obj, df, guid, customer_name, operation_code=None: ([], None),
    )
    monkeypatch.setattr(azure_sql, 'log_mapping_process', lambda *a, **k: None)
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
        '--customer-id',
        '1',
        '--customer-id',
        '2',
    ])

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out_json.read_text())
    assert 'Inserted 1 rows into RFP_OBJECT_DATA' in out
    assert captured['op'] == 'OP'
    assert captured['cust'] == 'Cust'
    assert captured['ids'] == ['1', '2']
    assert 'Lane ID' in captured['cols']
    assert captured['guid']
    assert data['process_guid'] == captured['guid']


def test_cli_postprocess_receives_codes(monkeypatch, tmp_path: Path, capsys):
    tpl = Path('templates/pit-bid.json')
    src = tmp_path / 'src.csv'
    src.write_text('Lane ID,Bid Volume\nL1,5\n')
    out_json = tmp_path / 'out.json'
    out_csv = tmp_path / 'out.csv'

    def fake_insert(df, op, cust, ids, guid, adhoc_headers):
        return len(df)

    captured: dict[str, object] = {}

    def fake_postprocess(
        tpl_obj, df, process_guid, cust_name, op_cd
    ):
        captured['op'] = op_cd
        captured['cust'] = cust_name
        captured['guid'] = process_guid
        return ['POST https://example.com/hook', 'Done'], {'foo': 'bar'}

    monkeypatch.setattr(azure_sql, 'insert_pit_bid_rows', fake_insert)
    monkeypatch.setattr(azure_sql, 'derive_adhoc_headers', lambda df: {})
    monkeypatch.setattr(cli, 'run_postprocess_if_configured', fake_postprocess)
    monkeypatch.setattr(azure_sql, 'log_mapping_process', lambda *a, **k: None)
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


def test_cli_requires_customer_name_for_pit_bid(monkeypatch, tmp_path: Path):
    tpl = Path('templates/pit-bid.json')
    src = tmp_path / 'src.csv'
    src.write_text('Lane ID,Bid Volume\nL1,5\n')
    out_json = tmp_path / 'out.json'
    out_csv = tmp_path / 'out.csv'

    monkeypatch.setattr(azure_sql, 'log_mapping_process', lambda *a, **k: None)
    monkeypatch.setattr(azure_sql, 'derive_adhoc_headers', lambda df: {})
    monkeypatch.setattr(sys, 'argv', [
        'cli.py',
        str(tpl),
        str(src),
        str(out_json),
        '--csv-output',
        str(out_csv),
        '--operation-code',
        'OP',
        '--customer-id',
        '1',
    ])

    with pytest.raises(SystemExit):
        cli.main()


def test_cli_sql_insert_without_customer_id(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    tpl = Path('templates/pit-bid.json')
    src = tmp_path / 'src.csv'
    src.write_text('Lane ID,Bid Volume\nL1,5\n')
    out_json = tmp_path / 'out.json'
    out_csv = tmp_path / 'out.csv'

    captured: dict[str, object] = {}

    def fake_insert(df, op, cust, ids, guid, adhoc_headers):
        captured['ids'] = ids
        return len(df)

    monkeypatch.setattr(azure_sql, 'insert_pit_bid_rows', fake_insert)
    monkeypatch.setattr(azure_sql, 'derive_adhoc_headers', lambda df: {})
    monkeypatch.setattr(
        cli,
        'run_postprocess_if_configured',
        lambda tpl_obj, df, guid, customer_name, operation_code=None: ([], None),
    )
    monkeypatch.setattr(azure_sql, 'log_mapping_process', lambda *a, **k: None)
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
    assert 'Inserted 1 rows into RFP_OBJECT_DATA' in out
    assert captured['ids'] == []


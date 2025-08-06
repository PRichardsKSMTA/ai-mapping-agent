import json
import subprocess
from pathlib import Path


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


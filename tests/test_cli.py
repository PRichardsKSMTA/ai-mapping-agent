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


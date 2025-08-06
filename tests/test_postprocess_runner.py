import types
import sys
import pandas as pd
from schemas.template_v2 import PostprocessSpec, Template
from app_utils.postprocess_runner import run_postprocess, run_postprocess_if_configured


def test_run_postprocess_calls_requests(monkeypatch):
    called = {}

    def fake_post(url, json=None, timeout=10):
        called['url'] = url
        called['json'] = json
        return types.SimpleNamespace(status_code=200)

    monkeypatch.setenv("ENABLE_POSTPROCESS", "1")
    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))
    cfg = PostprocessSpec(url="https://example.com/hook")
    run_postprocess(cfg, pd.DataFrame({"A": [1]}))
    assert called['url'] == cfg.url
    assert called['json'] == [{"A": 1}]


def test_run_postprocess_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_POSTPROCESS", raising=False)
    called = {}
    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=lambda *a, **k: called.setdefault('hit', True)))
    cfg = PostprocessSpec(url="https://example.com/hook")
    run_postprocess(cfg, pd.DataFrame({"A": [1]}))
    assert 'hit' not in called


def test_if_configured_helper(monkeypatch):
    monkeypatch.setenv("ENABLE_POSTPROCESS", "1")
    called = {}
    monkeypatch.setattr(
        'app_utils.postprocess_runner.run_postprocess',
        lambda cfg, df, log=None: called.setdefault('run', True)
    )
    tpl = Template.model_validate({
        'template_name': 'demo',
        'layers': [{'type': 'header', 'fields': [{'key': 'A'}]}],
        'postprocess': {'url': 'https://example.com'}
    })
    logs = run_postprocess_if_configured(tpl, pd.DataFrame())
    assert called.get('run') is True
    assert isinstance(logs, list)


def test_if_configured_applies_header_mappings(monkeypatch):
    captured = {}

    def fake_postprocess(cfg, df, log=None):  # pragma: no cover - executed via call
        captured['cols'] = list(df.columns)
        captured['lane'] = df.at[0, 'LANE_ID']

    monkeypatch.setenv("ENABLE_POSTPROCESS", "1")
    monkeypatch.setattr(
        'app_utils.postprocess_runner.run_postprocess',
        fake_postprocess,
    )

    tpl = types.SimpleNamespace(
        template_name='PIT BID',
        layers=[types.SimpleNamespace(type='header', fields=[types.SimpleNamespace(key='LANE_ID', source='Lane Code')])],
        postprocess=types.SimpleNamespace(url='http://example.com'),
    )

    df = pd.DataFrame({'Lane Code': ['L1']})

    run_postprocess_if_configured(tpl, df)

    assert captured['lane'] == 'L1'
    assert captured['cols'] == ['LANE_ID']


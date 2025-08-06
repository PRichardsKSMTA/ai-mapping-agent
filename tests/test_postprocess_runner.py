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


def test_if_configured_runs_pit_bid_insert(monkeypatch):
    called = {}
    tpl = Template.model_validate({
        'template_name': 'PIT BID',
        'layers': [{'type': 'header', 'fields': [{'key': 'Lane ID'}]}]
    })

    def fake_insert(df, op, cust, guid):  # pragma: no cover - executed via call
        called['hit'] = (op, cust, guid, len(df))

    monkeypatch.setattr('app_utils.azure_sql.insert_pit_bid_rows', fake_insert)
    df = pd.DataFrame({'Lane ID': ['L1']})
    run_postprocess_if_configured(
        tpl, df, process_guid='guid', operation_cd='OP', customer_name=None
    )
    assert called['hit'][0] == 'OP'
    assert called['hit'][1] is None
    assert called['hit'][2] == 'guid'


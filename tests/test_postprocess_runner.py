import types
import sys
import datetime
import json
from typing import Any, Dict
import pandas as pd
import pytest
from schemas.template_v2 import PostprocessSpec, Template
from app_utils.postprocess_runner import run_postprocess, run_postprocess_if_configured


def test_run_postprocess_calls_requests(load_env, monkeypatch):
    called = {}

    def fake_post(url, json=None, timeout=10):
        called['url'] = url
        called['json'] = json
        return types.SimpleNamespace(status_code=200)

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))
    cfg = PostprocessSpec(url="https://example.com/hook")
    run_postprocess(cfg, pd.DataFrame({"A": [1]}))
    assert called['url'] == cfg.url
    assert called['json'] == [{"A": 1}]


def test_run_postprocess_always_runs(monkeypatch):
    monkeypatch.delenv("ENABLE_POSTPROCESS", raising=False)
    called: dict[str, bool] = {}
    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(post=lambda *a, **k: called.setdefault('hit', True)),
    )
    cfg = PostprocessSpec(url="https://example.com/hook")
    run_postprocess(cfg, pd.DataFrame({"A": [1]}))
    assert called.get('hit') is True


def test_if_configured_helper(load_env, monkeypatch):
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
    logs, payload = run_postprocess_if_configured(tpl, pd.DataFrame(), "guid")
    assert called.get('run') is True
    assert isinstance(logs, list)
    assert payload == []


def test_if_configured_applies_header_mappings(load_env, monkeypatch):
    captured = {}

    def fake_postprocess(cfg, df, log=None):  # pragma: no cover - executed via call
        captured['cols'] = list(df.columns)
        captured['lane'] = df.at[0, 'LANE_ID']

    monkeypatch.setattr(
        'app_utils.postprocess_runner.run_postprocess',
        fake_postprocess,
    )

    tpl = types.SimpleNamespace(
        template_name='demo',
        layers=[types.SimpleNamespace(type='header', fields=[types.SimpleNamespace(key='LANE_ID', source='Lane Code')])],
        postprocess=types.SimpleNamespace(url='http://example.com'),
    )

    df = pd.DataFrame({'Lane Code': ['L1']})

    run_postprocess_if_configured(tpl, df, "guid")

    assert captured['lane'] == 'L1'
    assert captured['cols'] == ['LANE_ID']


def test_pit_bid_posts_payload(load_env, monkeypatch):
    payload = {
        "item/In_dtInputData": [{"NEW_EXCEL_FILENAME": "old.xlsm"}],
        "BID-Payload": "",
    }

    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload',
        lambda op_cd, week_ct=12: payload,
    )
    called = {}

    def fake_post(url, json=None, timeout=10):  # pragma: no cover - executed via call
        called['url'] = url
        called['json'] = json

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))
    fixed_now = datetime.datetime(2024, 1, 2, 3, 4, 5)
    monkeypatch.setattr(
        'app_utils.postprocess_runner.datetime',
        types.SimpleNamespace(utcnow=lambda: fixed_now),
    )
    tpl = Template.model_validate({
        'template_name': 'PIT BID',
        'layers': [{'type': 'header', 'fields': [{'key': 'A'}]}],
        'postprocess': {'url': 'https://example.com/post'},
    })
    logs, returned = run_postprocess_if_configured(
        tpl,
        pd.DataFrame({'A': [1]}),
        "guid",
        operation_cd='OP',
        customer_name='Cust',
    )
    expected = 'OP - BID - Cust BID.xlsm'
    assert returned['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME'] == expected
    assert returned['BID-Payload'] == "guid"
    assert called['url'] == tpl.postprocess.url
    assert called['json'] == returned
    payload_logs = [l for l in logs if l.startswith('Payload:')]
    assert len(payload_logs) == 2
    original_payload = json.loads(payload_logs[0].split('Payload: ')[1])
    assert original_payload['BID-Payload'] == ''
    assert 'old.xlsm' in payload_logs[0]
    logged_payload = json.loads(payload_logs[1].split('Payload: ')[1])
    assert logged_payload['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME'] == expected
    assert logged_payload['BID-Payload'] == 'guid'
    assert list(logged_payload['item/In_dtInputData'][0].keys()).count('NEW_EXCEL_FILENAME') == 1
    assert logs[-1] == 'Done'


def test_pit_bid_posts_without_flag(monkeypatch):
    payload = {
        "item/In_dtInputData": [{"NEW_EXCEL_FILENAME": "old.xlsm"}],
        "BID-Payload": "",
    }
    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload',
        lambda op_cd, week_ct=12: payload,
    )
    called: dict[str, Any] = {}

    def fake_post(url, json=None, timeout=10):  # pragma: no cover - executed via call
        called['url'] = url
        called['json'] = json

    monkeypatch.delenv("ENABLE_POSTPROCESS", raising=False)
    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))
    fixed_now = datetime.datetime(2024, 1, 2, 3, 4, 5)
    monkeypatch.setattr(
        'app_utils.postprocess_runner.datetime',
        types.SimpleNamespace(utcnow=lambda: fixed_now),
    )
    tpl = Template.model_validate({
        'template_name': 'PIT BID',
        'layers': [{'type': 'header', 'fields': [{'key': 'A'}]}],
        'postprocess': {'url': 'https://example.com/post'},
    })
    logs, returned = run_postprocess_if_configured(
        tpl,
        pd.DataFrame({'A': [1]}),
        "guid",
        operation_cd='OP',
        customer_name='Cust',
    )
    payload_logs = [l for l in logs if l.startswith('Payload:')]
    assert payload_logs
    expected = 'OP - BID - Cust BID.xlsm'
    original_payload = json.loads(payload_logs[0].split('Payload: ')[1])
    assert original_payload['BID-Payload'] == ''
    logged_payload = json.loads(payload_logs[-1].split('Payload: ')[1])
    assert logged_payload['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME'] == expected
    assert logged_payload['BID-Payload'] == 'guid'
    assert logs[-1] == 'Done'
    assert called['url'] == tpl.postprocess.url
    assert returned['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME'] == expected
    assert returned['BID-Payload'] == 'guid'


def test_pit_bid_requires_process_guid():
    tpl = Template.model_validate({
        'template_name': 'PIT BID',
        'layers': [{'type': 'header', 'fields': [{'key': 'A'}]}],
        'postprocess': {'url': 'https://example.com/post'},
    })
    with pytest.raises(ValueError):
        run_postprocess_if_configured(tpl, pd.DataFrame({'A': [1]}), '', operation_cd='OP')


def test_pit_bid_null_payload_logged(load_env, monkeypatch):
    def fake_get_pit_url_payload(op_cd: str, week_ct: int = 12) -> Dict[str, Any]:
        raise RuntimeError("null payload")

    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload',
        fake_get_pit_url_payload,
    )

    tpl = Template.model_validate({
        'template_name': 'PIT BID',
        'layers': [{'type': 'header', 'fields': [{'key': 'A'}]}],
        'postprocess': {'url': 'https://example.com/post'},
    })
    with pytest.raises(RuntimeError, match='null payload'):
        run_postprocess_if_configured(
            tpl,
            pd.DataFrame({'A': [1]}),
            'guid',
            operation_cd='OP',
        )


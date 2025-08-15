import types
import sys
import logging
from typing import Any, Dict
import pandas as pd
import pytest
from schemas.template_v2 import PostprocessSpec, Template
from app_utils.postprocess_runner import run_postprocess, run_postprocess_if_configured


def test_run_postprocess_calls_requests(load_env, monkeypatch):
    called: dict[str, Any] = {}

    def fake_post(url: str, json: Any | None = None, timeout: int = 10):
        called["url"] = url
        called["json"] = json
        return types.SimpleNamespace(status_code=200)

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))
    cfg = PostprocessSpec(url="https://example.com/hook")
    log: list[str] = []
    run_postprocess(cfg, pd.DataFrame({"A": [1]}), log)
    assert called["url"] == cfg.url
    assert called["json"] == [{"A": 1}]
    assert not any("ENABLE_POSTPROCESS" in msg for msg in log)


def test_run_postprocess_always_runs(monkeypatch):
    called: dict[str, bool] = {}
    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(post=lambda *a, **k: called.setdefault("hit", True)),
    )
    cfg = PostprocessSpec(url="https://example.com/hook")
    log: list[str] = []
    run_postprocess(cfg, pd.DataFrame({"A": [1]}), log)
    assert called.get("hit") is True
    assert not any("ENABLE_POSTPROCESS" in msg for msg in log)


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
    logs, payload = run_postprocess_if_configured(tpl, pd.DataFrame(), "guid", "Cust")
    assert called.get('run') is True
    assert isinstance(logs, list)
    assert payload == []
    assert not any("ENABLE_POSTPROCESS" in msg for msg in logs)


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

    logs, _ = run_postprocess_if_configured(tpl, df, "guid", "Cust")

    assert captured['lane'] == 'L1'
    # Original source column should remain alongside the mapped one
    assert captured['cols'] == ['Lane Code', 'LANE_ID']
    assert not any("ENABLE_POSTPROCESS" in msg for msg in logs)


def test_pit_bid_posts_payload(load_env, monkeypatch):
    payload = {
        "item/In_dtInputData": [{"NEW_EXCEL_FILENAME": "old.xlsm"}],
        "BID-Payload": "",
        "CLIENT_DEST_FOLDER_PATH": "/Client Downloads/Pricing Tools/Customer Bids",
    }

    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload',
        lambda op_cd, week_ct=12: payload,
    )
    monkeypatch.setattr(
        'app_utils.postprocess_runner.wait_for_postprocess_completion',
        lambda *a, **k: None,
    )
    called = {}

    def fake_post(url, json=None, timeout=10):  # pragma: no cover - executed via call
        called['url'] = url
        called['json'] = json

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))
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
    expected = 'OP - BID - Cust.xlsm'
    assert returned['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME'] == expected
    assert returned['BID-Payload'] == "guid"
    assert returned['CLIENT_DEST_FOLDER_PATH'] == "/Client Downloads/Pricing Tools/Customer Bids"
    assert all(
        item.get('CLIENT_DEST_FOLDER_PATH') == "/Client Downloads/Pricing Tools/Customer Bids"
        for item in returned.get('item/In_dtInputData', [])
    )
    assert called['url'] == tpl.postprocess.url
    assert called['json'] == returned
    assert "Payload loaded" in logs
    assert "Payload finalized" in logs
    assert logs[-1] == 'Done'
    assert not any("ENABLE_POSTPROCESS" in msg for msg in logs)


def test_pit_bid_posts(monkeypatch):
    payload = {
        "item/In_dtInputData": [{"NEW_EXCEL_FILENAME": "old.xlsm"}],
        "BID-Payload": "",
        "CLIENT_DEST_FOLDER_PATH": "/Client Downloads/Pricing Tools/Customer Bids",
    }
    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload',
        lambda op_cd, week_ct=12: payload,
    )
    monkeypatch.setattr(
        'app_utils.postprocess_runner.wait_for_postprocess_completion',
        lambda *a, **k: None,
    )
    called: dict[str, Any] = {}

    def fake_post(url, json=None, timeout=10):  # pragma: no cover - executed via call
        called['url'] = url
        called['json'] = json

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))
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
    assert "Payload loaded" in logs
    assert "Payload finalized" in logs
    expected = 'OP - BID - Cust.xlsm'
    assert logs[-1] == 'Done'
    assert called['url'] == tpl.postprocess.url
    assert returned['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME'] == expected
    assert returned['BID-Payload'] == 'guid'
    expected_path = "/Client Downloads/Pricing Tools/Customer Bids"
    assert returned['CLIENT_DEST_FOLDER_PATH'] == expected_path
    assert all(
        item.get('CLIENT_DEST_FOLDER_PATH') == expected_path
        for item in returned.get('item/In_dtInputData', [])
    )
    assert not any("ENABLE_POSTPROCESS" in msg for msg in logs)


def test_pit_bid_requires_process_guid():
    tpl = Template.model_validate({
        'template_name': 'PIT BID',
        'layers': [{'type': 'header', 'fields': [{'key': 'A'}]}],
        'postprocess': {'url': 'https://example.com/post'},
    })
    with pytest.raises(ValueError):
        run_postprocess_if_configured(tpl, pd.DataFrame({'A': [1]}), '', 'Cust', operation_cd='OP')


def test_pit_bid_null_payload_logged(load_env, monkeypatch):
    def fake_get_pit_url_payload(op_cd: str, week_ct: int = 12) -> Dict[str, Any]:
        raise RuntimeError("null payload")

    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload',
        fake_get_pit_url_payload,
    )
    monkeypatch.setattr(
        'app_utils.postprocess_runner.wait_for_postprocess_completion',
        lambda *a, **k: None,
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
            'Cust',
            operation_cd='OP',
        )


def test_wait_for_postprocess_completion_called(monkeypatch):
    called: dict[str, Any] = {}

    def fake_wait(
        pg: str, op: str, poll_interval: int = 30, max_attempts: int = 2
    ) -> None:
        called["args"] = (pg, op, poll_interval, max_attempts)
        logging.getLogger("app_utils.azure_sql").info("cycle")

    monkeypatch.setattr(
        "app_utils.postprocess_runner.wait_for_postprocess_completion",
        fake_wait,
    )
    monkeypatch.setattr(
        "app_utils.postprocess_runner.get_pit_url_payload",
        lambda op_cd, week_ct=12: {"BID-Payload": "", "item/In_dtInputData": [{}]},
    )
    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(post=lambda *a, **k: types.SimpleNamespace(status_code=200, text="", raise_for_status=lambda: None)),
    )
    tpl = Template.model_validate({
        "template_name": "PIT BID",
        "layers": [{"type": "header", "fields": [{"key": "A"}]}],
        "postprocess": {"url": "https://example.com/post"},
    })
    logs, _ = run_postprocess_if_configured(
        tpl,
        pd.DataFrame({"A": [1]}),
        "guid",
        customer_name="Cust",
        operation_cd="OP",
        poll_interval=1,
    )
    assert called["args"] == ("guid", "OP", 1, 2)
    assert "cycle" in logs


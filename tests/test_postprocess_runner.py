import types
import sys
import logging
from typing import Any, Dict
from datetime import datetime
import pandas as pd
import pytest
from schemas.template_v2 import PostprocessSpec, Template
from app_utils.azure_sql import PostprocessTimeoutError
from app_utils.postprocess_runner import (
    CLIENT_BIDS_DEST_PATH,
    generate_bid_filename,
    run_postprocess,
    run_postprocess_if_configured,
)


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
    logs, payload, fname = run_postprocess_if_configured(
        tpl, pd.DataFrame(), "guid", "Cust"
    )
    assert called.get('run') is True
    assert isinstance(logs, list)
    assert payload == []
    assert fname is None
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

    logs, _, fname = run_postprocess_if_configured(tpl, df, "guid", "Cust")

    assert captured['lane'] == 'L1'
    # Original source column should remain alongside the mapped one
    assert captured['cols'] == ['Lane Code', 'LANE_ID']
    assert fname is None
    assert not any("ENABLE_POSTPROCESS" in msg for msg in logs)


def test_pit_bid_posts_payload(load_env, monkeypatch):
    payload = {
        "item/In_dtInputData": [{"NEW_EXCEL_FILENAME": "old.xlsm"}],
        "BID-Payload": "",
    }

    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload',
        lambda op_cd, week_ct=12: payload,
    )
    monkeypatch.setattr(
        'app_utils.postprocess_runner.wait_for_postprocess_completion',
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        'app_utils.postprocess_runner.datetime',
        types.SimpleNamespace(now=lambda: datetime(2020, 1, 1)),
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
    logs, returned, fname = run_postprocess_if_configured(
        tpl,
        pd.DataFrame({'A': [1]}),
        "guid",
        operation_cd='OP',
        customer_name='Cust',
        user_email='user@example.com',
    )
    expected = 'OP - BID - Cust_20200101000000000.xlsm'
    assert returned['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME'] == expected
    assert returned['BID-Payload'] == "guid"
    assert 'CLIENT_DEST_FOLDER_PATH' not in returned
    assert all(
        item.get('CLIENT_DEST_FOLDER_PATH') == CLIENT_BIDS_DEST_PATH
        for item in returned.get('item/In_dtInputData', [])
    )
    assert returned['NOTIFY_EMAIL'] == 'user@example.com'
    assert all(
        item.get('NOTIFY_EMAIL') == 'user@example.com'
        for item in returned.get('item/In_dtInputData', [])
    )
    assert called['url'] == tpl.postprocess.url
    assert called['json'] == returned
    assert "Payload loaded" in logs
    assert "Payload finalized" in logs
    assert logs[-1] == 'Done'
    assert fname == expected
    assert not any("ENABLE_POSTPROCESS" in msg for msg in logs)


def test_pit_bid_posts(monkeypatch):
    payload = {
        "item/In_dtInputData": [{"NEW_EXCEL_FILENAME": "old.xlsm"}],
        "BID-Payload": "",
    }
    monkeypatch.setattr(
        'app_utils.postprocess_runner.get_pit_url_payload',
        lambda op_cd, week_ct=12: payload,
    )
    monkeypatch.setattr(
        'app_utils.postprocess_runner.wait_for_postprocess_completion',
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        'app_utils.postprocess_runner.datetime',
        types.SimpleNamespace(now=lambda: datetime(2020, 1, 1)),
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
    logs, returned, fname = run_postprocess_if_configured(
        tpl,
        pd.DataFrame({'A': [1]}),
        "guid",
        operation_cd='OP',
        customer_name='Cust',
        user_email='user@example.com',
    )
    assert "Payload loaded" in logs
    assert "Payload finalized" in logs
    expected = 'OP - BID - Cust_20200101000000000.xlsm'
    assert logs[-1] == 'Done'
    assert called['url'] == tpl.postprocess.url
    assert returned['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME'] == expected
    assert returned['BID-Payload'] == 'guid'
    expected_path = CLIENT_BIDS_DEST_PATH
    assert 'CLIENT_DEST_FOLDER_PATH' not in returned
    assert all(
        item.get('CLIENT_DEST_FOLDER_PATH') == expected_path
        for item in returned.get('item/In_dtInputData', [])
    )
    assert returned['NOTIFY_EMAIL'] == 'user@example.com'
    assert all(
        item.get('NOTIFY_EMAIL') == 'user@example.com'
        for item in returned.get('item/In_dtInputData', [])
    )
    assert fname == expected
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
        pg: str, op: str, poll_interval: int = 30, max_attempts: int = 24
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
    logs, _, fname = run_postprocess_if_configured(
        tpl,
        pd.DataFrame({"A": [1]}),
        "guid",
        customer_name="Cust",
        operation_cd="OP",
        poll_interval=1,
    )
    assert called["args"] == ("guid", "OP", 1, 24)
    assert "cycle" in logs
    assert fname is not None


def test_pit_bid_customer_name_sanitized(monkeypatch):
    payload = {"item/In_dtInputData": [{}], "BID-Payload": ""}
    monkeypatch.setattr('app_utils.postprocess_runner.get_pit_url_payload', lambda *a, **k: payload)
    monkeypatch.setattr('app_utils.postprocess_runner.wait_for_postprocess_completion', lambda *a, **k: None)
    monkeypatch.setattr('app_utils.postprocess_runner.datetime', types.SimpleNamespace(now=lambda: datetime(2020, 1, 1)))
    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=lambda *a, **k: None))
    tpl = Template.model_validate({'template_name': 'PIT BID', 'layers': [{'type': 'header', 'fields': [{'key': 'A'}]}], 'postprocess': {'url': 'https://example.com'}})
    _, ret, fname = run_postprocess_if_configured(
        tpl,
        pd.DataFrame({'A': [1]}),
        'guid',
        operation_cd='OP',
        customer_name='Sonoco/Tegrant, Inc.'
    )
    expected_name = 'OP - BID - SonocoTegrantInc_20200101000000000.xlsm'
    assert (
        ret['item/In_dtInputData'][0]['NEW_EXCEL_FILENAME']
        == expected_name
    )
    assert fname == expected_name


def test_pit_bid_postprocess_timeout_logs_and_raises(monkeypatch, caplog):
    def fake_wait(*args, **kwargs):
        logging.getLogger("app_utils.azure_sql").info("attempt logged")
        raise PostprocessTimeoutError("timeout occurred")

    monkeypatch.setattr(
        "app_utils.postprocess_runner.wait_for_postprocess_completion",
        fake_wait,
    )
    payload = {"item/In_dtInputData": [{}], "BID-Payload": ""}
    monkeypatch.setattr(
        "app_utils.postprocess_runner.get_pit_url_payload",
        lambda *a, **k: payload,
    )
    called: dict[str, Any] = {}

    def fake_post(*args, **kwargs):
        called["post"] = True

    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(post=fake_post),
    )

    tpl = Template.model_validate(
        {
            "template_name": "PIT BID",
            "layers": [{"type": "header", "fields": [{"key": "A"}]}],
            "postprocess": {"url": "https://example.com/post"},
        }
    )

    caplog.set_level(logging.INFO, logger="app_utils.azure_sql")
    with pytest.raises(PostprocessTimeoutError, match="timeout occurred"):
        run_postprocess_if_configured(
            tpl,
            pd.DataFrame({"A": [1]}),
            "guid",
            customer_name="Cust",
            operation_cd="OP",
        )
    assert "post" not in called
    assert "attempt logged" in caplog.messages
    assert any("timeout occurred" in msg for msg in caplog.messages)


def test_generate_bid_filename_preserves_case(monkeypatch):
    monkeypatch.setattr(
        'app_utils.postprocess_runner.datetime',
        types.SimpleNamespace(now=lambda: datetime(2020, 1, 1)),
    )
    fname = generate_bid_filename('OP', 'AOD')
    assert fname == 'OP - BID - AOD_20200101000000000.xlsm'


def test_generate_bid_filename_sanitizes_forbidden_chars(monkeypatch):
    monkeypatch.setattr(
        'app_utils.postprocess_runner.datetime',
        types.SimpleNamespace(now=lambda: datetime(2020, 1, 1)),
    )
    fname = generate_bid_filename('OP', 'ACME, Inc.')
    assert fname == 'OP - BID - ACMEInc_20200101000000000.xlsm'

import pandas as pd
import pytest

from schemas.template_v2 import PostprocessSpec, Template
import app_utils.postprocess_runner as runner
from app_utils.postprocess_runner import run_postprocess, run_postprocess_if_configured


def test_dispatch_excel(monkeypatch):
    called = {}
    monkeypatch.setitem(
        runner._DISPATCH,
        'excel_template',
        lambda cfg, df: called.setdefault('excel', True)
    )
    run_postprocess(PostprocessSpec(type='excel_template'), pd.DataFrame())
    assert called.get('excel') is True


def test_dispatch_sql(monkeypatch):
    called = {}
    monkeypatch.setitem(
        runner._DISPATCH,
        'sql_insert',
        lambda cfg, df: called.setdefault('sql', True)
    )
    run_postprocess(PostprocessSpec(type='sql_insert'), pd.DataFrame())
    assert called.get('sql') is True


def test_dispatch_http(monkeypatch):
    called = {}
    monkeypatch.setitem(
        runner._DISPATCH,
        'http_request',
        lambda cfg, df: called.setdefault('http', True)
    )
    run_postprocess(PostprocessSpec(type='http_request'), pd.DataFrame())
    assert called.get('http') is True


def test_dispatch_python(monkeypatch):
    called = {}
    monkeypatch.setitem(
        runner._DISPATCH,
        'python_script',
        lambda cfg, df: called.setdefault('py', True)
    )
    run_postprocess(PostprocessSpec(type='python_script', script=''), pd.DataFrame())
    assert called.get('py') is True


def test_if_configured_helper(monkeypatch):
    called = {}
    monkeypatch.setattr(
        'app_utils.postprocess_runner.run_postprocess',
        lambda cfg, df, log=None: called.setdefault('run', True)
    )
    tpl = Template.model_validate({
        'template_name': 'demo',
        'layers': [{'type': 'header', 'fields': [{'key': 'A'}]}],
        'postprocess': {'type': 'sql_insert'}
    })
    logs = run_postprocess_if_configured(tpl, pd.DataFrame())
    assert called.get('run') is True
    assert isinstance(logs, list)


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        run_postprocess(PostprocessSpec(type='unknown'), pd.DataFrame())

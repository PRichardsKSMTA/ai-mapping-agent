from schemas.template_v2 import Template
from app_utils.excel_utils import read_tabular_file
from app_utils.template_builder import build_header_template
from app_utils.template_builder import (
    load_template_json,
    save_template_file,
    apply_field_choices,
)


def test_scan_csv_columns():
    path = "tests/fixtures/simple.csv"
    with open(path, "rb") as f:
        _, cols = read_tabular_file(f)
    assert cols == ["Name", "Value"]


def test_build_header_template_valid():
    cols = ["A", "B"]
    required = {"A": True, "B": False}
    tpl = build_header_template("demo", cols, required, None)
    Template.model_validate(tpl)


def test_build_header_template_with_postprocess():
    cols = ["A"]
    required = {"A": True}
    post = {"type": "sql_insert"}
    tpl = build_header_template("demo", cols, required, post)
    assert tpl["postprocess"] == post
    Template.model_validate(tpl)


def test_load_template_json_valid():
    with open("tests/fixtures/simple-template.json") as f:
        tpl = load_template_json(f)
    assert tpl["template_name"] == "simple-template"


def test_save_template_file(tmp_path):
    tpl = {"template_name": "demo*temp", "layers": []}
    name = save_template_file(tpl, directory=tmp_path)
    assert (tmp_path / f"{name}.json").exists()


def test_render_sidebar_columns(monkeypatch):
    """Sidebar should list columns stored in session state."""
    import types
    import importlib
    import sys

    class DummySidebar:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def subheader(self, _txt: str) -> None:
            pass

        def write(self, txt: str) -> None:
            self.seen.append(txt)

        def info(self, _txt: str) -> None:
            pass

    class DummyContainer:
        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            pass

        def markdown(self, *a, **k) -> None:
            pass

        def progress(self, *a, **k) -> None:
            pass

    class DummyStreamlit:
        def __init__(self) -> None:
            self.session_state = {}
            self.sidebar = DummySidebar()

        def title(self, *a, **k) -> None:
            pass

        header = title
        subheader = title
        success = title
        error = title
        write = title
        warning = title
        info = title

        def text_input(self, *a, **k):
            return ""

        def file_uploader(self, *a, **k):
            return None

        def checkbox(self, *a, **k):
            return False

        def button(self, *a, **k):
            return False

        def text_area(self, label, key=None, **k):
            return ""

        def columns(self, spec):
            return [
                types.SimpleNamespace(button=self.button, write=self.write)
                for _ in spec
            ]

        def empty(self) -> DummyContainer:
            return DummyContainer()

        def divider(self) -> None:
            pass

        def dialog(self, *a, **k):
            def wrap(func):
                return func

            return wrap

        def rerun(self) -> None:
            pass

        def markdown(self, *a, **k) -> None:
            pass

        def cache_data(self, *a, **k):
            def wrap(func):
                return func

            return wrap

    dummy_st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", dummy_st)
    monkeypatch.setitem(
        sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None)
    )
    monkeypatch.setenv("DISABLE_AUTH", "1")

    mod = importlib.import_module("pages.template_manager")

    dummy_st.sidebar.seen.clear()
    mod.render_sidebar_columns(["A", "B"])

    assert dummy_st.sidebar.seen == ["A", "B"]


def test_apply_field_choices():
    cols = ["A", "B", "C"]
    choices = {"A": "required", "B": "omit", "C": "optional"}
    selected, required = apply_field_choices(cols, choices)
    assert selected == ["A", "C"]
    assert required == {"A": True, "C": False}

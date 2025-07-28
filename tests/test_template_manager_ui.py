import types
import importlib
import sys

class DummySidebar:
    def __init__(self) -> None:
        self.seen = []

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
    def __init__(self, uploaded=None) -> None:
        self.session_state = {}
        self.sidebar = DummySidebar()
        self._uploaded = uploaded
        self.text_input_calls = 0

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
        self.text_input_calls += 1
        return ""

    def file_uploader(self, *a, **k):
        return self._uploaded

    def checkbox(self, *a, **k):
        return False

    def button(self, *a, **k):
        return False

    def columns(self, spec):
        return [types.SimpleNamespace(button=self.button, write=self.write) for _ in spec]

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


def run_manager(monkeypatch, uploaded=None):
    dummy_st = DummyStreamlit(uploaded)
    monkeypatch.setitem(sys.modules, "streamlit", dummy_st)
    monkeypatch.setitem(
        sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None)
    )
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setattr(
        "app_utils.excel_utils.list_sheets", lambda _uploaded: ["Sheet1"]
    )
    monkeypatch.setattr(
        "app_utils.excel_utils.read_tabular_file",
        lambda _uploaded, sheet_name=None: ([], []),
    )
    sys.modules.pop("pages.template_manager", None)
    importlib.import_module("pages.template_manager")
    return dummy_st


def test_no_name_field_before_upload(monkeypatch):
    dummy = run_manager(monkeypatch, uploaded=None)
    assert dummy.text_input_calls == 0


def test_name_field_after_upload(monkeypatch):
    dummy_file = types.SimpleNamespace(name="demo.csv")
    dummy = run_manager(monkeypatch, uploaded=dummy_file)
    assert dummy.text_input_calls == 1


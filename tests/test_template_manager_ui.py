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
        self.text_area_labels: list[str] = []
        self.captions: list[str] = []

    def title(self, *a, **k) -> None:
        pass

    header = title
    subheader = title
    success = title
    error = title
    write = title
    warning = title
    info = title
    caption = lambda self, txt, **k: self.captions.append(txt)

    def text_input(self, *a, **k):
        self.text_input_calls += 1
        key = k.get("key")
        return self.session_state.get(key, "")

    def file_uploader(self, *a, **k):
        return self._uploaded

    def checkbox(self, *a, **k):
        return False

    def button(self, *a, **k):
        return False

    def json(self, *a, **k):
        pass

    def text_area(self, label, key=None, **k):
        self.text_area_labels.append(label)
        return self.session_state.get(key, "")

    def radio(self, label, options, index=0, **k):
        return options[index]

    def columns(self, spec):
        if isinstance(spec, int):
            spec = range(spec)
        cols = []
        for _ in spec:
            cols.append(
                types.SimpleNamespace(
                    button=self.button,
                    write=self.write,
                    text_input=self.text_input,
                    selectbox=lambda label, options, index=0, key=None, **k: self.session_state.get(key, options[index]),
                )
            )
        return cols

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

    class Spinner:
        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            pass

    def spinner(self, *a, **k):
        return self.Spinner()


def run_manager(
    monkeypatch,
    uploaded=None,
    button_patch=None,
    builder=None,
    session_state=None,
    cols=None,
    reader=None,
    gpt_patch=None,
):
    dummy_st = DummyStreamlit(uploaded)
    if button_patch:
        dummy_st.button = button_patch
    if session_state:
        dummy_st.session_state.update(session_state)
    monkeypatch.setitem(sys.modules, "streamlit", dummy_st)
    monkeypatch.setitem(
        sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None)
    )
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setattr(
        "app_utils.excel_utils.list_sheets", lambda _uploaded: ["Sheet1"]
    )
    if reader is None:
        reader = lambda _uploaded, sheet_name=None: ([], cols or [])
    monkeypatch.setattr(
        "app_utils.excel_utils.read_tabular_file",
        reader,
    )
    if gpt_patch:
        monkeypatch.setattr(
            "app_utils.template_builder.gpt_field_suggestions",
            gpt_patch,
        )
    if builder:
        monkeypatch.setattr(
            "app_utils.template_builder.build_template", builder
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


def test_postprocess_field_shown(monkeypatch):
    dummy_file = types.SimpleNamespace(name="demo.csv")
    dummy = run_manager(monkeypatch, uploaded=dummy_file, cols=["A"]) 
    assert "Postprocess JSON (optional)" in dummy.text_area_labels


def test_postprocess_field_hidden_without_columns(monkeypatch):
    dummy_file = types.SimpleNamespace(name="demo.csv")
    dummy = run_manager(monkeypatch, uploaded=dummy_file, cols=[])
    assert "Postprocess JSON (optional)" not in dummy.text_area_labels


def test_postprocess_passed_to_builder(monkeypatch):
    dummy_file = types.SimpleNamespace(name="demo.csv")

    captured = {}

    def fake_builder(name, layers, post=None, template_guid=None):
        captured["post"] = post
        return {
            "template_name": name,
            "layers": layers,
            "template_guid": template_guid or "guid",
        }

    dummy = run_manager(
        monkeypatch,
        uploaded=dummy_file,
        button_patch=lambda label, *a, **k: label == "Save Template",
        builder=fake_builder,
        session_state={"tm_name": "demo", "tm_postprocess": "{\"url\": \"https://example.com\"}"},
    )

    assert captured["post"] == {"url": "https://example.com"}


def test_postprocess_caption_displayed(monkeypatch):
    dummy_file = types.SimpleNamespace(name="demo.csv")
    dummy = run_manager(monkeypatch, uploaded=dummy_file, cols=["A"])
    assert any("POST mapped data" in c for c in dummy.captions)


def test_suggest_required_fields_without_file(monkeypatch):
    calls = {"read": 0}

    def fake_reader(_uploaded, sheet_name=None):
        calls["read"] += 1
        return [], []

    dummy = run_manager(
        monkeypatch,
        uploaded=None,
        cols=["A"],
        session_state={"tm_columns": ["A"]},
        button_patch=lambda label, *a, **k: label == "Suggest required fields",
        reader=fake_reader,
        gpt_patch=lambda df: {},
    )

    assert calls["read"] == 0




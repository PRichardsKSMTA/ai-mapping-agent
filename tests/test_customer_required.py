import importlib
import sys
import types


class DummyContainer:
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        pass
    def markdown(self, *a, **k):
        pass
    def progress(self, *a, **k):
        pass
    def write(self, *a, **k):
        pass
    def info(self, *a, **k):
        pass
    def caption(self, *a, **k):
        pass


class DummySidebar:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def subheader(self, *a, **k):
        pass

    def selectbox(self, label, options, index=0, key=None, **k):
        choice = options[index] if options else None
        if key:
            self.st.session_state[key] = choice
        return choice

    def empty(self):
        return DummyContainer()

    def button(self, *a, **k):
        return False

    def write(self, *a, **k):
        pass


class DummyStreamlit:
    def __init__(self):
        self.session_state = {}
        self.sidebar = DummySidebar(self)
        self.errors = []
        self.secrets = {}

    def set_page_config(self, *a, **k):
        pass

    def title(self, *a, **k):
        pass

    header = subheader = success = warning = info = caption = title

    def selectbox(self, label, options, index=0, key=None, **k):
        if label == "Customer":
            choice = None
        else:
            choice = options[index] if options else None
        if key:
            self.session_state[key] = choice
        return choice

    def file_uploader(self, *a, **k):
        raise RuntimeError("file_uploader should not run when no customer selected")

    def spinner(self, *a, **k):
        return DummyContainer()

    def empty(self):
        return DummyContainer()

    def button(self, *a, **k):
        return False

    def error(self, msg, *a, **k):
        self.errors.append(msg)

    def rerun(self):
        pass

    def cache_data(self, *a, **k):
        def wrap(func):
            return func
        return wrap


def run_app(monkeypatch):
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
    monkeypatch.setattr("auth.logout_button", lambda: None)
    monkeypatch.setattr("app_utils.excel_utils.list_sheets", lambda _u: [])
    monkeypatch.setattr("app_utils.azure_sql.fetch_operation_codes", lambda email=None: ["OP"])
    monkeypatch.setattr("app_utils.azure_sql.fetch_customers", lambda scac: [{"BILLTO_NAME": "Cust"}])
    monkeypatch.setattr("app_utils.azure_sql.get_operational_scac", lambda op: "SCAC")
    st.session_state.update({"template_name": "PIT BID"})
    sys.modules.pop("app", None)
    importlib.import_module("app")
    return st


def test_pit_bid_requires_customer(monkeypatch):
    st = run_app(monkeypatch)
    assert "Please select a customer to proceed." in st.errors

import importlib
import io
import sys
import types
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CUSTOMERS = [
    {
        "CLIENT_SCAC": "ADSJ",
        "BILLTO_ID": "1",
        "BILLTO_NAME": "Acme",
        "BILLTO_TYPE": "T",
        "OPERATIONAL_SCAC": "ADSJ",
    }
]


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

    def button(self, *a, **k):
        return False


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
        choice = options[index] if options and index is not None else None
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
        self.multiselect_calls: list[str] = []

    def set_page_config(self, *a, **k):
        pass

    def title(self, *a, **k):
        pass

    header = subheader = success = warning = info = caption = title

    def markdown(self, *a, **k):
        pass

    def dataframe(self, *a, **k):
        pass

    def selectbox(self, label, options, index=0, key=None, **k):
        if label == "Customer":
            choice = None if index is None else options[index]
        else:
            choice = options[index] if options and index is not None else None
        if key:
            self.session_state[key] = choice
        return choice

    def multiselect(self, label, options, default=None, key=None, **k):
        self.multiselect_calls.append(label)
        choice = default or []
        if key:
            self.session_state[key] = choice
        return choice

    def file_uploader(self, *a, **k):
        data = (FIXTURE_DIR / "simple.csv").read_bytes()

        class Upload(io.BytesIO):
            def read(self, *args, **kwargs):
                self.seek(0)
                return super().read(*args, **kwargs)

        file_obj = Upload(data)
        file_obj.name = "simple.csv"
        self.session_state["uploaded_file"] = file_obj
        return file_obj

    def spinner(self, *a, **k):
        return DummyContainer()

    def container(self) -> DummyContainer:
        return DummyContainer()

    def empty(self):
        return DummyContainer()

    def button(self, *a, **k):
        return False

    def text_input(self, label, value="", key=None, **k):
        if key:
            self.session_state[key] = value
        return value

    def error(self, msg, *a, **k):
        self.errors.append(msg)

    def stop(self):
        return None

    def columns(self, n):
        count = n if isinstance(n, int) else len(n)
        return (self,) * count

    def rerun(self):
        pass

    def cache_data(self, *a, **k):
        def wrap(func):
            return func
        return wrap


def run_app(monkeypatch, customers=None):
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
    monkeypatch.setattr("auth.logout_button", lambda: None)
    monkeypatch.setattr("app_utils.excel_utils.list_sheets", lambda _u: ["Sheet1"])
    monkeypatch.setattr("app_utils.azure_sql.fetch_operation_codes", lambda email=None: ["OP"])
    monkeypatch.setattr(
        "app_utils.azure_sql.fetch_customers",
        lambda scac: customers or [],
    )
    monkeypatch.setattr("app_utils.azure_sql.get_operational_scac", lambda op: "SCAC")
    sys.modules.pop("app", None)
    importlib.import_module("app")
    return st


def test_error_when_no_customer_after_upload(monkeypatch):
    st = run_app(monkeypatch, CUSTOMERS)
    assert st.session_state.get("uploaded_file") is not None
    assert "Please select a customer to proceed." in st.errors
    assert "Customer ID" not in st.multiselect_calls


def test_pit_bid_requires_customer_id(monkeypatch):
    def selectbox(self, label, options, index=0, key=None, **k):
        choice = options[0] if options else None
        if key:
            self.session_state[key] = choice
        return choice

    monkeypatch.setattr(DummyStreamlit, "selectbox", selectbox)
    customers = CUSTOMERS + [
        {
            "CLIENT_SCAC": "ADSJ",
            "BILLTO_ID": "2",
            "BILLTO_NAME": "Acme",
            "BILLTO_TYPE": "T",
            "OPERATIONAL_SCAC": "ADSJ",
        }
    ]
    st = run_app(monkeypatch, customers)
    assert "Select at least one Customer ID." in st.errors
    assert "Customer ID" in st.multiselect_calls

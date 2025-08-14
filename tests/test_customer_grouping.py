import importlib
import sys
import types
from typing import Any


class DummyContainer:
    def __enter__(self):
        return self

    def __exit__(self, *exc: Any) -> None:
        pass

    def markdown(self, *a: Any, **k: Any) -> None:
        pass

    def progress(self, *a: Any, **k: Any) -> None:
        pass

    def write(self, *a: Any, **k: Any) -> None:
        pass

    def info(self, *a: Any, **k: Any) -> None:
        pass

    def caption(self, *a: Any, **k: Any) -> None:
        pass

    def button(self, *a: Any, **k: Any) -> bool:
        return False


class DummySidebar:
    def __init__(self, st: "DummyStreamlit") -> None:
        self.st = st

    def __enter__(self) -> "DummySidebar":
        return self

    def __exit__(self, *exc: Any) -> None:
        pass

    def subheader(self, *a: Any, **k: Any) -> None:
        pass

    def selectbox(self, label: str, options: list[str], index: int | None = 0, key: str | None = None, **k: Any) -> str | None:
        choice = options[index] if options and index is not None else None
        if key:
            self.st.session_state[key] = choice
        return choice

    def empty(self) -> DummyContainer:
        return DummyContainer()

    def button(self, *a: Any, **k: Any) -> bool:
        return False

    def write(self, *a: Any, **k: Any) -> None:
        pass


class DummyStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}
        self.sidebar = DummySidebar(self)
        self.errors: list[str] = []
        self.customer_options: list[str] | None = None
        self.secrets = {}

    def set_page_config(self, *a: Any, **k: Any) -> None:
        pass

    def title(self, *a: Any, **k: Any) -> None:
        pass

    header = subheader = success = warning = info = caption = title

    def markdown(self, *a: Any, **k: Any) -> None:
        pass

    def selectbox(self, label: str, options: list[str], index: int | None = 0, key: str | None = None, **k: Any) -> str | None:
        if label == "Customer":
            self.customer_options = options
        choice = options[index] if options and index is not None else None
        if key:
            self.session_state[key] = choice
        return choice

    def multiselect(self, label: str, options: list[str], default: list[str] | None = None, key: str | None = None, **k: Any) -> list[str]:
        choice = options
        if key:
            self.session_state[key] = choice
        return choice

    def file_uploader(self, *a: Any, **k: Any) -> None:
        return None

    def spinner(self, *a: Any, **k: Any) -> DummyContainer:
        return DummyContainer()

    def empty(self) -> DummyContainer:
        return DummyContainer()

    def button(self, *a: Any, **k: Any) -> bool:
        return False

    def error(self, msg: str, *a: Any, **k: Any) -> None:
        self.errors.append(msg)

    def columns(self, n: int) -> tuple[DummyContainer, ...]:
        return (DummyContainer(),) * n

    def rerun(self) -> None:
        pass

    def cache_data(self, *a: Any, **k: Any):
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
    customers = [
        {
            "CLIENT_SCAC": "ADSJ",
            "BILLTO_ID": "A",
            "BILLTO_NAME": "BOISE CASCADE",
            "BILLTO_TYPE": "T",
            "OPERATIONAL_SCAC": "ADSJ",
        },
        {
            "CLIENT_SCAC": "ADSJ",
            "BILLTO_ID": "B",
            "BILLTO_NAME": "Boise Cascade",
            "BILLTO_TYPE": "T",
            "OPERATIONAL_SCAC": "ADSJ",
        },
    ]
    monkeypatch.setattr("app_utils.azure_sql.fetch_customers", lambda scac: customers)
    monkeypatch.setattr("app_utils.azure_sql.get_operational_scac", lambda op: "SCAC")
    st.session_state.update({"template_name": "PIT BID", "uploaded_file": object()})
    sys.modules.pop("app", None)
    importlib.import_module("app")
    return st


def test_customer_grouping(monkeypatch):
    st = run_app(monkeypatch)
    assert st.customer_options == ["Boise Cascade", "+ New Customer"]
    assert "customer_id_options" not in st.session_state

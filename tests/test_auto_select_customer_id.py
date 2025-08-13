import pytest
from tests.test_customer_required import DummyStreamlit, run_app

SINGLE_CUSTOMER = [
    {
        "CLIENT_SCAC": "ADSJ",
        "BILLTO_ID": "1",
        "BILLTO_NAME": "Acme",
        "BILLTO_TYPE": "T",
        "OPERATIONAL_SCAC": "ADSJ",
    }
]


def test_auto_select_single_customer_id(monkeypatch: pytest.MonkeyPatch) -> None:
    def selectbox(self, label, options, index=0, key=None, **k):
        choice = options[0] if options else None
        if key:
            self.session_state[key] = choice
        return choice

    def multiselect(self, *a, **k):
        pytest.fail("st.multiselect should not be called")

    monkeypatch.setattr(DummyStreamlit, "selectbox", selectbox)
    monkeypatch.setattr(DummyStreamlit, "multiselect", multiselect)

    st = run_app(monkeypatch, SINGLE_CUSTOMER)
    assert st.session_state.get("customer_ids") == ["1"]

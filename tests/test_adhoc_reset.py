from pytest import MonkeyPatch

from schemas.template_v2 import FieldSpec, HeaderLayer
from pages.steps import header as header_step
from tests.test_adhoc_labels import HeaderDummyCol, setup_header_env


def test_reset_button_clears_mapping_and_label(monkeypatch: MonkeyPatch) -> None:
    st = setup_header_env(monkeypatch)
    layer = HeaderLayer(
        type="header", fields=[FieldSpec(key="ADHOC_INFO1", required=False)]
    )
    header_step.render(layer, 0)
    st.session_state["src_ADHOC_INFO1"] = "A"
    header_step.set_field_mapping("ADHOC_INFO1", 0, {"src": "A"})
    st.session_state["adhoc_label_ADHOC_INFO1"] = "Custom"
    st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] = "Custom"
    st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] = False

    def fake_button(self, label, key=None, **k):
        if key == "reset_ADHOC_INFO1" and not self.st.session_state.get("_clicked"):
            self.st.session_state["_clicked"] = True
            return True
        return False

    monkeypatch.setattr(HeaderDummyCol, "button", fake_button)
    header_step.render(layer, 0)
    assert st.session_state.get("reset_src_ADHOC_INFO1") is True
    header_step.render(layer, 0)
    default = "AdHoc1"
    assert st.session_state["header_mapping_0"]["ADHOC_INFO1"] == {}
    assert st.session_state["src_ADHOC_INFO1"] == ""
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == default
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] is True
    assert st.session_state["adhoc_label_ADHOC_INFO1"] == default
    assert not st.session_state.get("reset_src_ADHOC_INFO1")


def test_multiple_resets_independent(monkeypatch: MonkeyPatch) -> None:
    st = setup_header_env(monkeypatch)
    layer = HeaderLayer(
        type="header",
        fields=[
            FieldSpec(key="ADHOC_INFO1", required=False),
            FieldSpec(key="ADHOC_INFO2", required=False),
        ],
    )
    header_step.render(layer, 0)
    st.session_state.update({"src_ADHOC_INFO1": "A", "src_ADHOC_INFO2": "B"})
    header_step.set_field_mapping("ADHOC_INFO1", 0, {"src": "A"})
    header_step.set_field_mapping("ADHOC_INFO2", 0, {"src": "B"})
    st.session_state.update(
        {
            "adhoc_label_ADHOC_INFO1": "Custom1",
            "adhoc_label_ADHOC_INFO2": "Custom2",
            "header_adhoc_headers": {
                "ADHOC_INFO1": "Custom1",
                "ADHOC_INFO2": "Custom2",
            },
            "header_adhoc_autogen": {"ADHOC_INFO1": False, "ADHOC_INFO2": False},
        }
    )

    def fake_button(self, label, key=None, **k):
        stage = self.st.session_state.get("_stage", 0)
        if stage == 0 and key == "reset_ADHOC_INFO1":
            self.st.session_state["_stage"] = 1
            return True
        if stage == 1 and key == "reset_ADHOC_INFO2":
            self.st.session_state["_stage"] = 2
            return True
        return False

    monkeypatch.setattr(HeaderDummyCol, "button", fake_button)

    header_step.render(layer, 0)
    assert st.session_state.get("reset_src_ADHOC_INFO1") is True
    header_step.render(layer, 0)
    default1, default2 = "AdHoc1", "AdHoc2"
    assert st.session_state["header_mapping_0"]["ADHOC_INFO1"] == {}
    assert st.session_state["src_ADHOC_INFO1"] == ""
    assert st.session_state["adhoc_label_ADHOC_INFO1"] == default1
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO1"] == default1
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO1"] is True
    header_step.render(layer, 0)
    header_step.render(layer, 0)
    assert st.session_state["header_mapping_0"]["ADHOC_INFO2"] == {}
    assert st.session_state["src_ADHOC_INFO2"] == ""
    assert st.session_state["adhoc_label_ADHOC_INFO2"] == default2
    assert st.session_state["header_adhoc_headers"]["ADHOC_INFO2"] == default2
    assert st.session_state["header_adhoc_autogen"]["ADHOC_INFO2"] is True
    assert not st.session_state.get("reset_src_ADHOC_INFO1")
    assert not st.session_state.get("reset_src_ADHOC_INFO2")

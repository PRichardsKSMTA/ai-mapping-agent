from app_utils.mapping_utils import suggest_header_mapping


def test_origin_zip_code_full_match() -> None:
    fields = ["Origin Zip Code Full"]
    cols = ["Origin Zip Cd", "Dest Zip Cd"]
    res = suggest_header_mapping(fields, cols)
    assert res["Origin Zip Code Full"]["src"] == "Origin Zip Cd"
    assert res["Origin Zip Code Full"]["confidence"] >= 0.6

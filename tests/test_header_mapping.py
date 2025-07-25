import pytest

from app_utils.mapping_utils import suggest_header_mapping


def test_header_mapping_confidence():
    fields = ["Balance", "Amount"]
    cols = ["balance", "amount"]
    res = suggest_header_mapping(fields, cols)
    assert res["Balance"]["src"] == "balance"
    assert res["Balance"]["confidence"] == 1.0
    assert res["Amount"]["src"] == "amount"
    assert res["Amount"]["confidence"] == 1.0


def test_header_mapping_no_match():
    res = suggest_header_mapping(["Date"], ["amount"])
    assert res["Date"] == {}



"""US-020: read-only helpers — find_text, get_document_outline, list_styles.

Uses the real PII-free 강사카드 fixture so the outline/styles reflect real HWPX.
"""

from pathlib import Path

from hangeul_core.read import find_text, get_document_outline, list_styles

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_find_text_counts_and_addresses():
    res = find_text(FIXTURE, "성명")
    assert res["count"] >= 1
    # at least one match is addressed to a table cell
    assert any("field_id" in o and o["section"] for o in res["cell_occurrences"])
    snippet_ok = any("성명" in o["snippet"] for o in res["cell_occurrences"])
    assert snippet_ok


def test_find_text_empty_query():
    res = find_text(FIXTURE, "")
    assert res["count"] == 0 and res["cell_occurrences"] == []


def test_find_text_absent():
    res = find_text(FIXTURE, "존재하지않는텍스트ZZZ")
    assert res["count"] == 0 and res["cell_occurrences"] == []


def test_get_document_outline_structure():
    out = get_document_outline(FIXTURE)
    assert out["sections"] >= 1
    assert out["tables"] and all({"index", "rows", "cols", "cells"} <= t.keys() for t in out["tables"])
    assert out["cell_count"] >= 1
    assert isinstance(out["fields_by_kind"], dict) and out["fields_by_kind"]


def test_list_styles_reports_charpr_and_parapr():
    st = list_styles(FIXTURE)
    assert st["charPr"] and any(c.get("height") for c in st["charPr"])
    assert "paraPr" in st
    # every charPr entry has an id
    assert all(c["id"] is not None for c in st["charPr"])

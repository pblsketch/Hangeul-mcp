"""US-028: verify_fill / get_table_map / find_cell_by_label (OWN, read-only)."""

from pathlib import Path

from hangeul_core.fill import fill
from hangeul_core.read import find_cell_by_label, get_table_map, verify_fill

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_get_table_map_structure():
    m = get_table_map(FIXTURE)
    assert m["tables"]
    t = m["tables"][0]
    assert {"index", "rows", "cols", "cells"} <= t.keys()
    assert t["cells"]
    c = t["cells"][0]
    assert {"field_id", "row", "col", "col_span", "row_span", "text", "is_empty"} <= c.keys()


def test_find_cell_by_label_resolves_value_cell():
    r = find_cell_by_label(FIXTURE, "성명")
    assert r["label"] == "성명"
    assert r["label_cells"]          # the '성명' label lives in a cell
    assert r["value_field_id"]       # and understand maps it to a value cell


def test_find_cell_by_label_unknown():
    r = find_cell_by_label(FIXTURE, "존재하지않는라벨ZZZ")
    assert r["label_cells"] == [] and r["value_field_id"] is None


def test_verify_fill_present_and_missing(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"성명": "홍길동"}, out)
    r = verify_fill(out, {"성명": "홍길동", "직위": "없는값ZZZ"})
    assert "성명" in r["present"]
    assert "직위" in r["missing"]
    assert r["verified"] is False


def test_verify_fill_all_present(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"성명": "홍길동"}, out)
    r = verify_fill(out, {"성명": "홍길동"})
    assert r["verified"] is True and r["missing"] == []

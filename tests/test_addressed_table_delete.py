"""S4: delete a whole table (보기 box / 네모 박스) with caption guard + XSD gate."""

import zipfile
from pathlib import Path
import pytest

from hangeul_core.addressed import (
    _delete_table_at,
    complete_addressed_template,
    inspect_editable_regions,
)
from hangeul_mcp.tools_file_edit import AddressedEdit, _normalize_addressed_edits

FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="template fixture not present in this checkout"
)


def _tbl_count(path: Path) -> int:
    with zipfile.ZipFile(path) as z:
        return z.read("Contents/section0.xml").decode("utf-8").count("<hp:tbl")


def _complete(edits, out: Path):
    return complete_addressed_template(
        FIXTURE, _normalize_addressed_edits([AddressedEdit(**e) for e in edits]), out
    )


def test_delete_bogi_table_passes_gate_and_drops_one_table(tmp_path):
    out = tmp_path / "no_bogi.hwpx"
    before = _tbl_count(FIXTURE)
    res = _complete([{"target": "t2", "operation": "delete_table"}], out)
    assert res["ok"] and res["state"] == "complete", res  # XSD gate passed
    assert _tbl_count(out) == before - 1
    # the other two tables survive (header title + Q5 box).
    regions = inspect_editable_regions(out, compact=True)
    text = str(regions)
    assert "학년" in text  # header table intact
    assert "원자핵" in text  # Q5 box (t3) intact


def test_delete_q5_box(tmp_path):
    out = tmp_path / "no_q5box.hwpx"
    res = _complete([{"target": "t3", "operation": "delete_table"}], out)
    assert res["ok"], res
    regions = str(inspect_editable_regions(out, compact=True))
    assert "원자핵" not in regions  # Q5 box removed


def test_delete_unknown_table_fails_closed(tmp_path):
    out = tmp_path / "noop.hwpx"
    res = _complete([{"target": "t99", "operation": "delete_table"}], out)
    assert not res["ok"]


def test_caption_run_in_same_paragraph_survives():
    # A paragraph holding a caption run AND the table run: deleting the table
    # must keep the caption (never delete more than addressed).
    section = (
        "<hp:p><hp:run charPrIDRef=\"5\"><hp:t>표 1. 캡션</hp:t></hp:run>"
        "<hp:run charPrIDRef=\"6\"><hp:tbl rowCnt=\"1\" colCnt=\"1\">"
        "<hp:tr><hp:tc><hp:cellAddr colAddr=\"0\" rowAddr=\"0\"/>"
        "<hp:subList><hp:p><hp:run charPrIDRef=\"6\"><hp:t>셀</hp:t></hp:run></hp:p></hp:subList>"
        "</hp:tc></hp:tr></hp:tbl></hp:run></hp:p>"
    )
    result = _delete_table_at(section, 1)
    assert result is not None
    new_section, _removed = result
    assert "<hp:tbl" not in new_section
    assert "표 1. 캡션" in new_section  # caption preserved
    assert new_section.count("<hp:p>") == 1  # paragraph kept (not emptied away)


def test_table_only_paragraph_is_removed():
    section = (
        "<hp:p><hp:run charPrIDRef=\"6\"><hp:tbl rowCnt=\"1\" colCnt=\"1\">"
        "<hp:tr><hp:tc><hp:cellAddr colAddr=\"0\" rowAddr=\"0\"/>"
        "<hp:subList><hp:p><hp:run charPrIDRef=\"6\"><hp:t>셀</hp:t></hp:run></hp:p></hp:subList>"
        "</hp:tc></hp:tr></hp:tbl></hp:run></hp:p>"
    )
    result = _delete_table_at(section, 1)
    assert result is not None
    new_section, _ = result
    assert new_section == ""  # table-only paragraph dropped entirely

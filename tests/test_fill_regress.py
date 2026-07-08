"""Regression tests for edge cases found by codex QA review."""

import re
from pathlib import Path

from hangeul_core.fill import _find_cell_span, fill
from hangeul_core.owpml import HwpxPackage

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def _section(hwpx) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")


def test_find_cell_span_does_not_spill_into_sibling_table():
    """A missing cell in the target table must NOT match a sibling table's cell."""
    section = (
        "<hs:sec>"
        '<hp:tbl><hp:tr><hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/>'
        '<hp:p id="1"><hp:run><hp:t>A</hp:t></hp:run></hp:p></hp:tc></hp:tr></hp:tbl>'
        '<hp:tbl><hp:tr><hp:tc><hp:cellAddr rowAddr="9" colAddr="9"/>'
        '<hp:p id="2"><hp:run><hp:t>B</hp:t></hp:run></hp:p></hp:tc></hp:tr></hp:tbl>'
        "</hs:sec>"
    )
    # table 1 has no (9,9) cell; must return None, not table 2's (9,9)="B".
    assert _find_cell_span(section, 1, 9, 9) is None
    # table 2's own (9,9) still resolves.
    assert _find_cell_span(section, 2, 9, 9) is not None


def test_crlf_value_leaves_no_raw_cr_in_text_nodes(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"소속": "A\r\nB"}, out)
    sec = _section(out)
    for m in re.finditer(r"<hp:t>(.*?)</hp:t>", sec, re.S):
        inner = m.group(1)
        assert "\r" not in inner and "\n" not in inner
    assert "A" in sec and "B" in sec


def test_inline_value_with_newline_has_no_raw_break(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"학력": "line1\nline2"}, out)
    sec = _section(out)
    for m in re.finditer(r"<hp:t>(.*?)</hp:t>", sec, re.S):
        assert "\n" not in m.group(1) and "\r" not in m.group(1)

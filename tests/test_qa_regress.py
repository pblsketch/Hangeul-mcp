"""Regression tests for the second-round codex QA findings.

HIGH: multi-section fill, inline marker double-marker.
MED:  merged-cell covered-coordinate mapping, .hwp conversion error wrapping.
"""

import zipfile
from pathlib import Path

import pytest

from hangeul_core.convert import hwp_to_hwpx
from hangeul_core.fill import fill
from hangeul_core.hwp import HwpBridge
from hangeul_core.owpml import HwpxPackage
from hangeul_core.schema import Cell
from hangeul_core.understand import _occupancy, _value_cell

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"
_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _make_multi_section_hwpx(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}/>'.encode()
    section1 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="1"><hp:run><hp:t>이름</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="2"><hp:run><hp:t/></hp:run></hp:p></hp:subList></hp:tc>'
        "</hp:tr></hp:tbl></hs:sec>"
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)
        z.writestr("Contents/section1.xml", section1)


def test_multi_section_fill(tmp_path):
    src = tmp_path / "multi.hwpx"
    out = tmp_path / "out.hwpx"
    _make_multi_section_hwpx(src)
    res = fill(src, {"이름": "홍길동"}, out)
    assert res.skipped == []
    sec1 = HwpxPackage.open(out).read("Contents/section1.xml").decode("utf-8")
    assert "홍길동" in sec1


def test_inline_marker_no_double_when_value_has_marker(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"학력": "∘ ABC"}, out)  # value already carries a marker
    sec = HwpxPackage.open(out).read("Contents/section0.xml").decode("utf-8")
    assert "∘ ABC" in sec
    assert "∘ ∘" not in sec


def test_occupancy_resolves_merged_covered_coordinate():
    label = Cell(table=1, row=1, col=0, text="라벨", is_empty=False)
    merged = Cell(table=1, row=0, col=1, col_span=1, row_span=2, text="", is_empty=True)
    grid = _occupancy([label, merged])
    # label's right coordinate (1,1) is a *covered* coord of the merged cell
    assert _value_cell(label, grid) is merged


def test_convert_wraps_com_exception_as_runtimeerror(monkeypatch, tmp_path):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))

    def boom(self, *args, **kwargs):
        raise ValueError("dispatch failed")

    monkeypatch.setattr(HwpBridge, "connect", boom)
    existing = tmp_path / "x.hwp"
    existing.write_bytes(b"HWP binary placeholder")
    with pytest.raises(RuntimeError, match="conversion via Hangul COM failed"):
        hwp_to_hwpx(str(existing))

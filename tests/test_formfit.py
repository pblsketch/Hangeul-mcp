"""US-017: form-fit overflow estimate (Tier1) + opt-in auto-fit (Tier2).

The estimate is a documented heuristic (no renderer); tests pin the arithmetic
on synthetic cell widths and font heights, and verify auto-fit shrinks only the
filled run's charPr, bounded by a floor, and is a no-op when disabled or fitting.
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from hangeul_core.fill import fill
from hangeul_core.formfit import analyze_formfit, estimate_width
from hangeul_core.owpml import HwpxPackage

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)
# width 3000 HWPUNIT, font height 1000 (10pt) -> available = 3000-280 = 2720
_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
    '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">'
    '<hh:refList><hh:charProperties itemCnt="1">'
    '<hh:charPr id="0" height="1000" textColor="#000000">'
    '<hh:spacing hangul="0" latin="0"/></hh:charPr>'
    '</hh:charProperties></hh:refList></hh:head>'
).encode()


def _cell(addr_col: str, inner: str, width: int = 3000) -> str:
    return (
        '<hp:tc>'
        f'<hp:cellAddr rowAddr="0" colAddr="{addr_col}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="1966"/>'
        '<hp:subList>' + inner + '</hp:subList></hp:tc>'
    )


def _build(dst: Path) -> None:
    label = '<hp:p id="1"><hp:run charPrIDRef="0"><hp:t>성명</hp:t></hp:run></hp:p>'
    value = '<hp:p id="2"><hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p>'
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        + _cell("0", label) + _cell("1", value) +
        '</hp:tr></hp:tbl></hs:sec>'
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", _HEADER)
        z.writestr("Contents/section0.xml", section0)


def _header(hwpx) -> bytes:
    return HwpxPackage.open(hwpx).read("Contents/header.xml")


def test_estimate_width_char_classes():
    assert estimate_width("가나", 1000) == 2000        # 2 Hangul x 1.0
    assert estimate_width("ab", 1000) == 1000          # 2 latin x 0.5


def test_analyze_formfit_flags_overflow(tmp_path):
    src = tmp_path / "ff.hwpx"
    _build(src)
    over = analyze_formfit(src, {"성명": "가나다라"})   # 4000 > 2720
    assert over["checked"] == 1 and over["warnings"]
    w = over["warnings"][0]
    assert w["field_id"] == "t1.r0.c1" and w["ratio"] > 1.0
    fit = analyze_formfit(src, {"성명": "가나"})          # 2000 < 2720
    assert fit["warnings"] == []


def test_auto_fit_shrinks_only_when_overflow(tmp_path):
    src = tmp_path / "ff.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "가나다라"}, out, auto_fit=True)  # ratio avail/est=0.68
    assert res.shrunk and res.shrunk[0]["field_id"] == "t1.r0.c1"
    assert res.shrunk[0]["scale"] == 0.68
    # a new, smaller charPr clone was appended and referenced
    assert _header(out) != _header(src)
    assert 'itemCnt="2"' in _header(out).decode("utf-8")


def test_auto_fit_respects_floor(tmp_path):
    src = tmp_path / "ff.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "가나다라마바사아자차"}, out, auto_fit=True)  # far over -> floor
    assert res.shrunk[0]["scale"] == 0.6


def test_auto_fit_noop_when_fits(tmp_path):
    src = tmp_path / "ff.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "가나"}, out, auto_fit=True)  # fits
    assert res.shrunk == []
    assert _header(out) == _header(src)  # header untouched


def test_auto_fit_disabled_by_default_no_header_change(tmp_path):
    src = tmp_path / "ff.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "가나다라마바사아자차"}, out)  # auto_fit off
    assert res.shrunk == []
    assert _header(out) == _header(src)  # pure fill, formatting untouched


def test_formfit_byte_preservation_and_wellformed(tmp_path):
    src = tmp_path / "ff.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"성명": "가나다라"}, out, auto_fit=True)
    a, b = HwpxPackage.open(src), HwpxPackage.open(out)
    for name in a.names():
        if name in ("Contents/section0.xml", "Contents/header.xml"):
            continue
        assert a.read(name) == b.read(name), f"entry changed: {name}"
    with zipfile.ZipFile(out) as z:
        assert z.infolist()[0].filename == "mimetype"
        sec_bytes = z.read("Contents/section0.xml")
    ET.fromstring(sec_bytes)
    ET.fromstring(b.read("Contents/header.xml"))  # header still well-formed

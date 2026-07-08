"""US-014: 형광펜(markpen) placeholder detection + highlight-preserving fill."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from hangeul_core.fill import fill
from hangeul_core.markpen import detect_markpen
from hangeul_core.owpml import HwpxPackage

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _build(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        # table: label cell "학년" + highlighted value cell "2학년"
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="1"><hp:run charPrIDRef="0"><hp:t>학년</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="2"><hp:run charPrIDRef="0"><hp:t>'
        '<hp:markpenBegin color="#FFFF00"/>2학년<hp:markpenEnd/>'
        '</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        # body: "학교명 [예시학교]" highlighted
        '<hp:p id="3"><hp:run charPrIDRef="0"><hp:t>학교명 '
        '<hp:markpenBegin color="#00FF00"/>예시학교<hp:markpenEnd/></hp:t></hp:run></hp:p>'
        "</hs:sec>"
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


def _section(hwpx) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")


def test_detect_markpen_regions_and_labels(tmp_path):
    src = tmp_path / "m.hwpx"
    _build(src)
    fields = detect_markpen(src)
    assert len(fields) == 2  # two distinct highlighted regions
    by_label = {f.label: f for f in fields}
    assert by_label["학년"].template == "2학년"       # label from left cell
    assert by_label["학교명"].template == "예시학교"    # label from in-node prefix
    assert all(f.kind == "markpen" for f in fields)


def test_fill_markpen_preserves_highlight(tmp_path):
    src = tmp_path / "m.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"학년": "3학년", "학교명": "세종초"}, out)
    sec = _section(out)
    # new values present, old highlighted samples gone
    assert "3학년" in sec and "세종초" in sec
    assert ">2학년<" not in sec  # old sample text replaced
    # highlight tags kept around BOTH replaced values
    assert '<hp:markpenBegin color="#FFFF00"/>3학년<hp:markpenEnd/>' in sec
    assert '<hp:markpenBegin color="#00FF00"/>세종초<hp:markpenEnd/>' in sec
    assert {f["label"] for f in res.filled} == {"학년", "학교명"}


def test_markpen_byte_preservation_and_wellformed(tmp_path):
    src = tmp_path / "m.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"학년": "3학년"}, out)
    a, b = HwpxPackage.open(src), HwpxPackage.open(out)
    for name in a.names():
        if name == "Contents/section0.xml":
            continue
        assert a.read(name) == b.read(name), f"entry changed: {name}"
    with zipfile.ZipFile(out) as z:
        assert z.infolist()[0].filename == "mimetype"
        sec_bytes = z.read("Contents/section0.xml")
    ET.fromstring(sec_bytes)
    assert sec_bytes.lstrip().startswith(
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"'
    )

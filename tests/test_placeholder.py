"""US-013: {placeholder} global replace + run-split token handling.

Golden + regression coverage for the section-wide locate/splice primitive:
tokens in body text, in a table cell, split across runs, and duplicated.
Byte-preservation of untouched entries is asserted the same way as test_fill.
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from hangeul_core.fill import fill
from hangeul_core.locate import detect_placeholders, find_placeholder_names
from hangeul_core.owpml import HwpxPackage

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _run(t: str, cid: str = "0") -> str:
    return f'<hp:run charPrIDRef="{cid}"><hp:t>{t}</hp:t></hp:run>'


def _build(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    # p1: token fully inside one <hp:t>; p2: token {반} SPLIT across three runs;
    # a table cell holds {담당자}; p3 duplicates {학교명}; an unprovided {미정} stays.
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="1">' + _run("학교: {학교명} 입니다") + "</hp:p>"
        '<hp:p id="2">' + _run("우리 {") + _run("반") + _run("}") + "</hp:p>"
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr><hp:tc>'
        '<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="3">' + _run("담당: {담당자}") + "</hp:p></hp:subList>"
        "</hp:tc></hp:tr></hp:tbl>"
        '<hp:p id="4">' + _run("{학교명} / {미정}") + "</hp:p>"
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


def test_detect_finds_all_token_names(tmp_path):
    src = tmp_path / "ph.hwpx"
    _build(src)
    names = {f.label for f in detect_placeholders(src)}
    assert names == {"학교명", "반", "담당자", "미정"}
    # the split token is only detectable via cross-<hp:t> concatenation
    assert "반" in find_placeholder_names(_section(src))


def test_fill_replaces_all_occurrences_incl_split_and_table(tmp_path):
    src = tmp_path / "ph.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"학교명": "세종초", "반": "3-2", "담당자": "홍길동"}, out)
    sec = _section(out)
    # braces gone, values present, split token collapsed correctly
    assert "{학교명}" not in sec and "{반}" not in sec and "{담당자}" not in sec
    assert sec.count("세종초") == 2  # duplicated token replaced everywhere
    assert "3-2" in sec and "홍길동" in sec
    assert "우리 3-2" in sec  # split token joined into leading run's text
    # unprovided token stays intact
    assert "{미정}" in sec
    assert {f["label"] for f in res.filled} == {"학교명", "반", "담당자"}


def test_unknown_value_key_is_skipped(tmp_path):
    src = tmp_path / "ph.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"없는것": "X"}, out)
    assert res.filled == [] and res.skipped


def test_placeholder_byte_preservation_and_wellformed(tmp_path):
    src = tmp_path / "ph.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"학교명": "세종초"}, out)
    a, b = HwpxPackage.open(src), HwpxPackage.open(out)
    for name in a.names():
        if name == "Contents/section0.xml":
            continue
        assert a.read(name) == b.read(name), f"entry changed: {name}"
    with zipfile.ZipFile(out) as z:
        assert z.infolist()[0].filename == "mimetype"
        assert z.infolist()[0].compress_type == zipfile.ZIP_STORED
        sec_bytes = z.read("Contents/section0.xml")
    ET.fromstring(sec_bytes)  # well-formed
    assert sec_bytes.lstrip().startswith(
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"'
    )

"""US-022: search_and_replace / batch_replace (OWN, byte-preserving)."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from hangeul_core.edit import batch_replace, search_and_replace
from hangeul_core.locate import replace_literals
from hangeul_core.owpml import HwpxPackage

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _run(t: str) -> str:
    return f'<hp:run charPrIDRef="0"><hp:t>{t}</hp:t></hp:run>'


def _build(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="1">' + _run("2025년 계획 (2025 기준)") + "</hp:p>"
        # "서울시" split across two runs
        '<hp:p id="2">' + _run("서울") + _run("시 교육청") + "</hp:p>"
        # cell boundary: "울시" must NOT be joined across a cell edge
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="3">'
        + _run("끝은 울") + "</hp:p></hp:subList></hp:tc>"
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:subList><hp:p id="4">'
        + _run("시작") + "</hp:p></hp:subList></hp:tc>"
        "</hp:tr></hp:tbl></hs:sec>"
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


def _section(hwpx) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")


def test_replace_literals_run_split_and_boundary():
    section = (
        '<hp:p><hp:run><hp:t>서울</hp:t></hp:run><hp:run><hp:t>시</hp:t></hp:run></hp:p>'
    )
    out, counts = replace_literals(section, {"서울시": "세종시"})
    assert counts == {"서울시": 1}
    assert "".join(ET.fromstring("<r xmlns:hp='x'>" + out + "</r>").itertext()) == "세종시"


def test_search_and_replace_counts_and_value(tmp_path):
    src = tmp_path / "s.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = search_and_replace(src, "2025", "2026", out)
    assert res.counts == {"2025": 2} and res.total == 2
    assert "2026년 계획 (2026 기준)" in _section(out)


def test_batch_replace_multi_and_split(tmp_path):
    src = tmp_path / "s.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = batch_replace(src, {"서울시": "세종시", "2025": "2026"}, out)
    sec = _section(out)
    assert res.counts.get("서울시") == 1 and res.counts.get("2025") == 2
    # split "서울"+"시" -> "세종시"; join left run, empty the second
    txt = "".join(__import__("re").findall(r"<hp:t>(.*?)</hp:t>", sec))
    assert "세종시 교육청" in txt


def test_no_cross_cell_bleed(tmp_path):
    src = tmp_path / "s.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    # "울시작" only exists if the cell boundary ("끝은 울" | "시작") is bridged —
    # the boundary guard must prevent it (it appears nowhere within one paragraph).
    res = search_and_replace(src, "울시작", "XX", out)
    assert res.total == 0
    assert "XX" not in _section(out)


def test_overlap_longest_wins(tmp_path):
    src = tmp_path / "s.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    # both "2025" and "2025년" could match at the same start; longest wins
    res = batch_replace(src, {"2025": "AA", "2025년": "BB"}, out)
    sec = _section(out)
    assert "BB 계획" in sec           # 2025년 -> BB (longest at that position)
    assert res.counts.get("2025년") == 1


def test_edit_byte_preservation_and_wellformed(tmp_path):
    src = tmp_path / "s.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    search_and_replace(src, "2025", "2026", out)
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

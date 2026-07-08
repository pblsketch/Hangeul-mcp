"""US-015: 체크박스(☑/□) detection + exclusive/multi toggle, byte-preserving."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from hangeul_core.checkbox import detect_checkbox
from hangeul_core.fill import fill
from hangeul_core.owpml import HwpxPackage

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _cell(inner_ts: str) -> str:
    return (
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr><hp:tc>'
        '<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="1">' + inner_ts + "</hp:p></hp:subList>"
        "</hp:tc></hp:tr></hp:tbl>"
    )


def _write(dst: Path, table_xml: str) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        + table_xml
        + "</hs:sec>"
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


def _simple(dst: Path) -> None:
    run = '<hp:run charPrIDRef="0"><hp:t>평가방법 ☑논술 □구술 □실기</hp:t></hp:run>'
    _write(dst, _cell(run))


def _split(dst: Path) -> None:
    # "□구술" split across three <hp:t> nodes (glyph isolated in its own run)
    runs = (
        '<hp:run charPrIDRef="0"><hp:t>평가방법 ☑논술 </hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t>□</hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t>구술 □실기</hp:t></hp:run>'
    )
    _write(dst, _cell(runs))


def _section(hwpx) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")


def test_detect_checkbox_options(tmp_path):
    src = tmp_path / "c.hwpx"
    _simple(src)
    fields = detect_checkbox(src)
    assert len(fields) == 1
    f = fields[0]
    assert f.kind == "checkbox" and f.label == "평가방법"
    assert f.options == [
        {"label": "논술", "checked": True},
        {"label": "구술", "checked": False},
        {"label": "실기", "checked": False},
    ]


def test_fill_checkbox_exclusive(tmp_path):
    src = tmp_path / "c.hwpx"
    _simple(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"평가방법": "구술"}, out)
    sec = _section(out)
    assert "□논술 ☑구술 □실기" in sec
    assert any(f["label"] == "평가방법" for f in res.filled)


def test_fill_checkbox_multi_non_exclusive(tmp_path):
    src = tmp_path / "c.hwpx"
    _simple(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"평가방법": "실기"}, out, checkbox_exclusive=False)
    sec = _section(out)
    assert "☑논술 □구술 ☑실기" in sec  # 논술 stays checked, 실기 added


def test_fill_checkbox_split_across_runs(tmp_path):
    src = tmp_path / "c.hwpx"
    _split(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"평가방법": "구술"}, out)
    txt = "".join(
        __import__("re").findall(r"<hp:t>(.*?)</hp:t>", _section(out))
    )
    assert txt == "평가방법 □논술 ☑구술 □실기"


def test_fill_checkbox_unknown_option_skipped(tmp_path):
    src = tmp_path / "c.hwpx"
    _simple(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"평가방법": "면접"}, out)
    assert res.filled == [] and res.skipped


def test_checkbox_idempotent_recheck(tmp_path):
    src = tmp_path / "c.hwpx"
    _simple(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"평가방법": "논술"}, out)  # 논술 already checked
    assert "☑논술 □구술 □실기" in _section(out)


def test_checkbox_byte_preservation_and_wellformed(tmp_path):
    src = tmp_path / "c.hwpx"
    _simple(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"평가방법": "구술"}, out)
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

"""Regression: analyze must read <hp:t> text wrapped in inline markup (highlight).

Found on a real 평가 운영 계획 template whose placeholder examples are wrapped in
<hp:markpenBegin> (yellow highlight). ElementTree carries that text as the *tail*
of the markpen child, so reading only `<hp:t>.text` made the cell look empty.
"""

import zipfile
from pathlib import Path

from hangeul_core.analyze import analyze

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _hwpx_with_markpen_cell(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr><hp:tc>'
        '<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="1"><hp:run><hp:t>'
        '<hp:markpenBegin color="#FFFF00"/>2학년<hp:markpenEnd/>'
        "</hp:t></hp:run></hp:p></hp:subList>"
        "</hp:tc></hp:tr></hp:tbl></hs:sec>"
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


def test_analyze_reads_highlighted_text(tmp_path):
    src = tmp_path / "markpen.hwpx"
    _hwpx_with_markpen_cell(src)
    cell = analyze(src).cell("t1.r0.c0")
    assert cell is not None
    assert cell.text == "2학년"
    assert cell.is_empty is False

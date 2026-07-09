"""US-031: checkbox label derivation (above/header + descriptive fallback) + type."""

import zipfile
from pathlib import Path

from hangeul_core.checkbox import detect_checkbox

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _tc(row: str, col: str, text: str) -> str:
    return (
        '<hp:tc>'
        f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p id="1"><hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run></hp:p></hp:subList>'
        '</hp:tc>'
    )


def _write(dst: Path, table_xml: str) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        + table_xml + "</hs:sec>"
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


def test_descriptive_fallback_label(tmp_path):
    # single cell, leading glyph, 3 section titles, no left/above label
    txt = "□개인정보 수집·이용 동의 □개인정보 제3자 제공 고지 □사진·영상 촬영 및 활용 동의"
    src = tmp_path / "a.hwpx"
    _write(src, '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>' + _tc("0", "0", txt) + "</hp:tr></hp:tbl>")
    f = detect_checkbox(src)[0]
    assert "선택0" not in f.label and "선택1" not in f.label  # not a bare 선택N
    assert "개인정보 수집·이용 동의" in f.label and f.label.endswith("중 선택")
    assert f.template == "select"
    assert [o["label"] for o in f.options] == [
        "개인정보 수집·이용 동의", "개인정보 제3자 제공 고지", "사진·영상 촬영 및 활용 동의",
    ]


def test_yes_no_type(tmp_path):
    src = tmp_path / "b.hwpx"
    _write(src, '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>' + _tc("0", "0", "동의 여부 ☑예 □아니요") + "</hp:tr></hp:tbl>")
    f = detect_checkbox(src)[0]
    assert f.label == "동의 여부" and f.template == "yes_no"


def test_label_from_header_above(tmp_path):
    # header cell above the checkbox cell in the same column
    table = (
        '<hp:tbl rowCnt="2" colCnt="1"><hp:tr>' + _tc("0", "0", "동의 항목") + "</hp:tr>"
        '<hp:tr>' + _tc("1", "0", "□항목A □항목B") + "</hp:tr></hp:tbl>"
    )
    src = tmp_path / "c.hwpx"
    _write(src, table)
    fields = detect_checkbox(src)
    f = [x for x in fields if x.options][0]
    assert f.label == "동의 항목"

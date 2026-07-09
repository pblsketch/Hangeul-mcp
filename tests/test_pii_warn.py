"""US-033: PII is always flagged in fill (warn-first), masked flag reflects mode.

All PII values below are SYNTHETIC (fake).
"""

import zipfile
from pathlib import Path

from hangeul_core.fill import fill

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _form(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="1"><hp:run charPrIDRef="0"><hp:t>주민번호</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="2"><hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl></hs:sec>'
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


def test_pii_warned_even_without_masking(tmp_path):
    src = tmp_path / "p.hwpx"
    _form(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"주민번호": "901231-1234567"}, out)  # mask_pii OFF
    assert res.masked == []                       # not masked
    assert res.pii_warnings                        # but flagged
    w = res.pii_warnings[0]
    assert w["key"] == "주민번호" and w["masked"] is False
    assert "resident_registration_number" in w["types"]


def test_pii_warning_marks_masked_true_when_masking(tmp_path):
    src = tmp_path / "p.hwpx"
    _form(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"주민번호": "901231-1234567"}, out, mask_pii=True)
    assert res.pii_warnings and res.pii_warnings[0]["masked"] is True
    assert res.masked  # masked list also populated


def test_no_pii_no_warning(tmp_path):
    src = tmp_path / "p.hwpx"
    _form(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"주민번호": "해당없음"}, out)
    assert res.pii_warnings == []

"""US-018: PII detection + masking gate. All PII below is SYNTHETIC (fake)."""

import zipfile
from pathlib import Path

from hangeul_core.fill import fill
from hangeul_core.owpml import HwpxPackage
from hangeul_core.pii import mask_value, scan_text

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def test_scan_text_detects_types():
    text = "홍길동 901231-1234567 010-1234-5678 hong@example.com 1234-5678-9012-3456"
    types = {f["type"] for f in scan_text(text)}
    assert "resident_registration_number" in types
    assert "phone" in types
    assert "email" in types
    assert "credit_card" in types


def test_mask_value_formats():
    assert mask_value("901231-1234567") == "901231-1******"
    assert mask_value("010-1234-5678") == "010-****-5678"
    assert mask_value("1234-5678-9012-3456") == "1234-****-****-3456"
    assert mask_value("hong@example.com") == "h***@example.com"


def test_no_false_positive_on_plain_text():
    assert scan_text("서울특별시 강남구 3층") == []


def _empty_cell_form(dst: Path) -> None:
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


def _section(hwpx) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")


def test_fill_mask_pii_masks_values(tmp_path):
    src = tmp_path / "p.hwpx"
    _empty_cell_form(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"주민번호": "901231-1234567"}, out, mask_pii=True)
    sec = _section(out)
    assert "901231-1******" in sec
    assert "901231-1234567" not in sec
    assert res.masked and res.masked[0]["types"] == ["resident_registration_number"]


def test_fill_without_mask_pii_is_unchanged(tmp_path):
    src = tmp_path / "p.hwpx"
    _empty_cell_form(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"주민번호": "901231-1234567"}, out)  # mask_pii off
    assert "901231-1234567" in _section(out)
    assert res.masked == []

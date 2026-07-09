"""US-026: mail_merge — bulk byte-preserving fill from one template + records."""

import zipfile
from pathlib import Path

from hangeul_core.mailmerge import mail_merge
from hangeul_core.owpml import HwpxPackage
from hangeul_core.validate import validate_hwpx

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _template(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="1"><hp:run charPrIDRef="0"><hp:t>성명</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p id="2"><hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '<hp:p id="3"><hp:run charPrIDRef="0"><hp:t>학교: {학교명}</hp:t></hp:run></hp:p>'
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


def test_mail_merge_produces_one_file_per_record(tmp_path):
    tpl = tmp_path / "t.hwpx"
    _template(tpl)
    records = [
        {"성명": "홍길동", "학교명": "세종초"},
        {"성명": "김철수", "학교명": "한글중"},
        {"성명": "이영희", "학교명": "누리고"},
    ]
    res = mail_merge(tpl, records, tmp_path / "out")
    assert res["count"] == 3 and len(res["outputs"]) == 3
    for i, rec in enumerate(records, start=1):
        out = res["outputs"][i - 1]["out_path"]
        assert Path(out).exists()
        sec = _section(out)
        assert rec["성명"] in sec and rec["학교명"] in sec
        assert "{학교명}" not in sec  # placeholder replaced per record


def test_mail_merge_outputs_are_byte_preserving_and_valid(tmp_path):
    tpl = tmp_path / "t.hwpx"
    _template(tpl)
    res = mail_merge(tpl, [{"성명": "홍길동", "학교명": "세종초"}], tmp_path / "out")
    out = res["outputs"][0]["out_path"]
    a, b = HwpxPackage.open(tpl), HwpxPackage.open(out)
    for name in a.names():
        if name == "Contents/section0.xml":
            continue
        assert a.read(name) == b.read(name), f"entry changed: {name}"
    assert validate_hwpx(out)["valid"] is True


def test_mail_merge_summary_counts(tmp_path):
    tpl = tmp_path / "t.hwpx"
    _template(tpl)
    res = mail_merge(tpl, [{"성명": "홍길동", "학교명": "세종초"}], tmp_path / "out")
    o = res["outputs"][0]
    assert o["filled"] >= 2 and o["skipped"] == 0  # 성명 cell + 학교명 placeholder

"""US-016: 누름틀(form field) headless detection + fill (no COM)."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from hangeul_core.fill import fill
from hangeul_core.formfield import detect_form_fields, form_field_names
from hangeul_core.owpml import HwpxPackage

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _field(begin: str, text_run: str, end: str) -> str:
    return (
        '<hp:run><hp:ctrl>' + begin + '</hp:ctrl></hp:run>'
        + text_run
        + '<hp:run><hp:ctrl>' + end + '</hp:ctrl></hp:run>'
    )


def _build(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    # 1) named-by-attribute field with existing text
    f1 = _field(
        '<hp:fieldBegin id="1" type="CLICKHERE" name="성명"/>',
        '<hp:run charPrIDRef="0"><hp:t>이름입력</hp:t></hp:run>',
        '<hp:fieldEnd id="1"/>',
    )
    # 2) empty field (self-closing <hp:t/>)
    f2 = _field(
        '<hp:fieldBegin id="2" type="CLICKHERE" name="학교"/>',
        '<hp:run charPrIDRef="0"><hp:t/></hp:run>',
        '<hp:fieldEnd id="2"/>',
    )
    # 3) name carried in a parameterset child (fallback path), not an attribute
    f3 = _field(
        '<hp:fieldBegin id="3" type="CLICKHERE">'
        '<hp:parameterset><hp:stringParam name="FieldName" value="주소"/></hp:parameterset>'
        "</hp:fieldBegin>",
        '<hp:run charPrIDRef="0"><hp:t>주소입력</hp:t></hp:run>',
        '<hp:fieldEnd id="3"/>',
    )
    # 4) hyperlink field — must NOT be treated as fillable
    f4 = _field(
        '<hp:fieldBegin id="4" type="HYPERLINK" name="링크"/>',
        '<hp:run charPrIDRef="0"><hp:t>http://x</hp:t></hp:run>',
        '<hp:fieldEnd id="4"/>',
    )
    # 5) a SECOND field named 성명 -> filling "성명" must fill both
    f5 = _field(
        '<hp:fieldBegin id="5" type="CLICKHERE" name="성명"/>',
        '<hp:run charPrIDRef="0"><hp:t>이름2</hp:t></hp:run>',
        '<hp:fieldEnd id="5"/>',
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        f'<hp:p id="1">{f1}</hp:p><hp:p id="2">{f2}</hp:p>'
        f'<hp:p id="3">{f3}</hp:p><hp:p id="4">{f4}</hp:p><hp:p id="5">{f5}</hp:p>'
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


def test_detect_form_fields(tmp_path):
    src = tmp_path / "f.hwpx"
    _build(src)
    names = form_field_names(src)
    assert names == ["성명", "학교", "주소"]  # hyperlink excluded, dupes deduped
    fields = {f.label: f for f in detect_form_fields(src)}
    assert fields["성명"].kind == "form_field"
    assert fields["성명"].template == "이름입력"


def test_fill_form_field_headless_preserves_controls(tmp_path):
    src = tmp_path / "f.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "홍길동", "field:학교": "세종초", "주소": "서울"}, out)
    sec = _section(out)
    # values in, old guide text gone; controls intact
    assert "홍길동" in sec and "세종초" in sec and "서울" in sec
    assert "이름입력" not in sec and "주소입력" not in sec
    assert sec.count('<hp:fieldBegin') == 5 and sec.count('<hp:fieldEnd') == 5
    # both 성명 fields filled (all occurrences)
    assert sec.count("홍길동") == 2
    assert {f["label"] for f in res.filled} == {"성명", "학교", "주소"}


def test_hyperlink_not_fillable(tmp_path):
    src = tmp_path / "f.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"링크": "hacked"}, out)
    assert "hacked" not in _section(out)
    assert res.filled == [] and res.skipped  # not a fillable field


def test_split_run_field_value_no_stale_tail(tmp_path):
    # a field whose display value is split across TWO runs must not leak the tail
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    field = _field(
        '<hp:fieldBegin id="1" type="CLICKHERE" name="성명"/>',
        '<hp:run charPrIDRef="0"><hp:t>이름</hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t>예시</hp:t></hp:run>',  # split value
        '<hp:fieldEnd id="1"/>',
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        f'<hp:p id="1">{field}</hp:p></hs:sec>'
    ).encode()
    src = tmp_path / "s.hwpx"
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)
    out = tmp_path / "o.hwpx"
    fill(src, {"성명": "홍길동"}, out)
    import re as _re
    txt = "".join(_re.findall(r"<hp:t>(.*?)</hp:t>", _section(out)))
    assert txt == "홍길동"          # not "홍길동예시" (stale tail cleared)
    assert "예시" not in _section(out)


def test_formfield_byte_preservation_and_wellformed(tmp_path):
    src = tmp_path / "f.hwpx"
    _build(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"성명": "홍길동"}, out)
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

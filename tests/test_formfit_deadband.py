"""US-030: form-fit deadband (no micro-shrink) + warn-first overflow reporting."""

import zipfile
from pathlib import Path

from hangeul_core.fill import fill

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)
_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
    '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">'
    '<hh:refList><hh:charProperties itemCnt="1">'
    '<hh:charPr id="0" height="1000" textColor="#000000">'
    '<hh:spacing hangul="0" latin="0"/></hh:charPr>'
    '</hh:charProperties></hh:refList></hh:head>'
).encode()


def _cell(addr_col: str, inner: str, width: int) -> str:
    return (
        '<hp:tc>'
        f'<hp:cellAddr rowAddr="0" colAddr="{addr_col}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="1966"/>'
        '<hp:subList>' + inner + '</hp:subList></hp:tc>'
    )


def _build(dst: Path, value_width: int) -> None:
    label = '<hp:p id="1"><hp:run charPrIDRef="0"><hp:t>성명</hp:t></hp:run></hp:p>'
    value = '<hp:p id="2"><hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p>'
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        + _cell("0", label, 3000) + _cell("1", value, value_width) +
        '</hp:tr></hp:tbl></hs:sec>'
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", _HEADER)
        z.writestr("Contents/section0.xml", section0)


def test_marginal_overflow_not_shrunk(tmp_path):
    # value cell avail = 3040-280 = 2760; value 3 Hangul = 3000 -> ratio 1.087.
    # within deadband? 1.087 > 1.05 so it WOULD shrink; make it truly marginal:
    # avail 2900 (width 3180), value 3000 -> ratio 1.034 < 1.05 -> NO shrink.
    src = tmp_path / "a.hwpx"
    _build(src, value_width=3180)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "가나다"}, out, auto_fit=True)  # ratio ~1.03
    assert res.shrunk == []                    # deadband: no micro-shrink
    assert res.overflow and res.overflow[0]["ratio"] > 1.0  # but still warned


def test_clear_overflow_still_shrinks(tmp_path):
    src = tmp_path / "b.hwpx"
    _build(src, value_width=3180)              # avail 2900
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "가나다라마바사"}, out, auto_fit=True)  # 7000 -> ratio 2.41
    assert res.shrunk and res.shrunk[0]["scale"] < 1.0


def test_warn_first_without_auto_fit(tmp_path):
    src = tmp_path / "c.hwpx"
    _build(src, value_width=3180)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "가나다라마바사"}, out)  # auto_fit OFF
    assert res.shrunk == []                     # no mutation
    assert res.overflow and res.overflow[0]["label"] == "성명"  # but reported


def test_fits_no_overflow_no_shrink(tmp_path):
    src = tmp_path / "d.hwpx"
    _build(src, value_width=6000)               # avail 5720
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "가나다"}, out, auto_fit=True)  # 3000 < 5720
    assert res.shrunk == [] and res.overflow == []

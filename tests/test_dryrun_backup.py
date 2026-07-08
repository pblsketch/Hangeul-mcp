"""US-019: fill dry-run (no write) + pre-overwrite backup."""

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
        '<hp:subList><hp:p id="1"><hp:run charPrIDRef="0"><hp:t>성명</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
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


def test_dry_run_writes_nothing_but_reports(tmp_path):
    src = tmp_path / "s.hwpx"
    _form(src)
    out = tmp_path / "o.hwpx"
    res = fill(src, {"성명": "홍길동"}, out, dry_run=True)
    assert not out.exists()             # nothing written
    assert res.out_path is None
    assert any(f["label"] == "성명" for f in res.filled)  # plan computed


def test_backup_created_when_overwriting(tmp_path):
    src = tmp_path / "s.hwpx"
    _form(src)
    out = tmp_path / "o.hwpx"
    fill(src, {"성명": "첫번째"}, out)          # create out
    first_bytes = out.read_bytes()
    fill(src, {"성명": "두번째"}, out, backup=True)  # overwrite with backup
    bak = Path(str(out) + ".bak")
    assert bak.exists() and bak.read_bytes() == first_bytes
    # new output reflects the second fill
    from hangeul_core.owpml import HwpxPackage
    sec = HwpxPackage.open(out).read("Contents/section0.xml").decode("utf-8")
    assert "두번째" in sec


def test_backup_noop_when_target_absent(tmp_path):
    src = tmp_path / "s.hwpx"
    _form(src)
    out = tmp_path / "fresh.hwpx"
    fill(src, {"성명": "홍길동"}, out, backup=True)  # no existing target
    assert out.exists()
    assert not Path(str(out) + ".bak").exists()

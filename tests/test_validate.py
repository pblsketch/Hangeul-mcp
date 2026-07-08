"""US-021: validate_hwpx — well-formedness, container invariants, optional XSD."""

import zipfile
from pathlib import Path

from hangeul_core.fill import fill
from hangeul_core.validate import validate_hwpx

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def test_real_fixture_is_valid():
    r = validate_hwpx(FIXTURE)
    assert r["valid"] is True
    assert r["well_formed"] and r["mimetype_ok"] and r["declaration_ok"]
    assert r["errors"] == []
    assert r["xsd"]["available"] is False  # python-hwpx not installed


def test_fill_output_stays_valid(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"성명": "홍길동"}, out)
    assert validate_hwpx(out)["valid"] is True


def test_corrupted_xml_is_invalid(tmp_path):
    bad = tmp_path / "bad.hwpx"
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="1"><hp:run><hp:t>unclosed'  # malformed: not closed
    ).encode()
    with zipfile.ZipFile(bad, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>')
        z.writestr("Contents/section0.xml", section0)
    r = validate_hwpx(bad)
    assert r["valid"] is False and r["well_formed"] is False
    assert any("section0.xml" in e for e in r["errors"])


def test_bad_mimetype_is_flagged(tmp_path):
    bad = tmp_path / "nomime.hwpx"
    with zipfile.ZipFile(bad, "w") as z:
        # header first (mimetype not first / not STORED) -> mimetype_ok False
        z.writestr("Contents/header.xml", b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>')
    r = validate_hwpx(bad)
    assert r["mimetype_ok"] is False and r["valid"] is False


def test_non_zip_is_invalid(tmp_path):
    notzip = tmp_path / "x.hwpx"
    notzip.write_bytes(b"this is not a zip file")
    r = validate_hwpx(notzip)
    assert r["valid"] is False and r["errors"]

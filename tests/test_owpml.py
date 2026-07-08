"""US-002: byte-preserving OWPML container I/O."""

import zipfile
from pathlib import Path

from hangeul_core.owpml import HwpxPackage

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_untouched_roundtrip_entries_byte_identical(tmp_path):
    pkg = HwpxPackage.open(FIXTURE)
    out = pkg.save(tmp_path / "out.hwpx")
    with zipfile.ZipFile(FIXTURE) as a, zipfile.ZipFile(out) as b:
        assert a.namelist() == b.namelist()  # order preserved
        for name in a.namelist():
            assert a.read(name) == b.read(name), f"entry changed: {name}"


def test_mimetype_first_and_stored(tmp_path):
    pkg = HwpxPackage.open(FIXTURE)
    assert pkg.is_mimetype_ok()
    out = pkg.save(tmp_path / "out.hwpx")
    with zipfile.ZipFile(out) as z:
        first = z.infolist()[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED
        assert z.read("mimetype").strip() == b"application/hwp+zip"


def test_replace_preserves_other_entries(tmp_path):
    pkg = HwpxPackage.open(FIXTURE)
    # Replace section with a trivially modified copy; all others must stay identical.
    sec = pkg.read("Contents/section0.xml")
    pkg.replace("Contents/section0.xml", sec.replace(b"</hs:sec>", b"</hs:sec>"))
    out = pkg.save(tmp_path / "out.hwpx")
    with zipfile.ZipFile(FIXTURE) as a, zipfile.ZipFile(out) as b:
        for name in a.namelist():
            if name == "Contents/section0.xml":
                continue
            assert a.read(name) == b.read(name), f"unrelated entry changed: {name}"


def test_xml_declaration_preserved(tmp_path):
    pkg = HwpxPackage.open(FIXTURE)
    sec = pkg.read("Contents/section0.xml")
    assert sec.lstrip().startswith(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"')
    out = pkg.save(tmp_path / "out.hwpx")
    with zipfile.ZipFile(out) as z:
        got = z.read("Contents/section0.xml")
    assert got.lstrip().startswith(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"')


def test_replace_rejects_unknown_entry():
    pkg = HwpxPackage.open(FIXTURE)
    try:
        pkg.replace("does/not/exist.xml", b"x")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass

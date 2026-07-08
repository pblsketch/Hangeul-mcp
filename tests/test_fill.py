"""US-006: format-preserving fill engine (set / append / inline)."""

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from hangeul_core.analyze import analyze
from hangeul_core.fill import fill
from hangeul_core.owpml import HwpxPackage

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def _section(hwpx) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")


def test_set_empty_cells(tmp_path):
    out = tmp_path / "o.hwpx"
    res = fill(FIXTURE, {"성명": "홍길동", "직위": "교사"}, out)
    assert res.skipped == []
    sec = _section(out)
    assert "홍길동" in sec and "교사" in sec


def test_inline_marker_no_duplicate(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"학력": "○○대학교"}, out)
    sec = _section(out)
    assert "∘ ○○대학교" in sec
    assert "∘ ∘" not in sec


def test_inline_colon_both_blanks(tmp_path):
    out = tmp_path / "o.hwpx"
    res = fill(FIXTURE, {"은행명": "농협", "계좌번호": "123-456-789"}, out)
    assert res.skipped == []
    sec = _section(out)
    assert "농협" in sec and "123-456-789" in sec


def test_multiline_becomes_paragraphs_no_raw_newline(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"소속": "1줄\n2줄"}, out)
    sec = _section(out)
    assert "1줄" in sec and "2줄" in sec
    for m in re.finditer(r"<hp:t>(.*?)</hp:t>", sec, re.S):
        assert "\n" not in m.group(1), "raw newline inside <hp:t>"


def test_only_target_cells_change(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"성명": "홍길동"}, out)
    before = {c.field_id: c.text for c in analyze(FIXTURE).all_cells()}
    after = {c.field_id: c.text for c in analyze(out).all_cells()}
    changed = [k for k in before if before.get(k) != after.get(k)]
    assert changed == ["t2.r2.c3"]


def test_other_entries_byte_identical(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"성명": "홍길동"}, out)  # no spacing normalization -> header unchanged too
    with zipfile.ZipFile(FIXTURE) as a, zipfile.ZipFile(out) as b:
        for name in a.namelist():
            if name == "Contents/section0.xml":
                continue
            assert a.read(name) == b.read(name), f"entry changed: {name}"


def test_wellformed_and_declaration_preserved(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"성명": "홍길동", "은행명": "농협"}, out)
    with zipfile.ZipFile(out) as z:
        assert z.infolist()[0].filename == "mimetype"
        sec_bytes = z.read("Contents/section0.xml")
    ET.fromstring(sec_bytes)  # well-formed
    assert sec_bytes.lstrip().startswith(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"')


def test_spacing_normalization_changes_header_only(tmp_path):
    out = tmp_path / "o.hwpx"
    fill(FIXTURE, {"성명": "홍길동"}, out, normalize_spacing=True)
    hdr_before = HwpxPackage.open(FIXTURE).read("Contents/header.xml")
    hdr_after = HwpxPackage.open(out).read("Contents/header.xml")
    assert hdr_after != hdr_before  # spacing-0 charPr clone added
    ET.fromstring(hdr_after)  # still well-formed


def test_unknown_field_is_skipped(tmp_path):
    out = tmp_path / "o.hwpx"
    res = fill(FIXTURE, {"존재하지않는필드": "x"}, out)
    assert res.filled == []
    assert res.skipped and res.skipped[0]["reason"] == "no matching field"

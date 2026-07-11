"""US-066: body-paragraph fields — fillable text outside any table.

Real forms are often running body paragraphs (government report templates,
memos) with no cells / named fields / {placeholder} tokens. Detection is
structural (enumerate every body paragraph) and marker detection is Unicode-
category based, so it adapts to any form's bullet style without hardcoding.
"""

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from hangeul_core.body import (
    body_field_index,
    detect_body_fields,
    marker_prefix,
    replace_body_paragraph,
    resolve_body_targets,
)
from hangeul_core.fill import fill
from hangeul_core.owpml import HwpxPackage
from hangeul_core.schema import KIND_BODY_PARA
from hangeul_mcp import server

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _wellformed(fragment: str) -> ET.Element:
    """Parse an <hp:*> fragment (validates the splice produced well-formed XML)."""
    return ET.fromstring(f'<r xmlns:hp="urn:x">{fragment}</r>')


def _run(t: str) -> str:
    return f'<hp:run charPrIDRef="0"><hp:t>{t}</hp:t></hp:run>'


def _build_two_body_paras(dst: Path) -> None:
    """Minimal doc: 본문1 = ``{x}`` (a placeholder token), 본문2 = ``SECOND``."""
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="1">' + _run("{x}") + "</hp:p>"
        '<hp:p id="2">' + _run("SECOND") + "</hp:p>"
        "</hs:sec>"
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)

FIXTURE = Path(__file__).parent / "fixtures" / "공공기관 보고서 양식.hwpx"


def test_marker_prefix_is_generic_not_hardcoded():
    # bullets/dashes/reference marks all detected via Unicode category
    assert marker_prefix(" □ 헤드라인") == " □ "
    assert marker_prefix("  ○ 항목") == "  ○ "
    assert marker_prefix("   ― 세부") == "   ― "
    assert marker_prefix("     ※ 참고") == "     ※ "
    assert marker_prefix("* 별표 목록") == "* "
    # plain text (no marker) -> empty prefix
    assert marker_prefix("2024. 5. 23.") == ""
    assert marker_prefix("추진 배경") == ""


# --- P4 / MEDIUM-8: marker GRAMMAR (no category-only false positives/negatives) ---

def test_marker_prefix_rejects_prose_punctuation():
    # lone ':' and sentence '-' / quotes are prose, not outline markers
    assert marker_prefix(": 정상 문장") == ""
    assert marker_prefix("- 정상 문장") == ""
    assert marker_prefix('" 인용 문장') == ""
    assert marker_prefix("A: B 설명") == ""


def test_marker_prefix_detects_number_markers():
    # roman / circled / parenthesised number markers were previously missed
    assert marker_prefix("Ⅰ. 항목") == "Ⅰ. "
    assert marker_prefix("① 항목") == "① "
    assert marker_prefix("(1) 항목") == "(1) "
    assert marker_prefix("1) 항목") == "1) "


def test_marker_prefix_keeps_symbol_bullets_and_dashes():
    # genuine bullets/reference marks/dashes stay markers; a following separator
    # is required so masked names like '○○대학교' are not mis-split
    assert marker_prefix("□ 진짜마커") == "□ "
    assert marker_prefix("※ 참고") == "※ "
    assert marker_prefix("― 세부") == "― "  # horizontal bar (not ASCII hyphen)
    assert marker_prefix("○○대학교") == ""  # no separator -> not a marker
    # a 4-digit date is not a numbered marker
    assert marker_prefix("2024. 5. 23.") == ""


def test_detect_enumerates_body_paragraphs_with_markers():
    fields = detect_body_fields(FIXTURE)
    assert fields, "government template has fillable body paragraphs"
    assert all(f.field_id.startswith("b") for f in fields)
    assert all(f.kind == KIND_BODY_PARA for f in fields)
    # every field exposes its current text so the client can decide what to fill
    assert all(f.template for f in fields)
    # at least one marker-led paragraph was detected generically
    assert any(f.insert_after and "□" in f.insert_after for f in fields)


def test_body_field_index_matches_detection_order():
    idx = body_field_index(FIXTURE)
    fields = detect_body_fields(FIXTURE)
    assert set(idx) == {f.field_id for f in fields}


def test_file_fill_replaces_body_and_preserves_marker(tmp_path):
    out = tmp_path / "filled.hwpx"
    fields = detect_body_fields(FIXTURE)
    marker_field = next(f for f in fields if f.insert_after and "□" in f.insert_after)
    res = fill(FIXTURE, {marker_field.field_id: "실제 내용으로 교체"}, out)
    assert any(f["field_id"] == marker_field.field_id for f in res.filled)
    after = {f.field_id: f.template for f in detect_body_fields(out)}
    assert after[marker_field.field_id] == f"{marker_field.insert_after}실제 내용으로 교체"


def test_file_fill_body_is_byte_preserving(tmp_path):
    out = tmp_path / "bp.hwpx"
    fill(FIXTURE, {"b2": "값"}, out)
    changed = []
    with zipfile.ZipFile(FIXTURE) as za, zipfile.ZipFile(out) as zb:
        for n in za.namelist():
            other = zb.read(n) if n in zb.namelist() else b""
            if za.read(n) != other:
                changed.append(n)
    assert changed == ["Contents/section0.xml"], changed


def test_file_fill_leaves_other_paragraphs_untouched(tmp_path):
    out = tmp_path / "one.hwpx"
    before = {f.field_id: f.template for f in detect_body_fields(FIXTURE)}
    fill(FIXTURE, {"b2": "새 제목"}, out)
    after = {f.field_id: f.template for f in detect_body_fields(out)}
    for fid, txt in before.items():
        if fid != "b2":
            assert after[fid] == txt, f"{fid} must be untouched"


def test_resolve_body_targets_peels_body_keys_only():
    targets = resolve_body_targets(FIXTURE, {"b2": "x", "성명": "홍길동", "없는키": "y"})
    ids = {t["field_id"] for t in targets}
    assert ids == {"b2"}
    t = targets[0]
    assert t["value"] == "x" and t["template"] and "marker" in t


def test_analyze_form_surfaces_body_fields():
    result = server.analyze_form(str(FIXTURE))
    kinds = {f["kind"] for f in result["fields"]}
    assert KIND_BODY_PARA in kinds
    body = [f for f in result["fields"] if f["kind"] == KIND_BODY_PARA]
    assert all(f["field_id"].startswith("b") for f in body)


# --- P1 / HIGH-3: entity-bearing marker/prefix must not be truncated by splice ---

def test_splice_with_entity_marker_stays_wellformed():
    # Marker '>' is stored raw as '&gt;': decoded prefix len (2) != raw len (5).
    # Using the decoded length to index the raw <hp:t> cut the entity in half and
    # produced malformed XML ('&g<value>'). The splice must be raw-offset aware.
    section = '<hp:p id="1"><hp:run><hp:t>&gt; old</hp:t></hp:run></hp:p>'
    new_section, applied = replace_body_paragraph(section, {1: "새값"})
    assert applied == [1]
    _wellformed(new_section)  # raises on the pre-fix truncation
    inner = "".join(t.text or "" for t in _wellformed(new_section).iter("{urn:x}t"))
    assert inner == "> 새값"  # marker '> ' kept, content replaced


def test_splice_preserves_entities_in_content_and_value():
    # Entities in both the kept marker region and the inserted value round-trip.
    section = '<hp:p id="1"><hp:run><hp:t>&lt; a&amp;b</hp:t></hp:run></hp:p>'
    new_section, applied = replace_body_paragraph(section, {1: "x&y<z"})
    assert applied == [1]
    inner = "".join(t.text or "" for t in _wellformed(new_section).iter("{urn:x}t"))
    assert inner == "< x&y<z"  # marker '< ' preserved; value entities intact


# --- P5 / HIGH-4: a prior placeholder pass must not shift body ordinals ---

def test_body_fill_not_shifted_by_prior_placeholder_pass(tmp_path):
    src = tmp_path / "shift.hwpx"
    _build_two_body_paras(src)
    out = tmp_path / "o.hwpx"
    # b1 addresses 본문1 ({x}). An empty ph:x blanks 본문1; if the body pass runs
    # after that and re-enumerates non-empty paragraphs, ordinal 1 slides onto
    # 본문2 and TARGET lands in the wrong paragraph.
    fill(src, {"ph:x": "", "b1": "TARGET"}, out)
    sec = HwpxPackage.open(out).read("Contents/section0.xml").decode("utf-8")
    p1 = re.search(r'<hp:p id="1">.*?</hp:p>', sec, re.S).group(0)
    p2 = re.search(r'<hp:p id="2">.*?</hp:p>', sec, re.S).group(0)
    assert "TARGET" in p1, "b1 must fill 본문1, not a shifted paragraph"
    assert "SECOND" in p2 and "TARGET" not in p2, "본문2 must be untouched"


def test_splice_entity_marker_across_split_runs():
    # Prefix split across two <hp:t> nodes with an entity in the first — the raw
    # offset must still land exactly at the marker boundary.
    section = (
        '<hp:p id="1"><hp:run><hp:t>&gt;</hp:t></hp:run>'
        '<hp:run><hp:t> tail</hp:t></hp:run></hp:p>'
    )
    new_section, applied = replace_body_paragraph(section, {1: "V"})
    assert applied == [1]
    inner = "".join(t.text or "" for t in _wellformed(new_section).iter("{urn:x}t"))
    assert inner == "> V"

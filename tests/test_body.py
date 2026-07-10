"""US-066: body-paragraph fields — fillable text outside any table.

Real forms are often running body paragraphs (government report templates,
memos) with no cells / named fields / {placeholder} tokens. Detection is
structural (enumerate every body paragraph) and marker detection is Unicode-
category based, so it adapts to any form's bullet style without hardcoding.
"""

import zipfile
from pathlib import Path

from hangeul_core.body import (
    body_field_index,
    detect_body_fields,
    marker_prefix,
    resolve_body_targets,
)
from hangeul_core.fill import fill
from hangeul_core.schema import KIND_BODY_PARA
from hangeul_mcp import server

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

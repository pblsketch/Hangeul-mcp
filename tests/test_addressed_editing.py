from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from hangeul_core import addressed as addressed_core
from hangeul_core.addressed import (
    apply_addressed_edits,
    complete_addressed_template,
    get_paragraph_map,
    inspect_editable_regions,
    plan_template_completion,
    preview_addressed_edits,
    verify_targets,
)
from hangeul_core.edit_session import restore_edit_session
from hangeul_core.fill import fill
from hangeul_core.owpml import HwpxPackage
from hangeul_core.read import find_cell_by_label
from hangeul_mcp import server

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _run(text: str) -> str:
    return f'<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run>'


def _write_hwpx(dst: Path, section0: str) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0.encode("utf-8"))



def _build_addressed_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="1">' + _run("자료") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:subList><hp:p id="2">' + _run("비고") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)



def _build_region_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="10">' + _run("▶ 본문 안내") + '</hp:p>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        '<hp:p id="11">' + _run("자료") + '</hp:p>'
        '<hp:p id="12">' + _run("추가") + '</hp:p>'
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)


def _build_occurrence_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="20">' + _run("○○○ 결정사항 ○○○") + '</hp:p>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        '<hp:p id="21">' + _run("자료") + '</hp:p>'
        '<hp:p id="22">' + _run("자료") + '</hp:p>'
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)



def _build_duplicate_label_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="2" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="1">' + _run("성명") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:subList><hp:p id="2">' + _run("") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="1" colAddr="0"/><hp:subList><hp:p id="3">' + _run("성명") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="1" colAddr="1"/><hp:subList><hp:p id="4">' + _run("") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)


def _build_nested_table_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        '<hp:p id="30">' + _run("외부") + '</hp:p>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="31">' + _run("내부") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)


def _build_mixed_label_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="3" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="1">' + _run("학교") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:subList><hp:p id="2">' + _run("") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="1" colAddr="0"/><hp:subList><hp:p id="3">' + _run("성명") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="1" colAddr="1"/><hp:subList><hp:p id="4">' + _run("") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="2" colAddr="0"/><hp:subList><hp:p id="5">' + _run("성명") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="2" colAddr="1"/><hp:subList><hp:p id="6">' + _run("") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)





def _section_text(hwpx: Path) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")



def test_preview_apply_restore_addressed_raw_cell_edit(tmp_path):
    src = tmp_path / "addressed.hwpx"
    out = tmp_path / "out.hwpx"
    _build_addressed_fixture(src)

    preview = preview_addressed_edits(
        src,
        [
            {
                "target": "t1.r0.c0",
                "kind": "cell",
                "operation": "replace_text",
                "value": "교과서",
                "expected_text": "자료",
            }
        ],
    )

    assert preview["ok"] is True
    assert preview["kind"] == "addressed_edits"
    assert preview["counts"] == {"requested": 1, "resolved": 1, "applied": 0, "skipped": 0, "unresolved": 0}
    assert preview["changed_entries"] == ["Contents/section0.xml"]
    assert preview["edits"][0]["before_text"] == "자료"
    assert preview["edits"][0]["after_text"] == "교과서"

    applied = apply_addressed_edits(preview["session_id"], out)

    assert applied["ok"] is True
    assert applied["counts"] == {"requested": 1, "resolved": 1, "applied": 1, "skipped": 0, "unresolved": 0}
    assert "교과서" in _section_text(out)

    journal = json.loads(Path(applied["journal_path"]).read_text(encoding="utf-8"))
    assert journal["kind"] == "addressed_edits"
    assert journal["counts"]["applied"] == 1

    restored = restore_edit_session(applied["journal_path"])
    assert restored.restored is True
    assert restored.target_exists is False
    assert not out.exists()



def test_inspect_regions_and_paragraph_map(tmp_path):
    src = tmp_path / "regions.hwpx"
    _build_region_fixture(src)

    inspected = inspect_editable_regions(src)
    assert inspected["source_sha256"]
    assert inspected["counts"] == {"regions": 2, "unsupported": 0}

    assert inspected["regions"] == [
        {
            "target": "b1",
            "kind": "body_para",
            "container": "body",
            "section": "Contents/section0.xml",
            "section_index": 1,
            "paragraph_target": "s1.p1",
            "paragraph_targets": ["s1.p1"],
            "paragraph_id": "10",
            "paragraph_ordinal": 1,
            "text": "▶ 본문 안내",
            "snippet": "▶ 본문 안내",
            "editable": True,
            "aliases": ["s1.p1"],
            "source_sha256": inspected["source_sha256"],
        },
        {
            "target": "t1.r0.c0",
            "kind": "cell",
            "container": "table_cell",
            "section": "Contents/section0.xml",
            "section_index": 1,
            "table": 1,
            "row": 0,
            "col": 0,
            "paragraph_targets": ["t1.r0.c0.p1", "t1.r0.c0.p2"],
            "paragraph_ids": ["11", "12"],
            "paragraph_count": 2,
            "text": "자료추가",
            "snippet": "자료추가",
            "editable": True,
            "aliases": [],
            "source_sha256": inspected["source_sha256"],
        },
    ]

    paragraph_map = get_paragraph_map(src)
    assert paragraph_map["paragraphs"] == [
        {
            "target": "s1.p1",
            "parent_target": "b1",
            "container": "body",
            "section": "Contents/section0.xml",
            "section_index": 1,
            "paragraph_id": "10",
            "paragraph_ordinal": 1,
            "text": "▶ 본문 안내",
            "snippet": "▶ 본문 안내",
            "editable": True,
            "source_sha256": paragraph_map["source_sha256"],
        },
        {
            "target": "t1.r0.c0.p1",
            "parent_target": "t1.r0.c0",
            "container": "table_cell",
            "section": "Contents/section0.xml",
            "section_index": 1,
            "table": 1,
            "row": 0,
            "col": 0,
            "paragraph_id": "11",
            "paragraph_ordinal": 1,
            "text": "자료",
            "snippet": "자료",
            "editable": True,
            "source_sha256": paragraph_map["source_sha256"],
        },
        {
            "target": "t1.r0.c0.p2",
            "parent_target": "t1.r0.c0",
            "container": "table_cell",
            "section": "Contents/section0.xml",
            "section_index": 1,
            "table": 1,
            "row": 0,
            "col": 0,
            "paragraph_id": "12",
            "paragraph_ordinal": 2,
            "text": "추가",
            "snippet": "추가",
            "editable": True,
            "source_sha256": paragraph_map["source_sha256"],
        },
    ]

    server_inspected = server.inspect_editable_regions(str(src))
    assert server_inspected["counts"] == inspected["counts"]
    server_paragraphs = server.get_paragraph_map(str(src))
    assert [p["target"] for p in server_paragraphs["paragraphs"]] == ["s1.p1", "t1.r0.c0.p1", "t1.r0.c0.p2"]


def test_preview_apply_addressed_paragraph_and_marker_tail_edits(tmp_path):
    src = tmp_path / "regions.hwpx"
    out = tmp_path / "out.hwpx"
    _build_region_fixture(src)

    preview = preview_addressed_edits(
        src,
        [
            {
                "target": "b1",
                "kind": "body_para",
                "operation": "preserve_marker_replace_tail",
                "value": "새 안내",
                "expected_text": "▶ 본문 안내",
            },
            {
                "target": "t1.r0.c0.p2",
                "kind": "paragraph",
                "operation": "replace_text",
                "value": "교과서",
                "expected_text": "추가",
            },
        ],
    )

    assert preview["ok"] is True
    assert preview["counts"] == {"requested": 2, "resolved": 2, "applied": 0, "skipped": 0, "unresolved": 0}
    assert [item["target"] for item in preview["edits"]] == ["b1", "t1.r0.c0.p2"]
    assert preview["edits"][0]["before_text"] == "▶ 본문 안내"
    assert preview["edits"][0]["after_text"] == "▶ 새 안내"
    assert preview["edits"][1]["before_text"] == "추가"
    assert preview["edits"][1]["after_text"] == "교과서"

    applied = apply_addressed_edits(preview["session_id"], out)

    assert applied["ok"] is True
    assert applied["counts"] == {"requested": 2, "resolved": 2, "applied": 2, "skipped": 0, "unresolved": 0}
    section = _section_text(out)
    assert "▶ 새 안내" in section
    assert "자료" in section
    assert "교과서" in section
    assert "추가" not in section


def test_find_text_occurrences_and_fail_closed_global_replace(tmp_path):
    src = tmp_path / "occurrence.hwpx"
    out = tmp_path / "out.hwpx"
    _build_occurrence_fixture(src)

    found = server.find_text_occurrences(str(src), "○○○")
    assert found["count"] == 2
    assert [item["target"] for item in found["occurrences"]] == ["s1.p1.occ1", "s1.p1.occ2"]
    assert all(item["context_digest"] for item in found["occurrences"])

    from hangeul_core.edit import search_and_replace

    try:
        search_and_replace(src, "자료", "교과서", out)
    except RuntimeError as exc:
        assert "scope='all'" in str(exc)
    else:
        raise AssertionError("ambiguous search_and_replace must fail closed")

    applied = search_and_replace(src, "자료", "교과서", out, scope="all")
    assert applied.counts == {"자료": 2}
    assert _section_text(out).count("교과서") == 2


def test_verify_targets_and_plan_completion(tmp_path):
    src = tmp_path / "regions.hwpx"
    out = tmp_path / "out.hwpx"
    duplicate = tmp_path / "duplicate.hwpx"
    _build_region_fixture(src)
    _build_duplicate_label_fixture(duplicate)

    preview = preview_addressed_edits(
        src,
        [
            {
                "target": "b1",
                "kind": "body_para",
                "operation": "preserve_marker_replace_tail",
                "value": "새 안내",
                "expected_text": "▶ 본문 안내",
            },
            {
                "target": "t1.r0.c0.p2",
                "kind": "paragraph",
                "operation": "replace_text",
                "value": "교과서",
                "expected_text": "추가",
            },
        ],
    )
    applied = apply_addressed_edits(preview["session_id"], out)
    assert applied["ok"] is True

    verified = verify_targets(
        out,
        [
            {"target": "b1", "expected_text": "▶ 새 안내"},
            {"target": "t1.r0.c0.p2", "expected_text": "교과서"},
            {"target": "s1.p1", "expected_text": "▶ 새 안내"},
        ],
    )
    assert verified["verified"] is True
    assert verified["counts"] == {"requested": 3, "verified": 3, "failed": 0}
    assert [item["actual_text"] for item in verified["results"]] == ["▶ 새 안내", "교과서", "▶ 새 안내"]

    server_verified = server.verify_targets(str(out), [{"target": "t1.r0.c0.p2", "expected_text": "교과서"}])
    assert server_verified["verified"] is True

    plan = plan_template_completion(duplicate)
    assert plan["state"] == "partial"
    assert plan["coverage_ratio"] == 0.0
    assert plan["ambiguous_labels"][0]["label"] == "성명"
    assert plan["user_attention_required"] is True

    server_plan = server.plan_template_completion(str(duplicate))
    assert server_plan["state"] == "partial"

    region_plan = plan_template_completion(src)
    assert region_plan["state"] == "partial"
    assert region_plan["coverage_ratio"] == 0.0
    assert region_plan["recommended_next_tool"] == "inspect_editable_regions"
    assert region_plan["user_attention_required"] is True

    nested = tmp_path / "nested.hwpx"
    _build_nested_table_fixture(nested)
    nested_plan = plan_template_completion(nested)
    assert nested_plan["state"] == "partial"
    assert nested_plan["unsupported_controls"][0]["reason"] == "nested_table"
    assert nested_plan["recommended_next_tool"] == "inspect_editable_regions"


def test_preview_and_apply_addressed_safety_states(tmp_path):
    src = tmp_path / "addressed.hwpx"
    out = tmp_path / "out.hwpx"
    _build_addressed_fixture(src)

    bad_preview = preview_addressed_edits(
        src,
        [
            {"target": "t1.r0.c0", "kind": "cell", "operation": "replace_text", "value": "교과서", "expected_text": "자료"},
            {"target": "t1.r0.c0", "kind": "cell", "operation": "replace_text", "value": "중복", "expected_text": "자료"},
            {"target": "b99", "kind": "body_para", "operation": "replace_text", "value": "없음", "expected_text": ""},
        ],
    )
    assert bad_preview["ok"] is False
    assert [item["reason"] for item in bad_preview["unresolved"]] == ["duplicate_target", "target_not_found"]
    blocked = apply_addressed_edits(bad_preview["session_id"], out)
    assert blocked["state"] == "ambiguous_target"

    mismatch = preview_addressed_edits(
        src,
        [{"target": "t1.r0.c0", "kind": "cell", "operation": "replace_text", "value": "교과서", "expected_text": "다름"}],
    )
    assert mismatch["ok"] is False
    assert mismatch["unresolved"][0]["reason"] == "expected_text_mismatch"

    missing = apply_addressed_edits("missing-session", out)
    assert missing["state"] == "unknown_session"

    preview = preview_addressed_edits(
        src,
        [{"target": "t1.r0.c0", "kind": "cell", "operation": "replace_text", "value": "교과서", "expected_text": "자료"}],
    )
    missing_out_path = apply_addressed_edits(preview["session_id"])
    assert missing_out_path["state"] == "invalid_output_path"
    same_out_path = apply_addressed_edits(preview["session_id"], src)
    assert same_out_path["state"] == "invalid_output_path"
    aliased_same_out_path = apply_addressed_edits(preview["session_id"], src.parent / "." / src.name)
    assert aliased_same_out_path["state"] == "invalid_output_path"
    hardlink_alias = src.parent / "hardlink-alias.hwpx"
    hardlink_alias.unlink(missing_ok=True)
    hardlink_alias.hardlink_to(src)
    hardlink_same_out_path = apply_addressed_edits(preview["session_id"], hardlink_alias)
    assert hardlink_same_out_path["state"] == "invalid_output_path"
    applied = apply_addressed_edits(preview["session_id"], out)
    assert applied["ok"] is True
    again = apply_addressed_edits(preview["session_id"], out)
    assert again["state"] == "already_applied"

    stale_preview = preview_addressed_edits(
        src,
        [{"target": "t1.r0.c1", "kind": "cell", "operation": "replace_text", "value": "메모", "expected_text": "비고"}],
    )
    _build_duplicate_label_fixture(src)
    stale = apply_addressed_edits(stale_preview["session_id"], out)
    assert stale["state"] == "stale_preview"
def test_complete_addressed_template_fail_closed_states(tmp_path):
    src = tmp_path / "regions.hwpx"
    out = tmp_path / "completed.hwpx"
    _build_region_fixture(src)

    ambiguous = complete_addressed_template(
        src,
        [
            {"target": "t1.r0.c0.p2", "kind": "paragraph", "operation": "replace_text", "value": "교과서", "expected_text": "추가"},
            {"target": "t1.r0.c0.p2", "kind": "paragraph", "operation": "replace_text", "value": "중복", "expected_text": "추가"},
        ],
        out,
    )
    assert ambiguous["ok"] is False
    assert ambiguous["state"] == "ambiguous_target"
    assert ambiguous["counts"] == {"requested": 2, "resolved": 1, "applied": 0, "verified": 0, "skipped": 1, "unresolved": 1}
    assert ambiguous["coverage_ratio"] == 0.5
    assert ambiguous["unresolved"] == [{"target": "t1.r0.c0.p2", "reason": "duplicate_target"}]
    assert ambiguous["failures"] == []
    assert not out.exists()

    same_path = complete_addressed_template(
        src,
        [{"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "교과서", "expected_text": "자료"}],
        src,
    )
    assert same_path["ok"] is False
    assert same_path["state"] == "failed"
    assert same_path["failures"] == [{"reason": "output_path_matches_source"}]
    assert same_path["counts"] == {"requested": 1, "resolved": 0, "applied": 0, "verified": 0, "skipped": 1, "unresolved": 0}

    aliased_same_path = complete_addressed_template(
        src,
        [{"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "교과서", "expected_text": "자료"}],
        src.parent / "." / src.name,
    )
    assert aliased_same_path["ok"] is False
    assert aliased_same_path["state"] == "failed"
    assert aliased_same_path["failures"] == [{"reason": "output_path_matches_source"}]


def test_complete_addressed_template_reports_verification_mismatch(tmp_path):
    src = tmp_path / "regions.hwpx"
    out = tmp_path / "completed.hwpx"
    _build_region_fixture(src)

    real_apply = addressed_core.apply_addressed_edits

    def tampered_apply(session_id, out_path=None):
        applied = real_apply(session_id, out_path)
        if applied.get("ok"):
            section = _section_text(Path(applied["target_path"])).replace("교과서", "검증실패")
            _write_hwpx(Path(applied["target_path"]), section)
        return applied

    with patch.object(addressed_core, "apply_addressed_edits", side_effect=tampered_apply):
        report = complete_addressed_template(
            src,
            [{"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "교과서", "expected_text": "자료"}],
            out,
        )

    assert report["ok"] is False
    assert report["state"] == "failed"
    assert report["counts"] == {"requested": 1, "resolved": 1, "applied": 1, "verified": 0, "skipped": 0, "unresolved": 0}
    assert report["coverage_ratio"] == 0.0
    assert report["failures"] == [
        {
            "target": "t1.r0.c0.p1",
            "reason": "verification_mismatch",
            "expected_text": "교과서",
            "actual_text": "검증실패",
        }
    ]
    assert report["target_sha256"] == addressed_core._sha256_path(out)


def test_complete_addressed_template_without_verify_reports_applied_coverage(tmp_path):
    src = tmp_path / "regions.hwpx"
    out = tmp_path / "completed.hwpx"
    _build_region_fixture(src)

    report = complete_addressed_template(
        src,
        [{"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "교과서", "expected_text": "자료"}],
        out,
        verify=False,
    )

    assert report["ok"] is True
    assert report["state"] == "applied"
    assert report["counts"] == {"requested": 1, "resolved": 1, "applied": 1, "verified": 0, "skipped": 0, "unresolved": 0}
    assert report["coverage_ratio"] == 1.0
    assert report["target_sha256"] == addressed_core._sha256_path(out)
def test_duplicate_label_fill_fails_closed(tmp_path):
    src = tmp_path / "duplicate.hwpx"
    out = tmp_path / "out.hwpx"
    _build_duplicate_label_fixture(src)

    result = fill(src, {"성명": "홍길동"}, out)

    assert result.filled == []
    assert result.skipped == [
        {
            "key": "성명",
            "reason": "ambiguous_label",
            "candidate_field_ids": ["t1.r0.c1", "t1.r1.c1"],
            "candidate_labels": ["성명", "성명"],
        }
    ]
    assert not out.exists()

    located = find_cell_by_label(src, "성명")
    assert located["state"] == "ambiguous_label"
    assert located["candidate_field_ids"] == ["t1.r0.c1", "t1.r1.c1"]
    assert located["value_field_id"] is None


def test_fill_refuses_to_write_when_ambiguous_label_is_mixed(tmp_path):
    src = tmp_path / "duplicate.hwpx"
    out = tmp_path / "out.hwpx"
    _build_duplicate_label_fixture(src)

    result = fill(src, {"성명": "홍길동", "없는필드": "x"}, out)

    assert result.filled == []
    assert not out.exists()
    assert any(item["reason"] == "ambiguous_label" for item in result.skipped)



def test_fill_clears_successes_when_ambiguous_label_is_mixed_with_resolved(tmp_path):
    src = tmp_path / "mixed.hwpx"
    out = tmp_path / "out.hwpx"
    _build_mixed_label_fixture(src)

    result = fill(src, {"학교": "세종초", "성명": "홍길동"}, out)

    assert result.filled == []
    assert not out.exists()
    assert any(item["reason"] == "ambiguous_label" for item in result.skipped)

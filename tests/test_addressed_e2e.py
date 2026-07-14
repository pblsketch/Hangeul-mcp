from __future__ import annotations

from pathlib import Path

from hangeul_core.addressed import complete_addressed_template
from hangeul_mcp import server

LESSON_PLAN = Path(__file__).parent / "fixtures" / "lesson_plan_addressed.hwpx"
MEETING_MINUTES = Path(__file__).parent / "fixtures" / "meeting_minutes_addressed.hwpx"


def test_lesson_plan_fixture_e2e(tmp_path):
    out = tmp_path / "lesson_plan_filled.hwpx"
    preview = server.preview_addressed_edits(
        str(LESSON_PLAN),
        [
            {"target": "b1", "kind": "body_para", "operation": "preserve_marker_replace_tail", "value": "빛의 반사", "expected_text": "▶ 수업 제목"},
            {"target": "b2", "kind": "body_para", "operation": "preserve_marker_replace_tail", "value": "반사 법칙 설명", "expected_text": "▶ 수업 목표"},
            {"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "거울", "expected_text": "자료"},
            {"target": "t1.r1.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "레이저 포인터", "expected_text": "자료"},
            {"target": "t1.r0.c1.p1", "kind": "paragraph", "operation": "replace_text", "value": "도입 활동", "expected_text": "▶"},
            {"target": "t1.r1.c1.p1", "kind": "paragraph", "operation": "replace_text", "value": "정리 활동", "expected_text": "▶"},
        ],
    )
    assert preview["ok"] is True
    applied = server.apply_addressed_edits(preview["session_id"], str(out))

    assert applied["ok"] is True

    verified = server.verify_targets(
        str(out),
        [
            {"target": "b1", "expected_text": "▶ 빛의 반사"},
            {"target": "b2", "expected_text": "▶ 반사 법칙 설명"},
            {"target": "t1.r0.c0.p1", "expected_text": "거울"},
            {"target": "t1.r1.c0.p1", "expected_text": "레이저 포인터"},
            {"target": "t1.r0.c1.p1", "expected_text": "도입 활동"},
            {"target": "t1.r1.c1.p1", "expected_text": "정리 활동"},
        ],
    )
    assert verified["verified"] is True

    assert verified["counts"]["verified"] == 6


def test_lesson_plan_complete_addressed_template_e2e(tmp_path):
    out = tmp_path / "lesson_plan_completed.hwpx"
    report = complete_addressed_template(
        LESSON_PLAN,
        [
            {"target": "b1", "kind": "body_para", "operation": "preserve_marker_replace_tail", "value": "빛의 반사", "expected_text": "▶ 수업 제목"},
            {"target": "b2", "kind": "body_para", "operation": "preserve_marker_replace_tail", "value": "반사 법칙 설명", "expected_text": "▶ 수업 목표"},
            {"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "거울", "expected_text": "자료"},
            {"target": "t1.r1.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "레이저 포인터", "expected_text": "자료"},
            {"target": "t1.r0.c1.p1", "kind": "paragraph", "operation": "replace_text", "value": "도입 활동", "expected_text": "▶"},
            {"target": "t1.r1.c1.p1", "kind": "paragraph", "operation": "replace_text", "value": "정리 활동", "expected_text": "▶"},
        ],
        out,
    )

    assert report["ok"] is True
    assert report["state"] == "complete"
    assert report["source_path"] == str(LESSON_PLAN)
    assert report["target_path"] == str(out)
    assert report["source_sha256"]
    assert report["target_sha256"]
    assert report["counts"] == {"requested": 6, "resolved": 6, "applied": 6, "verified": 6, "skipped": 0, "unresolved": 0}
    assert report["coverage_ratio"] == 1.0
    assert report["journal_path"]
    assert report["snapshot_path"]
    assert report["substrate"] == "own.byte_preserving_text"
    assert report["timings_ms"]["verify"] >= 0
    assert report["timings_ms"]["total"] >= report["timings_ms"]["apply"]

    verified = server.verify_targets(
        str(out),
        [
            {"target": "b1", "expected_text": "▶ 빛의 반사"},
            {"target": "b2", "expected_text": "▶ 반사 법칙 설명"},
            {"target": "t1.r0.c0.p1", "expected_text": "거울"},
            {"target": "t1.r1.c0.p1", "expected_text": "레이저 포인터"},
            {"target": "t1.r0.c1.p1", "expected_text": "도입 활동"},
            {"target": "t1.r1.c1.p1", "expected_text": "정리 활동"},
        ],
    )
    assert verified["verified"] is True
def test_server_complete_addressed_template_fixture_e2e(tmp_path):
    out = tmp_path / "lesson_plan_server_completed.hwpx"
    report = server.complete_addressed_template(
        str(LESSON_PLAN),
        [
            {"target": "b1", "kind": "body_para", "operation": "preserve_marker_replace_tail", "value": "빛의 반사", "expected_text": "▶ 수업 제목"},
            {"target": "b2", "kind": "body_para", "operation": "preserve_marker_replace_tail", "value": "반사 법칙 설명", "expected_text": "▶ 수업 목표"},
            {"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "거울", "expected_text": "자료"},
            {"target": "t1.r1.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "레이저 포인터", "expected_text": "자료"},
            {"target": "t1.r0.c1.p1", "kind": "paragraph", "operation": "replace_text", "value": "도입 활동", "expected_text": "▶"},
            {"target": "t1.r1.c1.p1", "kind": "paragraph", "operation": "replace_text", "value": "정리 활동", "expected_text": "▶"},
        ],
        str(out),
    )

    assert report["available"] is True
    assert report["ok"] is True
    assert report["state"] == "complete"
    assert report["counts"] == {"requested": 6, "resolved": 6, "applied": 6, "verified": 6, "skipped": 0, "unresolved": 0}

    verified = server.verify_targets(
        str(out),
        [
            {"target": "b1", "expected_text": "▶ 빛의 반사"},
            {"target": "b2", "expected_text": "▶ 반사 법칙 설명"},
            {"target": "t1.r0.c0.p1", "expected_text": "거울"},
            {"target": "t1.r1.c0.p1", "expected_text": "레이저 포인터"},
            {"target": "t1.r0.c1.p1", "expected_text": "도입 활동"},
            {"target": "t1.r1.c1.p1", "expected_text": "정리 활동"},
        ],
    )
    assert verified["verified"] is True


def test_meeting_minutes_fixture_e2e(tmp_path):
    out = tmp_path / "meeting_minutes_filled.hwpx"
    found = server.find_text_occurrences(str(MEETING_MINUTES), "○○○")
    assert [item["target"] for item in found["occurrences"]] == ["s1.p2.occ1", "t1.r0.c0.p1.occ1", "t1.r1.c0.p1.occ1"]

    preview = server.preview_addressed_edits(
        str(MEETING_MINUTES),
        [
            {"target": "b2", "kind": "body_para", "operation": "replace_text", "value": "결정 사항 예산 승인", "expected_text": "결정 사항 ○○○"},
            {"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "교실 환경 개선", "expected_text": "○○○"},
            {"target": "t1.r1.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "학부모 안내문 배포", "expected_text": "○○○"},
        ],
    )
    assert preview["ok"] is True
    applied = server.apply_addressed_edits(preview["session_id"], str(out))

    assert applied["ok"] is True

    verified = server.verify_targets(
        str(out),
        [
            {"target": "b2", "expected_text": "결정 사항 예산 승인"},
            {"target": "t1.r0.c0.p1", "expected_text": "교실 환경 개선"},
            {"target": "t1.r1.c0.p1", "expected_text": "학부모 안내문 배포"},
        ],
    )
    assert verified["verified"] is True
    assert verified["counts"]["verified"] == 3


def test_meeting_minutes_complete_addressed_template_e2e(tmp_path):
    out = tmp_path / "meeting_minutes_completed.hwpx"
    found = server.find_text_occurrences(str(MEETING_MINUTES), "○○○")
    assert [item["target"] for item in found["occurrences"]] == ["s1.p2.occ1", "t1.r0.c0.p1.occ1", "t1.r1.c0.p1.occ1"]

    report = complete_addressed_template(
        MEETING_MINUTES,
        [
            {"target": "b2", "kind": "body_para", "operation": "replace_text", "value": "결정 사항 예산 승인", "expected_text": "결정 사항 ○○○"},
            {"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "교실 환경 개선", "expected_text": "○○○"},
            {"target": "t1.r1.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "학부모 안내문 배포", "expected_text": "○○○"},
        ],
        out,
    )

    assert report["ok"] is True
    assert report["state"] == "complete"
    assert report["counts"] == {"requested": 3, "resolved": 3, "applied": 3, "verified": 3, "skipped": 0, "unresolved": 0}
    assert report["coverage_ratio"] == 1.0
    assert report["source_sha256"] != report["target_sha256"]

    verified = server.verify_targets(
        str(out),
        [
            {"target": "b2", "expected_text": "결정 사항 예산 승인"},
            {"target": "t1.r0.c0.p1", "expected_text": "교실 환경 개선"},
            {"target": "t1.r1.c0.p1", "expected_text": "학부모 안내문 배포"},
        ],
    )
    assert verified["verified"] is True
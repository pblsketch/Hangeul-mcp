from __future__ import annotations

from pathlib import Path

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

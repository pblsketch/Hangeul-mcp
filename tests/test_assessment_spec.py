from __future__ import annotations

from copy import deepcopy
import unicodedata

import pytest

from hangeul_core.assessment_spec import AssessmentSpecError, parse_assessment_spec
from hangeul_core.assessment_rubric import score_rubric


def valid_spec() -> dict[str, object]:
    return {
        "spec_version": 1,
        "profile_id": "formative.assessment.v1",
        "metadata": {
            "title": "읽기 형성평가",
            "subject": "국어",
            "grade": "고등학교 1학년",
            "unit": "설득하는 글 읽기",
            "learning_objectives": ["주장의 타당성을 판단한다."],
            "total_points": 10,
        },
        "learning_evidence": [
            {"evidence_id": "ev-1", "claim": "주장을 찾는다.", "expected_evidence": "핵심 주장을 선택한다."},
            {"evidence_id": "ev-2", "claim": "근거를 요약한다.", "expected_evidence": "허용 답 중 하나를 쓴다."},
            {"evidence_id": "ev-3", "claim": "타당성을 판단한다.", "expected_evidence": "준거에 따라 서술한다."},
        ],
        "items": [
            {
                "item_id": "item-1", "order": 1, "type": "multiple_choice",
                "stem": "글의 핵심 주장으로 알맞은 것은?", "points": 4,
                "evidence_ids": ["ev-1"],
                "choices": [{"choice_id": "A", "text": "첫째 주장"}, {"choice_id": "B", "text": "둘째 주장"}],
                "answer": "A", "rationale": "본문의 반복 표현이 근거다.",
                "misconceptions": ["예시를 주장으로 오해함"],
                "feedback": {"correct": "주장을 정확히 찾았다.", "incorrect": "반복되는 핵심 문장을 다시 보자."},
            },
            {
                "item_id": "item-2", "order": 2, "type": "short_answer",
                "stem": "핵심 근거를 한 문장으로 쓰시오.", "points": 2,
                "evidence_ids": ["ev-2"], "answer": ["자료의 신뢰성", "자료가 믿을 만함"],
                "rationale": "출처와 조사 방법이 제시되었다.", "misconceptions": [],
                "feedback": {"correct": "근거를 정확히 요약했다.", "incorrect": "자료의 출처를 확인하자."},
            },
            {
                "item_id": "item-3", "order": 3, "type": "constructed_response",
                "stem": "주장의 타당성을 평가하시오.", "points": 4,
                "evidence_ids": ["ev-3"], "answer": "근거의 관련성과 신뢰성을 함께 판단한다.",
                "rationale": "두 준거가 모두 필요하다.", "misconceptions": ["의견만 제시함"],
                "feedback": {"correct": "두 준거를 모두 적용했다.", "incorrect": "판단 준거를 명시하자."},
                "rubric": {"criteria": [
                    {"criterion_id": "relevance", "description": "관련성 판단", "levels": [
                        {"level_id": "none", "min_score": 0, "max_score": 0, "descriptor": "판단 없음"},
                        {"level_id": "partial", "min_score": 1, "max_score": 1, "descriptor": "판단만 제시"},
                        {"level_id": "full", "min_score": 2, "max_score": 2, "descriptor": "근거와 함께 판단"},
                    ]},
                    {"criterion_id": "credibility", "description": "신뢰성 판단", "levels": [
                        {"level_id": "none", "min_score": 0, "max_score": 0, "descriptor": "판단 없음"},
                        {"level_id": "partial", "min_score": 1, "max_score": 1, "descriptor": "판단만 제시"},
                        {"level_id": "full", "min_score": 2, "max_score": 2, "descriptor": "근거와 함께 판단"},
                    ]},
                ]},
            },
        ],
    }


def assert_code(raw: object, code: str) -> None:
    with pytest.raises(AssessmentSpecError) as caught:
        parse_assessment_spec(raw)
    assert caught.value.code == code


def test_valid_assessment_spec_normalizes_canonically():
    raw = valid_spec()
    equivalent = deepcopy(raw)
    equivalent["items"] = list(reversed(equivalent["items"]))

    def nfd(value: object) -> object:
        if isinstance(value, str):
            return unicodedata.normalize("NFD", value)
        if isinstance(value, list):
            return [nfd(child) for child in value]
        if isinstance(value, dict):
            return {key: nfd(child) for key, child in reversed(tuple(value.items()))}
        return value

    first = parse_assessment_spec(raw)
    second = parse_assessment_spec(nfd(equivalent))
    assert first == second
    assert first.spec_fingerprint == second.spec_fingerprint
    assert tuple(item.order for item in first.items) == (1, 2, 3)


@pytest.mark.parametrize("path", ["top", "metadata", "evidence", "item", "choice", "feedback", "rubric", "criterion", "level"])
def test_unknown_top_and_nested_keys_are_rejected(path: str):
    raw = valid_spec()
    targets = {
        "top": raw,
        "metadata": raw["metadata"],
        "evidence": raw["learning_evidence"][0],
        "item": raw["items"][0],
        "choice": raw["items"][0]["choices"][0],
        "feedback": raw["items"][0]["feedback"],
        "rubric": raw["items"][2]["rubric"],
        "criterion": raw["items"][2]["rubric"]["criteria"][0],
        "level": raw["items"][2]["rubric"]["criteria"][0]["levels"][0],
    }
    targets[path]["unexpected"] = "blocked"
    assert_code(raw, "invalid_spec" if path not in {"item", "rubric", "criterion", "level"} else "invalid_item_shape")


@pytest.mark.parametrize("kind", ["item_id", "choice_id", "evidence_id", "order"])
def test_duplicate_item_choice_evidence_ids_and_orders_are_rejected(kind: str):
    raw = valid_spec()
    if kind == "item_id": raw["items"][1]["item_id"] = "item-1"
    elif kind == "choice_id": raw["items"][0]["choices"][1]["choice_id"] = "A"
    elif kind == "evidence_id": raw["learning_evidence"][1]["evidence_id"] = "ev-1"
    else: raw["items"][1]["order"] = 1
    assert_code(raw, "invalid_spec")


@pytest.mark.parametrize("index,value", [(0, "Z"), (1, "not-a-list"), (2, ["not-a-string-answer"])])
def test_each_item_type_requires_its_exact_answer_shape(index: int, value: object):
    raw = valid_spec(); raw["items"][index]["answer"] = value
    assert_code(raw, "invalid_item_shape")


def test_item_point_sum_must_equal_total_points():
    raw = valid_spec(); raw["metadata"]["total_points"] = 11
    assert_code(raw, "score_mismatch")


@pytest.mark.parametrize("where,key", [("top", "student_name"), ("metadata", "student_id")])
def test_personal_identifier_fields_are_rejected(where: str, key: str):
    raw = valid_spec(); (raw if where == "top" else raw["metadata"])[key] = "sentinel"
    assert_code(raw, "invalid_spec")


def test_items_require_valid_evidence_and_orphans_are_rejected():
    raw = valid_spec(); raw["items"][0]["evidence_ids"] = ["missing"]
    assert_code(raw, "unknown_evidence_reference")
    raw = valid_spec(); raw["items"][2]["evidence_ids"] = ["ev-2"]
    assert_code(raw, "orphan_evidence")


def test_constructed_item_accepts_exact_recursive_rubric_shape():
    spec = parse_assessment_spec(valid_spec())
    assert spec.items[2].rubric.criteria[0].levels[-1].max_score == 2
    assert score_rubric(spec.items[2].rubric, {"relevance": 2, "credibility": 2}) == 4


@pytest.mark.parametrize("mutation", ["missing", "unknown"])
def test_rubric_rejects_missing_or_unknown_nested_keys(mutation: str):
    raw = valid_spec(); level = raw["items"][2]["rubric"]["criteria"][0]["levels"][0]
    if mutation == "missing": del level["descriptor"]
    else: level["weight"] = 1
    assert_code(raw, "invalid_item_shape")


@pytest.mark.parametrize("where", ["criteria", "levels"])
def test_rubric_rejects_empty_criteria_and_levels(where: str):
    raw = valid_spec(); rubric = raw["items"][2]["rubric"]
    if where == "criteria": rubric["criteria"] = []
    else: rubric["criteria"][0]["levels"] = []
    assert_code(raw, "invalid_item_shape")


@pytest.mark.parametrize("field", ["criterion_id", "description", "level_id", "descriptor"])
def test_rubric_rejects_blank_ids_descriptions_and_descriptors(field: str):
    raw = valid_spec(); criterion = raw["items"][2]["rubric"]["criteria"][0]
    (criterion if field in {"criterion_id", "description"} else criterion["levels"][0])[field] = "  "
    assert_code(raw, "invalid_item_shape")


@pytest.mark.parametrize("points", [True, 1.5, 0, -1])
def test_item_points_reject_bool_non_integer_zero_and_negative(points: object):
    raw = valid_spec(); raw["items"][0]["points"] = points
    assert_code(raw, "invalid_item_shape")


@pytest.mark.parametrize("scores", [(True, 0), (0.5, 1), (-1, 0), (0, -1), (0, 1), (2, 2)])
def test_rubric_score_ranges_reject_bool_non_integer_negative_gap_and_overlap(scores: tuple[object, object]):
    raw = valid_spec(); levels = raw["items"][2]["rubric"]["criteria"][0]["levels"]
    levels[1]["min_score"], levels[0]["max_score"] = scores
    assert_code(raw, "invalid_item_shape")


@pytest.mark.parametrize("kind", ["criterion", "level"])
def test_rubric_rejects_duplicate_criterion_and_level_ids(kind: str):
    raw = valid_spec(); criteria = raw["items"][2]["rubric"]["criteria"]
    if kind == "criterion": criteria[1]["criterion_id"] = "relevance"
    else: criteria[0]["levels"][1]["level_id"] = "none"
    assert_code(raw, "invalid_item_shape")


def test_rubric_maximum_sum_must_equal_item_points_at_boundaries():
    raw = valid_spec(); raw["items"][2]["rubric"]["criteria"][1]["levels"][-1]["max_score"] = 3
    assert_code(raw, "score_mismatch")

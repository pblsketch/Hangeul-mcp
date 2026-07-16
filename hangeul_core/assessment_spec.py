from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
from typing import TypeGuard
import unicodedata

from .assessment_rubric import RubricValidationError, parse_rubric
from .assessment_spec_models import (
    AssessmentItem, AssessmentMetadata, AssessmentSpec, Choice, ConstructedResponseItem,
    Feedback, LearningEvidence, MultipleChoiceItem, ShortAnswerItem,
)
from .assessment_plan import JsonValue
from .assessment_values import canonical_bytes


PROFILE_ID = "formative.assessment.v1"
RawMapping = Mapping[str, object]


class AssessmentSpecError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _is_mapping(value: object) -> TypeGuard[RawMapping]:
    return isinstance(value, Mapping) and all(isinstance(key, str) for key in value)


def _mapping(value: object, code: str = "invalid_spec") -> RawMapping:
    if not _is_mapping(value):
        raise AssessmentSpecError(code)
    return value


def _sequence(value: object, code: str = "invalid_spec") -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise AssessmentSpecError(code)
    return value


def _keys(raw: RawMapping, expected: frozenset[str], code: str = "invalid_spec") -> None:
    if frozenset(raw) != expected:
        raise AssessmentSpecError(code)


def _text(value: object, code: str = "invalid_spec") -> str:
    if not isinstance(value, str):
        raise AssessmentSpecError(code)
    result = unicodedata.normalize("NFC", value).strip()
    if not result:
        raise AssessmentSpecError(code)
    return result


def _positive_int(value: object, code: str = "invalid_spec") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AssessmentSpecError(code)
    return value


def _texts(value: object, code: str = "invalid_spec", *, nonempty: bool = True) -> tuple[str, ...]:
    result = tuple(_text(item, code) for item in _sequence(value, code))
    if nonempty and not result:
        raise AssessmentSpecError(code)
    return result


def _feedback(value: object) -> Feedback:
    raw = _mapping(value)
    _keys(raw, frozenset({"correct", "incorrect"}))
    return Feedback(_text(raw["correct"]), _text(raw["incorrect"]))


def _choices(value: object) -> tuple[Choice, ...]:
    result: list[Choice] = []
    for value_item in _sequence(value, "invalid_item_shape"):
        raw = _mapping(value_item, "invalid_item_shape")
        _keys(raw, frozenset({"choice_id", "text"}))
        result.append(Choice(_text(raw["choice_id"]), _text(raw["text"])))
    choices = tuple(result)
    if not 2 <= len(choices) <= 5 or len({choice.choice_id for choice in choices}) != len(choices):
        raise AssessmentSpecError("invalid_spec")
    return choices


_COMMON = frozenset({
    "item_id", "order", "type", "stem", "points", "evidence_ids", "answer",
    "rationale", "misconceptions", "feedback",
})


def _common(raw: RawMapping) -> tuple[str, int, str, str, int, tuple[str, ...], str, tuple[str, ...], Feedback]:
    item_type = _text(raw.get("type"), "invalid_item_shape")
    return (
        _text(raw.get("item_id")), _positive_int(raw.get("order")), item_type,
        _text(raw.get("stem"), "invalid_item_shape"), _positive_int(raw.get("points"), "invalid_item_shape"),
        _texts(raw.get("evidence_ids")), _text(raw.get("rationale"), "invalid_item_shape"),
        _texts(raw.get("misconceptions"), "invalid_item_shape", nonempty=False), _feedback(raw.get("feedback")),
    )


def _parse_item(value: object) -> AssessmentItem:
    raw = _mapping(value, "invalid_item_shape")
    item_type = _text(raw.get("type"), "invalid_item_shape")
    expected = _COMMON | ({"choices"} if item_type == "multiple_choice" else {"rubric"} if item_type == "constructed_response" else set())
    if item_type not in {"multiple_choice", "short_answer", "constructed_response"}:
        raise AssessmentSpecError("invalid_item_shape")
    _keys(raw, frozenset(expected), "invalid_item_shape")
    item_id, order, _, stem, points, evidence_ids, rationale, misconceptions, feedback = _common(raw)
    if item_type == "multiple_choice":
        choices = _choices(raw["choices"])
        answer = _text(raw["answer"], "invalid_item_shape")
        if answer not in {choice.choice_id for choice in choices}:
            raise AssessmentSpecError("invalid_item_shape")
        return MultipleChoiceItem(item_id, order, item_type, stem, points, evidence_ids, choices, answer, rationale, misconceptions, feedback)
    if item_type == "short_answer":
        short_answers = _texts(raw["answer"], "invalid_item_shape")
        return ShortAnswerItem(item_id, order, item_type, stem, points, evidence_ids, short_answers, rationale, misconceptions, feedback)
    try:
        rubric = parse_rubric(raw["rubric"], points)
    except RubricValidationError as error:
        raise AssessmentSpecError(error.code) from error
    return ConstructedResponseItem(item_id, order, item_type, stem, points, evidence_ids, _text(raw["answer"], "invalid_item_shape"), rationale, misconceptions, feedback, rubric)


def _metadata(value: object) -> AssessmentMetadata:
    raw = _mapping(value)
    _keys(raw, frozenset({"title", "subject", "grade", "unit", "learning_objectives", "total_points"}))
    return AssessmentMetadata(
        _text(raw["title"]), _text(raw["subject"]), _text(raw["grade"]), _text(raw["unit"]),
        _texts(raw["learning_objectives"]), _positive_int(raw["total_points"]),
    )


def _evidence(value: object) -> LearningEvidence:
    raw = _mapping(value)
    _keys(raw, frozenset({"evidence_id", "claim", "expected_evidence"}))
    return LearningEvidence(_text(raw["evidence_id"]), _text(raw["claim"]), _text(raw["expected_evidence"]))


def _canonical_payload(metadata: AssessmentMetadata, evidence: tuple[LearningEvidence, ...], items: tuple[AssessmentItem, ...]) -> JsonValue:
    def item_payload(item: AssessmentItem) -> dict[str, JsonValue]:
        value: dict[str, JsonValue] = {
            "item_id": item.item_id, "order": item.order, "type": item.type, "stem": item.stem,
            "points": item.points, "evidence_ids": item.evidence_ids, "answer": item.answer,
            "rationale": item.rationale, "misconceptions": item.misconceptions,
            "feedback": {"correct": item.feedback.correct, "incorrect": item.feedback.incorrect},
        }
        if item.choices: value["choices"] = tuple({"choice_id": choice.choice_id, "text": choice.text} for choice in item.choices)
        if item.rubric is not None:
            value["rubric"] = {"criteria": tuple({
                "criterion_id": criterion.criterion_id, "description": criterion.description,
                "levels": tuple({"level_id": level.level_id, "min_score": level.min_score, "max_score": level.max_score, "descriptor": level.descriptor} for level in criterion.levels),
            } for criterion in item.rubric.criteria)}
        return value
    metadata_payload: dict[str, JsonValue] = {
        "title": metadata.title, "subject": metadata.subject, "grade": metadata.grade,
        "unit": metadata.unit, "learning_objectives": metadata.learning_objectives,
        "total_points": metadata.total_points,
    }
    return {
        "spec_version": 1, "profile_id": PROFILE_ID,
        "metadata": metadata_payload,
        "learning_evidence": tuple({"evidence_id": row.evidence_id, "claim": row.claim, "expected_evidence": row.expected_evidence} for row in evidence),
        "items": tuple(item_payload(item) for item in items),
    }


def parse_assessment_spec(value: object) -> AssessmentSpec:
    raw = _mapping(value)
    _keys(raw, frozenset({"spec_version", "profile_id", "metadata", "learning_evidence", "items"}))
    if raw["spec_version"] != 1 or isinstance(raw["spec_version"], bool) or raw["profile_id"] != PROFILE_ID:
        raise AssessmentSpecError("invalid_spec")
    metadata = _metadata(raw["metadata"])
    evidence = tuple(sorted((_evidence(row) for row in _sequence(raw["learning_evidence"])), key=lambda row: row.evidence_id))
    items = tuple(sorted((_parse_item(row) for row in _sequence(raw["items"])), key=lambda row: (row.order, row.item_id)))
    if not evidence or not items:
        raise AssessmentSpecError("invalid_spec")
    if len({row.evidence_id for row in evidence}) != len(evidence) or len({row.item_id for row in items}) != len(items) or len({row.order for row in items}) != len(items):
        raise AssessmentSpecError("invalid_spec")
    known, used = {row.evidence_id for row in evidence}, {identifier for item in items for identifier in item.evidence_ids}
    if not used <= known: raise AssessmentSpecError("unknown_evidence_reference")
    if known != used: raise AssessmentSpecError("orphan_evidence")
    if sum(item.points for item in items) != metadata.total_points: raise AssessmentSpecError("score_mismatch")
    payload = _canonical_payload(metadata, evidence, items)
    fingerprint = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    return AssessmentSpec(1, PROFILE_ID, metadata, evidence, items, fingerprint)


validate_assessment_spec = parse_assessment_spec


__all__ = ["AssessmentSpecError", "PROFILE_ID", "parse_assessment_spec", "validate_assessment_spec"]

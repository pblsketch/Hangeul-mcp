from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeGuard
import unicodedata

from .assessment_spec_models import Rubric, RubricCriterion, RubricLevel


class RubricValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


RawMapping = Mapping[str, object]


def _is_mapping(value: object) -> TypeGuard[RawMapping]:
    return isinstance(value, Mapping) and all(isinstance(key, str) for key in value)


def _mapping(value: object) -> RawMapping:
    if not _is_mapping(value):
        raise RubricValidationError("invalid_item_shape")
    return value


def _sequence(value: object) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise RubricValidationError("invalid_item_shape")
    return value


def _exact_keys(value: RawMapping, keys: frozenset[str]) -> None:
    if frozenset(value) != keys:
        raise RubricValidationError("invalid_item_shape")


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise RubricValidationError("invalid_item_shape")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise RubricValidationError("invalid_item_shape")
    return normalized


def _score(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RubricValidationError("invalid_item_shape")
    return value


def _parse_level(value: object) -> RubricLevel:
    raw = _mapping(value)
    _exact_keys(raw, frozenset({"level_id", "min_score", "max_score", "descriptor"}))
    minimum, maximum = _score(raw["min_score"]), _score(raw["max_score"])
    if minimum > maximum:
        raise RubricValidationError("invalid_item_shape")
    return RubricLevel(_text(raw["level_id"]), minimum, maximum, _text(raw["descriptor"]))


def _parse_criterion(value: object) -> RubricCriterion:
    raw = _mapping(value)
    _exact_keys(raw, frozenset({"criterion_id", "description", "levels"}))
    levels = tuple(_parse_level(level) for level in _sequence(raw["levels"]))
    if not levels or len({level.level_id for level in levels}) != len(levels):
        raise RubricValidationError("invalid_item_shape")
    if levels[0].min_score != 0:
        raise RubricValidationError("invalid_item_shape")
    for previous, current in zip(levels, levels[1:]):
        if previous.min_score >= current.min_score or previous.max_score + 1 != current.min_score:
            raise RubricValidationError("invalid_item_shape")
    return RubricCriterion(_text(raw["criterion_id"]), _text(raw["description"]), levels)


def parse_rubric(value: object, item_points: int) -> Rubric:
    raw = _mapping(value)
    _exact_keys(raw, frozenset({"criteria"}))
    criteria = tuple(_parse_criterion(criterion) for criterion in _sequence(raw["criteria"]))
    if not criteria or len({criterion.criterion_id for criterion in criteria}) != len(criteria):
        raise RubricValidationError("invalid_item_shape")
    if sum(criterion.levels[-1].max_score for criterion in criteria) != item_points:
        raise RubricValidationError("score_mismatch")
    return Rubric(criteria)


def score_rubric(rubric: Rubric, scores: Mapping[str, int]) -> int:
    if frozenset(scores) != frozenset(criterion.criterion_id for criterion in rubric.criteria):
        raise RubricValidationError("score_mismatch")
    total = 0
    for criterion in rubric.criteria:
        score = scores[criterion.criterion_id]
        if not isinstance(score, int) or isinstance(score, bool):
            raise RubricValidationError("score_mismatch")
        if sum(level.min_score <= score <= level.max_score for level in criterion.levels) != 1:
            raise RubricValidationError("score_mismatch")
        total += score
    return total


__all__ = ["RubricValidationError", "parse_rubric", "score_rubric"]

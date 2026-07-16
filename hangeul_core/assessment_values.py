from __future__ import annotations

import json
import unicodedata
from typing import Mapping, Sequence, TypeGuard

from .assessment_plan import JsonValue, SpecMapping
from .assessment_profile import AssessmentProfileError


class AssessmentCompilerError(AssessmentProfileError):
    pass


def is_mapping(value: object) -> TypeGuard[SpecMapping]:
    return isinstance(value, Mapping) and all(isinstance(key, str) for key in value)


def mapping_value(value: object, code: str = "invalid_spec") -> SpecMapping:
    if not is_mapping(value):
        raise AssessmentCompilerError(code)
    return value


def is_sequence(value: object) -> TypeGuard[Sequence[JsonValue]]:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def sequence_value(value: object, code: str = "invalid_spec") -> Sequence[JsonValue]:
    if not is_sequence(value):
        raise AssessmentCompilerError(code)
    return value


def text_value(value: object) -> str:
    if not isinstance(value, str):
        raise AssessmentCompilerError("invalid_spec")
    return unicodedata.normalize("NFC", value)


def integer_value(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise AssessmentCompilerError("invalid_spec")
    return value


def normalized_value(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or type(value) in (bool, int, float):
        return value
    if isinstance(value, Mapping):
        pairs = ((unicodedata.normalize("NFC", key), normalized_value(child)) for key, child in value.items())
        return {key: child for key, child in sorted(pairs)}
    return [normalized_value(child) for child in sequence_value(value)]


def canonical_bytes(value: JsonValue) -> bytes:
    return json.dumps(
        normalized_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


__all__ = [
    "AssessmentCompilerError",
    "canonical_bytes",
    "integer_value",
    "mapping_value",
    "normalized_value",
    "sequence_value",
    "text_value",
]

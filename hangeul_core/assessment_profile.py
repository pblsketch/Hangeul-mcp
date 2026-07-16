from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


PROFILE_ID = "formative.assessment.v1"
PROFILE_VERSION = 1


class AssessmentProfileError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RegionSignature:
    target: str
    kind: str
    container: str
    table: int | None = None
    row: int | None = None
    col: int | None = None
    paragraph_count: int = 1
    markers: tuple[str, ...] = ()


@dataclass(frozen=True)
class MetadataSlot:
    slot_id: str
    target: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class SemanticItemSlot:
    item_type: str
    target: str


@dataclass(frozen=True)
class VariantRule:
    variant: str
    use_metadata_slots: tuple[str, ...]
    use_item_slots: tuple[str, ...]
    remove_targets: tuple[str, ...]
    teacher_fields: tuple[str, ...]


@dataclass(frozen=True)
class AssessmentProfile:
    profile_id: str
    profile_version: int
    regions: tuple[RegionSignature, ...]
    metadata_slots: tuple[MetadataSlot, ...]
    item_slots: tuple[SemanticItemSlot, ...]
    variant_rules: tuple[VariantRule, ...]
    allowed_operations: tuple[str, ...]
    profile_definition_digest: str


_EXPECTED_REGIONS = (
    *(RegionSignature(f"b{ordinal}", "body_para", "body") for ordinal in range(1, 37)),
    RegionSignature("t1.r0.c0", "cell", "table_cell", 1, 0, 0, 3, ("", "", "")),
    RegionSignature("t2.r0.c0", "cell", "table_cell", 2, 0, 0, 1, ("",)),
    RegionSignature("t2.r0.c1", "cell", "table_cell", 2, 0, 1, 1, ("< ",)),
    RegionSignature("t2.r0.c2", "cell", "table_cell", 2, 0, 2, 1, ("",)),
    RegionSignature("t2.r1.c0", "cell", "table_cell", 2, 1, 0, 1, ("",)),
    RegionSignature("t2.r1.c2", "cell", "table_cell", 2, 1, 2, 1, ("",)),
    RegionSignature("t2.r2.c0", "cell", "table_cell", 2, 2, 0, 3, ("", "", "")),
    RegionSignature("t3.r0.c0", "cell", "table_cell", 3, 0, 0, 1, ("",)),
)
_ALLOWED_OPERATIONS = ("replace_text",)
_METADATA_SLOTS = (
    MetadataSlot("assessment_header", "t1.r0.c0", ("title", "subject", "grade", "unit", "total_points")),
)
_ITEM_SLOTS = (
    *(SemanticItemSlot("multiple_choice", target) for target in ("b1", "b7", "b14", "b21", "b22")),
    *(SemanticItemSlot("short_answer", target) for target in ("b25", "b28", "b29", "b30")),
    *(SemanticItemSlot("constructed_response", target) for target in ("b33", "b34", "b35", "b36")),
)
_ITEM_TARGETS = tuple(slot.target for slot in _ITEM_SLOTS)
_VARIANT_RULES = (
    VariantRule("student", ("t1.r0.c0",), _ITEM_TARGETS, (), ()),
    VariantRule("teacher", ("t1.r0.c0",), _ITEM_TARGETS, (), ("answer", "rationale", "rubric", "misconceptions", "feedback")),
    VariantRule("answer_key", ("t1.r0.c0",), _ITEM_TARGETS, (), ("answer", "rationale", "rubric")),
)


def _profile_definition_digest() -> str:
    definition = {
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
        "regions": [asdict(region) for region in _EXPECTED_REGIONS],
        "metadata_slots": [asdict(slot) for slot in _METADATA_SLOTS],
        "item_slots": [asdict(slot) for slot in _ITEM_SLOTS],
        "variant_rules": [asdict(rule) for rule in _VARIANT_RULES],
        "allowed_operations": list(_ALLOWED_OPERATIONS),
    }
    canonical = json.dumps(
        definition,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


_PROFILE = AssessmentProfile(
    profile_id=PROFILE_ID,
    profile_version=PROFILE_VERSION,
    regions=_EXPECTED_REGIONS,
    metadata_slots=_METADATA_SLOTS,
    item_slots=_ITEM_SLOTS,
    variant_rules=_VARIANT_RULES,
    allowed_operations=_ALLOWED_OPERATIONS,
    profile_definition_digest=_profile_definition_digest(),
)


def registered_profiles() -> tuple[AssessmentProfile, ...]:
    return (_PROFILE,)


def get_assessment_profile(profile_id: str) -> AssessmentProfile:
    if profile_id != PROFILE_ID:
        raise AssessmentProfileError("profile_mismatch")
    return _PROFILE


def _inspection_signatures(inspection: Mapping[str, object]) -> tuple[RegionSignature, ...]:
    raw_regions = inspection.get("regions")
    if not isinstance(raw_regions, Sequence) or isinstance(raw_regions, (str, bytes)):
        raise AssessmentProfileError("profile_mismatch")

    signatures: list[RegionSignature] = []
    for raw_region in raw_regions:
        if not isinstance(raw_region, Mapping):
            raise AssessmentProfileError("profile_mismatch")
        target = raw_region.get("target")
        kind = raw_region.get("kind")
        container = raw_region.get("container")
        if (
            not isinstance(target, str)
            or not isinstance(kind, str)
            or not isinstance(container, str)
        ):
            raise AssessmentProfileError("profile_mismatch")
        if kind == "cell":
            table = raw_region.get("table")
            row = raw_region.get("row")
            col = raw_region.get("col")
            paragraph_count = raw_region.get("paragraph_count")
            paragraphs = raw_region.get("paragraphs")
            if (
                not isinstance(table, int)
                or not isinstance(row, int)
                or not isinstance(col, int)
                or not isinstance(paragraph_count, int)
                or not isinstance(paragraphs, Sequence)
                or isinstance(paragraphs, (str, bytes))
            ):
                raise AssessmentProfileError("profile_mismatch")
            markers: list[str] = []
            for paragraph in paragraphs:
                if not isinstance(paragraph, Mapping) or not isinstance(paragraph.get("marker"), str):
                    raise AssessmentProfileError("profile_mismatch")
                markers.append(paragraph["marker"])
            if len(markers) != paragraph_count:
                raise AssessmentProfileError("profile_mismatch")
            signatures.append(
                RegionSignature(
                    target,
                    kind,
                    container,
                    table,
                    row,
                    col,
                    paragraph_count,
                    tuple(markers),
                )
            )
        else:
            signatures.append(RegionSignature(target, kind, container))
    return tuple(signatures)


def match_assessment_profile(
    profile_id: str,
    inspection: Mapping[str, object],
) -> AssessmentProfile:
    profile = get_assessment_profile(profile_id)
    signatures = _inspection_signatures(inspection)
    targets = [signature.target for signature in signatures]
    if len(targets) != len(set(targets)):
        raise AssessmentProfileError("ambiguous_mapping")
    if inspection.get("unsupported_controls") or signatures != profile.regions:
        raise AssessmentProfileError("profile_mismatch")
    return profile


__all__ = [
    "PROFILE_ID",
    "PROFILE_VERSION",
    "AssessmentProfile",
    "AssessmentProfileError",
    "MetadataSlot",
    "RegionSignature",
    "SemanticItemSlot",
    "VariantRule",
    "get_assessment_profile",
    "match_assessment_profile",
    "registered_profiles",
]

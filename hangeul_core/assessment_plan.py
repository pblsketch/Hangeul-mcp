from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, TypeAlias, Union


JsonScalar: TypeAlias = Union[str, int, float, bool, None]
JsonValue: TypeAlias = Union[
    JsonScalar,
    Mapping[str, "JsonValue"],
    Sequence["JsonValue"],
]
SpecMapping: TypeAlias = Mapping[str, JsonValue]


@dataclass(frozen=True)
class AddressedEdit:
    target: str
    value: str
    expected_text: str
    kind: str
    operation: str


@dataclass(frozen=True)
class ItemTrace:
    item_id: str
    order: int
    points: int
    evidence_ids: tuple[str, ...]
    target: str


@dataclass(frozen=True)
class ProvenanceEdge:
    target: str
    source_field: str
    classification: str


@dataclass(frozen=True)
class VariantPlan:
    variant: str
    edits: tuple[AddressedEdit, ...]
    item_trace: tuple[ItemTrace, ...]
    provenance: tuple[ProvenanceEdge, ...]
    frozen_plan_digest: str


@dataclass(frozen=True)
class AssessmentPlan:
    profile_id: str
    profile_version: int
    profile_definition_digest: str
    source_digest: str
    variants: tuple[VariantPlan, ...]

    def variant(self, name: str) -> VariantPlan:
        for plan in self.variants:
            if plan.variant == name:
                return plan
        raise KeyError(name)


__all__ = [
    "AddressedEdit",
    "AssessmentPlan",
    "ItemTrace",
    "JsonValue",
    "ProvenanceEdge",
    "SpecMapping",
    "VariantPlan",
]

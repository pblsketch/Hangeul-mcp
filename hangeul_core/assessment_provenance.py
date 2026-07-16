from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, assert_never

from .assessment_plan import VariantPlan
from .assessment_values import AssessmentCompilerError


class ProvenanceVariant(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ANSWER_KEY = "answer_key"


class ProvenanceClassification(StrEnum):
    STUDENT_VISIBLE = "student_visible"
    TEACHER_ONLY = "teacher_only"


VISIBLE_SOURCE_FIELDS: Final = ("order", "stem", "points", "choices")
TEACHER_FIELDS_BY_VARIANT: Final = {
    ProvenanceVariant.STUDENT: (),
    ProvenanceVariant.TEACHER: ("answer", "rationale", "rubric", "misconceptions", "feedback"),
    ProvenanceVariant.ANSWER_KEY: ("answer", "rationale", "rubric"),
}
SECONDARY_FORBIDDEN_BY_VARIANT: Final = {
    ProvenanceVariant.STUDENT: ("answer", "rationale", "rubric", "misconceptions", "feedback"),
    ProvenanceVariant.TEACHER: (),
    ProvenanceVariant.ANSWER_KEY: ("misconceptions", "feedback"),
}
TEXT_MARKERS_BY_FIELD: Final = {
    "answer": ("answer:",),
    "rationale": ("rationale:",),
    "rubric": ("rubric:",),
    "misconceptions": ("misconceptions:",),
    "feedback": ("feedback:",),
}
XML_MARKERS_BY_FIELD: Final = {
    "answer": ("<answer", "</answer"),
    "rationale": ("<rationale", "</rationale"),
    "rubric": ("<rubric", "</rubric"),
    "misconceptions": ("<misconceptions", "</misconceptions"),
    "feedback": ("<feedback", "</feedback"),
}


@dataclass(frozen=True, slots=True)
class ProvenanceViolation:
    code: str
    variant: str
    target: str | None = None
    source_field: str | None = None
    classification: str | None = None
    surface: str | None = None


class ProvenanceAuditError(AssessmentCompilerError):
    def __init__(self, violations: tuple[ProvenanceViolation, ...]) -> None:
        code = violations[0].code if violations else "provenance_violation"
        super().__init__(code)
        self.violations = violations

    def __str__(self) -> str:
        return self.code


def _variant_name(raw: str) -> ProvenanceVariant:
    return ProvenanceVariant(raw)


def _classification_name(raw: str) -> ProvenanceClassification:
    return ProvenanceClassification(raw)


def _allowed_teacher_fields(variant: ProvenanceVariant) -> tuple[str, ...]:
    match variant:
        case ProvenanceVariant.STUDENT:
            return TEACHER_FIELDS_BY_VARIANT[ProvenanceVariant.STUDENT]
        case ProvenanceVariant.TEACHER:
            return TEACHER_FIELDS_BY_VARIANT[ProvenanceVariant.TEACHER]
        case ProvenanceVariant.ANSWER_KEY:
            return TEACHER_FIELDS_BY_VARIANT[ProvenanceVariant.ANSWER_KEY]
        case unreachable:
            assert_never(unreachable)


def _secondary_forbidden_fields(variant: ProvenanceVariant) -> tuple[str, ...]:
    match variant:
        case ProvenanceVariant.STUDENT:
            return SECONDARY_FORBIDDEN_BY_VARIANT[ProvenanceVariant.STUDENT]
        case ProvenanceVariant.TEACHER:
            return SECONDARY_FORBIDDEN_BY_VARIANT[ProvenanceVariant.TEACHER]
        case ProvenanceVariant.ANSWER_KEY:
            return SECONDARY_FORBIDDEN_BY_VARIANT[ProvenanceVariant.ANSWER_KEY]
        case unreachable:
            assert_never(unreachable)


def _contains_marker(fragment: str, markers: tuple[str, ...]) -> bool:
    lowered = fragment.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def _primary_violations(variant_plan: VariantPlan) -> tuple[ProvenanceViolation, ...]:
    try:
        variant = _variant_name(variant_plan.variant)
    except ValueError:
        return (ProvenanceViolation("unsupported_variant", "invalid"),)

    edit_targets = {edit.target for edit in variant_plan.edits}
    if not edit_targets:
        return (ProvenanceViolation("empty_edit_set", variant.value),)

    allowed_teacher_fields = _allowed_teacher_fields(variant)
    seen_primary_targets: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    violations: list[ProvenanceViolation] = []

    for edge in variant_plan.provenance:
        edge_key = (edge.target, edge.source_field, edge.classification)
        if edge_key in seen_edges:
            violations.append(
                ProvenanceViolation(
                    "duplicate_provenance_edge",
                    variant.value,
                    target=edge.target,
                    source_field=edge.source_field,
                    classification=edge.classification,
                )
            )
            continue
        seen_edges.add(edge_key)

        if edge.target not in edit_targets:
            violations.append(
                ProvenanceViolation(
                    "orphan_provenance_edge",
                    variant.value,
                    target=edge.target,
                    source_field=edge.source_field,
                    classification=edge.classification,
                )
            )
            continue

        try:
            classification = _classification_name(edge.classification)
        except ValueError:
            violations.append(
                ProvenanceViolation(
                    "unknown_provenance_classification",
                    variant.value,
                    target=edge.target,
                    source_field=edge.source_field,
                    classification=edge.classification,
                )
            )
            continue

        if classification == ProvenanceClassification.STUDENT_VISIBLE:
            if edge.source_field not in VISIBLE_SOURCE_FIELDS:
                violations.append(
                    ProvenanceViolation(
                        "invalid_visible_source_field",
                        variant.value,
                        target=edge.target,
                        source_field=edge.source_field,
                        classification=edge.classification,
                    )
                )
            seen_primary_targets.add(edge.target)
            continue

        if variant == ProvenanceVariant.STUDENT:
            violations.append(
                ProvenanceViolation(
                    "student_surface_leak",
                    variant.value,
                    target=edge.target,
                    source_field=edge.source_field,
                    classification=edge.classification,
                )
            )
            continue

        if edge.source_field not in allowed_teacher_fields:
            violations.append(
                ProvenanceViolation(
                    "invalid_teacher_source_field",
                    variant.value,
                    target=edge.target,
                    source_field=edge.source_field,
                    classification=edge.classification,
                )
            )

    for target in edit_targets - seen_primary_targets:
        violations.append(
            ProvenanceViolation(
                "missing_primary_provenance",
                variant.value,
                target=target,
            )
        )

    return tuple(violations)


def _secondary_violations(
    variant_plan: VariantPlan,
    rendered_text: Sequence[str],
    rendered_xml: Sequence[str],
) -> tuple[ProvenanceViolation, ...]:
    try:
        variant = _variant_name(variant_plan.variant)
    except ValueError:
        return (ProvenanceViolation("unsupported_variant", "invalid"),)

    forbidden_fields = _secondary_forbidden_fields(variant)
    if not forbidden_fields:
        return ()

    violations: list[ProvenanceViolation] = []
    for fragment in rendered_text:
        for field in forbidden_fields:
            if _contains_marker(fragment, TEXT_MARKERS_BY_FIELD[field]):
                violations.append(
                    ProvenanceViolation(
                        "secondary_text_leak",
                        variant.value,
                        source_field=field,
                        surface="text",
                    )
                )
                break

    for fragment in rendered_xml:
        for field in forbidden_fields:
            if _contains_marker(fragment, XML_MARKERS_BY_FIELD[field]):
                violations.append(
                    ProvenanceViolation(
                        "secondary_xml_leak",
                        variant.value,
                        source_field=field,
                        surface="xml",
                    )
                )
                break

    return tuple(violations)


def audit_variant_provenance(
    variant_plan: VariantPlan,
    rendered_text: Sequence[str],
    rendered_xml: Sequence[str],
) -> tuple[ProvenanceViolation, ...]:
    primary_violations = _primary_violations(variant_plan)
    if primary_violations and primary_violations[0].code == "unsupported_variant":
        return primary_violations
    return primary_violations + _secondary_violations(variant_plan, rendered_text, rendered_xml)


def guard_variant_provenance(
    variant_plan: VariantPlan,
    rendered_text: Sequence[str],
    rendered_xml: Sequence[str],
) -> None:
    violations = audit_variant_provenance(variant_plan, rendered_text, rendered_xml)
    if violations:
        raise ProvenanceAuditError(violations)


__all__ = [
    "ProvenanceAuditError",
    "ProvenanceClassification",
    "ProvenanceVariant",
    "ProvenanceViolation",
    "audit_variant_provenance",
    "guard_variant_provenance",
]

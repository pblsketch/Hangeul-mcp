from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
import re
import unicodedata
import xml.etree.ElementTree as ET

from .owpml import HwpxPackage
from .assessment_plan import VariantPlan
from .assessment_spec_models import AssessmentAnswer, AssessmentSpec, Choice, Feedback, Rubric


class AssessmentQaError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StudentItemIR:
    item_id: str
    order: int
    type: str
    stem: str
    points: int
    evidence_ids: tuple[str, ...]
    choices: tuple[Choice, ...]


@dataclass(frozen=True)
class TeacherItemIR:
    item_id: str
    order: int
    type: str
    stem: str
    points: int
    evidence_ids: tuple[str, ...]
    choices: tuple[Choice, ...]
    answer: AssessmentAnswer
    rationale: str
    rubric: Rubric | None
    misconceptions: tuple[str, ...]
    feedback: Feedback


@dataclass(frozen=True)
class AnswerKeyItemIR:
    item_id: str
    order: int
    type: str
    points: int
    evidence_ids: tuple[str, ...]
    answer: AssessmentAnswer
    rationale: str
    rubric: Rubric | None


@dataclass(frozen=True)
class StudentAssessmentIR:
    items: tuple[StudentItemIR, ...]


@dataclass(frozen=True)
class TeacherAssessmentIR:
    items: tuple[TeacherItemIR, ...]


@dataclass(frozen=True)
class AnswerKeyAssessmentIR:
    items: tuple[AnswerKeyItemIR, ...]


@dataclass(frozen=True)
class AssessmentVariants:
    student: StudentAssessmentIR
    teacher: TeacherAssessmentIR
    answer_key: AnswerKeyAssessmentIR


@dataclass(frozen=True, slots=True)
class AssessmentAuditValues:
    teacher_only: tuple[str, ...]
    student_visible: tuple[str, ...]


def project_assessment_variants(spec: AssessmentSpec) -> AssessmentVariants:
    student = tuple(StudentItemIR(item.item_id, item.order, item.type, item.stem, item.points, item.evidence_ids, item.choices) for item in spec.items)
    teacher = tuple(TeacherItemIR(
        item.item_id, item.order, item.type, item.stem, item.points, item.evidence_ids, item.choices,
        item.answer, item.rationale, item.rubric, item.misconceptions, item.feedback,
    ) for item in spec.items)
    answer_key = tuple(AnswerKeyItemIR(
        item.item_id, item.order, item.type, item.points, item.evidence_ids, item.answer, item.rationale, item.rubric,
    ) for item in spec.items)
    linkage = tuple((item.item_id, item.order, item.points, item.evidence_ids) for item in student)
    if linkage != tuple((item.item_id, item.order, item.points, item.evidence_ids) for item in teacher):
        raise AssessmentQaError("invalid_spec")
    if linkage != tuple((item.item_id, item.order, item.points, item.evidence_ids) for item in answer_key):
        raise AssessmentQaError("invalid_spec")
    return AssessmentVariants(StudentAssessmentIR(student), TeacherAssessmentIR(teacher), AnswerKeyAssessmentIR(answer_key))


def assert_student_plan_flow(plan: VariantPlan) -> None:
    if plan.variant != "student":
        raise AssessmentQaError("invalid_spec")
    if any(edge.classification == "teacher_only" for edge in plan.provenance):
        raise AssessmentQaError("answer_leakage")


def assessment_audit_values(spec: AssessmentSpec) -> AssessmentAuditValues:
    teacher_only: list[str] = []
    student_visible: list[str] = []
    for item in spec.items:
        student_visible.extend((item.stem, str(item.order), str(item.points)))
        for choice in item.choices:
            student_visible.extend((choice.choice_id, choice.text))
        teacher_only.extend(
            (
                *((item.answer,) if isinstance(item.answer, str) else item.answer),
                item.rationale,
                *item.misconceptions,
                item.feedback.correct,
                item.feedback.incorrect,
            )
        )
        if item.rubric is not None:
            for criterion in item.rubric.criteria:
                teacher_only.extend((criterion.criterion_id, criterion.description))
                for level in criterion.levels:
                    teacher_only.extend((level.level_id, level.descriptor))
    return AssessmentAuditValues(tuple(teacher_only), tuple(student_visible))


def read_hwpx_text_parts(path: str | Path) -> dict[str, tuple[str, ...]]:
    package = HwpxPackage.open(path)
    parts: dict[str, tuple[str, ...]] = {}
    for name in package.names():
        if not name.endswith((".xml", ".hpf", ".rdf")):
            continue
        root = ET.fromstring(package.read(name))
        parts[name] = tuple(
            fragment
            for element in root.iter()
            for fragment in (element.text, element.tail)
            if fragment is not None
        )
    return parts


def _audit_form(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", "", normalized)


def audit_student_document(
    parts: Mapping[str, Sequence[str]],
    teacher_only_values: Sequence[str],
    student_visible_values: Sequence[str],
) -> None:
    visible = _audit_form("".join(student_visible_values))
    document = _audit_form("".join(fragment for name in sorted(parts) for fragment in parts[name]))
    for value in teacher_only_values:
        secret = _audit_form(value)
        if secret and secret not in visible and secret in document:
            raise AssessmentQaError("answer_leakage")


def assert_student_variant_safe(
    plan: VariantPlan,
    parts: Mapping[str, Sequence[str]],
    teacher_only_values: Sequence[str],
    student_visible_values: Sequence[str],
) -> None:
    assert_student_plan_flow(plan)
    audit_student_document(parts, teacher_only_values, student_visible_values)


__all__ = [
    "AnswerKeyAssessmentIR", "AnswerKeyItemIR", "AssessmentAuditValues", "AssessmentQaError", "AssessmentVariants",
    "StudentAssessmentIR", "StudentItemIR", "TeacherAssessmentIR", "TeacherItemIR",
    "assert_student_plan_flow", "assert_student_variant_safe", "assessment_audit_values",
    "audit_student_document", "project_assessment_variants", "read_hwpx_text_parts",
]

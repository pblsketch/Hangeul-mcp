from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import unicodedata

import pytest

from hangeul_core.assessment_plan import AddressedEdit, ItemTrace, ProvenanceEdge, VariantPlan
from hangeul_core.assessment_qa import (
    AssessmentQaError,
    StudentItemIR,
    audit_student_document,
    assert_student_plan_flow,
    project_assessment_variants,
    read_hwpx_text_parts,
)
from hangeul_core.owpml import HwpxPackage
from tests.test_assessment_spec import valid_spec
from hangeul_core.assessment_spec import parse_assessment_spec


def student_plan(*edges: ProvenanceEdge) -> VariantPlan:
    return VariantPlan(
        "student",
        (AddressedEdit("b1", "visible", "before", "paragraph", "replace_text"),),
        (ItemTrace("item-1", 1, 4, ("ev-1",), "b1"),),
        tuple(edges),
        "0" * 64,
    )


def assert_leak(parts: dict[str, tuple[str, ...]], secret: str = "정답 비밀") -> None:
    with pytest.raises(AssessmentQaError) as caught:
        audit_student_document(parts, (secret,), ())
    assert caught.value.code == "answer_leakage"


def test_student_ir_type_has_no_teacher_only_fields():
    variants = project_assessment_variants(parse_assessment_spec(valid_spec()))
    names = {field.name for field in fields(StudentItemIR)}
    assert not names & {"answer", "rationale", "rubric", "misconceptions", "feedback"}
    assert tuple(item.item_id for item in variants.student.items) == ("item-1", "item-2", "item-3")


def test_teacher_only_provenance_cannot_reach_student_plan():
    with pytest.raises(AssessmentQaError) as caught:
        assert_student_plan_flow(student_plan(ProvenanceEdge("b1", "answer", "teacher_only")))
    assert caught.value.code == "answer_leakage"


def test_unicode_normalization_cannot_hide_teacher_content():
    secret = "정답 비밀"
    assert_leak({"body": (unicodedata.normalize("NFD", secret),)}, secret)


def test_split_text_runs_cannot_hide_teacher_content():
    assert_leak({"body": ("정", "답 ", "비", "밀")})


def test_styles_headers_footers_and_tables_cannot_hide_teacher_content():
    for part in ("styles", "header", "footer", "table"):
        assert_leak({part: ("정답 ", "비밀")})


def test_non_t_xml_text_in_real_hwpx_package_cannot_hide_teacher_content(tmp_path):
    fixture = next((Path(__file__).parent / "hwpx template").glob("12_*.hwpx"))
    package = HwpxPackage.open(fixture)
    secret = "NON-T-XML-ANSWER-SECRET"
    package.replace(
        "Contents/content.hpf",
        f'<?xml version="1.0" encoding="UTF-8"?><package><meta>{secret}</meta></package>'.encode(),
    )
    injected = package.save(tmp_path / "non-t-secret.hwpx")

    assert_leak(read_hwpx_text_parts(injected), secret)


def test_detected_leak_prevents_entire_bundle_publish():
    published = False
    try:
        audit_student_document({"body": ("정답 비밀",)}, ("정답 비밀",), ())
        published = True
    except AssessmentQaError as error:
        assert error.code == "answer_leakage"
    assert published is False


def test_legitimate_student_visible_string_equal_to_answer_is_not_false_positive():
    assert_student_plan_flow(student_plan(ProvenanceEdge("b1", "stem", "student_visible")))
    audit_student_document({"body": ("정답 비밀",)}, ("정답 비밀",), ("정답 비밀",))

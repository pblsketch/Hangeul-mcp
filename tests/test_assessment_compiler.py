from copy import deepcopy
from pathlib import Path
import unicodedata

import pytest

from hangeul_core.addressed import inspect_editable_regions
from hangeul_core.assessment_compiler import (
    ADDRESSED_OPERATION_ALLOWLIST,
    VARIANTS,
    AssessmentCompilerError,
    compile_assessment,
)
from hangeul_core.assessment_profile import (
    PROFILE_ID,
    get_assessment_profile,
    match_assessment_profile,
)


FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"


def _spec():
    return {
        "assessment_id": "assessment-001",
        "title": "형성평가",
        "total_points": 10,
        "evidence": [
            {"evidence_id": "ev-1", "description": "기사문의 특징"},
            {"evidence_id": "ev-2", "description": "표현 효과"},
        ],
        "items": [
            {
                "item_id": "item-1",
                "order": 1,
                "type": "multiple_choice",
                "points": 4,
                "stem": "기사문의 특징을 고르세요.",
                "choices": [
                    {"choice_id": "A", "text": "사실을 객관적으로 전달한다."},
                    {"choice_id": "B", "text": "운율을 반복해 만든다."},
                ],
                "answer": "A",
                "rationale": "기사문은 사실 전달을 중시한다.",
                "misconceptions": ["문학적 표현만 살핀다."],
                "feedback": {"correct": "핵심을 파악했습니다."},
                "evidence_ids": ["ev-1"],
            },
            {
                "item_id": "item-2",
                "order": 2,
                "type": "constructed_response",
                "points": 6,
                "stem": "표현 효과를 설명하세요.",
                "answer": "반복으로 의미를 강조한다.",
                "rationale": "동일한 표현의 반복은 의미를 돋보이게 한다.",
                "rubric": {
                    "criteria": [
                        {
                            "criterion_id": "effect",
                            "description": "표현 효과 설명",
                            "levels": [
                                {
                                    "level_id": "complete",
                                    "min_score": 0,
                                    "max_score": 6,
                                    "descriptor": "효과를 근거와 함께 설명함",
                                }
                            ],
                        }
                    ]
                },
                "evidence_ids": ["ev-2"],
            },
        ],
    }


def _inspection():
    return inspect_editable_regions(FIXTURE)


def _compiled(spec=None, inspection=None):
    profile = get_assessment_profile(PROFILE_ID)
    return compile_assessment(spec or _spec(), profile, inspection or _inspection())


def test_registered_profile_matches_verified_fixture():
    inspection = _inspection()
    profile = get_assessment_profile(PROFILE_ID)

    assert match_assessment_profile(PROFILE_ID, inspection) == profile

    plan = compile_assessment(_spec(), profile, inspection)
    assert plan.profile_id == PROFILE_ID
    assert plan.profile_version == profile.profile_version
    assert plan.profile_definition_digest == profile.profile_definition_digest
    assert plan.source_digest == inspection["source_sha256"]
    assert tuple(variant.variant for variant in plan.variants) == VARIANTS


@pytest.mark.parametrize("drift", ["missing_anchor", "changed_marker"])
def test_anchor_or_structure_drift_fails_closed(drift):
    inspection = deepcopy(_inspection())
    if drift == "missing_anchor":
        inspection["regions"] = inspection["regions"][1:]
    else:
        cell = next(region for region in inspection["regions"] if region["kind"] == "cell")
        cell["paragraphs"][0]["marker"] = "drifted"

    with pytest.raises(AssessmentCompilerError) as caught:
        _compiled(inspection=inspection)

    assert caught.value.code == "profile_mismatch"


def test_compiled_operations_are_exact_allowlist_subset():
    profile = get_assessment_profile(PROFILE_ID)
    plan = _compiled()

    operations = {
        edit.operation
        for variant in plan.variants
        for edit in variant.edits
    }

    assert operations == {"replace_text"}
    assert operations <= ADDRESSED_OPERATION_ALLOWLIST
    assert operations <= set(profile.allowed_operations)


def test_each_replacement_contains_expected_text():
    inspection = _inspection()
    expected_by_target = {
        region["target"]: region["text"]
        for region in inspection["regions"]
    }

    plan = _compiled(inspection=inspection)

    for variant in plan.variants:
        assert variant.edits
        for edit in variant.edits:
            assert isinstance(edit.expected_text, str)
            assert edit.expected_text
            assert edit.expected_text == expected_by_target[edit.target]


def test_compiled_body_edits_are_single_paragraph():
    plan = _compiled()

    for variant in plan.variants:
        for edit in variant.edits:
            assert edit.kind == "body_para"
            assert "\n" not in edit.value


def test_equivalent_canonical_input_compiles_identically():
    canonical = _spec()
    equivalent = deepcopy(canonical)
    equivalent["items"].reverse()
    equivalent = {
        key: equivalent[key]
        for key in reversed(tuple(equivalent))
    }

    def nfd(value):
        if isinstance(value, str):
            return unicodedata.normalize("NFD", value)
        if isinstance(value, list):
            return [nfd(child) for child in value]
        if isinstance(value, dict):
            return {key: nfd(child) for key, child in value.items()}
        return value

    equivalent = nfd(equivalent)

    assert _compiled(canonical) == _compiled(equivalent)


def test_variant_ordinals_points_and_evidence_links_are_identical():
    profile = get_assessment_profile(PROFILE_ID)
    items = sorted(_spec()["items"], key=lambda item: item["order"])
    item_types = tuple(item["type"] for item in items)
    slots_by_type = {
        item_type: [
            slot.target
            for slot in profile.item_slots
            if slot.item_type == item_type
        ]
        for item_type in set(item_types)
    }
    used_by_type = {item_type: 0 for item_type in slots_by_type}
    expected_targets = []
    for item_type in item_types:
        ordinal = used_by_type[item_type]
        expected_targets.append(slots_by_type[item_type][ordinal])
        used_by_type[item_type] += 1
    expected_targets = tuple(expected_targets)

    assert expected_targets == ("b1", "b33")

    plan = _compiled()
    expected = tuple(
        (
            trace.item_id,
            trace.order,
            trace.points,
            trace.evidence_ids,
            trace.target,
        )
        for trace in plan.variants[0].item_trace
    )

    assert expected
    for variant in plan.variants:
        assert tuple(edit.target for edit in variant.edits) == expected_targets
        assert tuple(trace.target for trace in variant.item_trace) == expected_targets
        actual = tuple(
            (
                trace.item_id,
                trace.order,
                trace.points,
                trace.evidence_ids,
                trace.target,
            )
            for trace in variant.item_trace
        )
        assert actual == expected

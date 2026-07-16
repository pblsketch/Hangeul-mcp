from copy import deepcopy
from pathlib import Path

import pytest

from hangeul_core.addressed import inspect_editable_regions
from hangeul_core.assessment_profile import (
    PROFILE_ID,
    AssessmentProfileError,
    get_assessment_profile,
    match_assessment_profile,
    registered_profiles,
)


FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"


def test_v1_has_one_explicit_profile_and_rejects_filename_or_unregistered_inference():
    inspection = inspect_editable_regions(FIXTURE)

    profiles = registered_profiles()

    assert len(profiles) == 1
    assert profiles[0].profile_id == PROFILE_ID == "formative.assessment.v1"
    assert get_assessment_profile(PROFILE_ID) == profiles[0]

    with pytest.raises(AssessmentProfileError) as unknown:
        get_assessment_profile("formative.assessment.unregistered")
    assert unknown.value.code == "profile_mismatch"

    known_filename_with_wrong_structure = deepcopy(inspection)
    known_filename_with_wrong_structure["regions"] = inspection["regions"][:-1]
    with pytest.raises(AssessmentProfileError) as wrong_structure:
        match_assessment_profile(PROFILE_ID, known_filename_with_wrong_structure)
    assert wrong_structure.value.code == "profile_mismatch"

    renamed_partial_match = deepcopy(inspection)
    renamed_partial_match["source_path"] = str(FIXTURE.with_name("renamed.hwpx"))
    renamed_partial_match["regions"] = inspection["regions"][:-1]
    with pytest.raises(AssessmentProfileError) as partial_match:
        match_assessment_profile(PROFILE_ID, renamed_partial_match)
    assert partial_match.value.code == "profile_mismatch"

    duplicate_target = deepcopy(inspection)
    duplicate_target["regions"] = [
        *inspection["regions"],
        deepcopy(inspection["regions"][0]),
    ]
    with pytest.raises(AssessmentProfileError) as ambiguous:
        match_assessment_profile(PROFILE_ID, duplicate_target)
    assert ambiguous.value.code == "ambiguous_mapping"

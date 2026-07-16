from __future__ import annotations

import json
import logging
from pathlib import Path

from hangeul_core.assessment_observability import (
    AssessmentLogEvent,
    AssessmentManifest,
    ManifestInput,
    VariantManifestInput,
    build_manifest,
    emit_assessment_event,
)
from hangeul_mcp import tools_assessment
from tests.test_assessment_spec import valid_spec


FIXTURE = next((Path(__file__).parent / "hwpx template").glob("12_*.hwpx"))


def _sentinel_spec() -> dict[str, object]:
    spec = valid_spec()
    metadata = spec["metadata"]
    metadata["title"] = "TITLE-SENTINEL"
    metadata["subject"] = "SUBJECT-SENTINEL"
    metadata["grade"] = "GRADE-SENTINEL"
    metadata["unit"] = "UNIT-SENTINEL"
    metadata["learning_objectives"] = ["OBJECTIVE-SENTINEL"]
    evidence_ids: list[str] = []
    for index, evidence in enumerate(spec["learning_evidence"], start=1):
        evidence_id = f"EVIDENCE-ID-SENTINEL-{index}"
        evidence_ids.append(evidence_id)
        evidence["evidence_id"] = evidence_id
        evidence["claim"] = f"CLAIM-SENTINEL-{index}"
        evidence["expected_evidence"] = f"EXPECTED-EVIDENCE-SENTINEL-{index}"
    for index, item in enumerate(spec["items"], start=1):
        item["item_id"] = f"ITEM-ID-SENTINEL-{index}"
        item["evidence_ids"] = [evidence_ids[index - 1]]
        item["stem"] = f"STEM-SENTINEL-{index}"
        item["rationale"] = f"RATIONALE-SENTINEL-{index}"
        item["misconceptions"] = [f"MISCONCEPTION-SENTINEL-{index}"]
        item["feedback"] = {
            "correct": f"FEEDBACK-CORRECT-SENTINEL-{index}",
            "incorrect": f"FEEDBACK-INCORRECT-SENTINEL-{index}",
        }
    choices = spec["items"][0]["choices"]
    for index, choice in enumerate(choices, start=1):
        choice["choice_id"] = f"CHOICE-ID-SENTINEL-{index}"
        choice["text"] = f"CHOICE-TEXT-SENTINEL-{index}"
    spec["items"][0]["answer"] = choices[0]["choice_id"]
    spec["items"][1]["answer"] = ["SHORT-ANSWER-SENTINEL-1", "SHORT-ANSWER-SENTINEL-2"]
    spec["items"][2]["answer"] = "CONSTRUCTED-ANSWER-SENTINEL"
    for criterion_index, criterion in enumerate(
        spec["items"][2]["rubric"]["criteria"], start=1
    ):
        criterion["criterion_id"] = f"CRITERION-ID-SENTINEL-{criterion_index}"
        criterion["description"] = f"RUBRIC-DESCRIPTION-SENTINEL-{criterion_index}"
        for level_index, level in enumerate(criterion["levels"], start=1):
            level["level_id"] = f"LEVEL-ID-SENTINEL-{criterion_index}-{level_index}"
            level["descriptor"] = f"RUBRIC-DESCRIPTOR-SENTINEL-{criterion_index}-{level_index}"
    return spec


def _variant(file_digest: str, item_count: int) -> VariantManifestInput:
    return VariantManifestInput(
        file_digest=file_digest,
        item_count=item_count,
        target_count=item_count + 1,
        verified_count=item_count + 1,
    )


def _manifest() -> AssessmentManifest:
    return build_manifest(
        ManifestInput(
            bundle_id="bundle-safe",
            session_id="session-safe",
            created_at="2026-07-16T00:00:00Z",
            spec_fingerprint="spec-digest-safe",
            source_digest="source-digest-safe",
            profile_id="formative.assessment.v1",
            profile_version=1,
            profile_definition_digest="profile-digest-safe",
            student=_variant("student-digest-safe", 3),
            teacher=_variant("teacher-digest-safe", 3),
            answer_key=_variant("answer-key-digest-safe", 3),
        )
    )


def test_manifest_matches_exact_recursive_allowlist() -> None:
    manifest = _manifest()

    assert set(manifest) == {
        "manifest_version",
        "bundle_id",
        "session_id",
        "created_at",
        "spec_fingerprint",
        "source_digest",
        "profile_id",
        "profile_version",
        "profile_definition_digest",
        "variants",
    }
    variants = manifest["variants"]
    assert isinstance(variants, dict)
    assert set(variants) == {"student", "teacher", "answer_key"}
    variant_values = (
        variants["student"],
        variants["teacher"],
        variants["answer_key"],
    )
    assert all(
        set(value) == {
            "filename",
            "file_digest",
            "item_count",
            "target_count",
            "verified_count",
        }
        for value in variant_values
    )


def test_manifest_uses_fixed_variant_filenames() -> None:
    variants = _manifest()["variants"]

    assert isinstance(variants, dict)
    assert variants["student"]["filename"] == "student.hwpx"
    assert variants["teacher"]["filename"] == "teacher.hwpx"
    assert variants["answer_key"]["filename"] == "answer-key.hwpx"


def test_all_spec_string_and_identifier_sentinels_are_absent_from_manifest(tmp_path) -> None:
    tools_assessment.configure_assessment_output_roots((tmp_path,))
    preview = tools_assessment.preview_assessment(str(FIXTURE), _sentinel_spec())
    applied = tools_assessment.apply_assessment(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )
    manifest_path = tmp_path / str(applied["bundle_id"]) / "manifest.json"

    rendered = manifest_path.read_text(encoding="utf-8")

    assert "SENTINEL" not in rendered


def test_all_spec_string_and_identifier_sentinels_are_absent_from_logs(tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO, logger="hangeul_core.assessment")
    tools_assessment.configure_assessment_output_roots((tmp_path,))
    preview = tools_assessment.preview_assessment(str(FIXTURE), _sentinel_spec())
    tools_assessment.apply_assessment(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )

    assert "SENTINEL" not in caplog.text


def test_all_spec_string_and_identifier_sentinels_are_absent_from_errors(caplog) -> None:
    caplog.set_level(logging.INFO, logger="hangeul_core.assessment")
    result = tools_assessment.preview_assessment(
        "C:/SECRET/PATH-SENTINEL.hwpx",
        {"unexpected": "ANSWER-SENTINEL"},
    )

    assert result["error_code"] == "invalid_spec"
    assert "SENTINEL" not in json.dumps(result, ensure_ascii=False)
    assert "SENTINEL" not in caplog.text


def test_unknown_evidence_reference_is_not_reported_as_publish_failure(caplog) -> None:
    # Given
    caplog.set_level(logging.INFO, logger="hangeul_core.assessment")
    spec = valid_spec()
    spec["items"][0]["evidence_ids"] = ["missing"]

    # When
    result = tools_assessment.preview_assessment(str(FIXTURE), spec)

    # Then
    assert result["error_code"] == "unknown_evidence_reference"
    assert json.loads(caplog.messages[-1])["error_code"] == "unknown_evidence_reference"


def test_orphan_evidence_is_not_reported_as_publish_failure(caplog) -> None:
    # Given
    caplog.set_level(logging.INFO, logger="hangeul_core.assessment")
    spec = valid_spec()
    spec["items"][2]["evidence_ids"] = ["ev-2"]

    # When
    result = tools_assessment.preview_assessment(str(FIXTURE), spec)

    # Then
    assert result["error_code"] == "orphan_evidence"
    assert json.loads(caplog.messages[-1])["error_code"] == "orphan_evidence"


def test_manifest_and_logs_expose_only_safe_counts_digests_and_durations(caplog) -> None:
    manifest = _manifest()
    caplog.set_level(logging.INFO, logger="hangeul_core.assessment")

    emit_assessment_event(
        AssessmentLogEvent(
            event="assessment_preview",
            state="preview_ready",
            session_id="session-safe",
            item_count=3,
            target_count=4,
            duration_ms=12,
        )
    )

    variants = manifest["variants"]
    assert isinstance(variants, dict)
    variant_values = (
        variants["student"],
        variants["teacher"],
        variants["answer_key"],
    )
    assert all(
        set(value) <= {
            "filename",
            "file_digest",
            "item_count",
            "target_count",
            "verified_count",
        }
        for value in variant_values
    )
    assert set(json.loads(caplog.messages[-1])) <= {
        "event",
        "state",
        "session_id",
        "variant",
        "item_count",
        "target_count",
        "duration_ms",
        "error_code",
    }


def test_failure_evidence_contains_only_error_code_and_safe_counts(tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO, logger="hangeul_core.assessment")
    tools_assessment.configure_assessment_output_roots((tmp_path,))
    preview = tools_assessment.preview_assessment(str(FIXTURE), _sentinel_spec())
    applied = tools_assessment.apply_assessment(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )
    failure = tools_assessment.apply_assessment(
        str(preview["session_id"]),
        "invalid-possession-token",
        str(tmp_path),
    )
    manifest = (tmp_path / str(applied["bundle_id"]) / "manifest.json").read_text(
        encoding="utf-8"
    )
    failure_log = json.loads(caplog.messages[-1])

    assert failure == {
        "available": True,
        "ok": False,
        "state": "failed",
        "error_code": "invalid_session_instance",
    }
    assert failure_log == {
        "event": "assessment_apply",
        "state": "failed",
        "error_code": "invalid_session_instance",
    }
    assert "SENTINEL" not in manifest + caplog.text + json.dumps(failure)

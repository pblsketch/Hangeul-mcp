from __future__ import annotations

import json
import logging

from hangeul_core.assessment_observability import (
    AssessmentLogEvent,
    AssessmentManifest,
    FailureCounts,
    ManifestInput,
    VariantManifestInput,
    build_failure_evidence,
    build_manifest,
    emit_assessment_event,
)


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


def test_all_spec_string_and_identifier_sentinels_are_absent_from_manifest() -> None:
    sentinels = (
        "TITLE-SENTINEL",
        "SUBJECT-SENTINEL",
        "UNIT-SENTINEL",
        "ITEM-ID-SENTINEL",
        "EVIDENCE-ID-SENTINEL",
        "STEM-SENTINEL",
        "ANSWER-SENTINEL",
        "RUBRIC-SENTINEL",
        "FEEDBACK-SENTINEL",
        "C:/SECRET/PATH-SENTINEL",
        "TOKEN-SENTINEL",
    )

    rendered = json.dumps(_manifest(), ensure_ascii=False)

    assert all(sentinel not in rendered for sentinel in sentinels)


def test_all_spec_string_and_identifier_sentinels_are_absent_from_logs(caplog) -> None:
    caplog.set_level(logging.INFO, logger="hangeul_core.assessment")

    emit_assessment_event(
        AssessmentLogEvent(
            event="assessment_apply",
            state="verified",
            session_id="session-safe",
            variant="student",
            item_count=3,
            target_count=4,
            duration_ms=25,
        )
    )

    record = json.loads(caplog.messages[-1])
    assert set(record) == {
        "event",
        "state",
        "session_id",
        "variant",
        "item_count",
        "target_count",
        "duration_ms",
    }
    assert "SENTINEL" not in caplog.text


def test_all_spec_string_and_identifier_sentinels_are_absent_from_errors() -> None:
    evidence = build_failure_evidence(
        "raw exception: ANSWER-SENTINEL at C:/SECRET/PATH-SENTINEL",
        FailureCounts(requested=3, resolved=2, unresolved=1, variant_count=3),
    )

    assert evidence == {
        "error_code": "publish_io_error",
        "requested": 3,
        "resolved": 2,
        "unresolved": 1,
        "variant_count": 3,
    }


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


def test_failure_evidence_contains_only_error_code_and_safe_counts() -> None:
    evidence = build_failure_evidence(
        "stale_source",
        FailureCounts(
            requested=4,
            resolved=3,
            applied=2,
            verified=1,
            unresolved=1,
            variant_count=3,
        ),
    )

    assert set(evidence) == {
        "error_code",
        "requested",
        "resolved",
        "applied",
        "verified",
        "unresolved",
        "variant_count",
    }
    assert evidence["error_code"] == "stale_source"

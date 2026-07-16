from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Final, Literal, TypedDict


AssessmentEvent = Literal["assessment_apply", "assessment_preview"]
AssessmentState = Literal["applied", "applying", "failed", "preview_ready", "verified"]
VariantName = Literal["student", "teacher", "answer_key"]

_LOGGER: Final = logging.getLogger("hangeul_core.assessment")
_MANIFEST_VERSION: Final = 1
_VARIANT_FILENAMES: Final[dict[VariantName, str]] = {
    "student": "student.hwpx",
    "teacher": "teacher.hwpx",
    "answer_key": "answer-key.hwpx",
}
_ERROR_CODES: Final = frozenset(
    {
        "invalid_spec",
        "invalid_item_shape",
        "profile_mismatch",
        "ambiguous_mapping",
        "stale_source",
        "stale_profile",
        "stale_plan",
        "answer_leakage",
        "score_mismatch",
        "invalid_output",
        "unregistered_output_root",
        "source_output_collision",
        "output_collision",
        "cross_device_publish",
        "publish_io_error",
        "already_applied",
        "apply_in_progress",
        "expired_session",
        "invalid_session_instance",
        "session_capacity",
        "atomic_publish_unavailable",
        "cleanup_unsafe_descendant",
    }
)


@dataclass(frozen=True, slots=True)
class VariantManifestInput:
    file_digest: str
    item_count: int
    target_count: int
    verified_count: int


@dataclass(frozen=True, slots=True)
class ManifestInput:
    bundle_id: str
    session_id: str
    created_at: str
    spec_fingerprint: str
    source_digest: str
    profile_id: str
    profile_version: int
    profile_definition_digest: str
    student: VariantManifestInput
    teacher: VariantManifestInput
    answer_key: VariantManifestInput


@dataclass(frozen=True, slots=True)
class AssessmentLogEvent:
    event: AssessmentEvent
    state: AssessmentState
    session_id: str
    variant: VariantName | None = None
    item_count: int | None = None
    target_count: int | None = None
    duration_ms: int | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class FailureCounts:
    requested: int | None = None
    resolved: int | None = None
    applied: int | None = None
    verified: int | None = None
    unresolved: int | None = None
    variant_count: int | None = None


class VariantManifest(TypedDict):
    filename: str
    file_digest: str
    item_count: int
    target_count: int
    verified_count: int


class VariantManifests(TypedDict):
    student: VariantManifest
    teacher: VariantManifest
    answer_key: VariantManifest


class AssessmentManifest(TypedDict):
    manifest_version: int
    bundle_id: str
    session_id: str
    created_at: str
    spec_fingerprint: str
    source_digest: str
    profile_id: str
    profile_version: int
    profile_definition_digest: str
    variants: VariantManifests


class SafeLogRecordRequired(TypedDict):
    event: AssessmentEvent
    state: AssessmentState
    session_id: str


class SafeLogRecord(SafeLogRecordRequired, total=False):
    variant: VariantName
    item_count: int
    target_count: int
    duration_ms: int
    error_code: str


class FailureEvidenceRequired(TypedDict):
    error_code: str


class FailureEvidence(FailureEvidenceRequired, total=False):
    requested: int
    resolved: int
    applied: int
    verified: int
    unresolved: int
    variant_count: int


def _variant_manifest(
    variant: VariantName,
    value: VariantManifestInput,
) -> VariantManifest:
    return {
        "filename": _VARIANT_FILENAMES[variant],
        "file_digest": value.file_digest,
        "item_count": value.item_count,
        "target_count": value.target_count,
        "verified_count": value.verified_count,
    }


def build_manifest(value: ManifestInput) -> AssessmentManifest:
    return {
        "manifest_version": _MANIFEST_VERSION,
        "bundle_id": value.bundle_id,
        "session_id": value.session_id,
        "created_at": value.created_at,
        "spec_fingerprint": value.spec_fingerprint,
        "source_digest": value.source_digest,
        "profile_id": value.profile_id,
        "profile_version": value.profile_version,
        "profile_definition_digest": value.profile_definition_digest,
        "variants": {
            "student": _variant_manifest("student", value.student),
            "teacher": _variant_manifest("teacher", value.teacher),
            "answer_key": _variant_manifest("answer_key", value.answer_key),
        },
    }


def _safe_error_code(error_code: str) -> str:
    if error_code in _ERROR_CODES:
        return error_code
    return "publish_io_error"


def _log_record(value: AssessmentLogEvent) -> SafeLogRecord:
    record: SafeLogRecord = {
        "event": value.event,
        "state": value.state,
        "session_id": value.session_id,
    }
    if value.variant is not None:
        record["variant"] = value.variant
    if value.item_count is not None:
        record["item_count"] = value.item_count
    if value.target_count is not None:
        record["target_count"] = value.target_count
    if value.duration_ms is not None:
        record["duration_ms"] = value.duration_ms
    if value.error_code is not None:
        record["error_code"] = _safe_error_code(value.error_code)
    return record


def emit_assessment_event(value: AssessmentLogEvent) -> None:
    _LOGGER.info(
        json.dumps(
            _log_record(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def build_failure_evidence(
    error_code: str,
    counts: FailureCounts,
) -> FailureEvidence:
    evidence: FailureEvidence = {"error_code": _safe_error_code(error_code)}
    if counts.requested is not None:
        evidence["requested"] = counts.requested
    if counts.resolved is not None:
        evidence["resolved"] = counts.resolved
    if counts.applied is not None:
        evidence["applied"] = counts.applied
    if counts.verified is not None:
        evidence["verified"] = counts.verified
    if counts.unresolved is not None:
        evidence["unresolved"] = counts.unresolved
    if counts.variant_count is not None:
        evidence["variant_count"] = counts.variant_count
    return evidence


__all__ = [
    "AssessmentLogEvent", "AssessmentManifest", "FailureCounts", "FailureEvidence",
    "ManifestInput", "SafeLogRecord", "VariantManifestInput", "build_failure_evidence",
    "build_manifest", "emit_assessment_event",
]

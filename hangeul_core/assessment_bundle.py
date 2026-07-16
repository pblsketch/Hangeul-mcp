from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .addressed import complete_addressed_template
from .assessment_cleanup import (
    CleanupError,
    MARKER_NAME,
    OwnershipRegistry,
    StagingOwner,
    cleanup_owned_staging,
    create_owned_staging,
    staging_directory_name,
)
from .assessment_observability import (
    AssessmentManifest,
    ManifestInput,
    VariantManifestInput,
    build_manifest,
)
from .assessment_plan import AssessmentPlan
from .assessment_quality import (
    addressed_requirements_for_variant,
    check_assessment_quality,
    requirements_for_variant,
)
from .assessment_publish import (
    AtomicPublishAdapter,
    PublishError,
    _publish_directory_no_replace,
    recover_published_session,
)
from .assessment_qa import (
    AssessmentAuditValues,
    assert_student_variant_safe,
    read_hwpx_text_parts,
)
from .validate import validate_hwpx


VARIANT_FILENAMES = {
    "student": "student.hwpx",
    "teacher": "teacher.hwpx",
    "answer_key": "answer-key.hwpx",
}


class AssessmentBundleError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class AssessmentBundleRequest:
    spec_fingerprint: str
    session_id: str
    source: Path
    root: Path
    final: Path
    plan: AssessmentPlan
    audit_values: AssessmentAuditValues
    ownership: OwnershipRegistry
    publisher: AtomicPublishAdapter


def _remove_private_artifacts(
    result: Mapping[str, object],
    payload: Path,
) -> None:
    for artifact_key in ("journal_path", "snapshot_path"):
        artifact_value = result.get(artifact_key)
        if not isinstance(artifact_value, str):
            raise AssessmentBundleError("invalid_output")
        artifact = Path(artifact_value)
        try:
            if artifact.resolve(strict=True).parent != payload.resolve(strict=True):
                raise AssessmentBundleError("invalid_output")
            artifact.unlink()
        except OSError:
            raise AssessmentBundleError("invalid_output") from None


def _generate_variants(
    request: AssessmentBundleRequest,
    payload: Path,
) -> dict[str, VariantManifestInput]:
    variants: dict[str, VariantManifestInput] = {}
    for variant in request.plan.variants:
        target = payload / VARIANT_FILENAMES[variant.variant]
        intermediate = payload / f".{variant.variant}-replaced.hwpx"
        replacement_edits = tuple(
            edit for edit in variant.edits if edit.operation != "delete_paragraph"
        )
        deletion_edits = tuple(
            edit for edit in variant.edits if edit.operation == "delete_paragraph"
        )
        replacement_result = complete_addressed_template(
            request.source,
            [asdict(edit) for edit in replacement_edits],
            intermediate,
            verify=True,
        )
        if not replacement_result.get("ok") or not check_assessment_quality(
            intermediate,
            addressed_requirements_for_variant(variant),
        ).valid:
            raise AssessmentBundleError("invalid_output")
        _remove_private_artifacts(replacement_result, payload)
        if deletion_edits:
            deletion_result = complete_addressed_template(
                intermediate,
                [asdict(edit) for edit in deletion_edits],
                target,
                verify=True,
            )
            if not deletion_result.get("ok"):
                raise AssessmentBundleError("invalid_output")
            _remove_private_artifacts(deletion_result, payload)
            deletion_counts = deletion_result.get("counts")
        else:
            intermediate.replace(target)
            deletion_counts = {}
        intermediate.unlink(missing_ok=True)
        if validate_hwpx(target).get("valid") is not True:
            raise AssessmentBundleError("invalid_output")
        if not check_assessment_quality(
            target,
            requirements_for_variant(variant),
        ).valid:
            raise AssessmentBundleError("invalid_output")
        if variant.variant == "student":
            assert_student_variant_safe(
                variant,
                read_hwpx_text_parts(target),
                request.audit_values.teacher_only,
                request.audit_values.student_visible,
            )
        replacement_counts = replacement_result.get("counts")
        safe_replacement_counts = (
            replacement_counts if isinstance(replacement_counts, Mapping) else {}
        )
        safe_deletion_counts = deletion_counts if isinstance(deletion_counts, Mapping) else {}
        variants[variant.variant] = VariantManifestInput(
            file_digest=hashlib.sha256(target.read_bytes()).hexdigest(),
            item_count=len(variant.item_trace),
            target_count=len(variant.edits),
            verified_count=int(safe_replacement_counts.get("verified", 0))
            + int(safe_deletion_counts.get("verified", 0)),
        )
    return variants


def _write_manifest(
    request: AssessmentBundleRequest,
    payload: Path,
    variants: Mapping[str, VariantManifestInput],
) -> AssessmentManifest:
    manifest = build_manifest(
        ManifestInput(
            bundle_id=f"assessment-{request.session_id}",
            session_id=request.session_id,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            spec_fingerprint=request.spec_fingerprint,
            source_digest=request.plan.source_digest,
            profile_id=request.plan.profile_id,
            profile_version=request.plan.profile_version,
            profile_definition_digest=request.plan.profile_definition_digest,
            student=variants["student"],
            teacher=variants["teacher"],
            answer_key=variants["answer_key"],
        )
    )
    (payload / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return manifest


def _cleanup_partial_staging(
    request: AssessmentBundleRequest,
    owner: StagingOwner,
    staging: Path,
) -> None:
    expected_name = staging_directory_name(owner.session_id, owner.ownership_nonce)
    try:
        resolved = staging.resolve(strict=True)
        root = request.root.resolve(strict=True)
        children = tuple(resolved.iterdir())
    except OSError:
        raise CleanupError("cleanup_unsafe_descendant") from None
    if (
        resolved.parent != root
        or resolved.name != expected_name
        or request.ownership.ownership(resolved)
        != (owner.session_id, owner.ownership_nonce)
        or any(
            child.name != MARKER_NAME or child.is_symlink() or not child.is_file()
            for child in children
        )
    ):
        raise CleanupError("cleanup_unsafe_descendant")
    try:
        for child in children:
            child.unlink()
        resolved.rmdir()
    except OSError:
        raise CleanupError("cleanup_unsafe_descendant") from None
    request.ownership.unregister(resolved)


def _applied_result(session_id: str, variant_count: int) -> dict[str, object]:
    return {
        "available": True,
        "ok": True,
        "state": "applied",
        "session_id": session_id,
        "bundle_id": f"assessment-{session_id}",
        "variant_count": variant_count,
    }


def publish_assessment_bundle(request: AssessmentBundleRequest) -> dict[str, object]:
    owner = StagingOwner(request.session_id, secrets.token_hex(16))
    staging = request.root / staging_directory_name(
        owner.session_id,
        owner.ownership_nonce,
    )
    payload = staging / "bundle"
    applied_result = _applied_result(request.session_id, len(request.plan.variants))
    published = False
    manifest: AssessmentManifest | None = None
    try:
        create_owned_staging(request.root, owner, request.ownership)
        payload.mkdir()
        request.ownership.activate(request.session_id)
        variants = _generate_variants(request, payload)
        manifest = _write_manifest(request, payload, variants)
        try:
            _publish_directory_no_replace(payload, request.final, request.publisher)
        except PublishError:
            if payload.exists():
                raise
            recover_published_session(request.final, request.publisher, manifest)
        published = True
        return applied_result
    finally:
        request.ownership.deactivate(request.session_id)
        if staging.exists():
            try:
                cleanup_owned_staging(staging, request.ownership, request.root)
            except CleanupError:
                if staging.exists() or not published or manifest is None:
                    raise
                recover_published_session(request.final, request.publisher, manifest)
            if staging.exists():
                if published:
                    raise CleanupError("cleanup_unsafe_descendant")
                _cleanup_partial_staging(request, owner, staging)
        if not published and request.final.exists():
            raise AssessmentBundleError("output_collision")

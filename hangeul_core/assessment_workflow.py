from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .addressed import complete_addressed_template, inspect_editable_regions
from .assessment_adapter import (
    assessment_inspection_to_compiler_mapping,
    assessment_plan_digest,
    assessment_spec_to_compiler_mapping,
)
from .assessment_apply import ApplyError, ApplyPreconditions, validate_apply
from .assessment_cleanup import (
    CleanupError,
    OwnershipRegistry,
    SafeOutputRootRegistry,
    StagingOwner,
    cleanup_owned_staging,
    create_owned_staging,
)
from .assessment_compiler import AssessmentCompilerError, compile_assessment
from .assessment_observability import ManifestInput, VariantManifestInput, build_manifest
from .assessment_plan import AssessmentPlan
from .assessment_profile import AssessmentProfileError, get_assessment_profile
from .assessment_publish import PublishError, _publish_directory_no_replace
from .assessment_qa import AssessmentQaError, assert_student_plan_flow, project_assessment_variants
from .assessment_session import AssessmentSessionError, AssessmentSessionStore
from .assessment_spec import AssessmentSpecError, parse_assessment_spec


VARIANT_FILENAMES = {
    "student": "student.hwpx",
    "teacher": "teacher.hwpx",
    "answer_key": "answer-key.hwpx",
}


class AssessmentWorkflowError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AssessmentWorkflow:
    def __init__(
        self,
        *,
        output_roots: tuple[str | Path, ...] = (),
        sessions: AssessmentSessionStore | None = None,
    ) -> None:
        self._sessions = sessions or AssessmentSessionStore()
        self._safe_roots = SafeOutputRootRegistry(output_roots) if output_roots else None
        self._ownership = OwnershipRegistry(self._sessions.instance_id)
        self._plan_digests: dict[str, str] = {}
        self._sources: dict[str, Path] = {}

    @property
    def session_count(self) -> int:
        return len(self._sources)

    def preview(self, template_path: str, raw_spec: object) -> dict[str, object]:
        try:
            spec = parse_assessment_spec(raw_spec)
        except AssessmentSpecError as exc:
            raise AssessmentWorkflowError(exc.code) from None

        try:
            profile = get_assessment_profile(spec.profile_id)
            inspection = inspect_editable_regions(template_path)
            plan = compile_assessment(
                assessment_spec_to_compiler_mapping(spec),
                profile,
                assessment_inspection_to_compiler_mapping(inspection),
            )
            project_assessment_variants(spec)
            assert_student_plan_flow(plan.variant("student"))
            created = self._sessions.create(
                spec_fingerprint=spec.spec_fingerprint,
                plan=plan,
            )
        except (AssessmentCompilerError, AssessmentProfileError, AssessmentQaError) as exc:
            raise AssessmentWorkflowError(exc.code) from None
        except (OSError, RuntimeError):
            raise AssessmentWorkflowError("profile_mismatch") from None

        self._sources[created.session_id] = Path(template_path)
        self._plan_digests[created.session_id] = assessment_plan_digest(plan)
        return {
            "available": True,
            "ok": True,
            "state": "preview_ready",
            "session_id": created.session_id,
            "possession_token": created.possession_token,
            "spec_fingerprint": spec.spec_fingerprint,
            "source_digest": plan.source_digest,
            "profile_id": plan.profile_id,
            "profile_version": plan.profile_version,
            "profile_definition_digest": plan.profile_definition_digest,
            "variants": {
                variant.variant: {
                    "item_count": len(variant.item_trace),
                    "target_count": len(variant.edits),
                    "plan_digest": variant.frozen_plan_digest,
                }
                for variant in plan.variants
            },
        }

    def apply(
        self,
        session_id: str,
        possession_token: str,
        output_dir: str,
    ) -> dict[str, object]:
        try:
            lease = self._sessions.apply(session_id, possession_token)
        except AssessmentSessionError as exc:
            raise AssessmentWorkflowError(exc.code) from None

        try:
            with lease as snapshot:
                source = self._sources.get(session_id)
                expected_plan_digest = self._plan_digests.get(session_id)
                if source is None or expected_plan_digest is None:
                    raise AssessmentWorkflowError("invalid_session_instance")
                try:
                    roots = self._safe_roots or SafeOutputRootRegistry((output_dir,))
                    root = roots.require_exact(output_dir)
                    profile = get_assessment_profile(snapshot.plan.profile_id)
                except (AssessmentProfileError, CleanupError) as exc:
                    raise AssessmentWorkflowError(exc.code) from None

                final = root / f"assessment-{session_id}"
                current_plan_digest = assessment_plan_digest(snapshot.plan)
                validate_apply(
                    ApplyPreconditions(
                        source_path=source,
                        output_path=final,
                        expected_source_digest=snapshot.plan.source_digest,
                        current_profile_definition_digest=profile.profile_definition_digest,
                        expected_profile_definition_digest=snapshot.plan.profile_definition_digest,
                        current_plan_digest=current_plan_digest,
                        expected_plan_digest=expected_plan_digest,
                    )
                )
                return self._publish(snapshot.spec_fingerprint, session_id, source, root, final, snapshot.plan)
        except AssessmentWorkflowError:
            raise
        except (ApplyError, CleanupError, PublishError) as exc:
            raise AssessmentWorkflowError(exc.code) from None
        except OSError:
            raise AssessmentWorkflowError("publish_io_error") from None

    def _publish(
        self,
        spec_fingerprint: str,
        session_id: str,
        source: Path,
        root: Path,
        final: Path,
        plan: AssessmentPlan,
    ) -> dict[str, object]:
        owner = StagingOwner(session_id, secrets.token_hex(16))
        staging = create_owned_staging(root, owner, self._ownership)
        payload = staging / "bundle"
        payload.mkdir()
        self._ownership.activate(session_id)
        published = False
        try:
            variants: dict[str, VariantManifestInput] = {}
            for variant in plan.variants:
                filename = VARIANT_FILENAMES[variant.variant]
                target = payload / filename
                result = complete_addressed_template(
                    source,
                    [asdict(edit) for edit in variant.edits],
                    target,
                    verify=True,
                )
                if not result.get("ok"):
                    raise AssessmentWorkflowError("invalid_output")
                for artifact_key in ("journal_path", "snapshot_path"):
                    artifact_value = result.get(artifact_key)
                    if not isinstance(artifact_value, str):
                        raise AssessmentWorkflowError("invalid_output")
                    artifact = Path(artifact_value)
                    try:
                        if artifact.resolve(strict=True).parent != payload.resolve(strict=True):
                            raise AssessmentWorkflowError("invalid_output")
                        artifact.unlink()
                    except OSError:
                        raise AssessmentWorkflowError("invalid_output") from None
                counts = result.get("counts")
                safe_counts = counts if isinstance(counts, Mapping) else {}
                variants[variant.variant] = VariantManifestInput(
                    file_digest=_sha256(target),
                    item_count=len(variant.item_trace),
                    target_count=len(variant.edits),
                    verified_count=int(safe_counts.get("verified", 0)),
                )

            manifest = build_manifest(
                ManifestInput(
                    bundle_id=f"assessment-{session_id}",
                    session_id=session_id,
                    created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    spec_fingerprint=spec_fingerprint,
                    source_digest=plan.source_digest,
                    profile_id=plan.profile_id,
                    profile_version=plan.profile_version,
                    profile_definition_digest=plan.profile_definition_digest,
                    student=variants["student"],
                    teacher=variants["teacher"],
                    answer_key=variants["answer_key"],
                )
            )
            (payload / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            _publish_directory_no_replace(payload, final)
            published = True
            return {
                "available": True,
                "ok": True,
                "state": "applied",
                "session_id": session_id,
                "bundle_id": f"assessment-{session_id}",
                "variant_count": len(variants),
            }
        finally:
            self._ownership.deactivate(session_id)
            if staging.exists():
                cleanup_owned_staging(staging, self._ownership, root)
            if not published and final.exists():
                raise AssessmentWorkflowError("output_collision")


__all__ = [
    "AssessmentWorkflow",
    "AssessmentWorkflowError",
    "VARIANT_FILENAMES",
]

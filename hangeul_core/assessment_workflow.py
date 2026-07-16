from __future__ import annotations

from pathlib import Path
from typing import Literal

from .addressed import inspect_editable_regions
from .assessment_adapter import (
    assessment_inspection_to_compiler_mapping,
    assessment_plan_digest,
    assessment_spec_to_compiler_mapping,
)
from .assessment_apply import ApplyError, ApplyPreconditions, validate_apply
from .assessment_bundle import (
    VARIANT_FILENAMES,
    AssessmentBundleError,
    AssessmentBundleRequest,
    publish_assessment_bundle,
)
from .assessment_cleanup import (
    CleanupError,
    OwnershipRegistry,
    SafeOutputRootRegistry,
    scan_owned_staging,
)
from .assessment_compiler import AssessmentCompilerError, compile_assessment
from .assessment_profile import AssessmentProfileError, get_assessment_profile
from .assessment_publish import (
    PublishError,
    platform_atomic_publish_adapter,
    run_atomic_publish_probe,
)
from .assessment_qa import (
    AssessmentAuditValues,
    AssessmentQaError,
    assert_student_plan_flow,
    assessment_audit_values,
    project_assessment_variants,
)
from .assessment_session import AssessmentSessionError, AssessmentSessionStore
from .assessment_spec import AssessmentSpecError, parse_assessment_spec


class AssessmentWorkflowError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _apply_response(
    session_id: str,
    state: Literal["applied", "already_applied"],
) -> dict[str, object]:
    return {
        "available": True,
        "ok": True,
        "state": state,
        "session_id": session_id,
        "bundle_id": f"assessment-{session_id}",
        "variant_count": 3,
    }


class AssessmentWorkflow:
    def __init__(
        self,
        *,
        output_roots: tuple[str | Path, ...] = (),
        sessions: AssessmentSessionStore | None = None,
    ) -> None:
        self._sessions = sessions or AssessmentSessionStore()
        self._safe_roots = SafeOutputRootRegistry(output_roots)
        self._ownership = OwnershipRegistry(self._sessions.instance_id)
        self._audit_values: dict[str, AssessmentAuditValues] = {}
        self._plan_digests: dict[str, str] = {}
        self._sources: dict[str, Path] = {}

    @property
    def session_count(self) -> int:
        self._prune_session_data()
        return len(self._sources)

    def preview(self, template_path: str, raw_spec: object) -> dict[str, object]:
        self._prune_session_data()
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
            audit_values = assessment_audit_values(spec)
            created = self._sessions.create(
                spec_fingerprint=spec.spec_fingerprint,
                plan=plan,
            )
        except (
            AssessmentCompilerError,
            AssessmentProfileError,
            AssessmentQaError,
            AssessmentSessionError,
        ) as exc:
            raise AssessmentWorkflowError(exc.code) from None
        except (OSError, RuntimeError):
            raise AssessmentWorkflowError("profile_mismatch") from None

        self._sources[created.session_id] = Path(template_path)
        self._audit_values[created.session_id] = audit_values
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
                    "items": [
                        {
                            "item_id": trace.item_id,
                            "order": trace.order,
                            "target": trace.target,
                            "before": edit.expected_text,
                            "after": edit.value,
                        }
                        for trace in variant.item_trace
                        for edit in variant.edits
                        if edit.target == trace.target
                    ],
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
        self._prune_session_data()
        try:
            lease = self._sessions.apply(session_id, possession_token)
        except AssessmentSessionError as exc:
            if exc.bundle_id == f"assessment-{session_id}":
                return _apply_response(session_id, "already_applied")
            raise AssessmentWorkflowError(exc.code) from None

        try:
            with lease as snapshot:
                source = self._sources.get(session_id)
                audit_values = self._audit_values.get(session_id)
                expected_plan_digest = self._plan_digests.get(session_id)
                if source is None or audit_values is None or expected_plan_digest is None:
                    raise AssessmentWorkflowError("invalid_session_instance")
                try:
                    root = self._safe_roots.require_exact(output_dir)
                    profile = get_assessment_profile(snapshot.plan.profile_id)
                    scan_owned_staging(
                        root,
                        self._safe_roots,
                        self._ownership,
                        active_sessions=self._sessions.active_session_ids,
                    )
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
                publisher = platform_atomic_publish_adapter()
                if not run_atomic_publish_probe(root, publisher).available:
                    raise AssessmentWorkflowError("atomic_publish_unavailable")
                publish_assessment_bundle(
                    AssessmentBundleRequest(
                        snapshot.spec_fingerprint,
                        session_id,
                        source,
                        root,
                        final,
                        snapshot.plan,
                        audit_values,
                        self._ownership,
                        publisher,
                    )
                )
                lease.mark_applied()
                return _apply_response(session_id, "applied")
        except AssessmentWorkflowError:
            raise
        except (
            ApplyError,
            AssessmentBundleError,
            AssessmentQaError,
            CleanupError,
            PublishError,
        ) as exc:
            raise AssessmentWorkflowError(exc.code) from None
        except OSError:
            raise AssessmentWorkflowError("publish_io_error") from None
        finally:
            self._prune_session_data()

    def _prune_session_data(self) -> None:
        active = self._sessions.active_session_ids
        for values in (self._sources, self._audit_values, self._plan_digests):
            for session_id in tuple(values):
                if session_id not in active:
                    values.pop(session_id)


__all__ = [
    "AssessmentWorkflow",
    "AssessmentWorkflowError",
    "VARIANT_FILENAMES",
]

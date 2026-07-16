from __future__ import annotations

import errno
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest

from hangeul_core import assessment_bundle, assessment_workflow
from hangeul_core.assessment_publish import AtomicPublishAdapter, AtomicPublishProbeResult
from hangeul_core.assessment_qa import assert_student_variant_safe, read_hwpx_text_parts
from hangeul_core.assessment_workflow import AssessmentWorkflow, AssessmentWorkflowError
from hangeul_core.validate import validate_hwpx
from tests.test_assessment_spec import valid_spec


FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"
UNREGISTERED_FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"
EXPECTED_FILES = {"answer-key.hwpx", "manifest.json", "student.hwpx", "teacher.hwpx"}


@dataclass(frozen=True, slots=True)
class PublishedAssessment:
    workflow: AssessmentWorkflow
    session_id: str
    token: str
    source_digest: str
    bundle: Path
    publisher: AtomicPublishAdapter


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _move_no_replace(source: Path, destination: Path, _flags: int) -> None:
    if destination.exists():
        raise OSError(errno.EEXIST, "destination exists")
    source.rename(destination)


def _configure_publish(monkeypatch: pytest.MonkeyPatch) -> AtomicPublishAdapter:
    publisher = AtomicPublishAdapter.windows(_move_no_replace, device_id=lambda _path: 1)
    monkeypatch.setattr(
        assessment_workflow,
        "platform_atomic_publish_adapter",
        lambda: publisher,
    )
    monkeypatch.setattr(
        assessment_workflow,
        "run_atomic_publish_probe",
        lambda _root, _publisher: AtomicPublishProbeResult(available=True),
    )
    return publisher


@pytest.fixture(scope="module")
def published_assessment(tmp_path_factory: pytest.TempPathFactory) -> PublishedAssessment:
    root = tmp_path_factory.mktemp("assessment-e2e")
    patcher = pytest.MonkeyPatch()
    publisher = _configure_publish(patcher)
    workflow = AssessmentWorkflow(output_roots=(root,))
    source_digest = _digest(FIXTURE)
    preview = workflow.preview(str(FIXTURE), valid_spec())
    assert _digest(FIXTURE) == source_digest
    applied = workflow.apply(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(root),
    )
    assert _digest(FIXTURE) == source_digest
    context = PublishedAssessment(
        workflow,
        str(preview["session_id"]),
        str(preview["possession_token"]),
        source_digest,
        root / str(applied["bundle_id"]),
        publisher,
    )
    yield context
    patcher.undo()


def test_real_fixture_generates_exact_three_variant_bundle(
    published_assessment: PublishedAssessment,
) -> None:
    assert {path.name for path in published_assessment.bundle.iterdir()} == EXPECTED_FILES
    assert len(tuple(published_assessment.bundle.glob("*.hwpx"))) == 3


def test_all_variants_pass_structural_validation(
    published_assessment: PublishedAssessment,
) -> None:
    for filename in EXPECTED_FILES - {"manifest.json"}:
        assert validate_hwpx(published_assessment.bundle / filename)["valid"] is True


def test_variant_failure_publishes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_digest = _digest(FIXTURE)
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())
    _configure_publish(monkeypatch)
    monkeypatch.setattr(assessment_bundle, "validate_hwpx", lambda _path: {"valid": False})

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "invalid_output"
    assert tuple(tmp_path.iterdir()) == ()
    assert _digest(FIXTURE) == source_digest


def test_student_output_has_no_teacher_only_flow(
    published_assessment: PublishedAssessment,
) -> None:
    snapshot = published_assessment.workflow._sessions.snapshot(published_assessment.session_id)
    audit = published_assessment.workflow._audit_values[published_assessment.session_id]
    assert_student_variant_safe(
        snapshot.plan.variant("student"),
        read_hwpx_text_parts(published_assessment.bundle / "student.hwpx"),
        audit.teacher_only,
        audit.student_visible,
    )


def test_all_variants_preserve_internal_item_evidence_linkage(
    published_assessment: PublishedAssessment,
) -> None:
    plan = published_assessment.workflow._sessions.snapshot(published_assessment.session_id).plan
    linkages = {
        tuple((trace.item_id, trace.order, trace.points, trace.evidence_ids) for trace in variant.item_trace)
        for variant in plan.variants
    }
    assert len(linkages) == 1
    assert len(next(iter(linkages))) == 3


def test_preview_and_apply_leave_source_unchanged(
    published_assessment: PublishedAssessment,
) -> None:
    assert _digest(FIXTURE) == published_assessment.source_digest


def test_unregistered_template_fails_profile_match() -> None:
    source_digest = _digest(UNREGISTERED_FIXTURE)

    with pytest.raises(AssessmentWorkflowError) as caught:
        AssessmentWorkflow().preview(str(UNREGISTERED_FIXTURE), valid_spec())

    assert caught.value.code == "profile_mismatch"
    assert _digest(UNREGISTERED_FIXTURE) == source_digest


def test_published_bundle_is_complete_and_immutable(
    published_assessment: PublishedAssessment,
) -> None:
    before = {
        path.name: _digest(path)
        for path in published_assessment.bundle.iterdir()
    }

    with pytest.raises(AssessmentWorkflowError) as caught:
        published_assessment.workflow.apply(
            published_assessment.session_id,
            published_assessment.token,
            str(published_assessment.bundle.parent),
        )

    assert caught.value.code == "already_applied"
    assert published_assessment.publisher.publish_count == 1
    assert before == {
        path.name: _digest(path)
        for path in published_assessment.bundle.iterdir()
    }

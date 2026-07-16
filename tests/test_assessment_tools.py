import asyncio
import errno
from pathlib import Path

import pytest

from hangeul_core.assessment_cleanup import (
    CleanupError,
    STAGING_PREFIX,
    StagingOwner,
    create_owned_staging,
)
from hangeul_core.assessment_qa import AssessmentQaError
from hangeul_core.assessment_publish import AtomicPublishAdapter, AtomicPublishProbeResult
from hangeul_core.assessment_session import (
    AssessmentSessionPolicy,
    AssessmentSessionState,
    AssessmentSessionStore,
)
from hangeul_core import assessment_bundle
from hangeul_core.assessment_workflow import AssessmentWorkflow, AssessmentWorkflowError
from hangeul_mcp import server
from hangeul_mcp import tools_assessment
from tests.test_assessment_spec import valid_spec


ASSESSMENT_TOOLS = {"preview_assessment", "apply_assessment"}
FIXTURE = next((Path(__file__).parent / "hwpx template").glob("12_*.hwpx"))


def _registered_tool_names() -> set[str]:
    return {tool.name for tool in asyncio.run(server.mcp.list_tools())}


def test_public_assessment_tools_are_exactly_preview_and_apply():
    registered = _registered_tool_names()
    public_assessment_tools = {name for name in registered if "assessment" in name}

    assert public_assessment_tools == ASSESSMENT_TOOLS


def test_internal_validator_is_not_registered():
    assert "validate_assessment_spec" not in _registered_tool_names()


def test_invalid_preview_creates_no_session_or_token(tmp_path):
    before = tools_assessment._WORKFLOW.session_count

    result = server.preview_assessment(str(tmp_path / "private-template.hwpx"), {})

    assert result == {
        "available": True,
        "ok": False,
        "state": "failed",
        "error_code": "invalid_spec",
    }
    assert tools_assessment._WORKFLOW.session_count == before
    assert "session_id" not in result
    assert "possession_token" not in result


def test_preview_returns_item_level_before_after_for_every_variant():
    preview = AssessmentWorkflow().preview(str(FIXTURE), valid_spec())

    variants = preview["variants"]
    assert isinstance(variants, dict)
    for variant in variants.values():
        assert isinstance(variant, dict)
        items = variant["items"]
        assert isinstance(items, list)
        assert len(items) == 3
        assert all(set(item) == {"item_id", "order", "target", "before", "after"} for item in items)
        assert all(item["before"] and item["after"] for item in items)


def test_preview_converts_session_capacity_to_workflow_error():
    sessions = AssessmentSessionStore(policy=AssessmentSessionPolicy(capacity=0))
    workflow = AssessmentWorkflow(sessions=sessions)

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.preview(str(FIXTURE), valid_spec())

    assert caught.value.code == "session_capacity"
    assert workflow.session_count == 0


def test_default_workflow_rejects_unregistered_output_dir_without_write(tmp_path):
    workflow = AssessmentWorkflow()
    preview = workflow.preview(str(FIXTURE), valid_spec())

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "unregistered_output_root"
    assert list(tmp_path.iterdir()) == []


def test_apply_compares_current_plan_to_preview_digest(tmp_path):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())
    session_id = str(preview["session_id"])
    workflow._plan_digests[session_id] = "0" * 64

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(session_id, str(preview["possession_token"]), str(tmp_path))

    assert caught.value.code == "stale_plan"
    assert list(tmp_path.iterdir()) == []


def test_atomic_publish_probe_failure_prevents_bundle_write(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())
    monkeypatch.setattr(
        "hangeul_core.assessment_workflow.run_atomic_publish_probe",
        lambda _root, _publisher: AtomicPublishProbeResult(available=False),
    )

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "atomic_publish_unavailable"
    assert list(tmp_path.iterdir()) == []


def test_student_document_audit_blocks_publish(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())

    def reject_student_document(*_values):
        raise AssessmentQaError("answer_leakage")

    monkeypatch.setattr(
        "hangeul_core.assessment_bundle.assert_student_variant_safe",
        reject_student_document,
    )

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "answer_leakage"
    assert list(tmp_path.iterdir()) == []


def test_each_generated_variant_requires_unconditional_hwpx_validation(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())
    validation_calls: list[Path] = []

    def reject_first_output(path):
        validation_calls.append(Path(path))
        return {"valid": False}

    monkeypatch.setattr("hangeul_core.assessment_bundle.validate_hwpx", reject_first_output)

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "invalid_output"
    assert len(validation_calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_marker_creation_failure_cleans_owned_staging_same_call(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())

    def fail_create(root, owner, registry):
        staging = Path(root) / f"{STAGING_PREFIX}{owner.session_id}-{owner.ownership_nonce}"
        staging.mkdir()
        registry.register(staging, owner.ownership_nonce, owner.session_id)
        raise OSError("injected marker failure")

    monkeypatch.setattr(
        "hangeul_core.assessment_bundle.create_owned_staging",
        fail_create,
    )

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "publish_io_error"
    assert list(tmp_path.iterdir()) == []


def test_payload_creation_failure_cleans_owned_staging_same_call(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())
    original_mkdir = Path.mkdir

    def fail_payload(path, *args, **kwargs):
        if path.name == "bundle" and path.parent.name.startswith(STAGING_PREFIX):
            raise OSError("injected payload failure")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_payload)

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "publish_io_error"
    assert list(tmp_path.iterdir()) == []


def test_apply_start_reclaims_owned_orphan_staging(tmp_path):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    orphan = create_owned_staging(
        tmp_path,
        StagingOwner("orphan-session", "orphan-nonce"),
        workflow._ownership,
    )
    (orphan / "payload").mkdir()
    preview = workflow.preview(str(FIXTURE), valid_spec())

    applied = workflow.apply(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )

    assert applied["state"] == "applied"
    assert orphan.exists() is False


def test_apply_start_cleanup_failure_is_fail_closed(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())

    def reject_cleanup(*_args, **_kwargs):
        raise CleanupError("cleanup_unsafe_descendant")

    monkeypatch.setattr(
        "hangeul_core.assessment_workflow.scan_owned_staging",
        reject_cleanup,
    )

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "cleanup_unsafe_descendant"
    assert tuple(tmp_path.iterdir()) == ()


def test_cleanup_failure_after_rename_recovers_as_applied(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())
    original_cleanup = assessment_bundle.cleanup_owned_staging

    def clean_then_report_failure(staging, ownership, root):
        original_cleanup(staging, ownership, root)
        raise CleanupError("cleanup_unsafe_descendant")

    monkeypatch.setattr(
        "hangeul_core.assessment_bundle.cleanup_owned_staging",
        clean_then_report_failure,
    )

    applied = workflow.apply(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )

    bundle = tmp_path / str(applied["bundle_id"])
    assert applied["state"] == "applied"
    assert sorted(path.name for path in bundle.iterdir()) == [
        "answer-key.hwpx",
        "manifest.json",
        "student.hwpx",
        "teacher.hwpx",
    ]


def test_cleanup_failure_after_rename_fails_closed_while_staging_remains(
    tmp_path,
    monkeypatch,
):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())

    def leave_staging_and_fail(_staging, _ownership, _root):
        raise CleanupError("cleanup_unsafe_descendant")

    monkeypatch.setattr(
        "hangeul_core.assessment_bundle.cleanup_owned_staging",
        leave_staging_and_fail,
    )

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )

    assert caught.value.code == "cleanup_unsafe_descendant"
    assert any(path.name.startswith(STAGING_PREFIX) for path in tmp_path.iterdir())


def test_rename_then_adapter_error_recovers_complete_bundle_as_applied(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())

    def move_then_raise(source, destination, _flags):
        source.replace(destination)
        raise OSError(errno.EACCES, "injected response failure")

    publisher = AtomicPublishAdapter.windows(move_then_raise, device_id=lambda _path: 1)
    monkeypatch.setattr(
        "hangeul_core.assessment_workflow.platform_atomic_publish_adapter",
        lambda: publisher,
    )
    monkeypatch.setattr(
        "hangeul_core.assessment_workflow.run_atomic_publish_probe",
        lambda _root, _publisher: AtomicPublishProbeResult(available=True),
    )

    applied = workflow.apply(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )

    bundle = tmp_path / str(applied["bundle_id"])
    assert applied["state"] == "applied"
    assert publisher.publish_count == 1
    assert workflow._sessions.snapshot(str(preview["session_id"])).state is AssessmentSessionState.APPLIED
    assert sorted(path.name for path in bundle.iterdir()) == [
        "answer-key.hwpx",
        "manifest.json",
        "student.hwpx",
        "teacher.hwpx",
    ]
    replay = workflow.apply(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )
    assert replay == {
        "available": True,
        "ok": True,
        "state": "already_applied",
        "session_id": str(preview["session_id"]),
        "bundle_id": applied["bundle_id"],
        "variant_count": 3,
    }
    assert publisher.publish_count == 1


def test_terminal_apply_releases_workflow_side_maps(tmp_path):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())

    workflow.apply(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )

    assert workflow.session_count == 0
    assert workflow._sources == {}
    assert workflow._audit_values == {}
    assert workflow._plan_digests == {}


def test_expired_session_releases_workflow_side_maps():
    now = [0.0]
    sessions = AssessmentSessionStore(
        clock=lambda: now[0],
        policy=AssessmentSessionPolicy(ttl_seconds=1.0),
    )
    workflow = AssessmentWorkflow(sessions=sessions)
    workflow.preview(str(FIXTURE), valid_spec())
    now[0] = 1.0

    assert workflow.session_count == 0
    assert workflow._sources == {}
    assert workflow._audit_values == {}
    assert workflow._plan_digests == {}


def test_response_construction_failure_preserves_applied_replay(tmp_path, monkeypatch):
    workflow = AssessmentWorkflow(output_roots=(tmp_path,))
    preview = workflow.preview(str(FIXTURE), valid_spec())
    publisher = AtomicPublishAdapter.windows(
        lambda source, destination, _flags: source.replace(destination),
        device_id=lambda _path: 1,
    )
    original_response = __import__(
        "hangeul_core.assessment_workflow", fromlist=["_apply_response"]
    )._apply_response

    def fail_applied_response(session_id, state):
        if state == "applied":
            raise OSError(errno.EACCES, "injected response failure")
        return original_response(session_id, state)

    monkeypatch.setattr(
        "hangeul_core.assessment_workflow.platform_atomic_publish_adapter",
        lambda: publisher,
    )
    monkeypatch.setattr(
        "hangeul_core.assessment_workflow.run_atomic_publish_probe",
        lambda _root, _publisher: AtomicPublishProbeResult(available=True),
    )
    monkeypatch.setattr(
        "hangeul_core.assessment_workflow._apply_response",
        fail_applied_response,
    )

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(
            str(preview["session_id"]),
            str(preview["possession_token"]),
            str(tmp_path),
        )
    replay = workflow.apply(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )

    assert caught.value.code == "publish_io_error"
    assert replay["state"] == "already_applied"
    assert replay["bundle_id"] == f"assessment-{preview['session_id']}"
    assert publisher.publish_count == 1


def test_student_flow_audit_runs_before_session_creation(monkeypatch):
    workflow = AssessmentWorkflow()

    def reject_student_flow(_plan):
        raise AssessmentQaError("answer_leakage")

    monkeypatch.setattr(
        "hangeul_core.assessment_workflow.assert_student_plan_flow",
        reject_student_flow,
    )

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.preview(str(FIXTURE), valid_spec())

    assert caught.value.code == "answer_leakage"
    assert workflow.session_count == 0

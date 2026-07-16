import asyncio
from pathlib import Path

import pytest

from hangeul_core.assessment_qa import AssessmentQaError
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


def test_default_workflow_accepts_exact_existing_output_dir(tmp_path):
    workflow = AssessmentWorkflow()
    preview = workflow.preview(str(FIXTURE), valid_spec())

    applied = workflow.apply(
        str(preview["session_id"]),
        str(preview["possession_token"]),
        str(tmp_path),
    )

    bundle = tmp_path / str(applied["bundle_id"])
    assert sorted(path.name for path in bundle.iterdir()) == [
        "answer-key.hwpx",
        "manifest.json",
        "student.hwpx",
        "teacher.hwpx",
    ]


def test_apply_compares_current_plan_to_preview_digest(tmp_path):
    workflow = AssessmentWorkflow()
    preview = workflow.preview(str(FIXTURE), valid_spec())
    session_id = str(preview["session_id"])
    workflow._plan_digests[session_id] = "0" * 64

    with pytest.raises(AssessmentWorkflowError) as caught:
        workflow.apply(session_id, str(preview["possession_token"]), str(tmp_path))

    assert caught.value.code == "stale_plan"
    assert list(tmp_path.iterdir()) == []


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

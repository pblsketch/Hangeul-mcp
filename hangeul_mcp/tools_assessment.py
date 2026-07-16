from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hangeul_core.assessment_observability import (
    AssessmentLogEvent,
    FailureCounts,
    build_failure_evidence,
    emit_assessment_event,
)
from hangeul_core.assessment_workflow import AssessmentWorkflow, AssessmentWorkflowError


def _configured_output_roots() -> tuple[Path, ...]:
    raw = os.environ.get("HANGEUL_MCP_ASSESSMENT_OUTPUT_ROOTS", "")
    return tuple(Path(value).expanduser() for value in raw.split(os.pathsep) if value.strip())


_WORKFLOW = AssessmentWorkflow(output_roots=_configured_output_roots())


def configure_assessment_output_roots(roots: tuple[str | Path, ...]) -> None:
    global _WORKFLOW
    _WORKFLOW = AssessmentWorkflow(output_roots=roots)


def _failure(code: str) -> dict[str, object]:
    return {
        "available": True,
        "ok": False,
        "state": "failed",
        **build_failure_evidence(code, FailureCounts()),
    }


def _preview_counts(result: Mapping[str, object]) -> tuple[int, int]:
    variants = result.get("variants")
    if not isinstance(variants, Mapping):
        return 0, 0
    item_count = 0
    target_count = 0
    for value in variants.values():
        if not isinstance(value, Mapping):
            continue
        items = value.get("item_count")
        targets = value.get("target_count")
        if type(items) is int:
            item_count += items
        if type(targets) is int:
            target_count += targets
    return item_count, target_count


def preview_assessment(template_path: str, spec: object) -> dict[str, object]:
    """Validate and preview three deterministic assessment variants without writing files."""
    try:
        result = _WORKFLOW.preview(template_path, spec)
    except AssessmentWorkflowError as exc:
        return _failure(exc.code)
    item_count, target_count = _preview_counts(result)
    emit_assessment_event(
        AssessmentLogEvent(
            event="assessment_preview",
            state="preview_ready",
            session_id=str(result["session_id"]),
            item_count=item_count,
            target_count=target_count,
        )
    )
    return result


def apply_assessment(
    session_id: str,
    possession_token: str,
    output_dir: str,
) -> dict[str, object]:
    """Atomically publish a reviewed three-variant assessment bundle to a safe root."""
    try:
        result = _WORKFLOW.apply(session_id, possession_token, output_dir)
    except AssessmentWorkflowError as exc:
        return _failure(exc.code)
    emit_assessment_event(
        AssessmentLogEvent(
            event="assessment_apply",
            state="applied",
            session_id=str(result["session_id"]),
        )
    )
    return result


def register_assessment_tools(mcp: Any) -> dict[str, Any]:
    registered_preview = mcp.tool()(preview_assessment)
    registered_apply = mcp.tool()(apply_assessment)
    return {
        "preview_assessment": registered_preview,
        "apply_assessment": registered_apply,
    }


__all__ = [
    "apply_assessment",
    "configure_assessment_output_roots",
    "preview_assessment",
    "register_assessment_tools",
]

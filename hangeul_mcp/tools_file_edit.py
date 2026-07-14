from __future__ import annotations

import re
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field

import hangeul_core.addressed as _addressed
from hangeul_core.addressed import apply_addressed_edits as _apply_addressed_edits
from hangeul_core.addressed import preview_addressed_edits as _preview_addressed_edits
from hangeul_core.convert import ensure_hwpx
from hangeul_core.edit import (
    apply_edit_session as _apply_edit_session,
    batch_replace as _batch_replace,
    preview_batch_replace as _preview_batch_replace,
    preview_search_and_replace as _preview_search_and_replace,
    restore_edit_session as _restore_edit_session,
    search_and_replace as _search_and_replace,
)


def _plan_payload(plan) -> Dict[str, Any]:
    return {
        "available": True,
        "ok": True,
        "session_id": plan.session_id,
        "kind": plan.kind,
        "substrate": plan.substrate,
        "source_path": plan.source_path,
        "source_sha256": plan.source_sha256,
        "counts": dict(plan.counts),
        "total": plan.total,
        "changed_entries": list(plan.changed_entries),
        "audit": list(plan.audit),
    }


def _structured_search_and_replace_error(exc: Exception) -> Dict[str, Any]:
    message = str(exc)
    if "scope='all'" in message:
        return {
            "available": True,
            "ok": False,
            "state": "ambiguous_match",
            "scope_required": "all",
            "error": message,
            "total": 0,
        }
    return {"available": True, "ok": False, "state": "error", "error": message, "total": 0}



def _requires_distinct_out_path(path: str, out_path: str) -> bool:
    if not out_path.strip():
        return True
    return _addressed._same_document_path(path, out_path)


class AddressedEdit(BaseModel):
    """One structural edit. Kind and operation are inferred when omitted."""

    target: str = Field(
        description=(
            "Exact target from inspect_editable_regions: tN.rN.cN for a whole cell, "
            "tN.rN.cN.pN for one paragraph inside a cell, or bN for a body paragraph. "
            "Do not pass sN.pN.occN occurrence IDs here."
        ),
        examples=["t2.r4.c2.p1"],
    )
    value: str = Field(description="Complete replacement text for this exact target")
    expected_text: str = Field(
        default="",
        description="Optional current text copied from inspection; mismatch fails closed",
    )
    kind: Literal["cell", "paragraph", "body_para"] | None = Field(
        default=None,
        description="Usually omit; inferred from target",
    )
    operation: Literal["replace_text", "preserve_marker_replace_tail"] | None = Field(
        default=None,
        description="Usually omit; defaults to replace_text. preserve_marker_replace_tail is only for bN.",
    )


_CELL_TARGET = re.compile(r"^t\d+\.r\d+\.c\d+$")
_PARAGRAPH_TARGET = re.compile(r"^t\d+\.r\d+\.c\d+\.p\d+$")
_BODY_TARGET = re.compile(r"^b\d+$")


def _normalize_addressed_edits(edits: list[AddressedEdit]) -> list[dict]:
    normalized: list[dict] = []
    for edit in edits:
        item = edit.model_dump() if isinstance(edit, BaseModel) else dict(edit)
        target = str(item.get("target") or "")
        inferred = (
            "cell" if _CELL_TARGET.fullmatch(target)
            else "paragraph" if _PARAGRAPH_TARGET.fullmatch(target)
            else "body_para" if _BODY_TARGET.fullmatch(target)
            else None
        )
        if not item.get("kind") and inferred:
            item["kind"] = inferred
        if not item.get("operation"):
            item["operation"] = "replace_text"
        normalized.append({key: value for key, value in item.items() if value is not None})
    return normalized


def register_file_edit_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def search_and_replace(path: str, find: str, replace: str, out_path: str, scope: str = "") -> Dict[str, Any]:
        """One-shot text replace written to a NEW file; fails closed on 2+ matches unless scope='all'."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "ok": False, "error": str(exc), "total": 0}
        try:
            res = _search_and_replace(path, find, replace, out_path, scope=scope)
        except RuntimeError as exc:
            return _structured_search_and_replace_error(exc)
        return {"available": True, "ok": True, "counts": res.counts, "total": res.total, "out_path": res.out_path}

    @mcp.tool()
    def batch_replace(path: str, replacements: Dict[str, str], out_path: str) -> Dict[str, Any]:
        """Apply multiple find->replace pairs to a NEW file in one pass (text substitution only)."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "ok": False, "error": str(exc), "total": 0}
        res = _batch_replace(path, replacements, out_path)
        return {"available": True, "ok": True, "counts": res.counts, "total": res.total, "out_path": res.out_path}

    @mcp.tool()
    def preview_search_and_replace(path: str, find: str, replace: str) -> Dict[str, Any]:
        """Preview a text replace as an edit session (entry/count audit) without writing output."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "ok": False, "error": str(exc), "total": 0}
        return _plan_payload(_preview_search_and_replace(path, find, replace))

    @mcp.tool()
    def preview_batch_replace(path: str, replacements: Dict[str, str]) -> Dict[str, Any]:
        """Preview multiple find->replace pairs as one edit session without writing output."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "ok": False, "error": str(exc), "total": 0}
        return _plan_payload(_preview_batch_replace(path, replacements))

    @mcp.tool()
    def apply_edit_session(session_id: str, out_path: str = "") -> Dict[str, Any]:
        """Write a previewed edit session to a NEW file with journal/snapshot for restore."""
        try:
            session = _apply_edit_session(session_id, out_path or None)
        except Exception as exc:
            return {"available": True, "ok": False, "error": str(exc)}
        return {
            "available": True,
            "ok": True,
            "session_id": session.session_id,
            "kind": session.kind,
            "substrate": session.substrate,
            "source_path": session.source_path,
            "target_path": session.target_path,
            "journal_path": session.journal_path,
            "snapshot_path": session.snapshot_path,
            "counts": dict(session.counts),
            "total": session.total,
            "changed_entries": list(session.changed_entries),
            "audit": list(session.audit),
        }

    @mcp.tool()
    def preview_addressed_edits(path: str, edits: list[AddressedEdit]) -> Dict[str, Any]:
        """Resolve STRUCTURAL addressed edits in file mode without writing output.

        `edits` do NOT require `{}` named fields. Use structural addresses for
        repeated "▶", repeated "○○○", ordinary table cells, and paragraphs.
        Repeated text must never be treated as a global replace; require
        explicit scope in the address. For whole-template completion, gather or
        generate all values first and prepare one edits array here instead of
        one tool call per cell. Start in file mode from the beginning instead
        of mixing live field writes and then falling back to file mode. Preview
        here first to confirm each edit resolves to the intended local target and
        returns the reviewed session that `apply_addressed_edits(session_id, out_path)`
        writes later as a completed copy. This addressed file-mode route does not mutate the already-open same Hangul window; open the verified output afterward if live review is needed.
        """
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {
                "available": True,
                "ok": False,
                "error": str(exc),
                "counts": {"requested": len(list(edits)), "resolved": 0, "applied": 0, "skipped": 0, "unresolved": 0},
            }
        return {"available": True, **_preview_addressed_edits(path, _normalize_addressed_edits(edits))}

    @mcp.tool()
    def apply_addressed_edits(session_id: str, out_path: str) -> Dict[str, Any]:
        """Write the previewed addressed edits to a NEW file-mode output copy.

        The reviewed addressed plan came from structural addresses, not `{}` named
        fields, so repeated "▶", repeated "○○○", ordinary table cells, and
        paragraphs stay explicitly scoped. This applies the `session_id` returned by
        `preview_addressed_edits(...)` together with the required `out_path` after
        you already gathered all values first; do not turn whole-template completion
        into one tool call per cell or mix live field writes and then fall back to
        file mode. It does not mutate the already-open same Hangul window for the
        same document. Keep repeated text explicit with structural scope instead of
        an unscoped global replacement. After apply succeeds, open the verified output
        file afterward if live review is needed.
        """
        if not out_path.strip():
            return {"available": True, "ok": False, "state": "invalid_output_path", "error": "out_path must be a separate output path for this tool"}
        return {"available": True, **_apply_addressed_edits(session_id, out_path)}

    @mcp.tool()
    def complete_addressed_template(path: str, edits: list[AddressedEdit], out_path: str, verify: bool = True) -> Dict[str, Any]:
        """Complete a whole template in ONE addressed file-mode call and write a new copy.

        Gather or generate all values first, then send one `edits` array here —
        not one call per cell. `edits` do NOT require `{}` named fields; use
        structural addresses for repeated "▶", repeated "○○○", ordinary table
        cells, and paragraphs, and never treat repeated text as a document-wide
        replace without explicit scope. Start in file mode for whole-template
        completion instead of mixing live field writes and falling back to file mode
        later. This addressed file-mode path writes `out_path` only and does not
        mutate the already-open same Hangul window; open the verified output
        afterward.
        """
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {
                "available": True,
                "ok": False,
                "state": "error",
                "error": str(exc),
                "counts": {"requested": len(list(edits)), "resolved": 0, "applied": 0, "skipped": 0, "unresolved": 0, "verified": 0},
            }
        if _requires_distinct_out_path(path, out_path):
            return {
                "available": True,
                "ok": False,
                "state": "invalid_output_path",
                "error": "out_path must be a separate output path for this tool",
                "counts": {"requested": len(list(edits)), "resolved": 0, "applied": 0, "skipped": 0, "unresolved": 0, "verified": 0},
            }
        complete = getattr(_addressed, "complete_addressed_template", None)
        if not callable(complete):
            return {
                "available": True,
                "ok": False,
                "state": "error",
                "error": "complete_addressed_template is unavailable in hangeul_core.addressed",
                "counts": {"requested": len(list(edits)), "resolved": 0, "applied": 0, "skipped": 0, "unresolved": 0, "verified": 0},
            }
        return {"available": True, **complete(path, _normalize_addressed_edits(edits), out_path, verify=verify)}

    @mcp.tool()
    def restore_edit_session(journal_path: str) -> Dict[str, Any]:
        """Restore the pre-apply snapshot of an applied edit session (file-mode undo)."""
        try:
            result = _restore_edit_session(journal_path)
        except Exception as exc:
            return {"available": True, "ok": False, "error": str(exc)}
        return {
            "available": True,
            "ok": True,
            "session_id": result.session_id,
            "substrate": result.substrate,
            "target_path": result.target_path,
            "journal_path": result.journal_path,
            "snapshot_path": result.snapshot_path,
            "restored": result.restored,
            "target_exists": result.target_exists,
        }

    return {name: obj for name, obj in locals().items() if callable(obj) and not name.startswith("_")}

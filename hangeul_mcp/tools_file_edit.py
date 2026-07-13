from __future__ import annotations

from typing import Any, Dict

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


def register_file_edit_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def search_and_replace(path: str, find: str, replace: str, out_path: str, scope: str = "") -> Dict[str, Any]:
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
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "ok": False, "error": str(exc), "total": 0}
        res = _batch_replace(path, replacements, out_path)
        return {"available": True, "ok": True, "counts": res.counts, "total": res.total, "out_path": res.out_path}

    @mcp.tool()
    def preview_search_and_replace(path: str, find: str, replace: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "ok": False, "error": str(exc), "total": 0}
        return _plan_payload(_preview_search_and_replace(path, find, replace))

    @mcp.tool()
    def preview_batch_replace(path: str, replacements: Dict[str, str]) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "ok": False, "error": str(exc), "total": 0}
        return _plan_payload(_preview_batch_replace(path, replacements))

    @mcp.tool()
    def apply_edit_session(session_id: str, out_path: str = "") -> Dict[str, Any]:
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
    def preview_addressed_edits(path: str, edits: list) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {
                "available": True,
                "ok": False,
                "error": str(exc),
                "counts": {"requested": len(list(edits)), "resolved": 0, "applied": 0, "skipped": 0, "unresolved": 0},
            }
        return {"available": True, **_preview_addressed_edits(path, list(edits))}

    @mcp.tool()
    def apply_addressed_edits(session_id: str, out_path: str = "") -> Dict[str, Any]:
        return {"available": True, **_apply_addressed_edits(session_id, out_path or None)}

    @mcp.tool()
    def restore_edit_session(journal_path: str) -> Dict[str, Any]:
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

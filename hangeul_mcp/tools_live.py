from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from hangeul_core.convert import ensure_hwpx
from hangeul_core.hwp import HwpBridge, normalize_field_values
from hangeul_core.hwp.com import find_rot_exact_path_candidates, list_rot_instances

from hangeul_core.hwp.live import apply_cells_to_open as _apply_cells_to_open
from hangeul_core.hwp.live import open_in_hwp as _open_in_hwp
from hangeul_core.hwp.live import preview_cells_to_open as _preview_cells_to_open
from hangeul_core.live_timeout import run_with_timeout
from hangeul_core.runtime_info import attach_ladder, feature_flags, runtime_identity
from hangeul_core.hwp.rot_attach import apply_named_fields_exact_path as _apply_named_fields_exact_path
from hangeul_mcp.live_current import (
    apply_to_current_hwp_document as _apply_to_current_hwp_document,
    preview_current_hwp_document as _preview_current_hwp_document,
    resolve_current_hwp_document as _resolve_current_hwp_document,
)


def _exact_attach_candidates(path: Path) -> List[Dict[str, Any]]:
    return [dict(item) for item in find_rot_exact_path_candidates(path)]


def _open_in_hwp_worker(path: str, visible: bool) -> Dict[str, Any]:
    return _open_in_hwp(Path(path), visible=visible)


def _run_open_in_hwp_timed(path: str, visible: bool, timeout_seconds: float) -> Dict[str, Any]:
    outcome = run_with_timeout(_open_in_hwp_worker, path, visible, timeout_seconds=timeout_seconds)
    if outcome["ok"]:
        result = dict(outcome["result"])
        result.setdefault("timeout_seconds", timeout_seconds)
        return result
    return {
        "available": True,
        "ok": False,
        "state": outcome.get("state", "timeout_outcome_unknown"),
        "may_have_partially_applied": outcome.get("may_have_partially_applied", True),
        "timeout_seconds": timeout_seconds,
        "elapsed_seconds": outcome.get("elapsed_seconds"),
        "requested_path": path,
        "error": outcome.get("error", "operation timed out in isolated worker"),
    }

def register_live_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def hwp_status() -> Dict[str, Any]:
        """Live COM availability probe — side-effect-free, never launches Hangul.

        connected:false is the NORMAL idle state (no attach is attempted here).
        `instances` lists automation-visible Hangul instances already in the COM
        ROT. For live edits, attach by exact path first with `open_in_hwp(path)` or
        use the saved-`.hwpx` current-document flow (`resolve_current_hwp_document`
        -> `preview_current_hwp_document` -> `apply_to_current_hwp_document`).
        """
        st = HwpBridge().status()
        instances = list_rot_instances()
        st.update(runtime_identity())
        st["feature_flags"] = feature_flags()
        st["instances"] = instances
        st["attach_ladder"] = attach_ladder(
            rot_visible=bool(instances),
            com_object_acquired=False,
            document_identity_proven=False,
        )
        st["attach_boundary"] = (
            "live tools use exact-path attach against automation-visible COM ROT instances; "
            "use open_in_hwp(path) first so the requested exact path is active before live apply"
        )
        st["first_call_hint"] = (
            "if instances is empty, the first open_in_hwp/apply call LAUNCHES Hangul — "
            "cold start can take tens of seconds (responses carry cold_start/elapsed_seconds); "
            "later calls take a few seconds"
        )
        if not st.get("connected"):
            st["note"] = (
                "connected:false is the normal idle state: hwp_status is side-effect-free "
                "and never attaches to Hangul. It does NOT mean live fill is unreachable."
            )
            st["next"] = (
                "whole-template completion: inspect_editable_regions(path, compact=true), then "
                "complete_addressed_template(path, output_path, edits) once; "
                "small live label:value cell fill only: open_in_hwp(path), "
                "preview_cells_to_open_hwp(path, values), then apply_cells_to_open_hwp"
            )
        return st

    @mcp.tool()
    def open_in_hwp(path: str, visible: bool = True, timeout_seconds: float = 0.0) -> Dict[str, Any]:
        """Open a .hwp/.hwpx file in a CONTROLLABLE Hangul window.

        Hand-opened windows are not a safe exact-path live-attach anchor on their
        own. Use this tool to attach by exact path in the automation-visible
        window first, then apply_to_open_hwp / apply_cells_to_open_hwp. Leaves the
        window open; saves and closes nothing. If Hangul is not running, this
        launches it — cold start can take tens of seconds
        (see cold_start/elapsed_seconds in the response). When timeout_seconds > 0,
        the call runs in an isolated worker and returns timeout_outcome_unknown on
        timeout because open state may be partially applied.
        """
        p = Path(path)
        if p.suffix.lower() not in (".hwp", ".hwpx"):
            return {"available": True, "ok": False, "error": "open_in_hwp accepts .hwp or .hwpx files"}
        if timeout_seconds > 0:
            return _run_open_in_hwp_timed(str(p), visible, timeout_seconds)
        return _open_in_hwp(p, visible=visible)

    @mcp.tool()
    def apply_to_open_hwp(
        values: Dict[str, str],
        path: str | None = None,
        visible: bool = True,
    ) -> Dict[str, Any]:
        """One-shot VALUE fill of named form fields (누름틀) in the OPEN Hangul window.

        Value insertion only — formatting/styling edits are not supported live;
        use the file-mode delegate tools and produce a new file instead. Legacy
        mode is pathless and writes to the active automation document. When
        path=... is provided, this tool performs broker-targeted exact-path live
        apply and refuses to guess across multiple automation brokers. This path
        does not currently expose a timeout_seconds worker-isolation contract.
        """

        if path is not None:
            p = Path(path)
            if p.suffix.lower() not in (".hwp", ".hwpx"):
                return {"available": True, "ok": False, "error": "apply_to_open_hwp accepts .hwp or .hwpx files"}
            return _apply_named_fields_exact_path(p, values, visible=visible)

        bridge = HwpBridge()
        if not bridge.available():
            return {
                "available": False,
                "connected": False,
                "state": "unavailable",
                "error": "COM bridge needs Windows + pywin32 + Hangul",
            }
        try:
            bridge.connect(visible=visible)
        except Exception as exc:
            return {
                "available": True,
                "connected": False,
                "state": "legacy_connect_failed",
                "error": str(exc),
            }
        fields = bridge.get_field_list()
        if not fields:
            return {
                "available": True,
                "connected": True,
                "state": "legacy_needs_field_registration",
                "needs_field_registration": True,
                "note": "no named fields; use apply_cells_to_open_hwp for cell-based forms",
            }
        result = bridge.put_field_text(normalize_field_values(values))
        return {
            "available": True,
            "connected": True,
            "state": "legacy_connected",
            "field_count": len(fields),
            **result,
        }

    @mcp.tool()
    def preview_cells_to_open_hwp(path: str, values: Dict[str, str]) -> Dict[str, Any]:
        """Preview small live label:value cell fills WITHOUT COM or ROT access.

        This is not whole-template completion. For a full lesson plan or other
        structured form, use compact inspect then complete_addressed_template.
        This pure preview does not probe COM ROT or attach candidates; exact-path
        attachment is deferred to apply_cells_to_open_hwp.
        """
        p = Path(path)
        if p.suffix.lower() == ".hwp":
            return {
                "available": True,
                "ok": False,
                "error": "preview_cells_to_open_hwp is side-effect free and only accepts .hwpx; save/convert .hwp to .hwpx first",
            }
        if p.suffix.lower() != ".hwpx":
            return {"available": True, "ok": False, "error": "preview_cells_to_open_hwp only accepts .hwpx files"}
        result = dict(_preview_cells_to_open(p, values))
        result.update(
            {
                "ok": result.get("ok", True),
                "resolver": {
                    "side_effect_free": True,
                    "exact_path": str(p),
                    "apply_to_open_hwp_state": "pathful_exact_path",
                    "apply_cells_to_open_hwp_state": "pathful_exact_path",
                },
                "attach_candidates": [],
                "attach_probe": "deferred_to_apply",
            }
        )
        return result

    @mcp.tool()
    def apply_cells_to_open_hwp(
        path: str,
        values: Dict[str, str],
        visible: bool = True,
        clear: bool = True,
        open_if_needed: bool = True,
    ) -> Dict[str, Any]:
        """Fill a small set of label:value CELLS in the OPEN Hangul window live.

        Handles empty label:value cells AND inline blanks (colon "은행명:",
        marker "∘ 프로그램명", checkboxes). Value insertion only — no
        formatting/styling. Not for whole-template completion: use compact inspect
        plus complete_addressed_template for lesson plans and other full forms.
        Attaches to the automation-visible instance on call
        and verifies the requested exact path is active; if not, it opens it there
        when open_if_needed=true. Cold start can take tens of seconds. Preview
        first with preview_cells_to_open_hwp.
        """
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "error": str(exc)}
        return _apply_cells_to_open(
            path, values, visible=visible, clear=clear, open_if_needed=open_if_needed
        )

    @mcp.tool()
    def resolve_current_hwp_document() -> Dict[str, Any]:
        """Resolve the current/open Hangul document inventory without writing anything.

        This is the side-effect-free entry point for the pathless current-document
        UX. It never auto-selects around an unsupported, unsaved, or unprovable
        current document.
        """
        return _resolve_current_hwp_document()

    @mcp.tool()
    def preview_current_hwp_document(
        values: Dict[str, str],
        candidate_id: str | None = None,
        mode: str = "auto",
    ) -> Dict[str, Any]:
        """Preview the saved current `.hwpx` document pathlessly without writing it.

        Saved `.hwp` current documents stay out of v1 scope and return
        `preview_requires_hwpx`. Successful preview returns the authoritative
        preview_token for `apply_to_current_hwp_document`.
        """
        return _preview_current_hwp_document(values=values, candidate_id=candidate_id, mode=mode)

    @mcp.tool()
    def apply_to_current_hwp_document(preview_token: str) -> Dict[str, Any]:
        """Apply a previously previewed pathless current-document edit by token only.

        The token is authoritative: this tool accepts no fresh values or target
        hints, and it revalidates the selected broker and exact target before
        mutating the live document. This path does not currently expose a
        timeout_seconds worker-isolation contract.
        """
        return _apply_to_current_hwp_document(preview_token)

    return {
        "hwp_status": hwp_status,
        "open_in_hwp": open_in_hwp,
        "apply_to_open_hwp": apply_to_open_hwp,
        "preview_cells_to_open_hwp": preview_cells_to_open_hwp,
        "apply_cells_to_open_hwp": apply_cells_to_open_hwp,
        "resolve_current_hwp_document": resolve_current_hwp_document,
        "preview_current_hwp_document": preview_current_hwp_document,
        "apply_to_current_hwp_document": apply_to_current_hwp_document,
    }

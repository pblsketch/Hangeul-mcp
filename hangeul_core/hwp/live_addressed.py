"""In-place live ADDRESSED editing of the open Hangul document (P0-C, gated).

``plan_live_addressed_edits`` stays PURE (no COM): it resolves ``AddressedEdit``
targets against the SAVED file, makes ``expected_text`` MANDATORY per edit, and
fails closed on anything the live substrate cannot replace safely — nested
tables (D7: the analyze global table index matches pyhwpx
``get_into_nth_table`` order only for top-level tables), body paragraphs, and
multi-paragraph cells. ``apply_live_addressed`` drives the open window over COM
and re-reads each cell's CURRENT text immediately before the destructive
replace, so a D7 drift surfaces as an ``expected_text_mismatch`` skip instead
of a silent mis-write. The document is NEVER saved, closed, or reloaded here;
the route stays behind ``feature_flags()['live_addressed_editing']`` until the
desktop-live QA gate passes.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Dict, List

from hangeul_core.addressed import preview_addressed_edits
from hangeul_core.analyze import analyze
from hangeul_core.hwp.com import (
    list_rot_instances,
    load_pyhwpx,
    restore_dialogs,
    suppress_dialogs,
)
from hangeul_core.hwp.live_attach import _ensure_active_document
from hangeul_core.runtime_info import feature_flags

_CELL_TARGET = re.compile(r"^t\d+\.r\d+\.c\d+$")
_PARA_TARGET = re.compile(r"^(?P<cell>t\d+\.r\d+\.c\d+)\.p(?P<ordinal>\d+)$")

HYBRID_FALLBACK = (
    "use the complete_and_load hybrid instead: preview_current_hwp_document(edits=[...]) "
    "-> apply_to_current_hwp_document — a NEW verified file opens as a new tab and the "
    "original stays untouched"
)


def live_addressed_enabled() -> bool:
    return bool(feature_flags().get("live_addressed_editing"))


def _cell_key(target: str, kind: str) -> tuple[str | None, str | None]:
    """Return (cell field_id, unsupported reason) for a live-editable target."""
    if kind == "cell" and _CELL_TARGET.match(target):
        return target, None
    if kind == "paragraph":
        match = _PARA_TARGET.match(target)
        if match is None:
            return None, "unsupported_target"
        if int(match.group("ordinal")) != 1:
            # live replace rewrites the WHOLE cell; only p1-of-1 is equivalent
            return None, "paragraph_ordinal_unsupported"
        return match.group("cell"), None
    if kind == "body_para":
        return None, "body_targets_file_mode_only"
    return None, "unsupported_target"


def plan_live_addressed_edits(path: str | Path, edits: List[dict]) -> Dict:
    """Resolve edits to live cell targets (PURE — no COM). Fail-closed by design."""
    result = analyze(path)
    cells = {c.field_id: c for c in result.all_cells()}
    base = {"available": True, "ok": False, "route": "live_addressed"}
    if any(c.has_nested_table for c in cells.values()):
        return {**base, "state": "nested_tables_unsupported", "next": HYBRID_FALLBACK}

    unresolved: List[dict] = []
    live_map: Dict[str, dict] = {}
    for item in edits:
        target = str(item.get("target") or "")
        if "expected_text" not in item:
            # live replace is destructive: the pre-write contrast is NOT optional
            unresolved.append({"target": target, "reason": "expected_text_required"})
            continue
        cell_key, reason = _cell_key(target, str(item.get("kind") or ""))
        if cell_key is None:
            unresolved.append({"target": target, "reason": reason, "next": HYBRID_FALLBACK})
            continue
        cell = cells.get(cell_key)
        if cell is None:
            unresolved.append({"target": target, "reason": "target_not_found"})
            continue
        live_map[target] = {
            "target": target,
            "cell": cell_key,
            "table": cell.table,
            "row": cell.row,
            "col": cell.col,
            "value": str(item.get("value") or ""),
            "expected_text": str(item.get("expected_text") or ""),
        }
    if unresolved:
        return {**base, "state": "live_targets_unresolved", "unresolved": unresolved}

    # file-side resolution + expected_text contrast (single source of truth)
    file_preview = preview_addressed_edits(path, edits)
    if not file_preview.get("ok"):
        return {
            **base,
            "state": str(file_preview.get("state") or "live_plan_failed"),
            "unresolved": list(file_preview.get("unresolved") or []),
            "counts": dict(file_preview.get("counts") or {}),
        }
    targets: List[dict] = []
    for entry in file_preview.get("edits") or []:
        planned = live_map[str(entry.get("target"))]
        cell = cells[planned["cell"]]
        if str(entry.get("kind")) == "paragraph" and str(entry.get("before_text")) != cell.text:
            # the cell holds more than this one paragraph; a whole-cell replace would destroy the rest
            unresolved.append({"target": planned["target"], "reason": "multi_paragraph_cell_unsupported", "next": HYBRID_FALLBACK})
            continue
        targets.append(planned)
    if unresolved:
        return {**base, "state": "live_targets_unresolved", "unresolved": unresolved}
    return {
        **base,
        "ok": True,
        "state": "planned",
        "targets": targets,
        "counts": {"requested": len(edits), "planned": len(targets)},
        "source_sha256": str(file_preview.get("source_sha256") or ""),
    }


def _recovery(applied_count: int) -> Dict:
    return {
        "undo_actions_per_cell": 2,
        "instruction": (
            f"{applied_count} cell(s) were already replaced in the open window. To roll back, "
            f"press Ctrl-Z up to {2 * applied_count} times (each cell = delete + insert) in the "
            "Hangul window, or close WITHOUT saving and reopen the original file."
        ),
    }


def _select_cell_content(hwp) -> None:
    hwp.HAction.Run("Cancel")  # drop any block selection -> caret in cell
    hwp.HAction.Run("MoveListBegin")
    hwp.HAction.Run("MoveSelListEnd")


def _read_cell_text(hwp, table: int, row: int, col: int) -> str | None:
    if not hwp.get_into_nth_table(table - 1):
        return None
    if not hwp.goto_addr(row + 1, col + 1, select_cell=False):
        return None
    _select_cell_content(hwp)
    text = str(hwp.get_selected_text() or "")
    hwp.HAction.Run("Cancel")
    return text


def apply_live_addressed(path: str | Path, targets: List[dict], *, visible: bool = True) -> Dict:
    """Apply planned targets to the OPEN window (COM). Never opens/saves/closes."""
    Hwp, err = load_pyhwpx()
    if err:
        return err
    started = time.monotonic()
    cold_start = not list_rot_instances()
    try:
        hwp = Hwp(new=False, visible=visible, on_quit=False)
    except Exception as exc:
        return {"available": True, "connected": False, "state": "connect_failed", "error": str(exc)}
    previous_mode = suppress_dialogs(hwp)
    applied: List[dict] = []
    skipped: List[dict] = []
    remaining: List[dict] = []
    aborted_error: str | None = None
    try:
        active, _opened, error = _ensure_active_document(hwp, path, open_if_needed=False)
        if error is not None:
            return error
        for index, t in enumerate(targets):
            try:
                if not hwp.get_into_nth_table(t["table"] - 1):
                    skipped.append({"target": t["target"], "reason": "table_not_found_live"})
                    continue
                if not hwp.goto_addr(t["row"] + 1, t["col"] + 1, select_cell=False):
                    skipped.append({"target": t["target"], "reason": "cell_unreachable"})
                    continue
                _select_cell_content(hwp)
                current = str(hwp.get_selected_text() or "")
                hwp.HAction.Run("Cancel")
                if current != t["expected_text"]:
                    skipped.append({
                        "target": t["target"],
                        "reason": "expected_text_mismatch",
                        "expected_text": t["expected_text"],
                        "actual_text": current,
                    })
                    continue
                # re-anchor + re-select before the destructive delete:
                # get_selected_text drops the selection on real hardware
                # (desktop capture 2026-07-15), so deleting right after the
                # read appends instead of replacing.
                if not hwp.goto_addr(t["row"] + 1, t["col"] + 1, select_cell=False):
                    skipped.append({"target": t["target"], "reason": "cell_unreachable"})
                    continue
                _select_cell_content(hwp)
                hwp.HAction.Run("Delete")
                for i, line in enumerate(str(t["value"]).split("\n")):
                    if i:
                        hwp.HAction.Run("BreakPara")
                    if line:
                        hwp.insert_text(line)
                applied.append({"target": t["target"], "value": t["value"]})
            except Exception as exc:
                skipped.append({"target": t["target"], "reason": f"live_error: {exc}"})
                remaining = [dict(r) for r in targets[index + 1 :]]
                aborted_error = str(exc)
                break
    finally:
        restore_dialogs(hwp, previous_mode)
    # fresh read-back over a NEW COM connection (never trusts the writer object)
    readback = {"verified": False, "failed": [], "checked": 0}
    if applied:
        try:
            fresh = Hwp(new=False, visible=visible, on_quit=False)
            fresh_mode = suppress_dialogs(fresh)
            try:
                by_target = {t["target"]: t for t in targets}
                failed = []
                for entry in applied:
                    t = by_target[entry["target"]]
                    text = _read_cell_text(fresh, t["table"], t["row"], t["col"])
                    if text != entry["value"]:
                        failed.append({"target": entry["target"], "expected": entry["value"], "actual": text})
                readback = {"verified": not failed, "failed": failed, "checked": len(applied)}
            finally:
                restore_dialogs(fresh, fresh_mode)
        except Exception as exc:
            readback = {"verified": False, "failed": [], "checked": 0, "error": str(exc)}
    fully_applied = len(applied) == len(targets) and not skipped and not remaining
    ok = fully_applied and (readback["verified"] or not applied)
    out = {
        "available": True,
        "connected": True,
        "ok": ok,
        "state": "applied_live_addressed" if ok else "live_addressed_partial",
        "active_document": active,
        "applied": applied,
        "skipped": skipped,
        "remaining": remaining,
        "counts": {"requested": len(targets), "applied": len(applied), "skipped": len(skipped), "remaining": len(remaining)},
        "readback": readback,
        "cold_start": cold_start,
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    if aborted_error:
        out["error"] = aborted_error
    if not ok:
        out["recovery"] = _recovery(len(applied))
        out["next"] = HYBRID_FALLBACK
    return out


__all__ = [
    "HYBRID_FALLBACK",
    "apply_live_addressed",
    "live_addressed_enabled",
    "plan_live_addressed_edits",
]

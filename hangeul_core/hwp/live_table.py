"""Live (COM) table-structure ops for the open Hangul window (S5).

Offline row delete is unsafe — it needs cellAddr/rowCnt/merge recompute that no
library covers — so ``delete_row`` is live-only: Hangul's ``TableSubtractRow``
recomputes merges for us. Planning stays PURE (no COM); application drives the
open window and never opens, saves, or closes the document.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from hangeul_core.analyze import analyze
from hangeul_core.hwp.com import load_pyhwpx, restore_dialogs, suppress_dialogs
from hangeul_core.hwp.live_attach import _ensure_active_document

_ROW_TARGET = re.compile(r"^t(?P<table>\d+)\.r(?P<row>\d+)$")


def _apply_live_bold(hwp, table: int, row: int, col: int, bold: bool) -> None:
    """Bold/unbold the whole cell content over COM (live parity with the file path).

    Re-anchors on the cell, selects its content, and applies the CharShape weight
    deterministically via pyhwpx ``set_font`` (``GetDefault("CharShape") ->
    pset.Bold -> Execute``).
    """
    if not hwp.get_into_nth_table(table - 1):
        return
    if not hwp.goto_addr(row + 1, col + 1, select_cell=False):
        return
    hwp.HAction.Run("Cancel")
    hwp.HAction.Run("MoveListBegin")
    hwp.HAction.Run("MoveSelListEnd")
    hwp.set_font(Bold=1 if bold else 0)
    hwp.HAction.Run("Cancel")


def plan_live_row_deletes(path: str | Path, edits: List[dict]) -> Dict:
    """Resolve ``delete_row`` edits (target ``tN.rN``) to live rows (PURE — no COM).

    Fails closed on nested tables (D7) and unknown table/row.
    """
    from hangeul_core.hwp.live_addressed import HYBRID_FALLBACK  # lazy: avoid import cycle

    result = analyze(path)
    cells = list(result.all_cells())
    base = {"available": True, "ok": False, "route": "live_delete_row"}
    if any(c.has_nested_table for c in cells):
        return {**base, "state": "nested_tables_unsupported", "next": HYBRID_FALLBACK}
    by_table_rows: Dict[int, set] = {}
    for c in cells:
        by_table_rows.setdefault(c.table, set()).add(c.row)
    unresolved: List[dict] = []
    targets: List[dict] = []
    seen: set = set()
    for item in edits:
        target = str(item.get("target") or "")
        if str(item.get("operation") or "") != "delete_row":
            unresolved.append({"target": target, "reason": "not_a_delete_row"})
            continue
        m = _ROW_TARGET.match(target)
        if m is None:
            unresolved.append({"target": target, "reason": "bad_row_target", "hint": "use tN.rN"})
            continue
        table, row = int(m.group("table")), int(m.group("row"))
        if row not in by_table_rows.get(table, set()):
            unresolved.append({"target": target, "reason": "target_not_found"})
            continue
        if (table, row) in seen:
            unresolved.append({"target": target, "reason": "duplicate_row"})
            continue
        seen.add((table, row))
        targets.append({"target": target, "table": table, "row": row})
    if unresolved:
        return {**base, "state": "live_targets_unresolved", "unresolved": unresolved}
    # Delete bottom-up so earlier deletions never shift a later row index.
    targets.sort(key=lambda t: (t["table"], -t["row"]))
    return {**base, "ok": True, "state": "planned", "targets": targets, "counts": {"requested": len(edits), "planned": len(targets)}}


def apply_live_row_deletes(path: str | Path, targets: List[dict], *, visible: bool = True) -> Dict:
    """Delete table rows in the OPEN window via COM ``TableSubtractRow``.

    Never opens/saves/closes. Targets must already be ordered bottom-up.
    """
    Hwp, err = load_pyhwpx()
    if err:
        return err
    try:
        hwp = Hwp(new=False, visible=visible, on_quit=False)
    except Exception as exc:
        return {"available": True, "connected": False, "state": "connect_failed", "error": str(exc)}
    previous_mode = suppress_dialogs(hwp)
    applied: List[dict] = []
    skipped: List[dict] = []
    try:
        active, _opened, error = _ensure_active_document(hwp, path, open_if_needed=False)
        if error is not None:
            return error
        for t in targets:
            if not hwp.get_into_nth_table(t["table"] - 1):
                skipped.append({"target": t["target"], "reason": "table_not_found_live"})
                continue
            if not hwp.goto_addr(t["row"] + 1, 1, select_cell=False):
                skipped.append({"target": t["target"], "reason": "row_unreachable"})
                continue
            hwp.HAction.Run("TableSubtractRow")
            applied.append({"target": t["target"]})
    finally:
        restore_dialogs(hwp, previous_mode)
    ok = bool(applied) and not skipped
    return {
        "available": True,
        "connected": True,
        "ok": ok,
        "state": "applied_live_row_delete" if ok else "live_row_delete_partial",
        "active_document": active,
        "applied": applied,
        "skipped": skipped,
    }

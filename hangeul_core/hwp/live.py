"""Live cell-fill of the *currently open* Hangul document — no 누름틀 required.

The existing COM path (``apply_to_open_hwp``) only fills **named fields (누름틀)**
via ``PutFieldText``. Cell-based forms (label:value tables, e.g. 강사카드) have no
named fields, so that path returns ``needs_field_registration``. This module fills
those cells *live* by navigating the open document's table cells and inserting text
— exactly the "just fill what I have open right now" workflow.

Two layers, deliberately separated:

* :func:`resolve_cell_targets` — PURE (no COM): maps each provided value key to a
  table-cell address using our own ``analyze``/``understand``. Fully unit-testable.
* :func:`apply_cells_to_open` — drives the open Hangul window via the optional
  ``pyhwpx`` substrate (extra ``live``), attaching to the running instance through
  the Running Object Table and navigating with ``get_into_nth_table`` + ``goto_addr``
  + ``insert_text``. COM only works from the user's *interactive* session, so this
  is validated in the client (e.g. Claude Desktop), not in headless CI.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from hangeul_core.analyze import analyze
from hangeul_core.schema import label_key
from hangeul_core.understand import understand


def live_available() -> bool:
    """True only where a live COM fill could actually work.

    Requires Windows and a *fully importable* pyhwpx (its transitive deps like
    numpy must be present) — a bare ``find_spec`` can be True while ``import
    pyhwpx`` fails, so we attempt the real guarded import.
    """
    if sys.platform != "win32" or importlib.util.find_spec("pyhwpx") is None:
        return False
    try:
        importlib.import_module("pyhwpx")  # transitive deps (numpy) must import too
        return True
    except Exception:
        return False


def resolve_cell_targets(
    path: str | Path, values: Dict[str, str]
) -> Tuple[List[dict], List[dict]]:
    """Map value keys to table-cell addresses (PURE — no COM).

    Returns ``(targets, skipped)``. Each target: ``{table, row, col, value, label,
    field_id}`` (table = 1-based global table index; row/col = 0-based cellAddr).
    Only cell-addressable label→value fields (empty_cell) are resolved here.
    """
    result = analyze(path)
    cells = {c.field_id: c for c in result.all_cells()}
    fields = understand(path).fields
    by_id = {f.field_id: f for f in fields}
    by_label: Dict[str, object] = {}
    for f in fields:
        by_label.setdefault(label_key(f.label), f)

    targets: List[dict] = []
    skipped: List[dict] = []
    for key, value in values.items():
        fld = by_id.get(key) or by_label.get(label_key(key))
        if fld is None:
            skipped.append({"key": key, "reason": "no matching cell field"})
            continue
        cell = cells.get(fld.field_id.split("#")[0])
        if cell is None:
            skipped.append({"key": key, "reason": "target cell not found"})
            continue
        targets.append(
            {
                "table": cell.table,
                "row": cell.row,
                "col": cell.col,
                "value": value,
                "label": fld.label,
                "field_id": cell.field_id,
            }
        )
    return targets, skipped


def apply_cells_to_open(
    path: str | Path,
    values: Dict[str, str],
    *,
    visible: bool = True,
    clear: bool = True,
) -> Dict:
    """Fill the currently OPEN Hangul document's cells live (via pyhwpx COM).

    Attaches to the running Hangul instance (does not close it). For each resolved
    target, enters the table, moves to the cell address, optionally clears it, and
    inserts the value. Requires the optional ``pyhwpx`` substrate on Windows with
    Hangul running. Returns ``{available, applied, skipped, count}``.
    """
    if sys.platform != "win32":
        return {"available": False, "error": "live COM fill needs Windows + Hangul"}
    try:
        from pyhwpx import Hwp  # optional; pulls pywin32/numpy/pandas
    except Exception as exc:  # ImportError or dependency error
        return {"available": False, "error": f"pyhwpx not installed (extra 'live'): {exc}"}

    targets, skipped = resolve_cell_targets(path, values)

    try:
        hwp = Hwp(new=False, visible=visible, on_quit=False)  # attach to running
    except Exception as exc:
        return {"available": True, "connected": False, "error": str(exc)}

    applied: List[dict] = []
    for t in targets:
        try:
            if not hwp.get_into_nth_table(t["table"] - 1):  # 0-based ctrl index
                skipped.append({"key": t["label"], "reason": "table not found live"})
                continue
            if not hwp.goto_addr(t["row"] + 1, t["col"] + 1, select_cell=True):  # 1-based
                skipped.append({"key": t["label"], "reason": "cell address not reachable"})
                continue
            if clear:
                hwp.HAction.Run("Delete")  # clear selected cell content
            hwp.insert_text(t["value"])
            applied.append({"label": t["label"], "field_id": t["field_id"], "value": t["value"]})
        except Exception as exc:  # pragma: no cover - live COM only
            skipped.append({"key": t["label"], "reason": f"live error: {exc}"})

    return {"available": True, "connected": True, "applied": applied, "skipped": skipped, "count": len(applied)}

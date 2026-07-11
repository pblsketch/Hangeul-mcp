"""Live cell-fill of the *currently open* Hangul document — no 누름틀 required.

Layered deliberately: resolve/preview stay PURE (unit-testable, no COM), while
apply drives the open window via the optional ``pyhwpx`` substrate (extra
``live``), attaching through the COM Running Object Table (validated on the
desktop, not in headless CI). Hand-opened windows never register there — open
documents via :func:`open_in_hwp` instead. empty_cell labels are filled as
direct value inserts; inline blanks ride the file-fill mirror in
:mod:`hangeul_core.hwp.live_inline`.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

from hangeul_core.analyze import analyze
from hangeul_core.hwp.com import (
    list_rot_instances,
    load_pyhwpx,
    restore_dialogs,
    same_doc as _same_doc,
    suppress_dialogs,
)
from hangeul_core.body import resolve_body_targets
from hangeul_core.hwp.live_body import apply_body_targets
from hangeul_core.hwp.live_inline import apply_text_targets, compute_cell_text_replacements
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


def open_in_hwp(path: str | Path, *, visible: bool = True) -> Dict:
    """Open *path* in a CONTROLLABLE (automation-created) Hangul window.

    Hand-opened windows never register in the COM ROT (observed 2026-07-10,
    PENDING_DESKTOP_LIVE_QA.md), so the reliable live workflow is: open THROUGH
    the automation instance here, then fill that window with the apply tools.
    Leaves the window open; saves and closes nothing.
    """
    p = Path(path)
    if not p.exists():
        return {"available": True, "ok": False, "error": f"file not found: {p}"}
    Hwp, err = load_pyhwpx()
    if err:
        return err
    started = time.monotonic()
    cold_start = not list_rot_instances()  # no instance -> this call launches Hangul
    try:
        hwp = Hwp(new=False, visible=visible, on_quit=False)
    except Exception as exc:
        return {"available": True, "connected": False, "error": str(exc)}
    previous_mode = suppress_dialogs(hwp)
    try:
        opened = bool(hwp.open(str(p)))
        active = str(hwp.XHwpDocuments.Active_XHwpDocument.FullName or "")
    except Exception as exc:
        return {
            "available": True,
            "connected": True,
            "opened": False,
            "cold_start": cold_start,
            "error": str(exc),
        }
    finally:
        restore_dialogs(hwp, previous_mode)
    return {
        "available": True,
        "connected": True,
        "ok": opened and _same_doc(active, p),
        "opened": opened,
        "active_document": active,
        "cold_start": cold_start,
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }


def _resolve_all_targets(path: str | Path, values: Dict[str, str]):
    """Resolve to ``(direct, text, body, skipped)``: empty_cell → direct values,
    body field_ids (``b{n}``) → body paragraphs, the rest → file-fill mirror."""
    targets, unresolved = resolve_cell_targets(path, values)
    leftover = {u["key"]: values[u["key"]] for u in unresolved if u["key"] in values}
    if not leftover:
        return targets, [], [], unresolved
    body_targets = resolve_body_targets(path, leftover)  # body field_ids (b{n})
    body_ids = {t["field_id"] for t in body_targets}
    inline_leftover = {k: v for k, v in leftover.items() if k not in body_ids}
    text_targets, skipped = (
        compute_cell_text_replacements(path, inline_leftover) if inline_leftover else ([], [])
    )
    return targets, text_targets, body_targets, skipped


def preview_cells_to_open(path: str | Path, values: Dict[str, str]) -> Dict:
    targets, text_targets, body_targets, skipped = _resolve_all_targets(path, values)
    return {
        "available": True,
        "live_available": live_available(),
        "targets": targets,
        "text_targets": text_targets,
        "body_targets": body_targets,
        "skipped": skipped,
        "count": len(targets) + len(text_targets) + len(body_targets),
        "apply_tool": "apply_cells_to_open_hwp",
    }


def apply_cells_to_open(
    path: str | Path,
    values: Dict[str, str],
    *,
    visible: bool = True,
    clear: bool = True,
    open_if_needed: bool = True,
) -> Dict:
    """Fill the OPEN (automation-controlled) Hangul document's cells live.

    Verifies the attached instance's ACTIVE document is *path* first (else a
    different active doc would be corrupted); on mismatch opens *path* when
    ``open_if_needed`` (default), else refuses — then edits the cell targets.
    """
    Hwp, err = load_pyhwpx()
    if err:
        return err

    targets, text_targets, body_targets, skipped = _resolve_all_targets(path, values)

    started = time.monotonic()
    cold_start = not list_rot_instances()  # no instance -> this call launches Hangul
    try:
        hwp = Hwp(new=False, visible=visible, on_quit=False)  # attach to running
    except Exception as exc:
        return {"available": True, "connected": False, "error": str(exc)}
    previous_mode = suppress_dialogs(hwp)
    try:
        return _apply_cells_connected(
            hwp, path, targets, text_targets, body_targets, skipped, clear=clear,
            open_if_needed=open_if_needed, cold_start=cold_start, started=started,
        )
    finally:
        restore_dialogs(hwp, previous_mode)


def _apply_cells_connected(
    hwp,
    path: str | Path,
    targets: List[dict],
    text_targets: List[dict],
    body_targets: List[dict],
    skipped: List[dict],
    *,
    clear: bool,
    open_if_needed: bool,
    cold_start: bool,
    started: float,
) -> Dict:
    try:
        active = str(hwp.XHwpDocuments.Active_XHwpDocument.FullName or "")
    except Exception:
        active = ""
    opened_here = False
    if not _same_doc(active, path):
        if not open_if_needed:
            return {
                "available": True,
                "connected": True,
                "ok": False,
                "active_document": active,
                "error": (
                    "attached instance's active document is not the requested file; "
                    "pass open_if_needed=true or call open_in_hwp first "
                    "(hand-opened windows are not attachable)"
                ),
            }
        try:
            opened_ok = bool(hwp.open(str(Path(path))))
            active = str(hwp.XHwpDocuments.Active_XHwpDocument.FullName or "")
        except Exception as exc:
            return {"available": True, "connected": True, "ok": False, "error": str(exc)}
        # open() can return True while the active document did NOT switch — editing
        # then would corrupt whatever stayed active. Re-verify before any edit.
        if not opened_ok or not _same_doc(active, path):
            return {
                "available": True,
                "connected": True,
                "ok": False,
                "active_document": active,
                "error": f"could not make {path} the active document in the automation instance",
            }
        opened_here = True

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

    apply_text_targets(hwp, text_targets, applied, skipped)
    apply_body_targets(hwp, path, body_targets, applied, skipped)

    return {
        "available": True,
        "connected": True,
        "opened": opened_here,
        "applied": applied,
        "skipped": skipped,
        "count": len(applied),
        "cold_start": cold_start,
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }

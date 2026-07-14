from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Tuple

from hangeul_core.hwp.com import (
    active_attached_document_path,
    find_attached_exact_path_documents,
    list_rot_instances,
    load_pyhwpx,
    restore_dialogs,
    same_doc as _same_doc,
    suppress_dialogs,
)


def _active_document_path(hwp) -> str:
    return active_attached_document_path(hwp)


def _has_exact_path(hwp, path: str | Path) -> bool:
    return bool(find_attached_exact_path_documents(hwp, path))


def _has_active_exact_path(hwp, path: str | Path) -> bool:
    return any(doc.get("is_active") for doc in find_attached_exact_path_documents(hwp, path))


def _open_exact_path(hwp, path: str | Path) -> Tuple[bool, str]:
    opened = bool(hwp.open(str(Path(path))))
    return opened, _active_document_path(hwp)


def _ensure_active_document(hwp, path: str | Path, *, open_if_needed: bool) -> Tuple[str, bool, Dict | None]:
    active = _active_document_path(hwp)
    if _same_doc(active, path) and _has_active_exact_path(hwp, path):
        return active, False, None
    if _same_doc(active, path) and not _has_exact_path(hwp, path):
        return active, False, {
            "available": True,
            "connected": True,
            "ok": False,
            "state": "path_unverified",
            "attached_existing": False,
            "active_document": active,
            "error": (
                "generic live attach reached a same-path active document, but the automation-visible "
                "XHwpDocuments list did not confirm that exact path; call open_in_hwp first"
            ),
        }
    if not open_if_needed:
        return active, False, {
            "available": True,
            "connected": True,
            "ok": False,
            "state": "path_mismatch",
            "attached_existing": False,
            "active_document": active,
            "error": (
                "attached instance's active document is not the requested exact path; "
                "pass open_if_needed=true or call open_in_hwp first"
            ),
        }
    try:
        opened_ok, active = _open_exact_path(hwp, path)
    except Exception as exc:
        return active, False, {
            "available": True,
            "connected": True,
            "ok": False,
            "state": "open_failed",
            "attached_existing": False,
            "error": str(exc),
        }
    if opened_ok and _same_doc(active, path) and _has_active_exact_path(hwp, path):
        return active, True, None
    return active, False, {
        "available": True,
        "connected": True,
        "ok": False,
        "state": "open_failed",
        "attached_existing": False,
        "active_document": active,
        "error": f"could not make {path} the active document in the automation instance",
    }


def open_as_new_tab(path: str | Path, *, visible: bool = True) -> Dict:
    """Open *path* as a NEW TAB in the automation window, preserving existing tabs.

    Real-device capture (2026-07-14) showed plain ``hwp.Open`` NAVIGATES the
    active tab away from its current document instead of adding one, so the
    complete_and_load contract ("the original stays open") requires adding a
    tab first. If the tab cannot be added (verified by document count), this
    FAILS CLOSED with ``new_tab_unavailable`` instead of navigating — a plain
    open here could close/replace the caller's active document.
    Saves and closes nothing.
    """
    p = Path(path)
    if not p.exists():
        return {
            "available": True,
            "ok": False,
            "state": "not_found",
            "requested_path": str(p),
            "error": f"file not found: {p}",
        }
    Hwp, err = load_pyhwpx()
    if err:
        return err
    started = time.monotonic()
    cold_start = not list_rot_instances()
    try:
        hwp = Hwp(new=False, visible=visible, on_quit=False)
    except Exception as exc:
        return {
            "available": True,
            "connected": False,
            "state": "connect_failed",
            "requested_path": str(p),
            "error": str(exc),
        }
    previous_mode = suppress_dialogs(hwp)
    added_tab = False
    try:
        if _same_doc(_active_document_path(hwp), p) and _has_active_exact_path(hwp, p):
            return {
                "available": True,
                "connected": True,
                "ok": True,
                "state": "attached_existing",
                "attached_existing": True,
                "opened": False,
                "added_tab": False,
                "requested_path": str(p),
                "active_document": _active_document_path(hwp),
                "cold_start": cold_start,
                "elapsed_seconds": round(time.monotonic() - started, 1),
            }
        try:
            count_before = int(hwp.XHwpDocuments.Count)
            hwp.XHwpDocuments.Add(1)  # 1 = new tab in the current window; becomes active
            added_tab = int(hwp.XHwpDocuments.Count) == count_before + 1
        except Exception:
            added_tab = False
        if not added_tab:
            # fail closed: a plain Open would navigate (and effectively close)
            # the caller's active document instead of adding a tab
            return {
                "available": True,
                "connected": True,
                "ok": False,
                "state": "new_tab_unavailable",
                "added_tab": False,
                "requested_path": str(p),
                "cold_start": cold_start,
                "error": (
                    "could not add a new tab (XHwpDocuments.Add); refusing plain open "
                    "because it would navigate the active document — open the file manually"
                ),
            }
        try:
            opened, active = _open_exact_path(hwp, p)
        except Exception as exc:
            return {
                "available": True,
                "connected": True,
                "ok": False,
                "state": "open_failed",
                "added_tab": added_tab,
                "requested_path": str(p),
                "cold_start": cold_start,
                "error": str(exc),
            }
    finally:
        restore_dialogs(hwp, previous_mode)
    ok = opened and _same_doc(active, p) and _has_active_exact_path(hwp, p)
    state = "opened_new_tab" if ok else "open_failed"
    return {
        "available": True,
        "connected": True,
        "ok": ok,
        "state": state,
        "added_tab": added_tab,
        "opened": opened,
        "requested_path": str(p),
        "active_document": active,
        "cold_start": cold_start,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        **({"error": f"could not make {p} the active document in the automation instance"} if not ok else {}),
    }


def open_in_hwp(path: str | Path, *, visible: bool = True) -> Dict:
    """Open *path* in a CONTROLLABLE Hangul window.

    Safe live attach is exact-path based: attach to the automation-visible
    instance, inspect its open documents, and reuse the requested file only on an
    exact normalized path match. Otherwise this opens *path* in that automation
    window. Leaves the window open; saves and closes nothing.
    """
    p = Path(path)
    if not p.exists():
        return {
            "available": True,
            "ok": False,
            "state": "not_found",
            "requested_path": str(p),
            "error": f"file not found: {p}",
        }
    Hwp, err = load_pyhwpx()
    if err:
        return err
    started = time.monotonic()
    cold_start = not list_rot_instances()
    try:
        hwp = Hwp(new=False, visible=visible, on_quit=False)
    except Exception as exc:
        return {
            "available": True,
            "connected": False,
            "state": "connect_failed",
            "requested_path": str(p),
            "error": str(exc),
        }
    previous_mode = suppress_dialogs(hwp)
    try:
        active = _active_document_path(hwp)
        if _same_doc(active, p) and _has_active_exact_path(hwp, p):
            return {
                "available": True,
                "connected": True,
                "ok": True,
                "state": "attached_existing",
                "attached_existing": True,
                "opened": False,
                "requested_path": str(p),
                "active_document": active,
                "resolution": "attached_existing_exact_path",
                "cold_start": cold_start,
                "elapsed_seconds": round(time.monotonic() - started, 1),
            }
        try:
            opened, active = _open_exact_path(hwp, p)
        except Exception as exc:
            return {
                "available": True,
                "connected": True,
                "ok": False,
                "state": "open_failed",
                "attached_existing": False,
                "opened": False,
                "requested_path": str(p),
                "cold_start": cold_start,
                "error": str(exc),
            }
    finally:
        restore_dialogs(hwp, previous_mode)
    ok = opened and _same_doc(active, p) and _has_active_exact_path(hwp, p)
    return {
        "available": True,
        "connected": True,
        "ok": ok,
        "state": "opened_new" if ok else "open_failed",
        "attached_existing": False,
        "opened": opened,
        "requested_path": str(p),
        "active_document": active,
        "resolution": "opened_in_automation_window" if ok else "active_document_mismatch",
        "cold_start": cold_start,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        **({"error": f"could not make {p} the active document in the automation instance"} if not ok else {}),
    }

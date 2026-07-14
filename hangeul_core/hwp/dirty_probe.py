"""COM dirty-probe for Track B replace+reload prerequisites (ADR D19).

Answers ONE question over COM: does the automation-visible document at an
exact path carry unsaved edits (``XHwpDocument.Modified``)? A reload reads the
DISK, so reloading a dirty window silently discards the user's typing — the
replace+reload route (NOT shipped yet) must refuse whenever this probe does
not return a provably-clean verdict.

Contract:
- This is a COM call. It must NEVER be wired into resolve/preview (those stay
  PURE per the live.py module contract); the only sanctioned call site is the
  step immediately before a consented replace+reload apply.
- Fail-closed reading: callers must treat every state other than
  ``{"state": "probed", "dirty": False}`` as dirty — including
  ``document_not_attached``, ``connect_failed`` and probe errors.
- Read-only: probing never writes, saves, closes, or changes the active tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from hangeul_core.hwp.com import load_pyhwpx, normalize_live_path


def probe_document_dirty(path: str | Path, *, visible: bool = True) -> Dict:
    """Read the unsaved-changes flag of the exact-path document, fail-closed."""
    requested = normalize_live_path(str(path))
    Hwp, err = load_pyhwpx()
    if err:
        return {**err, "dirty": None}
    try:
        hwp = Hwp(new=False, visible=visible, on_quit=False)
    except Exception as exc:
        return {
            "available": True,
            "connected": False,
            "ok": False,
            "state": "connect_failed",
            "dirty": None,
            "error": str(exc),
        }
    matches = []
    try:
        count = int(hwp.XHwpDocuments.Count)
        for index in range(count):
            document = hwp.XHwpDocuments.Item(index)
            full_name = str(getattr(document, "FullName", "") or "")
            if normalize_live_path(full_name) == requested:
                matches.append(int(getattr(document, "Modified", 1) or 0))
    except Exception as exc:
        return {
            "available": True,
            "connected": True,
            "ok": False,
            "state": "probe_error",
            "dirty": None,
            "error": str(exc),
        }
    if not matches:
        return {
            "available": True,
            "connected": True,
            "ok": False,
            "state": "document_not_attached",
            "dirty": None,
        }
    # same path in several slots: ANY dirty slot makes the document dirty
    dirty = any(flag != 0 for flag in matches)
    return {
        "available": True,
        "connected": True,
        "ok": True,
        "state": "probed",
        "dirty": dirty,
        "modified_flags": matches,
    }


__all__ = ["probe_document_dirty"]

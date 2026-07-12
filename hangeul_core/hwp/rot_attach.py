from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from hangeul_core.hwp.com import (
    HwpBridge,
    find_attached_exact_path_documents,
    find_rot_exact_path_candidates,
    inspect_attached_documents,
    list_rot_instances,
    normalize_field_values,
    restore_dialogs,
    suppress_dialogs,
)



def _attach_existing_moniker(moniker: str, *, visible: bool) -> HwpBridge:
    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    context = pythoncom.CreateBindCtx(0)
    rot = pythoncom.GetRunningObjectTable()
    for running in rot.EnumRunning():
        try:
            name = running.GetDisplayName(context, running)
        except Exception:
            continue
        if name != moniker:
            continue
        obj = rot.GetObject(running)
        hwp = win32.Dispatch(obj.QueryInterface(pythoncom.IID_IDispatch))
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        try:
            hwp.XHwpWindows.Item(0).Visible = visible
        except Exception:
            pass
        bridge = HwpBridge()
        bridge._hwp = hwp  # type: ignore[attr-defined]
        return bridge
    raise RuntimeError(f"ROT moniker not found: {moniker}")

def find_broker_exact_path_candidates(
    path: str | Path, instances: List[dict] | None = None
) -> List[dict]:
    return [dict(item) for item in find_rot_exact_path_candidates(path, instances)]


def pick_broker_exact_path_candidate(
    path: str | Path, instances: List[dict] | None = None
) -> dict | None:
    candidates = find_broker_exact_path_candidates(path, instances)
    return candidates[0] if len(candidates) == 1 else None


def revalidate_broker_exact_path_candidate(
    path: str | Path,
    candidate: Dict[str, Any],
    instances: List[dict] | None = None,
) -> dict | None:
    requested_moniker = str(candidate.get("moniker") or "")
    requested_slot = candidate.get("slot")
    for matched in find_broker_exact_path_candidates(path, instances):
        if str(matched.get("moniker") or "") != requested_moniker:
            continue
        if matched.get("slot") != requested_slot:
            continue
        return matched
    return None


def _resolve_target_bridge(path: Path, *, visible: bool) -> Tuple[HwpBridge | None, List[dict], Dict[str, Any] | None]:
    instances = list_rot_instances()
    candidates = find_rot_exact_path_candidates(path, instances)
    if len(candidates) > 1:
        return None, candidates, {
            "available": True,
            "connected": False,
            "ok": False,
            "state": "selection_required",
            "requested_path": str(path),
            "attach_candidates": candidates,
            "error": "exact path matches multiple automation brokers; refuse to guess the live target",
        }
    if not candidates and len(instances) > 1:
        return None, candidates, {
            "available": True,
            "connected": False,
            "ok": False,
            "state": "selection_required",
            "requested_path": str(path),
            "attach_candidates": [],
            "error": "multiple automation brokers are visible and none already proves the requested path",
        }
    try:
        if candidates:
            bridge = _attach_existing_moniker(str(candidates[0].get("moniker") or ""), visible=visible)
        else:
            bridge = HwpBridge().connect(visible=visible)
    except Exception as exc:
        return None, candidates, {
            "available": True,
            "connected": False,
            "ok": False,
            "state": "connect_failed",
            "requested_path": str(path),
            "attach_candidates": candidates,
            "error": str(exc),
        }
    return bridge, candidates, None


def _activate_exact_path(bridge: HwpBridge, path: Path, *, candidates: List[dict]) -> Tuple[bool, Dict[str, Any] | None]:
    docs = find_attached_exact_path_documents(bridge._hwp, path)  # type: ignore[attr-defined]
    active = next((doc for doc in docs if doc.get("is_active")), None)
    if active is not None:
        return False, None
    previous_mode = suppress_dialogs(bridge._hwp)  # type: ignore[attr-defined]
    try:
        opened = bool(bridge._hwp.open(str(path)))  # type: ignore[attr-defined]
    except Exception as exc:
        restore_dialogs(bridge._hwp, previous_mode)  # type: ignore[attr-defined]
        return False, {
            "available": True,
            "connected": True,
            "ok": False,
            "state": "open_failed",
            "requested_path": str(path),
            "attach_candidates": candidates,
            "error": str(exc),
        }
    finally:
        restore_dialogs(bridge._hwp, previous_mode)  # type: ignore[attr-defined]
    docs = find_attached_exact_path_documents(bridge._hwp, path)  # type: ignore[attr-defined]
    active = next((doc for doc in docs if doc.get("is_active")), None)
    if opened and active is not None:
        return True, None
    attached = inspect_attached_documents(bridge._hwp)  # type: ignore[attr-defined]
    active_path = next((doc.get("path") for doc in attached if doc.get("is_active")), "")
    return False, {
        "available": True,
        "connected": True,
        "ok": False,
        "state": "open_failed",
        "requested_path": str(path),
        "attach_candidates": candidates,
        "active_document": active_path,
        "error": f"could not make {path} the active document in the selected automation broker",
    }


def apply_named_fields_exact_path(
    path: str | Path,
    values: Dict[str, str],
    *,
    visible: bool = True,
) -> Dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {
            "available": True,
            "ok": False,
            "state": "not_found",
            "requested_path": str(target),
            "error": f"file not found: {target}",
        }
    if not HwpBridge.available():
        return {
            "available": False,
            "connected": False,
            "ok": False,
            "state": "unavailable",
            "requested_path": str(target),
            "error": "COM bridge needs Windows + pywin32 + Hangul",
        }
    started = time.monotonic()
    bridge, candidates, error = _resolve_target_bridge(target, visible=visible)
    if error is not None:
        return error
    assert bridge is not None
    docs = find_attached_exact_path_documents(bridge._hwp, target)  # type: ignore[attr-defined]
    was_active = any(doc.get("is_active") for doc in docs)
    opened, error = _activate_exact_path(bridge, target, candidates=candidates)
    if error is not None:
        return error
    exact_docs = find_attached_exact_path_documents(bridge._hwp, target)  # type: ignore[attr-defined]
    active_doc = next((doc for doc in exact_docs if doc.get("is_active")), None)
    if active_doc is None:
        return {
            "available": True,
            "connected": True,
            "ok": False,
            "state": "path_unverified",
            "requested_path": str(target),
            "attach_candidates": candidates,
            "error": "selected broker did not retain an active exact-path match for the requested document",
        }
    fields = bridge.get_field_list()
    if not fields:
        return {
            "available": True,
            "connected": True,
            "ok": False,
            "state": "needs_field_registration",
            "requested_path": str(target),
            "attach_candidates": candidates,
            "moniker": active_doc.get("moniker") or (candidates[0].get("moniker") if candidates else None),
            "active_document": active_doc.get("path"),
            "needs_field_registration": True,
            "note": "no named fields; use apply_cells_to_open_hwp for cell-based forms",
        }
    result = bridge.put_field_text(normalize_field_values(values))
    return {
        "available": True,
        "connected": True,
        "ok": True,
        "state": "attached_existing" if (was_active and not opened) else "opened_new",
        "requested_path": str(target),
        "attach_candidates": candidates,
        "active_document": active_doc.get("path"),
        "moniker": candidates[0].get("moniker") if candidates else None,
        "slot": active_doc.get("slot"),
        "attached_existing": bool(was_active and not opened),
        "opened": bool(opened),
        "field_count": len(fields),
        "elapsed_seconds": round(time.monotonic() - started, 1),
        **result,
    }


__all__ = [
    "apply_named_fields_exact_path",
    "find_broker_exact_path_candidates",
    "pick_broker_exact_path_candidate",
    "revalidate_broker_exact_path_candidate",
]

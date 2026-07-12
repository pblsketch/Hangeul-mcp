from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any, Dict, List

from hangeul_core.formfield import form_field_names
from hangeul_core.hwp import HwpBridge
from hangeul_core.hwp.com import list_rot_instances, normalize_live_path

from hangeul_core.hwp.current_document import (
    build_candidate_picker,
    candidate_format,
    candidate_saved,
    candidate_write_state,
    classify_live_write_blocker,
    inventory_digest,
    make_preview_digest,
    plan_preview_route,
    preview_state_from_resolution,
    refresh_candidate_state,
    summarize_resolution,
)
from hangeul_core.hwp.live import apply_cells_to_open, preview_cells_to_open
from hangeul_core.hwp.rot_attach import apply_named_fields_exact_path


_PREVIEW_TOKEN_TTL_SECONDS = 300
_CANDIDATE_CACHE: Dict[str, Dict[str, Any]] = {}
_PREVIEW_TOKENS: Dict[str, Dict[str, Any]] = {}


def _purge_preview_tokens(now: int | None = None) -> None:
    cutoff = int(time.time()) if now is None else now
    stale = [token for token, payload in _PREVIEW_TOKENS.items() if cutoff > int(payload.get("expires_at") or 0)]
    for token in stale:
        _PREVIEW_TOKENS.pop(token, None)



def _live_current_available() -> bool:
    return HwpBridge.available() or bool(list_rot_instances())



def _candidate_id(moniker: str, slot: Any, normalized_path: str) -> str:
    blob = f"{moniker}|{slot}|{normalized_path}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def _candidate_from_document(moniker: str, document: Dict[str, Any]) -> Dict[str, Any]:
    path = str(document.get("path") or "")
    normalized_path = str(document.get("normalized_path") or normalize_live_path(path))
    candidate = {
        "candidate_id": _candidate_id(moniker, document.get("slot"), normalized_path),
        "moniker": moniker,
        "slot": document.get("slot"),
        "path": path,
        "normalized_path": normalized_path,
        "format": candidate_format(path),
        "saved": bool(normalized_path),
        "is_active": bool(document.get("is_active")),
        "active_source": document.get("active_source"),
        "active_slot": document.get("active_slot"),
        "active_path_empty": bool(document.get("active_path_empty")),
        "active_identity_proven": bool(document.get("active_identity_proven")),
        "write_state": candidate_write_state(path),
    }
    candidate.update(build_candidate_picker(candidate))
    _CANDIDATE_CACHE[candidate["candidate_id"]] = dict(candidate)
    return candidate


def _list_candidates() -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for instance in list_rot_instances():
        moniker = str(instance.get("moniker") or "")
        for document in instance.get("documents") or []:
            candidates.append(_candidate_from_document(moniker, dict(document)))
    return candidates


def resolve_current_hwp_document() -> Dict[str, Any]:
    if not _live_current_available():
        return {"available": False, "ok": False, "state": "unavailable", "candidates": []}
    candidates = _list_candidates()
    resolution = summarize_resolution(candidates)
    resolution["available"] = True
    resolution["ok"] = resolution.get("state") in {"auto_selected", "selection_required", "no_open_documents"}
    resolution["candidates"] = candidates
    resolution["inventory_digest"] = inventory_digest(candidates)
    return resolution



def _select_candidate(resolution: Dict[str, Any], candidate_id: str | None) -> Dict[str, Any] | None:
    if candidate_id:
        for candidate in resolution.get("candidates") or []:
            if candidate.get("candidate_id") == candidate_id:
                return candidate
        return None
    return resolution.get("candidate")


def _named_values(values: Dict[str, str], keys: List[str]) -> Dict[str, str]:
    return {key: values[key] for key in keys if key in values}


def _preview_summary(route: str, named_keys: List[str], cell_preview: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "route": route,
        "named_field_keys": named_keys,
        "targets": list(cell_preview.get("targets") or []),
        "text_targets": list(cell_preview.get("text_targets") or []),
        "body_targets": list(cell_preview.get("body_targets") or []),
        "skipped": list(cell_preview.get("skipped") or []),
    }
    base["count"] = len(named_keys) + len(base["targets"]) + len(base["text_targets"]) + len(base["body_targets"])
    return base


def preview_current_hwp_document(
    values: Dict[str, str],
    candidate_id: str | None = None,
    mode: str = "auto",
) -> Dict[str, Any]:
    _purge_preview_tokens()
    resolution = resolve_current_hwp_document()

    blocked_state = preview_state_from_resolution(resolution)
    if resolution.get("state") == "unavailable":
        return {"available": False, "ok": False, "state": "unavailable", "candidates": []}

    if resolution.get("state") in {
        "no_open_documents",
        "current_document_unsaved",
        "current_document_unprovable",
        "current_document_unsupported",
    }:
        return {
            "available": True,
            "ok": False,
            "state": blocked_state,
            "selection_basis": resolution.get("selection_basis", "none"),
            "candidates": resolution.get("candidates") or [],
        }
    if resolution.get("state") == "selection_required" and not candidate_id:
        return {
            "available": True,
            "ok": False,
            "state": "selection_required",
            "selection_basis": "none",
            "candidates": resolution.get("candidates") or [],
        }
    candidate = _select_candidate(resolution, candidate_id)
    if candidate is None:
        return {
            "available": True,
            "ok": False,
            "state": "stale_candidate",
            "selection_basis": resolution.get("selection_basis", "none"),
            "candidates": resolution.get("candidates") or [],
        }
    if not candidate_saved(candidate):
        return {
            "available": True,
            "ok": False,
            "state": "current_document_unsaved",
            "candidate": candidate,
            "candidates": resolution.get("candidates") or [],
        }
    if candidate_format(candidate.get("path")) == "hwp":
        return {
            "available": True,
            "ok": False,
            "state": "preview_requires_hwpx",
            "candidate": candidate,
            "candidates": resolution.get("candidates") or [],
        }
    if candidate.get("write_state") == "read_only":
        return {
            "available": True,
            "ok": False,
            "state": "read_only",
            "candidate": candidate,
            "candidates": resolution.get("candidates") or [],
        }
    field_names = form_field_names(candidate["path"])
    cell_preview = preview_cells_to_open(candidate["path"], values)
    route_plan = plan_preview_route(values, field_names=field_names, cell_preview=cell_preview)
    if route_plan["route"] == "route_conflict":
        return {
            "available": True,
            "ok": False,
            "state": "route_conflict",
            "candidate": candidate,
            "candidates": resolution.get("candidates") or [],
            "conflict_keys": route_plan["overlap_keys"],
            "named_field_keys": route_plan["named_field_keys"],
            "cell_keys": route_plan["cell_keys"],
        }
    preview = _preview_summary(route_plan["route"], route_plan["named_field_keys"], cell_preview)
    issued_at = int(time.time())
    expires_at = issued_at + _PREVIEW_TOKEN_TTL_SECONDS
    token_payload = {
        "candidate_id": candidate["candidate_id"],
        "selection_basis": resolution.get("selection_basis", "none"),
        "route": route_plan["route"],
        "normalized_path": candidate.get("normalized_path"),
        "moniker": candidate.get("moniker"),
        "slot": candidate.get("slot"),
        "inventory_digest": resolution["inventory_digest"],
        "value_digest": hashlib.sha256(
            json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "preview_digest": make_preview_digest(route_plan["route"], preview),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "write_state": candidate.get("write_state"),
        "mode": mode,
        "values": dict(values),
        "named_field_keys": list(route_plan["named_field_keys"]),
        "cell_keys": list(route_plan["cell_keys"]),
    }
    token = secrets.token_urlsafe(18)
    _PREVIEW_TOKENS[token] = token_payload
    return {
        "available": True,
        "ok": True,
        "state": "preview_ready",
        "selection_basis": resolution.get("selection_basis", "none"),
        "candidate": candidate,
        "candidates": resolution.get("candidates") or [],
        "route": route_plan["route"],
        "preview": preview,
        "preview_token": token,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }


def _apply_named_route(candidate: Dict[str, Any], token: Dict[str, Any]) -> Dict[str, Any]:
    values = _named_values(token["values"], token.get("named_field_keys") or [])
    return apply_named_fields_exact_path(candidate["path"], values)


def _apply_cell_route(candidate: Dict[str, Any], token: Dict[str, Any]) -> Dict[str, Any]:
    values = _named_values(token["values"], list(token.get("cell_keys") or []))
    return apply_cells_to_open(candidate["path"], values)


def _normalize_apply_error(route: str, result: Dict[str, Any]) -> Dict[str, Any]:
    state = result.get("state")
    if state == "reload_blocked_existing":
        return {"available": True, "ok": False, "state": state, **result}
    if result.get("available") is False or state == "unavailable":
        return {"available": False, "ok": False, "state": "unavailable", **result}
    blocker = classify_live_write_blocker(
        write_state=str(result.get("write_state") or "unknown"),
        route=route,
        exc_text=str(result.get("error") or ""),
        dialog_hint=str(result.get("warning") or ""),
    )
    if blocker == "read_only":
        return {"available": True, "ok": False, "state": "read_only", **result}
    return {"available": True, "ok": False, "state": "error", "detail_state": state, **result}


def apply_to_current_hwp_document(preview_token: str) -> Dict[str, Any]:
    now = int(time.time())
    _purge_preview_tokens(now)
    token = _PREVIEW_TOKENS.get(preview_token)
    if token is None:
        return {"available": True, "ok": False, "state": "stale_preview_token"}

    resolution = resolve_current_hwp_document()
    if resolution.get("state") == "unavailable":
        return {"available": False, "ok": False, "state": "unavailable", "candidates": []}

    if resolution.get("state") in {
        "current_document_unsaved",
        "current_document_unprovable",
        "current_document_unsupported",
    }:
        return {"available": True, "ok": False, "state": "active_race", "candidates": resolution.get("candidates") or []}
    candidates = resolution.get("candidates") or []
    refresh_state = refresh_candidate_state(token, candidates)
    if refresh_state != "ok":
        return {"available": True, "ok": False, "state": refresh_state, "candidates": candidates}
    candidate = next(item for item in candidates if item.get("candidate_id") == token.get("candidate_id"))
    if candidate.get("write_state") == "read_only" and token.get("write_state") != "read_only":
        return {"available": True, "ok": False, "state": "read_only", "candidate": candidate}
    route = str(token.get("route") or "")
    if route == "named_field":
        result = _apply_named_route(candidate, token)
        if not result.get("ok"):
            return _normalize_apply_error(route, result)
        _PREVIEW_TOKENS.pop(preview_token, None)
        return {**result, "available": True, "ok": True, "state": "applied_named_field", "candidate": candidate}


    if route == "cells":
        result = _apply_cell_route(candidate, token)
        if not result.get("ok"):
            return _normalize_apply_error(route, result)
        _PREVIEW_TOKENS.pop(preview_token, None)
        return {**result, "available": True, "ok": True, "state": "applied_cells", "candidate": candidate}

    if route == "mixed":
        named_result = _apply_named_route(candidate, token)
        if not named_result.get("ok"):
            return _normalize_apply_error(route, named_result)
        cell_result = _apply_cell_route(candidate, token)
        if not cell_result.get("ok"):
            _PREVIEW_TOKENS.pop(preview_token, None)
            normalized = _normalize_apply_error(route, {**cell_result, "named_result": named_result})
            return {
                **normalized,
                "available": normalized.get("available", True),
                "ok": False,
                "state": "partial_apply_error",
                "detail_state": normalized.get("state"),
                "partial_apply": True,
                "candidate": candidate,
                "named_result": named_result,
                "cell_result": cell_result,
            }
        _PREVIEW_TOKENS.pop(preview_token, None)
        return {
            "available": True,
            "ok": True,
            "state": "applied_mixed",
            "candidate": candidate,
            "named_result": named_result,
            "cell_result": cell_result,
            "applied": list(named_result.get("applied") or []) + list(cell_result.get("applied") or []),
            "skipped": list(named_result.get("skipped") or []) + list(cell_result.get("skipped") or []),
            "count": int(named_result.get("count") or len(named_result.get("applied") or []))
            + int(cell_result.get("count") or len(cell_result.get("applied") or [])),
        }
    return {"available": True, "ok": False, "state": "error", "error": f"unsupported preview route: {route}"}


__all__ = [
    "apply_to_current_hwp_document",
    "preview_current_hwp_document",
    "resolve_current_hwp_document",
]

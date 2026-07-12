from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List


_RESOLVER_BLOCKERS = {
    "current_document_unsaved",
    "current_document_unsupported",
    "current_document_unprovable",
}


def candidate_write_state(path: str | Path | None) -> str:
    raw = str(path or "").strip()
    if not raw:
        return "unknown"
    try:
        return "writable" if os.access(raw, os.W_OK) else "read_only"
    except OSError:
        return "unknown"


def candidate_format(path: str | Path | None) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    return Path(raw).suffix.lower().lstrip(".")


def candidate_saved(candidate: Dict[str, Any]) -> bool:
    return bool(candidate.get("normalized_path") or candidate.get("path"))


def candidate_supported(candidate: Dict[str, Any]) -> bool:
    return candidate_format(candidate.get("path")) in {"hwp", "hwpx"}


def inventory_digest(candidates: Iterable[Dict[str, Any]]) -> str:
    payload = []
    for candidate in candidates:
        payload.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "moniker": candidate.get("moniker"),
                "slot": candidate.get("slot"),
                "normalized_path": candidate.get("normalized_path"),
                "is_active": candidate.get("is_active"),
                "active_source": candidate.get("active_source"),
                "active_slot": candidate.get("active_slot"),
                "active_path_empty": candidate.get("active_path_empty"),
                "active_identity_proven": candidate.get("active_identity_proven"),
                "write_state": candidate.get("write_state"),
            }
        )
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def summarize_resolution(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not candidates:
        return {"state": "no_open_documents", "selection_basis": "none", "candidates": []}

    active = next((item for item in candidates if item.get("is_active")), None)
    if active is None:
        return {
            "state": "current_document_unprovable",
            "selection_basis": "none",
            "candidates": candidates,
        }
    if active.get("active_path_empty"):
        return {
            "state": "current_document_unsaved",
            "selection_basis": "none",
            "candidates": candidates,
            "current_candidate_id": active.get("candidate_id"),
        }
    if not active.get("active_identity_proven"):
        return {
            "state": "current_document_unprovable",
            "selection_basis": "none",
            "candidates": candidates,
            "current_candidate_id": active.get("candidate_id"),
        }
    if not candidate_supported(active):
        return {
            "state": "current_document_unsupported",
            "selection_basis": "none",
            "candidates": candidates,
            "current_candidate_id": active.get("candidate_id"),
        }
    if candidate_format(active.get("path")) == "hwp":
        return {
            "state": "current_document_unsupported",
            "selection_basis": "none",
            "candidates": candidates,
            "current_candidate_id": active.get("candidate_id"),
        }
    saved_hwpx = [item for item in candidates if candidate_saved(item) and candidate_format(item.get("path")) == "hwpx"]
    all_saved_hwpx = bool(candidates) and all(
        candidate_saved(item) and candidate_format(item.get("path")) == "hwpx" for item in candidates
    )
    if len(saved_hwpx) == 1 and all_saved_hwpx and len(candidates) == 1:
        return {
            "state": "auto_selected",
            "selection_basis": "single_saved_hwpx_total",
            "candidate_id": saved_hwpx[0].get("candidate_id"),
            "candidate": saved_hwpx[0],
            "candidates": candidates,
        }
    if candidate_saved(active) and len(saved_hwpx) == 1:
        return {
            "state": "auto_selected",
            "selection_basis": "single_saved_active_hwpx",
            "candidate_id": active.get("candidate_id"),
            "candidate": active,
            "candidates": candidates,
        }
    return {
        "state": "selection_required",
        "selection_basis": "none",
        "candidates": candidates,
        "current_candidate_id": active.get("candidate_id"),
    }


def preview_state_from_resolution(resolution: Dict[str, Any]) -> str:
    mapping = {
        "no_open_documents": "no_open_documents",
        "selection_required": "selection_required",
        "current_document_unsaved": "current_document_unsaved",
        "current_document_unprovable": "current_document_unprovable",
        "current_document_unsupported": "preview_requires_hwpx",
    }
    return mapping.get(str(resolution.get("state") or ""), "error")


def classify_live_write_blocker(
    *,
    write_state: str,
    route: str,
    exc_text: str | None = None,
    dialog_hint: str | None = None,
) -> str:
    if write_state == "read_only":
        return "read_only"
    haystack = " ".join(x for x in [route, exc_text or "", dialog_hint or ""] if x).lower()
    if any(token in haystack for token in ("read only", "read-only", "readonly", "읽기 전용", "읽기전용")):
        return "read_only"
    return "error"


def matched_named_field_keys(values: Dict[str, str], field_names: Iterable[str]) -> List[str]:
    known = set(field_names)
    matched: List[str] = []
    for key in values:
        if key in known or key.removeprefix("field:") in known:
            matched.append(key)
    return matched


def _label_aliases(target: Dict[str, Any]) -> List[str]:
    aliases: List[str] = []
    if target.get("field_id"):
        aliases.append(str(target["field_id"]))
    if target.get("label"):
        aliases.append(str(target["label"]))
    for label in target.get("labels") or []:
        aliases.append(str(label))
    return aliases


def matched_cell_keys(values: Dict[str, str], preview: Dict[str, Any]) -> List[str]:
    matched: List[str] = []
    seen = set()
    targets = list(preview.get("targets") or []) + list(preview.get("text_targets") or []) + list(preview.get("body_targets") or [])
    for key in values:
        for target in targets:
            if key in _label_aliases(target):
                if key not in seen:
                    matched.append(key)
                    seen.add(key)
                break
    return matched


def plan_preview_route(
    values: Dict[str, str],
    *,
    field_names: Iterable[str],
    cell_preview: Dict[str, Any],
) -> Dict[str, Any]:
    named_keys = matched_named_field_keys(values, field_names)
    cell_keys = matched_cell_keys(values, cell_preview)
    overlap = sorted(set(named_keys) & set(cell_keys))
    if overlap:
        route = "route_conflict"
    elif named_keys and cell_keys:
        route = "mixed"
    elif named_keys:
        route = "named_field"
    else:
        route = "cells"
    return {
        "route": route,
        "named_field_keys": named_keys,
        "cell_keys": cell_keys,
        "overlap_keys": overlap,
    }


def make_preview_digest(route: str, payload: Dict[str, Any]) -> str:
    blob = json.dumps({"route": route, "payload": payload}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def refresh_candidate_state(token: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    matched = [item for item in candidates if item.get("candidate_id") == token.get("candidate_id")]
    if matched:
        candidate = matched[0]
        if not candidate.get("active_identity_proven") or not candidate.get("is_active"):
            return "active_race"
        return "ok"
    same_path = [item for item in candidates if item.get("normalized_path") == token.get("normalized_path")]
    if not same_path:
        return "closed_document"
    if any(not item.get("active_identity_proven") for item in same_path):
        return "active_race"
    return "stale_candidate"


__all__ = [
    "candidate_format",
    "candidate_saved",
    "candidate_supported",
    "candidate_write_state",
    "classify_live_write_blocker",
    "inventory_digest",
    "make_preview_digest",
    "matched_cell_keys",
    "matched_named_field_keys",
    "plan_preview_route",
    "preview_state_from_resolution",
    "refresh_candidate_state",
    "summarize_resolution",
]

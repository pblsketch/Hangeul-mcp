from __future__ import annotations

import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List

from hangeul_core.addressed import (
    complete_addressed_template as _complete_addressed_template,
    preview_addressed_edits as _preview_addressed_edits,
)
from hangeul_core.formfield import form_field_names
from hangeul_core.hwp import HwpBridge
from hangeul_core.hwp.com import list_rot_instances, normalize_live_path
from hangeul_core.live_timeout import run_with_timeout
from hangeul_core.hwp.live_attach import open_as_new_tab as _open_completed_in_window

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
from hangeul_core.hwp.live_addressed import (
    HYBRID_FALLBACK as _LIVE_ADDRESSED_FALLBACK,
    apply_live_addressed,
    live_addressed_enabled,
    plan_live_addressed_edits,
)
from hangeul_core.hwp.rot_attach import apply_named_fields_exact_path
from hangeul_core.runtime_info import runtime_identity


_PREVIEW_TOKEN_TTL_SECONDS = 300
# batches at or below this keep the fresh-connection read-back; larger ones skip it
# for speed (the per-cell expected_text pre-check still guards every write)
_LIVE_VERIFY_MAX_CELLS = 12
_CANDIDATE_CACHE: Dict[str, Dict[str, Any]] = {}
_PREVIEW_TOKENS: Dict[str, Dict[str, Any]] = {}


def _purge_preview_tokens(now: int | None = None) -> None:
    cutoff = int(time.time()) if now is None else now
    stale = [token for token, payload in _PREVIEW_TOKENS.items() if cutoff > int(payload.get("expires_at") or 0)]
    for token in stale:
        _PREVIEW_TOKENS.pop(token, None)



def _live_current_available() -> bool:
    return HwpBridge.available() or bool(list_rot_instances())


def _server_instance_id() -> str:
    return str(runtime_identity()["server_instance_id"])


def _mint_preview_token() -> str:
    return f"{_server_instance_id()}.{secrets.token_urlsafe(18)}"


def _preview_token_server_instance_id(preview_token: str) -> str | None:
    server_id, sep, _rest = preview_token.partition(".")
    return server_id if sep and server_id else None



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


_COMPLETE_AND_LOAD_NOTE = (
    "a NEW verified file was created and its path is returned; the original document stays "
    "open untouched (never saved/closed/reloaded) and the verified copy opens as a new tab "
    "in front (the active view switches). If the original window is not automation-visible, "
    "the copy may open in a separate window/new instance."
)


def _sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _plan_completion_output_path(candidate: Dict[str, Any], requested: str | None):
    """Pick the NEW output file for complete_and_load; never the original path."""
    original = Path(str(candidate.get("path") or ""))
    if requested:
        out = Path(requested)
        if out.suffix.lower() != ".hwpx":
            return None, "output_requires_hwpx"
        requested_norm = normalize_live_path(str(out))
        original_norms = {
            normalize_live_path(str(candidate.get("normalized_path") or "")),
            normalize_live_path(str(original)),
        }
        if requested_norm in original_norms:
            return None, "output_overwrites_original"
        if out.exists():
            return None, "output_exists"
        return out, None
    out = original.with_name(f"{original.stem}.completed.hwpx")
    counter = 2
    while out.exists() and counter < 100:
        out = original.with_name(f"{original.stem}.completed-{counter}.hwpx")
        counter += 1
    if out.exists():
        return None, "output_exists"
    return out, None


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


def _preview_complete_and_load(
    resolution: Dict[str, Any],
    candidate: Dict[str, Any],
    edits: List[Dict[str, Any]],
    output_path: str | None,
    mode: str,
) -> Dict[str, Any]:
    candidates = resolution.get("candidates") or []
    planned_out, out_error = _plan_completion_output_path(candidate, output_path)
    if out_error:
        return {
            "available": True,
            "ok": False,
            "state": out_error,
            "candidate": candidate,
            "candidates": candidates,
        }
    completion_preview = _preview_addressed_edits(candidate["path"], edits)
    if not completion_preview.get("ok"):
        return {
            "available": True,
            "ok": False,
            "state": "addressed_preview_failed",
            "detail_state": str(completion_preview.get("state") or ""),
            "unresolved": list(completion_preview.get("unresolved") or []),
            "counts": dict(completion_preview.get("counts") or {}),
            "candidate": candidate,
            "candidates": candidates,
        }
    source_sha256 = str(completion_preview.get("source_sha256") or "")
    preview = {
        "route": "complete_and_load",
        "output_path": str(planned_out),
        "edit_count": len(edits),
        "counts": dict(completion_preview.get("counts") or {}),
        "source_sha256": source_sha256,
        "note": _COMPLETE_AND_LOAD_NOTE,
    }
    issued_at = int(time.time())
    expires_at = issued_at + _PREVIEW_TOKEN_TTL_SECONDS
    token_payload = {
        "candidate_id": candidate["candidate_id"],
        "selection_basis": resolution.get("selection_basis", "none"),
        "route": "complete_and_load",
        "normalized_path": candidate.get("normalized_path"),
        "moniker": candidate.get("moniker"),
        "slot": candidate.get("slot"),
        "server_instance_id": _server_instance_id(),
        "inventory_digest": resolution["inventory_digest"],
        "value_digest": hashlib.sha256(
            json.dumps(edits, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "preview_digest": make_preview_digest("complete_and_load", preview),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "write_state": candidate.get("write_state"),
        "mode": mode,
        "values": {},
        "named_field_keys": [],
        "cell_keys": [],
        "edits": [dict(item) for item in edits],
        "output_path": str(planned_out),
        "source_sha256": source_sha256,
    }
    token = _mint_preview_token()
    _PREVIEW_TOKENS[token] = token_payload
    return {
        "available": True,
        "ok": True,
        "state": "preview_ready",
        "server_instance_id": _server_instance_id(),
        "selection_basis": resolution.get("selection_basis", "none"),
        "candidate": candidate,
        "candidates": candidates,
        "route": "complete_and_load",
        "preview": preview,
        "preview_token": token,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }


def _preview_live_addressed(
    resolution: Dict[str, Any],
    candidate: Dict[str, Any],
    edits: List[Dict[str, Any]],
) -> Dict[str, Any]:
    candidates = resolution.get("candidates") or []
    if not live_addressed_enabled():
        return {
            "available": True,
            "ok": False,
            "state": "live_addressed_gated",
            "candidate": candidate,
            "candidates": candidates,
            "next": (
                "in-place live addressed editing is gated behind the desktop-live QA "
                "evidence pass (feature_flags.live_addressed_editing); " + _LIVE_ADDRESSED_FALLBACK
            ),
        }
    plan = plan_live_addressed_edits(candidate["path"], edits)
    if not plan.get("ok"):
        return {
            "available": True,
            "ok": False,
            "state": str(plan.get("state") or "live_addressed_plan_failed"),
            "unresolved": list(plan.get("unresolved") or []),
            "counts": dict(plan.get("counts") or {}),
            "candidate": candidate,
            "candidates": candidates,
            **({"next": plan["next"]} if plan.get("next") else {}),
        }
    preview = {
        "route": "live_addressed",
        "targets": list(plan.get("targets") or []),
        "counts": dict(plan.get("counts") or {}),
        "source_sha256": str(plan.get("source_sha256") or ""),
        "note": (
            "in-place COM edit of the OPEN window — NOT byte-preserving; the document is "
            "never saved/closed/reloaded by the server, and every cell is re-checked "
            "against expected_text immediately before replacement"
        ),
    }
    issued_at = int(time.time())
    expires_at = issued_at + _PREVIEW_TOKEN_TTL_SECONDS
    token_payload = {
        "candidate_id": candidate["candidate_id"],
        "selection_basis": resolution.get("selection_basis", "none"),
        "route": "live_addressed",
        "normalized_path": candidate.get("normalized_path"),
        "moniker": candidate.get("moniker"),
        "slot": candidate.get("slot"),
        "server_instance_id": _server_instance_id(),
        "inventory_digest": resolution["inventory_digest"],
        "value_digest": hashlib.sha256(
            json.dumps(edits, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "preview_digest": make_preview_digest("live_addressed", preview),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "write_state": candidate.get("write_state"),
        "mode": "live_addressed",
        "values": {},
        "named_field_keys": [],
        "cell_keys": [],
        "targets": [dict(t) for t in plan.get("targets") or []],
        "source_sha256": str(plan.get("source_sha256") or ""),
    }
    token = _mint_preview_token()
    _PREVIEW_TOKENS[token] = token_payload
    return {
        "available": True,
        "ok": True,
        "state": "preview_ready",
        "server_instance_id": _server_instance_id(),
        "selection_basis": resolution.get("selection_basis", "none"),
        "candidate": candidate,
        "candidates": candidates,
        "route": "live_addressed",
        "preview": preview,
        "preview_token": token,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }


def preview_current_hwp_document(
    values: Dict[str, str],
    candidate_id: str | None = None,
    mode: str = "auto",
    edits: List[Dict[str, Any]] | None = None,
    output_path: str | None = None,
) -> Dict[str, Any]:
    _purge_preview_tokens()
    resolution = resolve_current_hwp_document()

    blocked_state = preview_state_from_resolution(resolution)
    if resolution.get("state") == "unavailable":
        return {"available": False, "ok": False, "state": "unavailable", "candidates": []}

    if resolution.get("state") == "no_open_documents" or (
        resolution.get("state")
        in {
            "current_document_unsaved",
            "current_document_unprovable",
            "current_document_unsupported",
        }
        and not candidate_id
    ):
        # An explicit candidate_id is judged on that candidate's own state below
        # (saved/.hwpx/write_state); blockers from other instances' actives must
        # not veto it. Identity proof is deliberately DEFERRED to apply, where
        # refresh_candidate_state requires is_active + active_identity_proven.
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
    if candidate.get("write_state") == "read_only" and (not edits or mode == "live_addressed"):
        # complete_and_load only READS the original, so read-only must not block it;
        # live_addressed writes into the window, so read-only blocks it like the small fills.
        return {
            "available": True,
            "ok": False,
            "state": "read_only",
            "candidate": candidate,
            "candidates": resolution.get("candidates") or [],
        }
    if edits:
        field_names: List[str] = []
        cell_preview: Dict[str, Any] = {}
    else:
        field_names = form_field_names(candidate["path"])
        cell_preview = preview_cells_to_open(candidate["path"], values)
    route_plan = plan_preview_route(values, field_names=field_names, cell_preview=cell_preview, edits=edits)
    if route_plan["route"] == "route_conflict":
        response = {
            "available": True,
            "ok": False,
            "state": "route_conflict",
            "candidate": candidate,
            "candidates": resolution.get("candidates") or [],
            "conflict_keys": route_plan["overlap_keys"],
            "named_field_keys": route_plan["named_field_keys"],
            "cell_keys": route_plan["cell_keys"],
        }
        if route_plan.get("input_conflict"):
            response["input_conflict"] = route_plan["input_conflict"]
            response["error"] = "pass either values (live small fills) or edits (complete_and_load), not both"
        return response
    if route_plan["route"] == "complete_and_load":
        if mode == "live_addressed":
            return _preview_live_addressed(resolution, candidate, list(edits or []))
        return _preview_complete_and_load(resolution, candidate, list(edits or []), output_path, mode)
    if route_plan["route"] == "mixed":
        return {
            "available": True,
            "ok": False,
            "state": "mixed_route_unsupported",
            "candidate": candidate,
            "candidates": resolution.get("candidates") or [],
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
        "server_instance_id": _server_instance_id(),
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
    token = _mint_preview_token()

    _PREVIEW_TOKENS[token] = token_payload
    return {
        "available": True,
        "ok": True,
        "state": "preview_ready",
        "server_instance_id": _server_instance_id(),
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


def _apply_complete_and_load(preview_token: str, token: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    output_path = str(token.get("output_path") or "")
    edits = [dict(item) for item in token.get("edits") or []]
    if Path(output_path).exists():
        return {
            "available": True,
            "ok": False,
            "state": "output_exists",
            "output_path": output_path,
            "candidate": candidate,
        }
    original_path = str(candidate.get("path") or "")
    try:
        original_sha_before = _sha256_file(original_path)
    except OSError as exc:
        return {
            "available": True,
            "ok": False,
            "state": "io_error",
            "output_path": output_path,
            "candidate": candidate,
            "error": f"could not read the original for hashing: {exc}",
        }
    previewed_sha = str(token.get("source_sha256") or "")
    if previewed_sha and original_sha_before != previewed_sha:
        # the reviewed audit no longer describes this file — never complete blind
        _PREVIEW_TOKENS.pop(preview_token, None)
        return {
            "available": True,
            "ok": False,
            "state": "stale_preview",
            "output_path": output_path,
            "original_sha256": original_sha_before,
            "previewed_sha256": previewed_sha,
            "candidate": candidate,
            "next": "the original changed after preview; call preview_current_hwp_document(edits=...) again",
        }
    # complete into a unique sibling temp file, then publish atomically (no replace)
    tmp_path = Path(f"{output_path}.{secrets.token_hex(4)}.part")

    def _discard_tmp() -> None:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    try:
        completion = _complete_addressed_template(original_path, edits, str(tmp_path), verify=True)
    except OSError as exc:
        _discard_tmp()
        return {
            "available": True,
            "ok": False,
            "state": "io_error",
            "output_path": output_path,
            "candidate": candidate,
            "error": str(exc),
        }
    if not completion.get("ok"):
        # discard any partially written temp output; the token stays usable for retry
        partial_output_removed = tmp_path.exists()
        _discard_tmp()
        return {
            "available": True,
            "ok": False,
            "state": "complete_failed",
            "detail_state": str(completion.get("state") or ""),
            "unresolved": list(completion.get("unresolved") or []),
            "failures": list(completion.get("failures") or []),
            "counts": dict(completion.get("counts") or {}),
            "partial_output_removed": partial_output_removed,
            "output_path": output_path,
            "candidate": candidate,
        }
    original_sha_after = _sha256_file(original_path)
    completion_summary = {
        "state": completion.get("state"),
        "counts": dict(completion.get("counts") or {}),
        "coverage_ratio": completion.get("coverage_ratio"),
        "source_sha256": completion.get("source_sha256"),
        "target_sha256": completion.get("target_sha256"),
    }
    if original_sha_before != original_sha_after:
        _discard_tmp()
        _PREVIEW_TOKENS.pop(preview_token, None)
        return {
            "available": True,
            "ok": False,
            "state": "original_modified_during_completion",
            "output_path": output_path,
            "original_sha256_before": original_sha_before,
            "original_sha256_after": original_sha_after,
            "completion": completion_summary,
            "candidate": candidate,
            "error": "the original file changed while completing; result discarded — re-preview and retry",
        }
    try:
        # exclusive create = atomic no-replace publish (portable)
        with open(output_path, "xb") as published:
            published.write(tmp_path.read_bytes())
    except FileExistsError:
        _discard_tmp()
        return {
            "available": True,
            "ok": False,
            "state": "output_exists",
            "output_path": output_path,
            "candidate": candidate,
        }
    except OSError as exc:
        _discard_tmp()
        return {
            "available": True,
            "ok": False,
            "state": "io_error",
            "output_path": output_path,
            "candidate": candidate,
            "error": str(exc),
        }
    _discard_tmp()
    # the verified output file exists now, so the token must never replay
    _PREVIEW_TOKENS.pop(preview_token, None)
    base = {
        "available": True,
        "candidate": candidate,
        "route": "complete_and_load",
        "output_path": output_path,
        "original_sha256": original_sha_before,
        "original_untouched": True,
        "completion": completion_summary,
        "note": _COMPLETE_AND_LOAD_NOTE,
    }
    open_result = _open_completed_in_window(output_path, visible=True)
    open_summary = {
        key: open_result.get(key)
        for key in (
            "available",
            "connected",
            "ok",
            "state",
            "active_document",
            "attached_existing",
            "opened",
            "cold_start",
            "elapsed_seconds",
            "error",
        )
        if key in open_result
    }
    if open_result.get("ok"):
        return {**base, "ok": True, "state": "completed_and_loaded", "open": open_summary}
    return {
        **base,
        "ok": False,
        "state": "completed_open_failed",
        "open": open_summary,
        "next": (
            f"the verified file was created at {output_path}; automatic open failed — "
            "open it manually or call open_in_hwp(output_path)"
        ),
    }


def _apply_live_addressed_route(preview_token: str, token: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    if not live_addressed_enabled():
        return {
            "available": True,
            "ok": False,
            "state": "live_addressed_gated",
            "candidate": candidate,
            "next": _LIVE_ADDRESSED_FALLBACK,
        }
    original_path = str(candidate.get("path") or "")
    try:
        current_sha = _sha256_file(original_path)
    except OSError as exc:
        return {
            "available": True,
            "ok": False,
            "state": "io_error",
            "candidate": candidate,
            "error": f"could not read the saved file for hashing: {exc}",
        }
    previewed_sha = str(token.get("source_sha256") or "")
    if previewed_sha and current_sha != previewed_sha:
        _PREVIEW_TOKENS.pop(preview_token, None)
        return {
            "available": True,
            "ok": False,
            "state": "stale_preview",
            "original_sha256": current_sha,
            "previewed_sha256": previewed_sha,
            "candidate": candidate,
            "next": "the saved file changed after preview; call preview_current_hwp_document(edits=..., mode='live_addressed') again",
        }
    # single-use: consume BEFORE any COM mutation so no outcome can replay the write
    _PREVIEW_TOKENS.pop(preview_token, None)
    targets = [dict(t) for t in token.get("targets") or []]
    # A hung COM call cannot be interrupted in-process, so run the destructive apply
    # in an isolated worker with a bounded budget (60s + 4s/cell, capped 180s). This
    # turns the old "client blocks for 4 minutes" hang into a structured timeout that
    # names the safe recovery — the saved file is never touched by this path.
    timeout_seconds = min(60 + 4 * len(targets), 180)
    # the fresh-connection read-back is a whole second COM pass (~30% of wall time);
    # skip it for large batches where each per-cell expected_text pre-check already
    # guarded the write, so a 40-cell form finishes noticeably faster
    verify = len(targets) <= _LIVE_VERIFY_MAX_CELLS
    outcome = run_with_timeout(
        apply_live_addressed, original_path, targets, timeout_seconds=timeout_seconds, verify=verify
    )
    if outcome.get("ok") and "result" in outcome:
        result = {**outcome["result"], "candidate": candidate, "route": "live_addressed"}
        if not verify:
            result["note"] = (
                f"read-back verification was skipped for speed ({len(targets)} cells); each write "
                "passed its expected_text pre-check — spot-check the result in the window"
            )
        return result
    return {
        "available": True,
        "ok": False,
        "state": str(outcome.get("state") or "live_addressed_worker_failed"),
        "route": "live_addressed",
        "candidate": candidate,
        "may_have_partially_applied": bool(outcome.get("may_have_partially_applied", True)),
        "timeout_seconds": outcome.get("timeout_seconds"),
        "elapsed_seconds": outcome.get("elapsed_seconds"),
        "error": outcome.get("error"),
        "recovery": {
            "instruction": (
                "the live apply did not confirm completion within the time budget and may have "
                "replaced some cells. Close the Hangul window WITHOUT saving and reopen the "
                "original to be safe — this path never modified the saved file — then retry a "
                "whole 40-cell form with the complete_and_load hybrid."
            ),
        },
        "next": _LIVE_ADDRESSED_FALLBACK,
    }


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
    token_server_instance = _preview_token_server_instance_id(preview_token)
    if token_server_instance and token_server_instance != _server_instance_id():
        return {"available": True, "ok": False, "state": "wrong_server_instance"}
    _purge_preview_tokens(now)
    token = _PREVIEW_TOKENS.get(preview_token)
    if token is None:
        return {"available": True, "ok": False, "state": "stale_preview_token"}
    if token.get("server_instance_id") != _server_instance_id():
        return {"available": True, "ok": False, "state": "wrong_server_instance"}

    resolution = resolve_current_hwp_document()
    if resolution.get("state") == "unavailable":
        return {"available": False, "ok": False, "state": "unavailable", "candidates": []}

    candidates = resolution.get("candidates") or []
    # Judge the token's candidate on its own instance state first; global
    # resolver blockers (another instance's empty/unsaved active) must not
    # veto an apply whose candidate is still provably active.
    refresh_state = refresh_candidate_state(token, candidates)
    if refresh_state != "ok":
        return {"available": True, "ok": False, "state": refresh_state, "candidates": candidates}
    if resolution.get("state") in {
        "current_document_unsaved",
        "current_document_unprovable",
        "current_document_unsupported",
    }:
        # Residual fail-closed guard: unreachable when refresh passed, kept so a
        # blocked resolution can never fall through to a live write.
        return {"available": True, "ok": False, "state": "active_race", "candidates": candidates}
    candidate = next(item for item in candidates if item.get("candidate_id") == token.get("candidate_id"))
    route = str(token.get("route") or "")
    if route != "complete_and_load" and candidate.get("write_state") == "read_only" and token.get("write_state") != "read_only":
        return {"available": True, "ok": False, "state": "read_only", "candidate": candidate}
    if route == "complete_and_load":
        return _apply_complete_and_load(preview_token, token, candidate)
    if route == "live_addressed":
        return _apply_live_addressed_route(preview_token, token, candidate)
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
        _PREVIEW_TOKENS.pop(preview_token, None)
        return {"available": True, "ok": False, "state": "mixed_route_unsupported", "candidate": candidate}
    return {"available": True, "ok": False, "state": "error", "error": f"unsupported preview route: {route}"}


__all__ = [
    "apply_to_current_hwp_document",
    "preview_current_hwp_document",
    "resolve_current_hwp_document",
]

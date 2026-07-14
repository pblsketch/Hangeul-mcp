from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from hangeul_core import __version__

_SERVER_INSTANCE_ID = uuid.uuid4().hex
_STARTED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
_TOOL_SCHEMA_VERSION = 1


def runtime_identity() -> Dict[str, Any]:
    return {
        "version": __version__,
        "build_identifier": __version__,
        "server_instance_id": _SERVER_INSTANCE_ID,
        "pid": os.getpid(),
        "started_at": _STARTED_AT,
        "tool_schema_version": _TOOL_SCHEMA_VERSION,
        "session_scope": "this stdio process",
        "survives_restart": False,
    }


def feature_flags() -> Dict[str, bool]:
    return {
        "body_paragraph": True,
        "raw_cell_editing": True,
        "occurrence_editing": False,
        "live_addressed_editing": False,
    }


def live_routes() -> List[Dict[str, str]]:
    """Additive route inventory so full-form live intent is never dead-ended.

    ``feature_flags()['live_addressed_editing']`` stays a locked boolean; this
    list only ADDS routing signal. In-place addressed editing of the open
    window flips that boolean only after the desktop-live QA gate.
    """
    return [
        {
            "route": "small_label_cells",
            "scope": "a few label:value cells / inline blanks in the open window",
            "flow": "open_in_hwp(path) -> preview_small_live_label_cells -> apply_small_live_label_cells",
        },
        {
            "route": "named_fields_exact_path",
            "scope": "named form fields (누름틀) in the open window",
            "flow": "apply_to_open_hwp(values, path=...)",
        },
        {
            "route": "current_document_token",
            "scope": "pathless saved-.hwpx current document",
            "flow": "resolve_current_hwp_document -> preview_current_hwp_document -> apply_to_current_hwp_document",
        },
        {
            "route": "hybrid_complete_then_open",
            "scope": "whole-template / full-form fills (e.g. lesson plans, ~40-cell forms)",
            "flow": (
                "inspect_editable_regions(path, compact=true) -> preview_current_hwp_document(edits=[...]) "
                "-> apply_to_current_hwp_document(preview_token); file-mode fallback: "
                "complete_addressed_template(path, edits, out_path) then open_in_hwp(out_path)"
            ),
            "honesty": (
                "a NEW verified file is created and its path is always returned; the original "
                "document is untouched (never saved/closed/reloaded) and the verified copy opens "
                "as a new tab in front (the active view switches). It lands in the same Hangul "
                "instance only when that instance is automation-visible; a hand-opened original "
                "may not be, in which case the copy opens in a separate window/new instance."
            ),
        },
    ]


def attach_ladder(*, rot_visible: bool, com_object_acquired: bool, document_identity_proven: bool, window_detected: bool = False) -> Dict[str, bool]:
    return {
        "window_detected": window_detected,
        "rot_visible": rot_visible,
        "com_object_acquired": com_object_acquired,
        "document_identity_proven": document_identity_proven,
    }

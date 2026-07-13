from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

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


def attach_ladder(*, rot_visible: bool, com_object_acquired: bool, document_identity_proven: bool, window_detected: bool = False) -> Dict[str, bool]:
    return {
        "window_detected": window_detected,
        "rot_visible": rot_visible,
        "com_object_acquired": com_object_acquired,
        "document_identity_proven": document_identity_proven,
    }

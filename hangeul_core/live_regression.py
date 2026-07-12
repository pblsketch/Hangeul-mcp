from __future__ import annotations

from typing import Any, Dict, List

_REQUIRED_JSON_REFS = {
    "exact_path": ["status", "preview", "apply"],
    "current_document": ["status", "resolve", "preview", "apply"],
}


def build_windows_live_artifact(flow: str) -> Dict[str, Any]:
    if flow not in _REQUIRED_JSON_REFS:
        raise ValueError(f"unsupported flow: {flow}")
    return {
        "schemaVersion": 1,
        "flow": flow,
        "fixturePath": "tests/fixtures/sample_form.hwpx",
        "jsonRefs": {key: "" for key in _REQUIRED_JSON_REFS[flow]},
        "readback": {
            "verified": False,
            "method": "fresh_com_readback",
            "notes": "",
        },
        "screenshotPath": "",
        "savedCopyPath": "",
        "notes": [
            "Fill this artifact only after real Windows + Hangul desktop execution.",
            "Resolver-path existence and literal write-safe proof must be captured separately.",
        ],
    }



def validate_windows_live_artifact(payload: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    if payload.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    flow = str(payload.get("flow") or "")
    if flow not in _REQUIRED_JSON_REFS:
        errors.append("flow must be exact_path or current_document")
        return {"valid": False, "errors": errors}

    fixture = str(payload.get("fixturePath") or "").strip()
    if not fixture:
        errors.append("fixturePath is required")

    json_refs = payload.get("jsonRefs")
    if not isinstance(json_refs, dict):
        errors.append("jsonRefs must be an object")
        json_refs = {}
    for key in _REQUIRED_JSON_REFS[flow]:
        if not str(json_refs.get(key) or "").strip():
            errors.append(f"jsonRefs.{key} is required")

    readback = payload.get("readback")
    if not isinstance(readback, dict):
        errors.append("readback must be an object")
    else:
        if not isinstance(readback.get("verified"), bool):
            errors.append("readback.verified must be boolean")
        if not str(readback.get("method") or "").strip():
            errors.append("readback.method is required")

    screenshot = str(payload.get("screenshotPath") or "").strip()
    saved_copy = str(payload.get("savedCopyPath") or "").strip()
    if not screenshot and not saved_copy:
        errors.append("screenshotPath or savedCopyPath is required")

    return {"valid": not errors, "errors": errors}


__all__ = [
    "build_windows_live_artifact",
    "validate_windows_live_artifact",
]

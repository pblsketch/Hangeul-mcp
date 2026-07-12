from __future__ import annotations

from pathlib import Path
from typing import Dict

from hangeul_core.fill import fill


_UNREACHED_REASONS = {
    "table not found live",
    "cell address not reachable",
}


def _is_unreached(item: dict) -> bool:
    return item.get("reason") in _UNREACHED_REASONS


def reload_if_unreached(hwp, path: str | Path, values: Dict[str, str], result: dict) -> dict:
    unreached = [item for item in result.get("skipped", []) if _is_unreached(item)]
    if not unreached:
        return result

    kept_skipped = [item for item in result.get("skipped", []) if item not in unreached]
    result["unreached"] = unreached

    if result.get("attached_existing") or result.get("state") == "attached_existing":
        result["state"] = "reload_blocked_existing"
        result["skipped"] = kept_skipped + unreached
        result["count"] = len(result.get("applied", []))
        result["warning"] = (
            "File reload is blocked for attached_existing because it could discard unsaved changes; "
            "save or discard in Hangul, then reopen with open_in_hwp before retrying."
        )
        return result

    if not result.get("allow_file_reload"):
        result["skipped"] = kept_skipped + unreached
        return result
    reload_values = {
        item["key"]: values[item["key"]]
        for item in unreached
        if item.get("key") in values
    }
    if not reload_values:
        return result

    src = Path(path)
    out_path = src.with_name(f"{src.stem}.live-reload{src.suffix}")
    refill = fill(src, reload_values, out_path=out_path)
    hwp.open(str(refill.out_path))

    applied = list(result.get("applied", []))
    for item in refill.filled:
        applied.append({**item, "via": "file_reload"})

    result["applied"] = applied
    result["skipped"] = kept_skipped + list(refill.skipped)
    result["count"] = len(applied)
    result["file_reload"] = {
        "source_path": str(src),
        "out_path": str(refill.out_path),
        "applied": list(refill.filled),
        "skipped": list(refill.skipped),
    }
    return result

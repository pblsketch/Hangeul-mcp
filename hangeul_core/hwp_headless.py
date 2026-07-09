from __future__ import annotations

import importlib.util
from pathlib import Path


CANDIDATES = ("rhwp", "kordoc", "hwp5", "pyhwp")


def headless_status() -> dict:
    checked = {name: importlib.util.find_spec(name) is not None for name in CANDIDATES}
    return {"available": any(checked.values()), "checked": checked}


def extract_hwp_text(path: str | Path) -> dict:
    p = Path(path)
    if p.suffix.lower() != ".hwp":
        return {"available": True, "ok": False, "error": "extract_hwp_text only accepts .hwp files"}
    if not p.exists():
        return {"available": True, "ok": False, "error": "file not found"}
    status = headless_status()
    if not status["available"]:
        return {
            "available": False,
            "ok": False,
            "format": "hwp",
            "checked": status["checked"],
            "error": "no headless .hwp reader installed; COM conversion is not used for this tool",
        }
    return {
        "available": False,
        "ok": False,
        "format": "hwp",
        "checked": status["checked"],
        "error": "headless .hwp reader substrate detected but no adapter has been selected yet",
    }

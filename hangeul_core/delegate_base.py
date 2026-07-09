from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Dict

from hangeul_core.validate import validate_hwpx


def hwpx_available() -> bool:
    return importlib.util.find_spec("hwpx") is not None


def module():
    if not hwpx_available():
        raise RuntimeError(
            "python-hwpx not installed; run `pip install python-hwpx` "
            "(or `pip install -e \".[delegate]\"`) to enable delegated editing/export"
        )
    import hwpx

    return hwpx


def doc(path: str | Path):
    return module().HwpxDocument.open(str(path))


def save(doc_obj, out_path: str | Path) -> None:
    saver = getattr(doc_obj, "save_to_path", None)
    if callable(saver):
        saver(str(out_path))
    else:
        doc_obj.save(str(out_path))


def edit_result(out_path: str | Path) -> Dict:
    report = validate_hwpx(out_path)
    xsd_ok = report.get("xsd", {}).get("valid", True) is not False
    return {
        "ok": bool(report["valid"]) and xsd_ok,
        "out_path": str(out_path),
        "validation": report,
    }


def to_html(path: str | Path) -> str:
    return doc(path).export_html()


def to_markdown(path: str | Path) -> str:
    return doc(path).export_markdown()


def to_text_rich(path: str | Path) -> str:
    return doc(path).export_text()

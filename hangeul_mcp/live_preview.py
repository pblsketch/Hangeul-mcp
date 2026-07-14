from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from hangeul_core.hwp.live import preview_cells_to_open as _preview_cells_to_open
from hangeul_core.live_timeout import run_with_timeout


def _preview_worker(path: str, values: Dict[str, str]) -> Dict[str, Any]:
    return dict(_preview_cells_to_open(Path(path), values))


def preview_small_live_label_cells(
    path: str,
    values: Dict[str, str],
    timeout_seconds: float = 10.0,
) -> Dict[str, Any]:
    """Bounded, file-only preview for a few live label:value cells."""
    p = Path(path)
    if p.suffix.lower() == ".hwp":
        return {
            "available": True,
            "ok": False,
            "error": "preview_small_live_label_cells only accepts .hwpx; save/convert .hwp first",
        }
    if p.suffix.lower() != ".hwpx":
        return {
            "available": True,
            "ok": False,
            "error": "preview_small_live_label_cells only accepts .hwpx files",
        }

    outcome = run_with_timeout(
        _preview_worker,
        str(p),
        values,
        timeout_seconds=max(timeout_seconds, 0.1),
    )
    if not outcome.get("ok"):
        return {
            "available": True,
            "ok": False,
            "state": "live_preview_failed",
            "may_have_partially_applied": False,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": outcome.get("elapsed_seconds"),
            "error": outcome.get("error", "live label-cell preview failed"),
        }

    result = dict(outcome["result"])
    result.update(
        {
            "ok": result.get("ok", True),
            "resolver": {
                "side_effect_free": True,
                "exact_path": str(p),
                "apply_to_open_hwp_state": "pathful_exact_path",
                "apply_small_live_label_cells_state": "pathful_exact_path",
            },
            "attach_candidates": [],
            "attach_probe": "deferred_to_apply",
        }
    )
    return result

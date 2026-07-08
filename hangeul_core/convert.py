"""`.hwp` -> `.hwpx` conversion policy (D3).

v1 auto-converts binary ``.hwp`` to ``.hwpx`` using the local Hangul (한글) via
COM. This requires Windows + Hangul + pywin32; otherwise a clear, actionable
error is raised (asking the user to save as ``.hwpx``). ``.hwpx`` inputs pass
through unchanged and stay fully cross-platform.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def ensure_hwpx(path: str) -> str:
    """Return an HWPX path, converting a ``.hwp`` input when possible."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".hwpx":
        return str(p)
    if suffix == ".hwp":
        return hwp_to_hwpx(p)
    return str(p)  # let downstream reject unknown formats


def hwp_to_hwpx(hwp_path, out_path: Optional[str] = None) -> str:
    """Convert a binary ``.hwp`` to ``.hwpx`` via Hangul COM (SaveAs)."""
    from hangeul_core.hwp import HwpBridge

    bridge = HwpBridge()
    if not bridge.available():
        raise RuntimeError(
            "HWP->HWPX auto-conversion requires Windows + Hangul (한글) + pywin32. "
            "Open the file in Hangul and save it as .hwpx, then retry."
        )
    src = Path(hwp_path).resolve()
    dst = Path(out_path).resolve() if out_path else src.with_suffix(".hwpx")
    bridge.connect(visible=False)
    hwp = bridge._hwp  # noqa: SLF001 - controlled internal use
    hwp.Open(str(src))
    hwp.SaveAs(str(dst), "HWPX", "")
    return str(dst)

"""Plain-text extraction from HWPX (read-only helper)."""

from __future__ import annotations

import re
from pathlib import Path

from hangeul_core.owpml import HwpxPackage

_T = re.compile(r"<hp:t>(.*?)</hp:t>", re.S)


def _unescape(s: str) -> str:
    return (
        s.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&amp;", "&")
    )


def extract_text(path: str | Path) -> str:
    """Return document text, one line per non-empty text node, in document order."""
    pkg = HwpxPackage.open(path)
    sections = sorted(
        n for n in pkg.names() if n.startswith("Contents/section") and n.endswith(".xml")
    )
    lines = []
    for name in sections:
        xml = pkg.read(name).decode("utf-8", "ignore")
        for m in _T.finditer(xml):
            text = _unescape(m.group(1)).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)

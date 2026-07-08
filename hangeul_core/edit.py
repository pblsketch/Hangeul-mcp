"""General text editing (search/replace) — OWN, byte-preserving.

Unlike the structural editing planned for Phase C (paragraphs/tables/formatting/
images, which is delegated to python-hwpx), literal text replacement is squarely
in our byte-splice wheelhouse: only ``<hp:t>`` text changes, every untouched ZIP
entry stays byte-identical, and nothing is re-serialized. Built on
``locate.replace_literals`` (run-split aware, boundary-guarded).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dfield
from pathlib import Path
from typing import Dict, Optional

from hangeul_core.analyze import _section_names
from hangeul_core.locate import replace_literals
from hangeul_core.owpml import HwpxPackage


@dataclass
class ReplaceResult:
    counts: Dict[str, int] = dfield(default_factory=dict)
    total: int = 0
    out_path: Optional[str] = None


def batch_replace(
    path: str | Path,
    mapping: Dict[str, str],
    out_path: Optional[str | Path] = None,
) -> ReplaceResult:
    """Apply every ``{find: replace}`` pair across all sections in one pass."""
    pkg = HwpxPackage.open(path)
    counts: Dict[str, int] = {}
    for sname in _section_names(pkg):
        text = pkg.read(sname).decode("utf-8")
        newtext, c = replace_literals(text, mapping)
        if c:
            pkg.replace(sname, newtext.encode("utf-8"))
            for k, v in c.items():
                counts[k] = counts.get(k, 0) + v
    if out_path is not None:
        pkg.save(out_path)
    return ReplaceResult(
        counts=counts,
        total=sum(counts.values()),
        out_path=str(out_path) if out_path else None,
    )


def search_and_replace(
    path: str | Path,
    find: str,
    replace: str,
    out_path: Optional[str | Path] = None,
) -> ReplaceResult:
    """Replace every occurrence of *find* with *replace* (byte-preserving)."""
    return batch_replace(path, {find: replace}, out_path)

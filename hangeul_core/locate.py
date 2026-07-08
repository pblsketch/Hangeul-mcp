"""Section-wide text-token locate + byte-splice primitive.

The cell-based fill path (``fill._find_cell_span``) can only address text that
lives in a table cell. Template variables like ``{학교명}`` appear anywhere —
body paragraphs, table cells, nested tables — and are frequently *split across
runs* by the editor (e.g. ``{``, ``학교명``, ``}`` in three separate ``<hp:t>``
nodes). This module provides a small, well-tested primitive that:

* concatenates the inner text of every ``<hp:t>`` node in document order,
* maps each concatenated-text character back to its ``<hp:t>`` segment + offset,
* finds ``{token}`` matches (even across adjacent segments), and
* edits *only the text inside* the affected ``<hp:t>`` nodes — never the tags —
  so run/charPr markup and byte-preservation of untouched regions are kept.

Working entirely in the decoded ``str`` (the section is re-encoded once by the
caller via ``HwpxPackage.replace``) sidesteps multibyte byte-offset hazards.

This is the bounded slice of the deferred Expat/SAX index (see
``docs/qa-codex-v0.1.0.md``): just enough to make run-split tokens robust
without re-scanning risk to the 56 green tests.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from hangeul_core.analyze import _section_names  # reuse ordered section listing
from hangeul_core.owpml import HwpxPackage
from hangeul_core.schema import KIND_PLACEHOLDER, Field

_T = re.compile(r"<hp:t>(.*?)</hp:t>", re.S)
# A token must not silently bridge a paragraph/cell/table boundary.
_BOUNDARY = re.compile(r"</hp:tc>|<hp:tc\b|</hp:p>|<hp:tbl\b|</hp:tbl>")
_TOKEN = re.compile(r"\{([^{}\r\n]{1,40})\}")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _segments(section: str) -> List[Tuple[int, int]]:
    """Raw (start, end) offsets of every ``<hp:t>`` node's *inner* text."""
    return [(m.start(1), m.end(1)) for m in _T.finditer(section)]


def _concat_map(section: str, segs: List[Tuple[int, int]]) -> Tuple[str, List[Tuple[int, int]]]:
    """Return (concatenated inner text, idxmap[char] -> (seg_index, local_off))."""
    chunks: List[str] = []
    idxmap: List[Tuple[int, int]] = []
    for si, (s, e) in enumerate(segs):
        inner = section[s:e]
        for off in range(len(inner)):
            idxmap.append((si, off))
        chunks.append(inner)
    return "".join(chunks), idxmap


def find_placeholder_names(section: str) -> List[str]:
    """Distinct ``{token}`` names present in *section* (order-preserving)."""
    segs = _segments(section)
    concat, _ = _concat_map(section, segs)
    seen: List[str] = []
    for m in _TOKEN.finditer(concat):
        name = m.group(1).strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _gaps_clean(section: str, segs: List[Tuple[int, int]], si: int, sj: int) -> bool:
    """True if no structural boundary lies between segments *si*..*sj*."""
    for k in range(si, sj):
        gap = section[segs[k][1]:segs[k + 1][0]]
        if _BOUNDARY.search(gap):
            return False
    return True


def replace_placeholders(section: str, values: Dict[str, str]) -> Tuple[str, List[str]]:
    """Replace every ``{name}`` whose *name* is in *values*.

    Returns ``(new_section, applied_names)``. Tokens split across adjacent
    ``<hp:t>`` nodes are handled; tokens whose span would cross a paragraph /
    cell / table boundary are left untouched (defensive). Only text inside
    ``<hp:t>`` nodes changes; tags are preserved verbatim.
    """
    segs = _segments(section)
    if not segs:
        return section, []
    concat, idxmap = _concat_map(section, segs)

    # Per-segment character edits: seg_index -> list of (local_start, local_end, text)
    edits: Dict[int, List[Tuple[int, int, str]]] = {}
    applied: List[str] = []

    for m in _TOKEN.finditer(concat):
        name = m.group(1).strip()
        if name not in values:
            continue
        s, e = m.start(), m.end()  # covers the braces
        s_si, s_off = idxmap[s]
        e_si, e_off = idxmap[e - 1]
        e_off += 1  # exclusive end within the last segment
        if s_si != e_si and not _gaps_clean(section, segs, s_si, e_si):
            continue
        repl = _esc(values[name])
        if s_si == e_si:
            edits.setdefault(s_si, []).append((s_off, e_off, repl))
        else:
            first_len = segs[s_si][1] - segs[s_si][0]
            edits.setdefault(s_si, []).append((s_off, first_len, repl))
            for mid in range(s_si + 1, e_si):
                mid_len = segs[mid][1] - segs[mid][0]
                edits.setdefault(mid, []).append((0, mid_len, ""))
            edits.setdefault(e_si, []).append((0, e_off, ""))
        applied.append(name)

    if not edits:
        return section, []

    # Apply, rebuilding each touched segment's inner text, then splice segments
    # back into the section right-to-left so raw offsets stay valid.
    out = section
    for si in sorted(edits.keys(), reverse=True):
        s, e = segs[si]
        inner = section[s:e]
        for local_start, local_end, text in sorted(edits[si], reverse=True):
            inner = inner[:local_start] + text + inner[local_end:]
        out = out[:s] + inner + out[e:]
    # de-dup applied preserving order
    seen: List[str] = []
    for n in applied:
        if n not in seen:
            seen.append(n)
    return out, seen


def replace_literals(section: str, mapping: Dict[str, str]) -> Tuple[str, Dict[str, int]]:
    """Replace arbitrary literal substrings inside ``<hp:t>`` text.

    ``mapping`` is ``{find: replace}``. Matching spans the concatenated ``<hp:t>``
    text (so a match may cross runs) but never bridges a paragraph/cell/table
    boundary. Longer finds win on overlap and each position is edited at most
    once (no chained re-replacement). Returns ``(new_section, counts)``.
    """
    segs = _segments(section)
    if not segs:
        return section, {}
    concat, idxmap = _concat_map(section, segs)

    # collect all candidate match spans across all finds
    spans: List[Tuple[int, int, str]] = []
    for find in mapping:
        if not find:
            continue
        start = 0
        while True:
            i = concat.find(find, start)
            if i < 0:
                break
            spans.append((i, i + len(find), find))
            start = i + len(find)
    # longest-first at each position; greedily claim non-overlapping left-to-right
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))

    edits: Dict[int, List[Tuple[int, int, str]]] = {}
    counts: Dict[str, int] = {}
    last_end = -1
    for s, e, find in spans:
        if s < last_end:
            continue  # overlaps an already-claimed span
        s_si, s_off = idxmap[s]
        e_si, e_off = idxmap[e - 1]
        e_off += 1
        if s_si != e_si and not _gaps_clean(section, segs, s_si, e_si):
            continue
        repl = _esc(mapping[find])
        if s_si == e_si:
            edits.setdefault(s_si, []).append((s_off, e_off, repl))
        else:
            first_len = segs[s_si][1] - segs[s_si][0]
            edits.setdefault(s_si, []).append((s_off, first_len, repl))
            for mid in range(s_si + 1, e_si):
                edits.setdefault(mid, []).append((0, segs[mid][1] - segs[mid][0], ""))
            edits.setdefault(e_si, []).append((0, e_off, ""))
        counts[find] = counts.get(find, 0) + 1
        last_end = e

    if not edits:
        return section, {}
    out = section
    for si in sorted(edits.keys(), reverse=True):
        s, e = segs[si]
        inner = section[s:e]
        for start, end, text in sorted(edits[si], reverse=True):
            inner = inner[:start] + text + inner[end:]
        out = out[:s] + inner + out[e:]
    return out, counts


def detect_placeholders(path: str | Path) -> List[Field]:
    """Detect ``{token}`` template variables across all sections as fields."""
    pkg = HwpxPackage.open(path)
    fields: List[Field] = []
    seen: set[str] = set()
    for sname in _section_names(pkg):
        section = pkg.read(sname).decode("utf-8")
        for name in find_placeholder_names(section):
            if name in seen:
                continue
            seen.add(name)
            fields.append(
                Field(
                    field_id=f"ph:{name}",
                    label=name,
                    kind=KIND_PLACEHOLDER,
                    template="{" + name + "}",
                )
            )
    return fields

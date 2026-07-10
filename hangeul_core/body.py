"""Body-paragraph fields — fillable text that lives OUTSIDE any table.

Many real forms (government report templates, memos) are not built from label
cells or named fields (누름틀) or ``{placeholder}`` tokens — they are running
body paragraphs, often led by an outline marker (``□ ○ ― ※ ∘ • ·`` …) whose
text is placeholder guidance the writer replaces. The cell/inline detectors only
scan table cells, so those paragraphs were invisible and unfillable.

Design (intentionally dynamic, NOT pattern-hardcoded — forms differ per user):

* We do NOT decide which paragraph is "a blank" with form-specific rules. We
  ENUMERATE every non-empty body paragraph as an addressable slot (``b1``,
  ``b2`` …), exposing its current text and a generically-detected marker prefix.
  The client LLM (the brain) decides which to fill and with what.
* Marker detection is Unicode-category based (symbol/punctuation run after
  leading spaces), so any form's bullet style is recognized without a fixed
  ``□○―`` list.
* Filling replaces only the text AFTER the marker prefix (or the whole paragraph
  when there is no marker), editing only ``<hp:t>`` inner text so run/charPr
  markup and byte-preservation of untouched regions are kept.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

from hangeul_core.analyze import _section_names
from hangeul_core.owpml import HwpxPackage
from hangeul_core.schema import KIND_BODY_PARA, Field, normalize_label

_TAG = re.compile(r"<hp:(?:p|tbl)\b[^>]*>|</hp:(?:p|tbl)>")
_T = re.compile(r"<hp:t>(.*?)</hp:t>", re.S)
# Unicode categories that count as an outline marker character (bullets, dashes,
# reference marks, etc.) — general, not a hardcoded 표-specific list.
_MARKER_CATS = {"So", "Sm", "Sk", "Sc", "Po", "Pd", "Pc"}


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def marker_prefix(text: str) -> str:
    """Leading run of ``whitespace + marker-symbols + whitespace`` (may be '').

    Detects the outline marker generically via Unicode category so any form's
    bullet style works. Stops at the first letter/digit/Hangul.
    """
    i = 0
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    j = i
    while j < n and unicodedata.category(text[j]) in _MARKER_CATS:
        j += 1
    if j == i:  # no marker symbol found
        return ""
    while j < n and text[j].isspace():
        j += 1
    return text[:j]


def _body_para_spans(section: str) -> List[Tuple[int, int, bool]]:
    """Raw (start, end, contains_table) of every TOP-LEVEL ``<hp:p>`` (tbl-depth 0).

    Paragraphs inside table cells are skipped (they are handled by the cell
    detectors). A body paragraph that *wraps* a table is flagged so callers can
    skip it as structural rather than fillable.
    """
    spans: List[Tuple[int, int, bool]] = []
    tbl_depth = 0
    p_start = -1
    p_has_table = False
    for m in _TAG.finditer(section):
        tag = m.group(0)
        if tag.startswith("<hp:tbl"):
            if p_start >= 0 and tbl_depth == 0:
                p_has_table = True
            tbl_depth += 1
        elif tag.startswith("</hp:tbl"):
            tbl_depth -= 1
        elif tag.startswith("<hp:p"):
            if tbl_depth == 0 and p_start < 0:
                p_start = m.start()
                p_has_table = False
        else:  # </hp:p>
            if tbl_depth == 0 and p_start >= 0:
                spans.append((p_start, m.end(), p_has_table))
                p_start = -1
    return spans


def _para_text(section: str, start: int, end: int) -> str:
    return "".join(m.group(1) for m in _T.finditer(section[start:end]))


def _iter_body_paras(pkg):
    """Yield ``(global_n, section_name, local_ordinal, text)`` for fillable body
    paragraphs — the single source of truth both the field list and the fill
    index derive from, so their numbering can never drift apart.
    """
    global_n = 0
    for sname in _section_names(pkg):
        section = pkg.read(sname).decode("utf-8")
        local = 0
        for start, end, has_table in _body_para_spans(section):
            if has_table:
                continue  # structural wrapper (wraps a table), not a fill slot
            raw = _para_text(section, start, end)
            text = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            if not text.strip():
                continue
            global_n += 1
            local += 1
            yield global_n, sname, local, text


def detect_body_fields(path: str | Path) -> List[Field]:
    """Enumerate fillable body paragraphs across all sections (PURE, no COM).

    Returns Fields with ``field_id`` ``b{n}`` (document order, non-empty leaf
    paragraphs only), ``template`` = current paragraph text, ``insert_after`` =
    detected marker prefix, ``label`` = readable current text.
    """
    fields: List[Field] = []
    pkg = HwpxPackage.open(path)
    for gn, _sname, _local, text in _iter_body_paras(pkg):
        prefix = marker_prefix(text)
        fields.append(
            Field(
                field_id=f"b{gn}",
                label=normalize_label(text) or f"본문 {gn}",
                kind=KIND_BODY_PARA,
                template=text,
                insert_after=prefix or None,
            )
        )
    return fields


def body_field_index(path: str | Path) -> Dict[str, Tuple[str, int]]:
    """Map body field_id ``b{n}`` -> ``(section_name, section_local_ordinal)``
    so the file/live fill can address the right paragraph within its section."""
    pkg = HwpxPackage.open(path)
    return {f"b{gn}": (sname, local) for gn, sname, local, _text in _iter_body_paras(pkg)}


def resolve_body_targets(path: str | Path, values: Dict[str, str]) -> List[dict]:
    """Peel body-paragraph keys out of *values* (PURE, no COM).

    Returns targets for keys that are body field_ids (``b{n}``); other keys are
    left for the caller's other resolvers. Each target:
    ``{field_id, value, template, marker}`` (value newlines collapsed — a body
    paragraph is a single line).
    """
    by_id = {f.field_id: f for f in detect_body_fields(path)}
    targets: List[dict] = []
    for key, value in values.items():
        f = by_id.get(key)
        if f is None:
            continue
        targets.append(
            {
                "field_id": key,
                "value": value.replace("\n", " "),
                "template": f.template,
                "marker": f.insert_after or "",
            }
        )
    return targets


def replace_body_paragraph(section: str, ordinal_map: Dict[int, str], keep_marker: bool = True) -> Tuple[str, List[int]]:
    """Replace body paragraphs' text by 1-based ordinal within *section*.

    ``ordinal_map`` maps the section-local paragraph ordinal (1-based over
    non-empty leaf body paragraphs, same order as :func:`detect_body_fields`
    assigns within this section) to the new value. Keeps the marker prefix when
    ``keep_marker``; edits only ``<hp:t>`` inner text. Returns
    ``(new_section, applied_ordinals)``.
    """
    spans = [(s, e) for (s, e, has_tbl) in _body_para_spans(section) if not has_tbl]
    # keep only non-empty (must match detect_body_fields numbering)
    ordered: List[Tuple[int, int]] = []
    for s, e in spans:
        if _para_text(section, s, e).strip():
            ordered.append((s, e))

    applied: List[int] = []
    # apply right-to-left so raw offsets stay valid
    for idx in sorted(ordinal_map.keys(), reverse=True):
        if idx < 1 or idx > len(ordered):
            continue
        s, e = ordered[idx - 1]
        para = section[s:e]
        prefix = marker_prefix(
            _para_text(section, s, e).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        ) if keep_marker else ""
        new_para = _splice_after_prefix(para, len(prefix), ordinal_map[idx])
        if new_para is None:
            continue
        section = section[:s] + new_para + section[e:]
        applied.append(idx)
    return section, applied


def _splice_after_prefix(para: str, prefix_len: int, value: str) -> str | None:
    """Within one paragraph's XML, replace concat-text[prefix_len:] with *value*.

    Edits only ``<hp:t>`` inner segments; tags/charPr are preserved. Returns the
    new paragraph XML, or None if the paragraph has no text node.
    """
    segs = [(m.start(1), m.end(1)) for m in _T.finditer(para)]
    if not segs:
        return None
    # char -> (segment_index, local_offset), over concatenated inner text
    idxmap: List[Tuple[int, int]] = []
    for si, (s, e) in enumerate(segs):
        for off in range(e - s):
            idxmap.append((si, off))
    total = len(idxmap)
    start = min(prefix_len, total)
    repl = _esc(value)

    # edits per segment: (local_start, local_end, text)
    edits: Dict[int, List[Tuple[int, int, str]]] = {}
    if start >= total:
        # nothing after the marker yet: append value to the last segment
        last = len(segs) - 1
        seg_len = segs[last][1] - segs[last][0]
        edits[last] = [(seg_len, seg_len, repl)]
    else:
        s_si, s_off = idxmap[start]
        e_si, e_off = idxmap[total - 1]
        e_off += 1
        if s_si == e_si:
            edits[s_si] = [(s_off, e_off, repl)]
        else:
            first_len = segs[s_si][1] - segs[s_si][0]
            edits[s_si] = [(s_off, first_len, repl)]
            for mid in range(s_si + 1, e_si):
                edits[mid] = [(0, segs[mid][1] - segs[mid][0], "")]
            edits[e_si] = [(0, e_off, "")]

    out = para
    for si in sorted(edits.keys(), reverse=True):
        s, e = segs[si]
        inner = para[s:e]
        for local_start, local_end, text in sorted(edits[si], reverse=True):
            inner = inner[:local_start] + text + inner[local_end:]
        out = out[:s] + inner + out[e:]
    return out

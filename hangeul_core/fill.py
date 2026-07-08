"""Format-preserving fill engine.

Fills values into an HWPX form while touching *only* the target cells' bytes.
Location is done by walking the raw section XML and matching each cell's
``<hp:cellAddr>`` within its table (tracking table nesting depth), so unrelated
regions stay byte-identical. Learned rules baked in:

* multi-line values become real ``<hp:p>`` paragraphs (never raw ``\\n`` in ``<hp:t>``),
* bullet (auto-marker) cells do not get a duplicated ``-`` / ``∘``,
* ``normalize_spacing`` sets filled runs to spacing 0 via cloned charPr,
  without affecting untouched runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dfield
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hangeul_core.analyze import analyze
from hangeul_core.inline import MARKERS
from hangeul_core.locate import detect_placeholders, replace_placeholders
from hangeul_core.markpen import markpen_regions, replace_markpen
from hangeul_core.owpml import HwpxPackage
from hangeul_core.schema import KIND_INLINE_BLANK, label_key
from hangeul_core.understand import understand

_TAG = re.compile(r"<(/?)([A-Za-z][\w:.\-]*)([^>]*?)(/?)>")
_T = re.compile(r"<hp:t\s*/>|<hp:t>(.*?)</hp:t>", re.S)
_MARKER_PREFIX = re.compile(r"^\s*[-∘○•·]\s*")


@dataclass
class FillResult:
    filled: List[dict] = dfield(default_factory=list)
    skipped: List[dict] = dfield(default_factory=list)
    out_path: Optional[str] = None


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _match_close(text: str, start: int, tag: str) -> int:
    """Return end offset of the element opened at *start* (matching close tag)."""
    depth = 0
    for m in _TAG.finditer(text, start):
        if m.group(2) != tag or m.group(4) == "/":
            continue
        if m.group(1) == "/":
            depth -= 1
            if depth == 0:
                return m.end()
        else:
            depth += 1
    return len(text)


def _find_cell_span(section: str, table_index: int, row: int, col: int) -> Optional[Tuple[int, int]]:
    """Byte span of the target cell's ``<hp:tc>...</hp:tc>`` (nesting-aware)."""
    open_tbl = 0
    seen_tbl = 0
    target_level: Optional[int] = None
    cell_start: Optional[int] = None
    for m in _TAG.finditer(section):
        closing = m.group(1) == "/"
        name = m.group(2)
        attrs = m.group(3)
        selfclose = m.group(4) == "/"
        if name == "hp:tbl" and not selfclose:
            if not closing:
                open_tbl += 1
                seen_tbl += 1
                if seen_tbl == table_index:
                    target_level = open_tbl
            else:
                open_tbl -= 1
                if target_level is not None and open_tbl < target_level:
                    # exited the target table without a match; do not spill into siblings
                    return None
        elif name == "hp:tc" and not selfclose and not closing:
            if target_level is not None and open_tbl == target_level:
                cell_start = m.start()
        elif name == "hp:cellAddr" and target_level is not None and open_tbl == target_level:
            ca = dict(re.findall(r'(\w+)="(-?\d+)"', attrs))
            if (
                ca.get("rowAddr") == str(row)
                and ca.get("colAddr") == str(col)
                and cell_start is not None
            ):
                return cell_start, _match_close(section, cell_start, "hp:tc")
    return None


def _first_paragraph(tc_xml: str) -> Optional[Tuple[int, int, str]]:
    pm = re.search(r"<hp:p\b[^>]*>", tc_xml)
    if not pm:
        return None
    p_start = pm.start()
    p_end = _match_close(tc_xml, p_start, "hp:p")
    return p_start, p_end, tc_xml[p_start:p_end]


def _run_open_of(pblock: str) -> Optional[str]:
    """First run's open tag, converting a self-closing ``<hp:run .../>`` to open."""
    rm = re.search(r"<hp:run\b[^>]*?/>|<hp:run\b[^>]*>", pblock)
    if not rm:
        return None
    tag = rm.group(0)
    return (tag[:-2].rstrip() + ">") if tag.endswith("/>") else tag


def _build_paragraphs(pblock, lines, alloc, first_prefix="") -> Optional[str]:
    """Replace a paragraph with N paragraphs (one per line) — real line breaks."""
    pm = re.match(r"<hp:p\b[^>]*>", pblock)
    run_open = _run_open_of(pblock)
    if not pm or not run_open:
        return None
    p_open = pm.group(0)
    out = []
    for i, ln in enumerate(lines):
        po = p_open if i == 0 else re.sub(r'\bid="[^"]*"', 'id="%d"' % alloc(), p_open, count=1)
        inner = (first_prefix + _esc(ln)) if i == 0 else _esc(ln)
        out.append(po + run_open + "<hp:t>" + inner + "</hp:t></hp:run></hp:p>")
    return "".join(out)


def _splice_colon(pblock: str, anchor: str, value: str) -> Optional[str]:
    """Insert *value* after the colon *anchor*, in whichever text node holds it."""
    for m in re.finditer(r"<hp:t>(.*?)</hp:t>", pblock, re.S):
        cur = m.group(1)
        idx = cur.find(anchor)
        if idx < 0:
            continue
        pos = idx + len(anchor)
        rest = cur[pos:]
        tail = rest if rest.startswith(" ") else ((" " + rest) if rest else "")
        newcur = cur[:pos] + " " + _esc(value) + tail
        return pblock[: m.start()] + "<hp:t>" + newcur + "</hp:t>" + pblock[m.end():]
    return None


def _set_empty(pblock: str, esc_value: str) -> Optional[str]:
    """Place text into an empty cell whose run may be self-closing or textless."""
    tm = _T.search(pblock)
    if tm:  # an (empty) <hp:t> exists -> fill it
        return pblock[: tm.start()] + "<hp:t>" + esc_value + "</hp:t>" + pblock[tm.end():]
    m = re.search(r"<hp:run\b([^>]*?)/>", pblock)  # self-closing empty run
    if m:
        return (
            pblock[: m.start()]
            + "<hp:run" + m.group(1) + "><hp:t>" + esc_value + "</hp:t></hp:run>"
            + pblock[m.end():]
        )
    m = re.search(r"(<hp:run\b[^>]*>)(</hp:run>)", pblock)  # empty open/close run
    if m:
        return pblock[: m.start()] + m.group(1) + "<hp:t>" + esc_value + "</hp:t>" + m.group(2) + pblock[m.end():]
    return None


def _apply_inline(tc: str, fld, value: str, respect_bullets: bool = True) -> Optional[str]:
    """Splice an inline blank (marker or colon) anywhere in the whole cell.

    Inline blanks can live in any paragraph/run of the cell (e.g. '은행명' and
    '계좌번호' are separate paragraphs), so this operates on the full ``<hp:tc>``.
    """
    value = value.replace("\n", " ")  # inline blanks are single-line
    anchor = fld.insert_after or ""
    if anchor.endswith(":"):
        return _splice_colon(tc, anchor, value)
    if anchor in MARKERS:
        if respect_bullets:
            # strip only a leading duplicate of THIS cell's marker, not other
            # content that merely starts with a different marker char (e.g. "○○대학교").
            value = re.sub(r"^\s*" + re.escape(anchor) + r"\s*", "", value, count=1)
        for m in re.finditer(r"<hp:t>(.*?)</hp:t>", tc, re.S):
            cur = m.group(1)
            if cur.strip() == anchor:
                base = cur.rstrip()
                sep = "" if base.endswith(" ") else " "
                return tc[: m.start()] + "<hp:t>" + base + sep + _esc(value) + "</hp:t>" + tc[m.end():]
    return None


def _apply_cell(pblock: str, cell, value: str, respect_bullets: bool, alloc) -> Optional[str]:
    """Fill an empty cell (set) or append to a non-empty cell (bullet-aware)."""
    tm = _T.search(pblock)
    cur = (tm.group(1) if (tm and tm.lastindex) else "") if tm else ""
    is_empty = (tm is None) or (cur.strip() == "")
    lines = value.split("\n")

    # empty cell -> set (handles self-closing / textless runs)
    if is_empty:
        if len(lines) == 1:
            return _set_empty(pblock, _esc(value))
        return _build_paragraphs(pblock, lines, alloc)

    # non-empty cell -> append (bullet-aware dedup)
    v = value
    if respect_bullets and cell.para_bullet:
        v = _MARKER_PREFIX.sub("", v)
    vlines = v.split("\n")
    base = cur.rstrip()
    sep = "" if base.endswith(" ") else " "
    if len(vlines) == 1:
        return pblock[: tm.start()] + "<hp:t>" + base + sep + _esc(v) + "</hp:t>" + pblock[tm.end():]
    return _build_paragraphs(pblock, vlines, alloc, first_prefix=base + sep)


def _clone_charpr_spacing0(header: str, char_pr: str) -> Tuple[str, Optional[str]]:
    """Add a spacing-0 clone of *char_pr* to header; return (header, new_id)."""
    m = re.search(r'<hh:charPr id="' + re.escape(char_pr) + r'"(?:(?!</hh:charPr>).)*</hh:charPr>', header, re.S)
    if not m:
        return header, None
    ids = [int(x) for x in re.findall(r'<hh:charPr id="(\d+)"', header)]
    new_id = (max(ids) + 1) if ids else 1
    block = re.sub(r'id="' + re.escape(char_pr) + r'"', 'id="%d"' % new_id, m.group(0), count=1)

    def zero(mm):
        inner = re.sub(r'(hangul|latin|hanja|japanese|other|symbol|user)="-?\d+"', lambda x: x.group(1) + '="0"', mm.group(1))
        return "<hh:spacing " + inner + "/>"

    block = re.sub(r"<hh:spacing ([^/]*)/>", zero, block)
    header = header.replace("</hh:charProperties>", block + "</hh:charProperties>", 1)
    header = re.sub(
        r'<hh:charProperties itemCnt="(\d+)">',
        lambda x: '<hh:charProperties itemCnt="%d">' % (int(x.group(1)) + 1),
        header,
        count=1,
    )
    return header, str(new_id)


def fill(
    path: str | Path,
    values: Dict[str, str],
    out_path: Optional[str | Path] = None,
    *,
    respect_bullets: bool = True,
    normalize_spacing: bool = False,
) -> FillResult:
    """Fill *values* (keyed by field_id or label) into the form at *path*."""
    result = analyze(path)
    cells = {c.field_id: c for c in result.all_cells()}
    fields = understand(path).fields + list(_inline(path))
    by_id = {f.field_id: f for f in fields}
    by_label: Dict[str, object] = {}
    for f in fields:
        by_label.setdefault(label_key(f.label), f)

    # Section-wide {placeholder} tokens are resolved separately from the
    # cell-based path: keys matching a token name (or "ph:<name>") are routed
    # to a whole-document replacement pass after the per-cell fills.
    ph_names = {f.label for f in detect_placeholders(path)}
    ph_values: Dict[str, str] = {}

    # markpen (형광펜) highlighted example values: selectable by field_id/label/sample.
    mk_regions = markpen_regions(path)
    mk_selectors: Dict[str, List[Tuple[str, int]]] = {}
    for r in mk_regions:
        for sel in {r["field_id"], r["label"], r["sample"]}:
            mk_selectors.setdefault(sel, []).append((r["section"], r["occ"]))
    mk_edits: Dict[str, Dict[int, str]] = {}

    pkg = HwpxPackage.open(path)
    header = pkg.read("Contents/header.xml").decode("utf-8")
    header_changed = False
    sections: Dict[str, str] = {}

    def section_text(name: str) -> str:
        if name not in sections:
            sections[name] = pkg.read(name).decode("utf-8")
        return sections[name]

    # High base so newly minted paragraph ids never collide with real ones
    # (real ids are <= 2^31), across any number of sections.
    counter = [4_290_000_000]

    def alloc() -> int:
        counter[0] += 1
        return counter[0]

    filled: List[dict] = []
    skipped: List[dict] = []
    spacing_clone: Dict[str, Optional[str]] = {}

    for key, value in values.items():
        value = value.replace("\r\n", "\n").replace("\r", "\n")  # normalize line breaks
        ph_name = key[3:] if key.startswith("ph:") else key
        if ph_name in ph_names:
            ph_values[ph_name] = value.replace("\n", " ")  # tokens are single-line
            continue
        if key in mk_selectors:
            for sname, occ in mk_selectors[key]:
                mk_edits.setdefault(sname, {})[occ] = value.replace("\n", " ")
            continue
        fld = by_id.get(key) or by_label.get(label_key(key))
        if fld is None:
            skipped.append({"key": key, "reason": "no matching field"})
            continue
        base = fld.field_id.split("#")[0]
        cell = cells.get(base)
        if cell is None or not cell.section:
            skipped.append({"key": key, "reason": "target cell not found"})
            continue
        section = section_text(cell.section)
        span = _find_cell_span(section, cell.table_in_section, cell.row, cell.col)
        if span is None:
            skipped.append({"key": key, "reason": "cell not located in xml"})
            continue
        cs, ce = span
        tc = section[cs:ce]

        if fld.kind == KIND_INLINE_BLANK:
            newtc = _apply_inline(tc, fld, value, respect_bullets)
            if newtc is None:
                skipped.append({"key": key, "reason": "could not apply value"})
                continue
        else:
            fp = _first_paragraph(tc)
            if fp is None:
                skipped.append({"key": key, "reason": "no paragraph in cell"})
                continue
            p_start, p_end, pblock = fp
            if normalize_spacing and cell.char_pr:
                if cell.char_pr not in spacing_clone:
                    header, new_id = _clone_charpr_spacing0(header, cell.char_pr)
                    spacing_clone[cell.char_pr] = new_id
                    header_changed = header_changed or new_id is not None
                new_id = spacing_clone[cell.char_pr]
                if new_id:
                    pblock = re.sub(
                        r'(<hp:run\b[^>]*charPrIDRef=")' + re.escape(cell.char_pr) + r'(")',
                        r"\g<1>" + new_id + r"\g<2>",
                        pblock,
                    )
            newp = _apply_cell(pblock, cell, value, respect_bullets, alloc)
            if newp is None:
                skipped.append({"key": key, "reason": "could not apply value"})
                continue
            newtc = tc[:p_start] + newp + tc[p_end:]

        sections[cell.section] = section[:cs] + newtc + section[ce:]
        filled.append({"field_id": fld.field_id, "label": fld.label, "value": value})

    # markpen pass: swap only highlighted text, keeping markpenBegin/End tags.
    if mk_edits:
        region_by_pair = {(r["section"], r["occ"]): r for r in mk_regions}
        for sname, occ_values in mk_edits.items():
            text = section_text(sname)
            newtext, applied = replace_markpen(text, occ_values, _esc)
            if applied:
                sections[sname] = newtext
            applied_set = set(applied)
            for occ, val in occ_values.items():
                r = region_by_pair[(sname, occ)]
                if occ in applied_set:
                    filled.append({"field_id": r["field_id"], "label": r["label"], "value": val})
                else:
                    skipped.append({"key": r["field_id"], "reason": "markpen span has inline markup"})

    # Whole-document {placeholder} pass (touches only <hp:t> text of matched tokens).
    if ph_values:
        applied_all: set[str] = set()
        from hangeul_core.analyze import _section_names  # ordered section list

        for sname in _section_names(pkg):
            text = section_text(sname)
            newtext, applied = replace_placeholders(text, ph_values)
            if applied:
                sections[sname] = newtext
                applied_all.update(applied)
        for name in applied_all:
            filled.append({"field_id": f"ph:{name}", "label": name, "value": ph_values[name]})
        for name in ph_values:
            if name not in applied_all:
                skipped.append({"key": name, "reason": "placeholder token not found"})

    for name, text in sections.items():
        pkg.replace(name, text.encode("utf-8"))
    if header_changed:
        pkg.replace("Contents/header.xml", header.encode("utf-8"))

    if out_path is not None:
        pkg.save(out_path)
    return FillResult(filled=filled, skipped=skipped, out_path=str(out_path) if out_path else None)


def _inline(path):
    # local import to avoid a heavy import at module load
    from hangeul_core.inline import detect_inline

    return detect_inline(path)

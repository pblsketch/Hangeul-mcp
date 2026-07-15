"""Character-property (charPr) helpers for byte-preserving bold on addressed edits.

The addressed/live pipeline replaces run *text* but never touched run *formatting*:
`_replace_text_nodes` dumps the value into the first ``<hp:t>`` and inherits
whatever ``charPrIDRef`` was already there. To make a question stem bold or a
choice non-bold we must resolve a ``charPr`` id whose only difference from the
run's current one is the presence of ``<hh:bold/>`` and repoint the run at it.

This mirrors python-hwpx ``ensure_run_style`` (find-or-create a charPr and
reassign ``charPrIDRef``) but stays in our string engine so the header is a
byte-preserving *append* — every existing ``charPr`` keeps its bytes and id.

OWPML ``charPr`` is a fixed *sequence*: ``fontRef, ratio, spacing, relSz,
offset, [bold], [italic], underline, strikeout, outline, shadow, ...``. So
``<hh:bold/>`` must be inserted at its slot (immediately before
``<hh:underline``), not appended, or the header fails XSD validation.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# The bold marker — usually self-closing (<hh:bold/>), but tolerate the paired
# empty form (<hh:bold></hh:bold>) that is equally valid XML.
_BOLD_RE = re.compile(r"<hh:bold\b[^>]*?(?:/>|>\s*</hh:bold>)")
# OWPML charPr sequence order is: ... offset, [bold], [italic], underline, ...
# so bold must be inserted BEFORE italic when italic is present, else before
# underline, else right after offset.
_ITALIC_RE = re.compile(r"<hh:italic\b")
_UNDERLINE_RE = re.compile(r"<hh:underline\b")
_OFFSET_END_RE = re.compile(r"(<hh:offset\b[^>]*/>)")
_CHARPR_ID_RE = re.compile(r'<hh:charPr id="(\d+)"')


def _charpr_block(header: str, char_pr: str) -> Optional[str]:
    """Return the full ``<hh:charPr id="char_pr">…</hh:charPr>`` block, or None."""
    m = re.search(
        r'<hh:charPr id="' + re.escape(char_pr) + r'"(?:(?!</hh:charPr>).)*</hh:charPr>',
        header,
        re.S,
    )
    return m.group(0) if m else None


def _has_bold(block: str) -> bool:
    return bool(_BOLD_RE.search(block))


def _with_bold(block: str, bold: bool) -> Optional[str]:
    """Return *block* with ``<hh:bold/>`` present iff *bold*.

    Returns None (fail-closed) if bold must be added but no valid slot is found,
    so callers never emit a schema-invalid header.
    """
    present = _has_bold(block)
    if present == bold:
        return block
    if not bold:
        # Remove the bold marker (self-closing or paired form).
        return _BOLD_RE.sub("", block, count=1)
    # Insert at the fixed slot: before italic (bold precedes italic), else before
    # underline, else right after the offset element.
    if _ITALIC_RE.search(block):
        return _ITALIC_RE.sub("<hh:bold/><hh:italic", block, count=1)
    if _UNDERLINE_RE.search(block):
        return _UNDERLINE_RE.sub("<hh:bold/><hh:underline", block, count=1)
    if _OFFSET_END_RE.search(block):
        return _OFFSET_END_RE.sub(r"\1<hh:bold/>", block, count=1)
    return None


def _strip_id(block: str) -> str:
    """Normalize a charPr block for identity comparison (id removed)."""
    return _CHARPR_ID_RE.sub('<hh:charPr id="_"', block, count=1)


def ensure_char_pr(header: str, base_char_pr: str, *, bold: bool) -> Tuple[str, Optional[str]]:
    """Resolve a charPr id equal to *base_char_pr* except for bold == *bold*.

    Returns ``(header, char_pr_id)``:
      * base already matches           -> (header unchanged, base_char_pr)
      * an existing charPr matches      -> (header unchanged, that id)  [reuse]
      * otherwise                       -> (header + one appended charPr, new id)
        with ``charProperties itemCnt`` incremented by one.

    Returns ``(header, None)`` fail-closed if *base_char_pr* is missing or the
    bold marker cannot be placed at its schema slot.
    """
    base = _charpr_block(header, base_char_pr)
    if base is None:
        return header, None
    if _has_bold(base) == bold:
        return header, base_char_pr

    target = _with_bold(base, bold)
    if target is None:
        return header, None
    target_norm = _strip_id(target)

    # Find-or-reuse: an existing charPr whose body already equals the target.
    for m in re.finditer(r"<hh:charPr id=\"(\d+)\"(?:(?!</hh:charPr>).)*</hh:charPr>", header, re.S):
        if _strip_id(m.group(0)) == target_norm:
            return header, m.group(1)

    ids = [int(x) for x in _CHARPR_ID_RE.findall(header)]
    new_id = (max(ids) + 1) if ids else 0
    new_block = _CHARPR_ID_RE.sub('<hh:charPr id="%d"' % new_id, target, count=1)
    header = header.replace("</hh:charProperties>", new_block + "</hh:charProperties>", 1)
    # Tolerate attribute order / whitespace: match itemCnt anywhere in the tag.
    header = re.sub(
        r'(<hh:charProperties\b[^>]*\bitemCnt=")(\d+)(")',
        lambda x: x.group(1) + str(int(x.group(2)) + 1) + x.group(3),
        header,
        count=1,
    )
    return header, str(new_id)


# A run element: self-closing (<hp:run .../>) OR paired. Matching the
# self-closing form first stops it from swallowing the following run's close tag
# (runs never nest runs, so the paired non-greedy match is safe).
_RUN_RE = re.compile(r"<hp:run\b[^>]*/>|<hp:run\b[^>]*>.*?</hp:run>", re.S)
_RUN_CPR_RE = re.compile(r'(<hp:run\b[^>]*\bcharPrIDRef=")(\d+)(")')
# A text node carrying at least one non-whitespace character.
_NONEMPTY_T_RE = re.compile(r"<hp:t>(?:[^<]*\S[^<]*)</hp:t>", re.S)


def set_runs_bold(block: str, header: str, bold: bool) -> Tuple[str, str]:
    """Repoint every text-bearing run in *block* at a charPr with the given bold.

    Applies uniformly to all runs whose ``<hp:t>`` holds non-whitespace text —
    which is exactly the desired "whole stem bold / whole choice normal"
    semantic, and naturally covers multiline clones (each clone is its own run).
    Runs with empty/whitespace text (markers, spacers) keep their formatting.
    Returns ``(block, header)`` with the header possibly extended by one charPr.
    """
    # A run wrapping a table would break run matching (the first </hp:run>
    # belongs to an inner cell run); bold never targets such a block (body paras
    # with tables and nested-table cells are filtered upstream), so leave it
    # untouched rather than risk mis-parsing.
    if "<hp:tbl" in block:
        return block, header
    out: list[str] = []
    last = 0
    for m in _RUN_RE.finditer(block):
        run = m.group(0)
        out.append(block[last:m.start()])
        if _NONEMPTY_T_RE.search(run):
            cpr_m = _RUN_CPR_RE.search(run)
            if cpr_m:
                header, new_id = ensure_char_pr(header, cpr_m.group(2), bold=bold)
                if new_id is not None and new_id != cpr_m.group(2):
                    run = _RUN_CPR_RE.sub(
                        lambda mm: mm.group(1) + new_id + mm.group(3), run, count=1
                    )
        out.append(run)
        last = m.end()
    out.append(block[last:])
    return "".join(out), header


_CHARPR_BLOCK_RE = re.compile(r"<hh:charPr id=\"(\d+)\"(?:(?!</hh:charPr>).)*</hh:charPr>", re.S)


_BOLD_IDS_RE = re.compile(r"<hh:charPr id=\"(\d+)\"(?:(?!</hh:charPr>).)*?<hh:bold\s*/>", re.S)
_EMPTY_T_RUN_RE = re.compile(
    r"<hp:run\b[^>]*\bcharPrIDRef=\"(\d+)\"[^>]*>(?:(?!</hp:run>).)*?"
    r"(?:<hp:t\s*/>|<hp:t>\s*</hp:t>)(?:(?!</hp:run>).)*?</hp:run>",
    re.S,
)


def bold_charpr_ids(header: str) -> set[str]:
    """Ids of every charPr carrying ``<hh:bold/>``."""
    return set(_BOLD_IDS_RE.findall(header))


def count_stray_empty_bold_runs(section: str, header: str) -> int:
    """Count runs with empty/whitespace text pointing at a bold charPr.

    These render as bold blank lines — the exact artifact the old text-only fill
    left behind — so a clean structural edit should keep this at zero.
    """
    bold = bold_charpr_ids(header)
    if not bold:
        return 0
    return sum(1 for cid in _EMPTY_T_RUN_RE.findall(section) if cid in bold)


def header_charpr_order_ok(header: str) -> Tuple[bool, list[str]]:
    """Verify each charPr keeps ``<hh:bold/>`` at its OWPML sequence slot.

    python-hwpx ``validate_package`` does not flag a mis-ordered ``<hh:bold/>``,
    so this is the targeted guard that makes the fail-closed gate real for the
    element we mutate: bold must sit after ``<hh:offset>`` and before
    ``<hh:underline>`` (and before strikeout/outline/shadow) when present.
    """
    errors: list[str] = []
    # bold must sit after offset and before italic/underline/strikeout/outline/shadow.
    followers = ("<hh:italic", "<hh:underline", "<hh:strikeout", "<hh:outline", "<hh:shadow")
    for m in _CHARPR_BLOCK_RE.finditer(header):
        block = m.group(0)
        bpos = block.find("<hh:bold")
        if bpos < 0:
            continue
        opos = block.find("<hh:offset")
        if opos >= 0 and bpos < opos:
            errors.append(f"charPr {m.group(1)}: <hh:bold/> before <hh:offset>")
        for follower in followers:
            fpos = block.find(follower)
            if fpos >= 0 and bpos > fpos:
                errors.append(f"charPr {m.group(1)}: <hh:bold/> after {follower}>")
                break
    return (not errors), errors

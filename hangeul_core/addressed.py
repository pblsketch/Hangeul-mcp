from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from hangeul_core.analyze import _section_names, analyze
from hangeul_core.body import _body_para_spans, _render, body_field_index, marker_prefix, replace_body_paragraph
from hangeul_core.edit_session import (
    OWN_TEXT_SUBSTRATE,
    _JOURNAL_VERSION,
    _journal_path,
    _sha256_path,
    _snapshot_path,
    _utc_now,
)
from hangeul_core.fill import _find_cell_span, _match_close
from hangeul_core.owpml import HwpxPackage

_TARGET = re.compile(r"^t(?P<table>\d+)\.r(?P<row>\d+)\.c(?P<col>\d+)$")
_PARA_TARGET = re.compile(r"^(?P<cell>t\d+\.r\d+\.c\d+)\.p(?P<ordinal>\d+)$")
_BODY_TARGET = re.compile(r"^b(?P<ordinal>\d+)$")
_TEXT_NODE = re.compile(r"<hp:t>(.*?)</hp:t>", re.S)
_PARA_ID = re.compile(r'\bid="([^"]*)"')


@dataclass
class _AddressedSession:
    session_id: str
    source_path: str
    source_sha256: str
    edits: List[dict] = field(default_factory=list)
    changed_sections: Dict[str, str] = field(default_factory=dict)
    changed_entries: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    audit: List[str] = field(default_factory=list)
    applied: bool = False


_SESSIONS: Dict[str, _AddressedSession] = {}
_INSPECTION_CACHE_MAX = 32
_INSPECTION_CACHE: "OrderedDict[tuple[str, str], str]" = OrderedDict()

def _inspection_cache_key(path: str | Path, source_sha256: str) -> tuple[str, str]:
    return (str(Path(path).resolve()), source_sha256)

def _inspection_cache_get(path: str | Path, source_sha256: str) -> Dict[str, object] | None:
    key = _inspection_cache_key(path, source_sha256)
    payload = _INSPECTION_CACHE.get(key)
    if payload is None:
        return None
    _INSPECTION_CACHE.move_to_end(key)
    return json.loads(payload)

def _inspection_cache_put(path: str | Path, source_sha256: str, value: Dict[str, object]) -> None:
    key = _inspection_cache_key(path, source_sha256)
    _INSPECTION_CACHE[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    _INSPECTION_CACHE.move_to_end(key)
    while len(_INSPECTION_CACHE) > _INSPECTION_CACHE_MAX:
        _INSPECTION_CACHE.popitem(last=False)

def _same_document_path(left: str | Path, right: str | Path) -> bool:
    left_path = Path(left)
    right_path = Path(right)
    try:
        if left_path.exists() and right_path.exists() and right_path.samefile(left_path):
            return True
    except OSError:
        pass
    return left_path.resolve() == right_path.resolve()


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _snippet(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _replace_text_nodes(xml: str, value: str) -> str | None:
    matches = list(_TEXT_NODE.finditer(xml))
    if not matches:
        return None
    out = xml
    first = True
    for match in reversed(matches):
        replacement = _esc(value) if first else ""
        out = out[: match.start(1)] + replacement + out[match.end(1) :]
        first = False
    return out


# <hp:linesegarray> is Hangul's cached line layout. Leaving the old cache on a
# paragraph whose text we just changed makes Hangul paint the new (longer) text
# into the old line boxes — glyphs overlap on screen (desktop capture
# 2026-07-15). The cache is optional; Hangul recomputes it when absent.
_LINESEG = re.compile(r"<hp:linesegarray(?:\s[^>]*)?(?:/>|>.*?</hp:linesegarray>)", re.S)

# Prose-safe grammar in hangeul_core.body treats a lone '-' as punctuation, but
# inside TEMPLATE CELLS the dash family and bare-marker-only paragraphs are
# list markers (Korean official-document 개조식: □ ○ ▷ • - ㆍ …).
_DASH_MARKERS = "-－–—ㆍ·"


def _strip_linesegs(xml: str | None) -> str | None:
    return None if xml is None else _LINESEG.sub("", xml)


def _paragraph_marker(text: str) -> str:
    """Leading list marker of a CELL paragraph (``''`` if none).

    Extends :func:`hangeul_core.body.marker_prefix` (kept prose-safe for body
    paragraphs) with the dash family and bare marker-only paragraphs.
    """
    marker = marker_prefix(text)
    if marker:
        return marker
    head = text.lstrip()
    lead = text[: len(text) - len(head)]
    if head and head[0] in _DASH_MARKERS and (len(head) == 1 or head[1].isspace()):
        tail = head[1:]
        return lead + head[0] + tail[: len(tail) - len(tail.lstrip())]
    if head:
        bare = marker_prefix(text + " ")
        if bare and bare.strip() == text.strip():
            return text
    return ""


def _marker_lines(marker: str, lines: List[str]) -> List[str]:
    prefix = marker.rstrip()
    return [f"{prefix} {line}" if line.strip() else line for line in lines]


def _multiline_paragraph_clones(base_block: str, lines: List[str]) -> str | None:
    clones: List[str] = []
    for line in lines:
        clone = _strip_linesegs(_replace_text_nodes(base_block, line))
        if clone is None:
            return None
        clones.append(clone)
    return "".join(clones)


def _edit_cell_of(item: dict) -> str:
    target = str(item.get("target") or "")
    para = _PARA_TARGET.match(target)
    if para:
        return para.group("cell")
    return target if _TARGET.match(target) else ""


def _ordered_edits(edits: List[dict]) -> List[dict]:
    """Apply same-cell paragraph edits bottom-up (descending pN).

    Multiline edits INSERT paragraphs; applying high ordinals first keeps the
    lower ordinals still waiting in the batch valid.
    """
    indexed = list(enumerate(edits))
    cell_first_index: Dict[str, int] = {}
    for idx, item in indexed:
        match = _PARA_TARGET.match(str(item.get("target") or ""))
        if match and match.group("cell") not in cell_first_index:
            cell_first_index[match.group("cell")] = idx

    def sort_key(pair):
        idx, item = pair
        match = _PARA_TARGET.match(str(item.get("target") or ""))
        if match:
            return (cell_first_index[match.group("cell")], -int(match.group("ordinal")))
        return (idx, 0)

    return [item for _, item in sorted(indexed, key=sort_key)]


def _multiline_conflicts(edits: List[dict]) -> set[str]:
    """Targets of multiline edits sharing a cell with any other edit (fail closed)."""
    cell_counts: Dict[str, int] = {}
    for item in edits:
        cell = _edit_cell_of(item)
        if cell:
            cell_counts[cell] = cell_counts.get(cell, 0) + 1
    conflicted: set[str] = set()
    for item in edits:
        if "\n" not in str(item.get("value") or ""):
            continue
        cell = _edit_cell_of(item)
        if cell and cell_counts.get(cell, 0) > 1:
            conflicted.add(str(item.get("target") or ""))
    return conflicted


def _context_digest(target: str, expected_text: str, value: str) -> str:
    blob = json.dumps(
        {"target": target, "expected_text": expected_text, "value": value},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _section_index_map(pkg: HwpxPackage) -> Dict[str, int]:
    return {name: idx for idx, name in enumerate(_section_names(pkg), start=1)}


def _paragraph_text(block: str) -> str:
    return _render("".join(m.group(1) for m in _TEXT_NODE.finditer(block)))


def _paragraph_id(block: str) -> str:
    match = _PARA_ID.search(block)
    return match.group(1) if match else ""


def _paragraph_blocks(xml: str) -> List[dict]:
    items: List[dict] = []
    start = 0
    ordinal = 0
    while True:
        p_start = xml.find("<hp:p", start)
        if p_start < 0:
            break
        p_end = _match_close(xml, p_start, "hp:p")
        block = xml[p_start:p_end]
        ordinal += 1
        items.append(
            {
                "ordinal": ordinal,
                "start": p_start,
                "end": p_end,
                "block": block,
                "paragraph_id": _paragraph_id(block),
                "text": _paragraph_text(block),
            }
        )
        start = p_end
    return items


def _body_paragraphs_in_section(section: str, section_number: int) -> List[dict]:
    items: List[dict] = []
    local_body = 0
    for start, end, has_table in _body_para_spans(section):
        if has_table:
            continue
        block = section[start:end]
        text = _paragraph_text(block)
        if not text.strip():
            continue
        local_body += 1
        items.append(
            {
                "target": f"s{section_number}.p{local_body}",
                "start": start,
                "end": end,
                "block": block,
                "paragraph_id": _paragraph_id(block),
                "paragraph_ordinal": local_body,
                "text": text,
            }
        )
    return items


def _cell_paragraph_entry(section: str, cell, ordinal: int) -> tuple[tuple[int, int], str, dict] | None:
    span = _find_cell_span(section, cell.table_in_section, cell.row, cell.col)
    if span is None:
        return None
    tc_xml = section[span[0]:span[1]]
    paragraphs = _paragraph_blocks(tc_xml)
    if ordinal < 1 or ordinal > len(paragraphs):
        return None
    return span, tc_xml, paragraphs[ordinal - 1]

def _compact_region_item(item: dict) -> dict:
    compact = {
        "target": item["target"],
        "kind": item["kind"],
        "text": item["text"],
        "snippet": item["snippet"],
    }
    for key in (
        "paragraph_target",
        "paragraph_targets",
        "paragraph_count",
        "paragraphs",
        "table",
        "row",
        "col",
        "aliases",
        "paragraph_id",
        "paragraph_ordinal",
        "paragraph_ids",
        "reason",
        "editable",
    ):
        if key in item:
            compact[key] = item[key]
    return compact


def inspect_editable_regions(path: str | Path, compact: bool = False) -> Dict[str, object]:
    source = Path(path)
    for _ in range(2):
        source_sha256 = _sha256_path(source)
        cached = _inspection_cache_get(source, source_sha256)
        if cached is None:
            pkg = HwpxPackage.open(source)
            section_index = _section_index_map(pkg)
            regions: List[dict] = []
            unsupported_controls: List[dict] = []

            global_body = 0
            for sname in _section_names(pkg):
                section_items = _body_paragraphs_in_section(pkg.read(sname).decode("utf-8"), section_index[sname])
                for item in section_items:
                    global_body += 1
                    regions.append(
                        {
                            "target": f"b{global_body}",
                            "kind": "body_para",
                            "container": "body",
                            "section": sname,
                            "section_index": section_index[sname],
                            "paragraph_target": item["target"],
                            "paragraph_targets": [item["target"]],
                            "paragraph_id": item["paragraph_id"],
                            "paragraph_ordinal": item["paragraph_ordinal"],
                            "text": item["text"],
                            "snippet": _snippet(item["text"]),
                            "editable": True,
                            "aliases": [item["target"]],
                            "source_sha256": source_sha256,
                        }
                    )

            result = analyze(source)
            for cell in result.all_cells():
                if not cell.section:
                    continue
                if cell.has_nested_table:
                    unsupported_controls.append(
                        {
                            "target": cell.field_id,
                            "kind": "cell",
                            "container": "table_cell",
                            "section": cell.section,
                            "section_index": section_index[cell.section],
                            "table": cell.table,
                            "row": cell.row,
                            "col": cell.col,
                            "text": cell.text,
                            "snippet": _snippet(cell.text),
                            "editable": False,
                            "reason": "nested_table",
                            "source_sha256": source_sha256,
                        }
                    )
                    continue
                section = pkg.read(cell.section).decode("utf-8")
                span = _find_cell_span(section, cell.table_in_section, cell.row, cell.col)
                if span is None:
                    continue
                tc_xml = section[span[0]:span[1]]
                paragraphs = _paragraph_blocks(tc_xml)
                if not paragraphs:
                    continue
                regions.append(
                    {
                        "target": cell.field_id,
                        "kind": "cell",
                        "container": "table_cell",
                        "section": cell.section,
                        "section_index": section_index[cell.section],
                        "table": cell.table,
                        "row": cell.row,
                        "col": cell.col,
                        "paragraph_targets": [f"{cell.field_id}.p{item['ordinal']}" for item in paragraphs],
                        "paragraph_ids": [item["paragraph_id"] for item in paragraphs],
                        "paragraph_count": len(paragraphs),
                        "paragraphs": [
                            {
                                "target": f"{cell.field_id}.p{item['ordinal']}",
                                "text": item["text"],
                                "marker": _paragraph_marker(item["text"]),
                            }
                            for item in paragraphs
                        ],
                        "text": cell.text,
                        "snippet": _snippet(cell.text),
                        "editable": True,
                        "aliases": [],
                        "source_sha256": source_sha256,
                    }
                )

            if _sha256_path(source) != source_sha256:
                continue
            cached = {
                "source_path": str(source),
                "source_sha256": source_sha256,
                "counts": {"regions": len(regions), "unsupported": len(unsupported_controls)},
                "regions": regions,
                "unsupported_controls": unsupported_controls,
            }
            _inspection_cache_put(source, source_sha256, cached)

        if compact:
            regions = [_compact_region_item(region) for region in cached["regions"]]
            unsupported_controls = [_compact_region_item(control) for control in cached["unsupported_controls"]]
            return {
                "source_path": str(cached["source_path"]),
                "source_sha256": str(cached["source_sha256"]),
                "counts": dict(cached["counts"]),
                "regions": regions,
                "unsupported_controls": unsupported_controls,
            }

        return cached
    raise RuntimeError("source file changed during inspect read; retry")



def get_paragraph_map(path: str | Path) -> Dict[str, object]:
    source = Path(path)
    for _ in range(2):
        pkg = HwpxPackage.open(source)
        section_index = _section_index_map(pkg)
        source_sha256 = _sha256_path(source)
        paragraphs: List[dict] = []

        global_body = 0
        for sname in _section_names(pkg):
            section_items = _body_paragraphs_in_section(pkg.read(sname).decode("utf-8"), section_index[sname])
            for item in section_items:
                global_body += 1
                paragraphs.append(
                    {
                        "target": item["target"],
                        "parent_target": f"b{global_body}",
                        "container": "body",
                        "section": sname,
                        "section_index": section_index[sname],
                        "paragraph_id": item["paragraph_id"],
                        "paragraph_ordinal": item["paragraph_ordinal"],
                        "text": item["text"],
                        "snippet": _snippet(item["text"]),
                        "editable": True,
                        "source_sha256": source_sha256,
                    }
                )

        result = analyze(source)
        for cell in result.all_cells():
            if cell.has_nested_table or not cell.section:
                continue
            section = pkg.read(cell.section).decode("utf-8")
            span = _find_cell_span(section, cell.table_in_section, cell.row, cell.col)
            if span is None:
                continue
            tc_xml = section[span[0]:span[1]]
            for item in _paragraph_blocks(tc_xml):
                paragraphs.append(
                    {
                        "target": f"{cell.field_id}.p{item['ordinal']}",
                        "parent_target": cell.field_id,
                        "container": "table_cell",
                        "section": cell.section,
                        "section_index": section_index[cell.section],
                        "table": cell.table,
                        "row": cell.row,
                        "col": cell.col,
                        "paragraph_id": item["paragraph_id"],
                        "paragraph_ordinal": item["ordinal"],
                        "text": item["text"],
                        "snippet": _snippet(item["text"]),
                        "editable": True,
                        "source_sha256": source_sha256,
                    }
                )

        if _sha256_path(source) != source_sha256:
            continue
        return {
            "source_path": str(source),
            "source_sha256": source_sha256,
            "counts": {"paragraphs": len(paragraphs)},
            "paragraphs": paragraphs,
        }
    raise RuntimeError("source file changed during paragraph read; retry")

def _stable_inspection_paragraph_bundle(source: str | Path, *, compact: bool = False) -> tuple[Dict[str, object], Dict[str, object]]:
    src = Path(source)
    for _ in range(2):
        inspected = inspect_editable_regions(src, compact=compact)
        paragraph_map = get_paragraph_map(src)
        source_sha256 = str(inspected["source_sha256"])
        if str(paragraph_map["source_sha256"]) != source_sha256:
            continue
        if _sha256_path(src) != source_sha256:
            continue
        return inspected, paragraph_map
    raise RuntimeError("source file changed during structural read; retry")

def find_text_occurrences(path: str | Path, query: str) -> Dict[str, object]:
    source = Path(path)
    paragraph_map = get_paragraph_map(source)
    source_sha256 = str(paragraph_map["source_sha256"])
    if not query:
        return {
            "query": query,
            "count": 0,
            "occurrences": [],
            "source_path": str(source),
            "source_sha256": source_sha256,
        }

    occurrences: List[dict] = []
    for paragraph in paragraph_map["paragraphs"]:
        text = str(paragraph["text"])
        start = 0
        ordinal = 0
        while True:
            index = text.find(query, start)
            if index < 0:
                break
            ordinal += 1
            target = f"{paragraph['target']}.occ{ordinal}"
            digest = hashlib.sha256(
                json.dumps(
                    {
                        "target": target,
                        "query": query,
                        "text": text,
                        "index": index,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            occurrences.append(
                {
                    "target": target,
                    "paragraph_target": paragraph["target"],
                    "parent_target": paragraph["parent_target"],
                    "container": paragraph["container"],
                    "section": paragraph["section"],
                    "section_index": paragraph["section_index"],
                    "snippet": _snippet(text),
                    "context_digest": digest,
                    "source_sha256": source_sha256,
                }
            )
            start = index + len(query)

    return {
        "query": query,
        "count": len(occurrences),
        "occurrences": occurrences,
        "source_path": str(source),
        "source_sha256": source_sha256,
    }

def verify_targets(path: str | Path, expected_targets: List[dict]) -> Dict[str, object]:
    source = Path(path)
    inspected, paragraph_map = _stable_inspection_paragraph_bundle(source)
    texts: Dict[str, str] = {}
    for region in inspected["regions"]:
        texts[str(region["target"])] = str(region["text"])
    for paragraph in paragraph_map["paragraphs"]:
        texts[str(paragraph["target"])] = str(paragraph["text"])

    results: List[dict] = []
    verified_count = 0
    for item in expected_targets:
        target = str(item.get("target") or "")
        expected_text = str(item.get("expected_text") or "")
        actual_text = texts.get(target)
        verified = actual_text == expected_text if actual_text is not None else False
        if verified:
            verified_count += 1
        results.append(
            {
                "target": target,
                "expected_text": expected_text,
                "actual_text": actual_text,
                "verified": verified,
            }
        )

    return {
        "verified": verified_count == len(expected_targets),
        "counts": {"requested": len(expected_targets), "verified": verified_count, "failed": len(expected_targets) - verified_count},
        "results": results,
        "source_path": str(source),
        "source_sha256": _sha256_path(source),
    }


def complete_addressed_template(
    path: str | Path,
    edits: List[dict],
    out_path: str | Path,
    verify: bool = True,
) -> Dict[str, object]:
    total_started = time.perf_counter()
    source = Path(path)
    target = Path(out_path)
    source_sha256 = _sha256_path(source)
    requested = len(edits)

    def elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    def counts_from(base: Dict[str, object] | None = None, *, verified: int = 0) -> Dict[str, int]:
        raw = dict((base or {}).get("counts") or {})
        return {
            "requested": int(raw.get("requested", requested)),
            "resolved": int(raw.get("resolved", 0)),
            "applied": int(raw.get("applied", 0)),
            "verified": verified,
            "skipped": int(raw.get("skipped", 0)),
            "unresolved": int(raw.get("unresolved", 0)),
        }

    if _same_document_path(source, target):
        timings_ms = {"preview": 0, "apply": 0, "verify": 0, "total": elapsed_ms(total_started)}
        counts = counts_from()
        counts["skipped"] = requested
        return {
            "ok": False,
            "state": "failed",
            "source_path": str(source),
            "source_sha256": source_sha256,
            "target_path": str(target),
            "target_sha256": None,
            "counts": counts,
            "coverage_ratio": 0.0,
            "unresolved": [],
            "failures": [{"reason": "output_path_matches_source"}],
            "timings_ms": timings_ms,
            "substrate": OWN_TEXT_SUBSTRATE,
        }

    preview_started = time.perf_counter()
    preview = preview_addressed_edits(source, edits)
    preview_ms = elapsed_ms(preview_started)
    unresolved = list(preview.get("unresolved") or [])
    preview_counts = counts_from(preview)
    if not preview.get("ok"):
        preview_counts["skipped"] = preview_counts["requested"] - preview_counts["resolved"]
        timings_ms = {"preview": preview_ms, "apply": 0, "verify": 0, "total": elapsed_ms(total_started)}
        return {
            "ok": False,
            "state": str(preview.get("state") or "ambiguous_target"),
            "source_path": str(source),
            "source_sha256": str(preview.get("source_sha256") or source_sha256),
            "target_path": str(target),
            "target_sha256": None,
            "counts": preview_counts,
            "coverage_ratio": 0.0 if requested == 0 else round(preview_counts["resolved"] / requested, 2),
            "unresolved": unresolved,
            "failures": [],
            "timings_ms": timings_ms,
            "substrate": str(preview.get("substrate") or OWN_TEXT_SUBSTRATE),
        }

    apply_started = time.perf_counter()
    applied = apply_addressed_edits(str(preview["session_id"]), target)
    apply_ms = elapsed_ms(apply_started)
    if not applied.get("ok"):
        apply_counts = counts_from(preview)
        apply_counts["skipped"] = apply_counts["requested"] - apply_counts["resolved"]
        failures = [{"reason": str(applied.get("state") or "failed")}]
        timings_ms = {"preview": preview_ms, "apply": apply_ms, "verify": 0, "total": elapsed_ms(total_started)}
        return {
            "ok": False,
            "state": str(applied.get("state") or "failed"),
            "source_path": str(source),
            "source_sha256": str(preview.get("source_sha256") or source_sha256),
            "target_path": str(target),
            "target_sha256": None,
            "counts": apply_counts,
            "coverage_ratio": 0.0 if requested == 0 else round(apply_counts["applied"] / requested, 2),
            "unresolved": unresolved,
            "failures": failures,
            "timings_ms": timings_ms,
            "substrate": str(applied.get("substrate") or preview.get("substrate") or OWN_TEXT_SUBSTRATE),
        }

    verify_ms = 0
    verified_count = 0
    failures: List[dict] = []
    state = "applied"
    ok = True
    if verify:
        verify_started = time.perf_counter()
        expectations: List[dict] = []
        for item in preview["edits"]:
            # multiline edits become consecutive paragraphs — verify each line
            expectations.extend(
                item.get("verify_expansion")
                or [{"target": item["target"], "expected_text": item["after_text"]}]
            )
        verification = verify_targets(target, expectations)
        verify_ms = elapsed_ms(verify_started)
        verified_count = int((verification.get("counts") or {}).get("verified", 0))
        failures = [
            {
                "target": str(item.get("target") or ""),
                "reason": "verification_mismatch",
                "expected_text": str(item.get("expected_text") or ""),
                "actual_text": item.get("actual_text"),
            }
            for item in verification.get("results") or []
            if not item.get("verified")
        ]
        if failures:
            ok = False
            state = "partial" if verified_count > 0 else "failed"
        else:
            state = "complete"

    counts = counts_from(applied, verified=verified_count)
    if not verify:
        counts["verified"] = 0
    counts["skipped"] = counts["requested"] - counts["applied"]
    target_sha256 = _sha256_path(target)
    coverage_numerator = counts["verified"] if verify else counts["applied"]
    coverage_ratio = 1.0 if requested == 0 else round(coverage_numerator / requested, 2)
    timings_ms = {"preview": preview_ms, "apply": apply_ms, "verify": verify_ms, "total": elapsed_ms(total_started)}
    return {
        "ok": ok,
        "state": state,
        "session_id": applied["session_id"],
        "source_path": str(source),
        "source_sha256": str(applied.get("source_sha256") or source_sha256),
        "target_path": str(target),
        "target_sha256": target_sha256,
        "counts": counts,
        "coverage_ratio": coverage_ratio,
        "unresolved": unresolved,
        "failures": failures,
        "timings_ms": timings_ms,
        "substrate": str(applied.get("substrate") or OWN_TEXT_SUBSTRATE),
        "journal_path": applied.get("journal_path"),
        "snapshot_path": applied.get("snapshot_path"),
        "changed_entries": list(applied.get("changed_entries") or []),
        "audit": list(applied.get("audit") or []),
    }

def plan_template_completion(path: str | Path, compact: bool = False) -> Dict[str, object]:
    from hangeul_core.schema import label_key
    from hangeul_core.understand import understand

    source = Path(path)
    for _ in range(2):
        inspected, paragraph_map = _stable_inspection_paragraph_bundle(source, compact=compact)
        regions = inspected["regions"]
        paragraphs = paragraph_map["paragraphs"]
        schema = understand(source)
        fields = schema.fields
        if schema.source_sha256 == str(inspected["source_sha256"]):
            break
    else:
        raise RuntimeError("source file changed during planning read; retry")
    grouped: Dict[str, List[object]] = {}
    for entry in fields:
        grouped.setdefault(label_key(entry.label), []).append(entry)

    ambiguous_labels = [
        {
            "label": items[0].label,
            "field_ids": [item.field_id for item in items],
        }
        for items in grouped.values()
        if len(items) > 1
    ]
    unique_fields = [items[0] for items in grouped.values() if len(items) == 1]

    repeated_text_candidates: List[dict] = []
    repeated_groups: Dict[str, List[str]] = {}
    for paragraph in paragraphs:
        text = str(paragraph["text"]).strip()
        if text:
            repeated_groups.setdefault(text, []).append(str(paragraph["target"]))
    for text, targets in repeated_groups.items():
        if len(targets) > 1:
            repeated_text_candidates.append({"text": text, "targets": targets, "count": len(targets)})

    unsupported_controls = list(inspected.get("unsupported_controls") or [])
    coverage_ratio = 0.0 if not regions else round(len(unique_fields) / len(regions), 2)
    user_attention_required = bool(ambiguous_labels or repeated_text_candidates or unsupported_controls or coverage_ratio < 1.0)
    state = "partial" if user_attention_required else "complete"
    if ambiguous_labels or unsupported_controls or coverage_ratio < 1.0:
        recommended_next_tool = "inspect_editable_regions"
    elif repeated_text_candidates:
        recommended_next_tool = "find_text_occurrences"
    else:
        recommended_next_tool = "fill_form"

    return {
        "state": state,
        "addressable_regions": regions,
        "directly_fillable_fields": [{"label": entry.label, "field_id": entry.field_id} for entry in unique_fields],
        "raw_structural_targets": [region["target"] for region in regions] + [paragraph["target"] for paragraph in paragraphs],
        "repeated_text_candidates": repeated_text_candidates,
        "ambiguous_labels": ambiguous_labels,
        "unsupported_controls": unsupported_controls,
        "coverage_ratio": coverage_ratio,
        "user_attention_required": user_attention_required,
        "recommended_next_tool": recommended_next_tool,
        "source_path": str(source),
        "source_sha256": str(inspected["source_sha256"]),
    }


def preview_addressed_edits(path: str | Path, edits: List[dict]) -> Dict[str, object]:
    source = Path(path)
    result = analyze(source)
    session_id = uuid.uuid4().hex
    session = _AddressedSession(
        session_id=session_id,
        source_path=str(source),
        source_sha256=_sha256_path(source),
        counts={"requested": len(edits), "resolved": 0, "applied": 0, "skipped": 0, "unresolved": 0},
    )
    cells = {cell.field_id: cell for cell in result.all_cells()}
    body_index = body_field_index(source)
    sections: Dict[str, str] = {}
    seen_targets: set[str] = set()
    preview_items: List[dict] = []
    unresolved: List[dict] = []

    pkg = HwpxPackage.open(source)
    section_numbers = _section_index_map(pkg)

    def section_text(name: str) -> str:
        if name not in sections:
            sections[name] = pkg.read(name).decode("utf-8")
        return sections[name]

    conflicted_multiline = _multiline_conflicts(list(edits))
    for item in _ordered_edits(list(edits)):
        target = str(item.get("target") or "")
        kind = str(item.get("kind") or "")
        operation = str(item.get("operation") or "")
        value = str(item.get("value") or "")
        expected_text = str(item.get("expected_text") or "")
        if target in seen_targets:
            unresolved.append({"target": target, "reason": "duplicate_target"})
            continue
        seen_targets.add(target)
        if target in conflicted_multiline:
            unresolved.append({"target": target, "reason": "multiline_requires_exclusive_cell"})
            continue
        verify_expansion: List[dict] | None = None

        if kind == "cell" and operation == "replace_text" and _TARGET.match(target):
            cell = cells.get(target)
            if cell is None or not cell.section:
                unresolved.append({"target": target, "reason": "target_not_found"})
                continue
            if expected_text and cell.text != expected_text:
                unresolved.append({"target": target, "reason": "expected_text_mismatch", "actual_text": cell.text})
                continue
            section = section_text(cell.section)
            span = _find_cell_span(section, cell.table_in_section, cell.row, cell.col)
            if span is None:
                unresolved.append({"target": target, "reason": "target_not_found"})
                continue
            start, end = span
            tc_xml = section[start:end]
            lines = value.split("\n")
            new_tc = _replace_text_nodes(tc_xml, lines[0])
            if new_tc is None:
                unresolved.append({"target": target, "reason": "no_text_nodes"})
                continue
            if len(lines) > 1:
                anchor = next((p for p in _paragraph_blocks(tc_xml) if "<hp:t>" in p["block"]), None)
                clones = None if anchor is None else _multiline_paragraph_clones(anchor["block"], lines[1:])
                if clones is None:
                    unresolved.append({"target": target, "reason": "no_text_nodes"})
                    continue
                insert_at = _paragraph_blocks(new_tc)[anchor["ordinal"] - 1]["end"]
                new_tc = new_tc[:insert_at] + clones + new_tc[insert_at:]
                verify_expansion = [
                    {"target": f"{target}.p{anchor['ordinal'] + offset}", "expected_text": line}
                    for offset, line in enumerate(lines)
                ]
            new_tc = _strip_linesegs(new_tc)
            sections[cell.section] = section[:start] + new_tc + section[end:]
            before_text = cell.text
            after_text = value
            section_name = cell.section
        elif kind == "paragraph" and operation in {"replace_text", "preserve_marker_replace_tail"}:
            match = _PARA_TARGET.match(target)
            if match is None:
                unresolved.append({"target": target, "reason": "unsupported_target"})
                continue
            cell = cells.get(match.group("cell"))
            if cell is None or not cell.section:
                unresolved.append({"target": target, "reason": "target_not_found"})
                continue
            section = section_text(cell.section)
            resolved = _cell_paragraph_entry(section, cell, int(match.group("ordinal")))
            if resolved is None:
                unresolved.append({"target": target, "reason": "target_not_found"})
                continue
            span, tc_xml, paragraph = resolved
            if expected_text and paragraph["text"] != expected_text:
                unresolved.append({"target": target, "reason": "expected_text_mismatch", "actual_text": paragraph["text"]})
                continue
            lines = value.split("\n")
            if operation == "preserve_marker_replace_tail":
                marker = _paragraph_marker(paragraph["text"])
                if not marker:
                    unresolved.append({"target": target, "reason": "no_marker", "actual_text": paragraph["text"]})
                    continue
                lines = _marker_lines(marker, lines)
            new_para = _strip_linesegs(_replace_text_nodes(paragraph["block"], lines[0]))
            if new_para is None:
                unresolved.append({"target": target, "reason": "no_text_nodes"})
                continue
            if len(lines) > 1:
                clones = _multiline_paragraph_clones(paragraph["block"], lines[1:])
                if clones is None:
                    unresolved.append({"target": target, "reason": "no_text_nodes"})
                    continue
                new_para += clones
                ordinal = int(match.group("ordinal"))
                verify_expansion = [
                    {"target": f"{match.group('cell')}.p{ordinal + offset}", "expected_text": line}
                    for offset, line in enumerate(lines)
                ]
            new_tc = tc_xml[: paragraph["start"]] + new_para + tc_xml[paragraph["end"] :]
            sections[cell.section] = section[: span[0]] + new_tc + section[span[1] :]
            before_text = paragraph["text"]
            after_text = "\n".join(lines)
            section_name = cell.section
        elif kind == "body_para" and operation in {"replace_text", "preserve_marker_replace_tail"} and _BODY_TARGET.match(target):
            if "\n" in value:
                unresolved.append({"target": target, "reason": "multiline_unsupported_target"})
                continue
            section_name, local_ordinal = body_index.get(target, (None, None))
            if not section_name or local_ordinal is None:
                unresolved.append({"target": target, "reason": "target_not_found"})
                continue
            section = section_text(section_name)
            paragraphs = _body_paragraphs_in_section(section, section_numbers[section_name])
            if local_ordinal < 1 or local_ordinal > len(paragraphs):
                unresolved.append({"target": target, "reason": "target_not_found"})
                continue
            paragraph = paragraphs[local_ordinal - 1]
            if expected_text and paragraph["text"] != expected_text:
                unresolved.append({"target": target, "reason": "expected_text_mismatch", "actual_text": paragraph["text"]})
                continue
            new_section, applied_ordinals = replace_body_paragraph(
                section,
                {local_ordinal: value},
                keep_marker=operation == "preserve_marker_replace_tail",
            )
            if local_ordinal not in applied_ordinals:
                unresolved.append({"target": target, "reason": "no_text_nodes"})
                continue
            before_text = paragraph["text"]
            refreshed = _body_paragraphs_in_section(new_section, section_numbers[section_name])[local_ordinal - 1]
            after_text = refreshed["text"]
            stripped_block = _strip_linesegs(refreshed["block"])
            new_section = new_section[: refreshed["start"]] + stripped_block + new_section[refreshed["end"] :]
            sections[section_name] = new_section
        else:
            unresolved.append({"target": target, "reason": "unsupported_target"})
            continue

        session.counts["resolved"] += 1
        preview_items.append(
            {
                "target": target,
                "kind": kind,
                "operation": operation,
                "expected_text": expected_text,
                "before_text": before_text,
                "after_text": after_text,
                "section": section_name,
                "context_digest": _context_digest(target, expected_text, value),
                **({"verify_expansion": verify_expansion} if verify_expansion else {}),
            }
        )
        session.audit.append(f"{section_name}: {target} {operation}")

    session.counts["unresolved"] = len(unresolved)
    session.edits = preview_items
    session.changed_sections = sections
    session.changed_entries = sorted(sections)
    _SESSIONS[session_id] = session
    return {
        "ok": not unresolved,
        "state": "preview_ready" if not unresolved else "ambiguous_target",
        "session_id": session_id,
        "kind": "addressed_edits",
        "substrate": OWN_TEXT_SUBSTRATE,
        "source_path": str(source),
        "source_sha256": session.source_sha256,
        "counts": dict(session.counts),
        "changed_entries": list(session.changed_entries),
        "edits": preview_items,
        "unresolved": unresolved,
        "audit": list(session.audit),
    }


def apply_addressed_edits(session_id: str, out_path: str | Path | None = None) -> Dict[str, object]:
    session = _SESSIONS.get(session_id)
    if session is None:
        return {"ok": False, "state": "unknown_session"}
    if session.applied:
        return {"ok": False, "state": "already_applied"}
    source = Path(session.source_path)
    if _sha256_path(source) != session.source_sha256:
        return {"ok": False, "state": "stale_preview"}
    if session.counts.get("unresolved"):
        return {"ok": False, "state": "ambiguous_target", "unresolved": session.counts.get("unresolved")}

    if out_path is None or not str(out_path).strip():
        return {"ok": False, "state": "invalid_output_path", "error": "out_path is required for addressed apply"}
    target = Path(out_path)
    if _same_document_path(source, target):
        return {"ok": False, "state": "invalid_output_path", "error": "out_path must be a separate output path for addressed apply"}
    snapshot_path = _snapshot_path(target, session_id)
    journal_path = _journal_path(target, session_id)
    target_existed = target.exists()
    snapshot_source = target if target_existed else source
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot_source, snapshot_path)

    pkg = HwpxPackage.open(source)
    for name, text in session.changed_sections.items():
        pkg.replace(name, text.encode("utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    pkg.save(target)
    session.applied = True

    counts = dict(session.counts)
    counts["applied"] = counts["resolved"]
    journal = {
        "journal_version": _JOURNAL_VERSION,
        "session_id": session_id,
        "kind": "addressed_edits",
        "substrate": OWN_TEXT_SUBSTRATE,
        "source_path": str(source),
        "source_sha256": session.source_sha256,
        "target_path": str(target),
        "target_existed_before_apply": target_existed,
        "snapshot_path": str(snapshot_path),
        "snapshot_role": "target_before_apply" if target_existed else "source_reference",
        "applied_target_sha256": _sha256_path(target),
        "counts": counts,
        "total": counts["applied"],
        "changed_entries": list(session.changed_entries),
        "audit": list(session.audit) or ["No addressed edits applied."],
        "created_at": _utc_now(),
    }
    journal_path.write_text(json.dumps(journal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "state": "applied",
        "session_id": session_id,
        "kind": "addressed_edits",
        "substrate": OWN_TEXT_SUBSTRATE,
        "source_path": str(source),
        "target_path": str(target),
        "journal_path": str(journal_path),
        "snapshot_path": str(snapshot_path),
        "counts": counts,
        "changed_entries": list(session.changed_entries),
        "audit": list(session.audit),
    }


__all__ = [
    "apply_addressed_edits",
    "complete_addressed_template",
    "find_text_occurrences",
    "get_paragraph_map",
    "inspect_editable_regions",
    "plan_template_completion",
    "preview_addressed_edits",
    "verify_targets",
]

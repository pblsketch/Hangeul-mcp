from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from hangeul_core.analyze import _section_names, analyze
from hangeul_core.body import _body_para_spans, _render, body_field_index, replace_body_paragraph
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


def inspect_editable_regions(path: str | Path) -> Dict[str, object]:
    source = Path(path)
    pkg = HwpxPackage.open(source)
    section_index = _section_index_map(pkg)
    source_sha256 = _sha256_path(source)
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
                "text": cell.text,
                "snippet": _snippet(cell.text),
                "editable": True,
                "aliases": [],
                "source_sha256": source_sha256,
            }
        )

    return {
        "source_path": str(source),
        "source_sha256": source_sha256,
        "counts": {"regions": len(regions), "unsupported": len(unsupported_controls)},
        "regions": regions,
        "unsupported_controls": unsupported_controls,
    }



def get_paragraph_map(path: str | Path) -> Dict[str, object]:
    source = Path(path)
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

    return {
        "source_path": str(source),
        "source_sha256": source_sha256,
        "counts": {"paragraphs": len(paragraphs)},
        "paragraphs": paragraphs,
    }

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
    texts: Dict[str, str] = {}
    for region in inspect_editable_regions(source)["regions"]:
        texts[str(region["target"])] = str(region["text"])
    for paragraph in get_paragraph_map(source)["paragraphs"]:
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


def plan_template_completion(path: str | Path) -> Dict[str, object]:
    from hangeul_core.schema import label_key
    from hangeul_core.understand import understand

    source = Path(path)
    inspected = inspect_editable_regions(source)
    regions = inspected["regions"]
    paragraphs = get_paragraph_map(source)["paragraphs"]
    fields = understand(source).fields
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
        "source_sha256": _sha256_path(source),
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

    for item in edits:
        target = str(item.get("target") or "")
        kind = str(item.get("kind") or "")
        operation = str(item.get("operation") or "")
        value = str(item.get("value") or "")
        expected_text = str(item.get("expected_text") or "")
        if target in seen_targets:
            unresolved.append({"target": target, "reason": "duplicate_target"})
            continue
        seen_targets.add(target)

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
            new_tc = _replace_text_nodes(tc_xml, value)
            if new_tc is None:
                unresolved.append({"target": target, "reason": "no_text_nodes"})
                continue
            sections[cell.section] = section[:start] + new_tc + section[end:]
            before_text = cell.text
            after_text = value
            section_name = cell.section
        elif kind == "paragraph" and operation == "replace_text":
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
            new_para = _replace_text_nodes(paragraph["block"], value)
            if new_para is None:
                unresolved.append({"target": target, "reason": "no_text_nodes"})
                continue
            new_tc = tc_xml[: paragraph["start"]] + new_para + tc_xml[paragraph["end"] :]
            sections[cell.section] = section[: span[0]] + new_tc + section[span[1] :]
            before_text = paragraph["text"]
            after_text = value
            section_name = cell.section
        elif kind == "body_para" and operation in {"replace_text", "preserve_marker_replace_tail"} and _BODY_TARGET.match(target):
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
            sections[section_name] = new_section
            before_text = paragraph["text"]
            refreshed = _body_paragraphs_in_section(new_section, section_numbers[section_name])[local_ordinal - 1]
            after_text = refreshed["text"]
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

    target = Path(out_path) if out_path is not None else source
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
    "find_text_occurrences",
    "get_paragraph_map",
    "inspect_editable_regions",
    "plan_template_completion",
    "preview_addressed_edits",
    "verify_targets",
]

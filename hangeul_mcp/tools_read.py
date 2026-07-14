from __future__ import annotations

from typing import Any, Dict

from hangeul_core.convert import ensure_hwpx
from hangeul_core.hwp_headless import extract_hwp_text as _extract_hwp_text_headless
from hangeul_core.addressed import get_paragraph_map as _get_paragraph_map
from hangeul_core.addressed import inspect_editable_regions as _inspect_editable_regions
from hangeul_core.addressed import find_text_occurrences as _find_text_occurrences
from hangeul_core.addressed import plan_template_completion as _plan_template_completion
from hangeul_core.addressed import verify_targets as _verify_targets
from hangeul_core.read import find_cell_by_label as _find_cell_by_label
from hangeul_core.read import find_text as _find_text
from hangeul_core.read import get_document_outline as _get_document_outline
from hangeul_core.read import get_table_map as _get_table_map
from hangeul_core.read import list_styles as _list_styles
from hangeul_core.read import verify_fill as _verify_fill
from hangeul_core.validate import validate_hwpx as _validate_hwpx


def register_read_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def find_text(path: str, query: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "query": query, "count": 0, "cell_occurrences": []}
        return _find_text(path, query)

    @mcp.tool()
    def get_document_outline(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc)}
        return _get_document_outline(path)

    @mcp.tool()
    def get_table_map(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "tables": []}
        return _get_table_map(path)

    @mcp.tool()
    def inspect_editable_regions(path: str, compact: bool = False) -> Dict[str, Any]:
        """Inspect FILE-MODE structural edit targets before any addressed/template write.

        Named fields / `{}` placeholders are NOT required. Use these structural
        addresses for repeated `▶`, repeated `○○○`, ordinary table cells, and
        paragraphs when the template has no reliable field names. Do not treat
        repeated visible text as a global-replace target without explicit scope;
        inspect regions first, then send one addressed edits array to
        `preview_addressed_edits` and apply the reviewed `session_id` with
        `apply_addressed_edits(session_id, out_path)`, or use `complete_addressed_template`.
        file mode, gather/generate all values first, and send one edits array
        rather than one tool call per cell. Addressed file mode writes a
        completed copy; it does NOT mutate the already-open same Hangul window,
        so open the verified output afterward if live viewing is needed.
        """
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {
                "error": str(exc),
                "source_path": path,
                "source_sha256": None,
                "counts": {"regions": 0, "unsupported": 0},
                "regions": [],
                "unsupported_controls": [],
            }
        try:
            return _inspect_editable_regions(path, compact=compact)
        except RuntimeError as exc:
            if not str(exc).startswith("source file changed during"):
                raise
            return {
                "error": str(exc),
                "source_path": path,
                "source_sha256": None,
                "counts": {"regions": 0, "unsupported": 0},
                "regions": [],
                "unsupported_controls": [],
            }

    @mcp.tool()
    def get_paragraph_map(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "source_path": path, "source_sha256": None, "counts": {"paragraphs": 0}, "paragraphs": []}
        try:
            return _get_paragraph_map(path)
        except RuntimeError as exc:
            if not str(exc).startswith("source file changed during"):
                raise
            return {"error": str(exc), "source_path": path, "source_sha256": None, "counts": {"paragraphs": 0}, "paragraphs": []}

    @mcp.tool()
    def find_text_occurrences(path: str, query: str) -> Dict[str, Any]:
        """Locate repeated visible text in FILE MODE so edits can be scoped, not guessed.

        Named fields / `{}` placeholders are NOT required. Use this when the
        template is driven by repeated `▶`, repeated `○○○`, ordinary table
        cells, or paragraphs and you need structural addresses instead of a
        blind text replace. Repeated text must NOT be globally replaced without
        explicit scope; use the returned occurrences to choose exact structural
        targets, then send one addressed edits array to
        `preview_addressed_edits` and apply the reviewed `session_id` with
        `apply_addressed_edits(session_id, out_path)`, or use `complete_addressed_template`.
        values first and stay in file mode from the start; addressed file mode
        produces a completed copy and does not mutate the already-open same Hangul window.
        """
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {
                "error": str(exc),
                "query": query,
                "count": 0,
                "occurrences": [],
                "source_path": path,
                "source_sha256": None,
            }
        try:
            return _find_text_occurrences(path, query)
        except RuntimeError as exc:
            if not str(exc).startswith("source file changed during"):
                raise
            return {
                "error": str(exc),
                "query": query,
                "count": 0,
                "occurrences": [],
                "source_path": path,
                "source_sha256": None,
            }

    @mcp.tool()
    def find_cell_by_label(path: str, label: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "label": label}
        return _find_cell_by_label(path, label)

    @mcp.tool()
    def verify_fill(path: str, expected: Dict[str, str]) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "verified": False}
        return _verify_fill(path, expected)

    @mcp.tool()
    def verify_targets(path: str, expected_targets: list) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "verified": False, "counts": {"requested": len(list(expected_targets)), "verified": 0, "failed": len(list(expected_targets))}, "results": [], "source_path": path, "source_sha256": None}
        try:
            return _verify_targets(path, list(expected_targets))
        except RuntimeError as exc:
            if not str(exc).startswith("source file changed during"):
                raise
            return {"error": str(exc), "verified": False, "counts": {"requested": len(list(expected_targets)), "verified": 0, "failed": len(list(expected_targets))}, "results": [], "source_path": path, "source_sha256": None}

    @mcp.tool()
    def plan_template_completion(path: str, compact: bool = False) -> Dict[str, Any]:
        """Plan whole-template completion in FILE MODE and return addressable edit targets.

        Named fields / `{}` placeholders are NOT required. This planner is for
        templates filled by repeated `▶`, repeated `○○○`, ordinary table cells,
        and paragraphs using structural addresses. Do not globally replace
        repeated text without explicit scope. Gather/generate ALL values first,
        then hand one complete addressed edits array to
        `complete_addressed_template` instead of one tool call per cell. Start
        in file mode rather than mixing live field writes and then falling back
        to file mode. Addressed file mode writes a completed copy and does not mutate the already-open same Hangul window; open the verified output afterward if a live Hangul window must show the result.
        """
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {
                "error": str(exc),
                "state": "failed",
                "addressable_regions": [],
                "directly_fillable_fields": [],
                "raw_structural_targets": [],
                "repeated_text_candidates": [],
                "ambiguous_labels": [],
                "unsupported_controls": [],
                "coverage_ratio": 0.0,
                "user_attention_required": True,
                "recommended_next_tool": "inspect_editable_regions",
                "source_path": path,
                "source_sha256": None,
            }
        try:
            return _plan_template_completion(path, compact=compact)
        except RuntimeError as exc:
            if not str(exc).startswith("source file changed during"):
                raise
            return {
                "error": str(exc),
                "state": "failed",
                "addressable_regions": [],
                "directly_fillable_fields": [],
                "raw_structural_targets": [],
                "repeated_text_candidates": [],
                "ambiguous_labels": [],
                "unsupported_controls": [],
                "coverage_ratio": 0.0,
                "user_attention_required": True,
                "recommended_next_tool": "inspect_editable_regions",
                "source_path": path,
                "source_sha256": None,
            }

    @mcp.tool()
    def list_styles(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "charPr": [], "paraPr": []}
        return _list_styles(path)

    @mcp.tool()
    def extract_hwp_text(path: str) -> Dict[str, Any]:
        return _extract_hwp_text_headless(path)

    @mcp.tool()
    def validate_hwpx(path: str) -> Dict[str, Any]:
        return _validate_hwpx(path)

    return {
        "find_text": find_text,
        "get_document_outline": get_document_outline,
        "get_table_map": get_table_map,
        "inspect_editable_regions": inspect_editable_regions,
        "find_text_occurrences": find_text_occurrences,
        "get_paragraph_map": get_paragraph_map,
        "find_cell_by_label": find_cell_by_label,
        "verify_fill": verify_fill,
        "verify_targets": verify_targets,
        "plan_template_completion": plan_template_completion,
        "list_styles": list_styles,
        "extract_hwp_text": extract_hwp_text,
        "validate_hwpx": validate_hwpx,
    }

from __future__ import annotations

from typing import Any, Dict

from hangeul_core.convert import ensure_hwpx
from hangeul_core.hwp_headless import extract_hwp_text as _extract_hwp_text_headless
from hangeul_core.addressed import get_paragraph_map as _get_paragraph_map
from hangeul_core.addressed import inspect_editable_regions as _inspect_editable_regions
from hangeul_core.addressed import find_text_occurrences as _find_text_occurrences
from hangeul_core.addressed import plan_template_completion as _plan_template_completion
from hangeul_core.addressed import verify_targets as _verify_targets
from hangeul_core.read import find_cell_by_label as _find_cell_by_label, find_text as _find_text, get_document_outline as _get_document_outline
from hangeul_core.read import get_table_map as _get_table_map, list_styles as _list_styles, verify_fill as _verify_fill
from hangeul_core.validate import validate_hwpx as _validate_hwpx
from hangeul_mcp.envelope import enveloped


def register_read_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    @enveloped
    def find_text(path: str, query: str) -> Dict[str, Any]:
        """Count plain-text matches per cell in FILE MODE; for edit-ready structural addresses use find_text_occurrences."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "query": query, "count": 0, "cell_occurrences": []}
        return _find_text(path, query)

    @mcp.tool()
    @enveloped
    def get_document_outline(path: str) -> Dict[str, Any]:
        """Return the heading/outline structure of an HWPX document."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc)}
        return _get_document_outline(path)

    @mcp.tool()
    @enveloped
    def get_table_map(path: str) -> Dict[str, Any]:
        """Map tables with per-cell text and merge structure for label-to-cell reasoning."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "tables": []}
        return _get_table_map(path)

    @mcp.tool()
    @enveloped
    def inspect_editable_regions(path: str, compact: bool = False) -> Dict[str, Any]:
        """Inspect FILE-MODE structural edit targets before any addressed/template write.

        Named fields / `{}` placeholders are NOT required. Use these structural
        addresses for repeated `▶`, repeated `○○○`, ordinary table cells, and
        paragraphs when the template lacks reliable field names. Never treat
        repeated visible text as a global-replace target without explicit scope;
        send ONE addressed edits array (gather all values first) to
        `preview_addressed_edits` + `apply_addressed_edits(session_id, out_path)`,
        or `complete_addressed_template`. The output is a completed copy and
        does not mutate the already-open same Hangul window — open it afterward.
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
    @enveloped
    def get_paragraph_map(path: str) -> Dict[str, Any]:
        """List body paragraphs with stable bN addresses for addressed edits."""
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
    @enveloped
    def find_text_occurrences(path: str, query: str) -> Dict[str, Any]:
        """Locate repeated visible text in FILE MODE so edits can be scoped, not guessed.

        Named fields / `{}` placeholders are NOT required. Use this when the
        template is driven by repeated `▶`, repeated `○○○`, ordinary table
        cells, or paragraphs and you need structural addresses instead of a
        blind text replace. Repeated text must NOT be globally replaced without
        explicit scope; use the returned occurrences to choose exact structural
        targets, then send ONE addressed edits array (gather all values first)
        to `preview_addressed_edits` + `apply_addressed_edits(session_id, out_path)`,
        or `complete_addressed_template`. Addressed file mode produces a
        completed copy and does not mutate the already-open same Hangul window.
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
    @enveloped
    def find_cell_by_label(path: str, label: str) -> Dict[str, Any]:
        """Locate the input cell next to or under a label cell in tables."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "label": label}
        return _find_cell_by_label(path, label)

    @mcp.tool()
    @enveloped
    def verify_fill(path: str, expected: Dict[str, str]) -> Dict[str, Any]:
        """Verify expected label:value pairs actually appear in the (filled) document."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "verified": False}
        result = _verify_fill(path, expected)
        return {**result, "ok": bool(result.get("verified"))}

    @mcp.tool()
    @enveloped
    def verify_targets(path: str, expected_targets: list) -> Dict[str, Any]:
        """Verify expected_text at exact structural targets (tN.rN.cN[.pN] / bN) after edits."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "verified": False, "counts": {"requested": len(list(expected_targets)), "verified": 0, "failed": len(list(expected_targets))}, "results": [], "source_path": path, "source_sha256": None}
        try:
            result = _verify_targets(path, list(expected_targets))
            return {**result, "ok": bool(result.get("verified"))}
        except RuntimeError as exc:
            if not str(exc).startswith("source file changed during"):
                raise
            return {"error": str(exc), "verified": False, "counts": {"requested": len(list(expected_targets)), "verified": 0, "failed": len(list(expected_targets))}, "results": [], "source_path": path, "source_sha256": None}

    @mcp.tool()
    @enveloped
    def plan_template_completion(path: str, compact: bool = False) -> Dict[str, Any]:
        """Plan whole-template completion in FILE MODE and return addressable edit targets.

        Named fields / `{}` placeholders are NOT required: repeated `▶`,
        repeated `○○○`, ordinary table cells, and paragraphs are addressed
        structurally. Never replace repeated text without explicit scope. Gather
        ALL values first, then hand one complete addressed edits array to
        `complete_addressed_template` instead of one tool call per cell — start in
        file mode instead of mixing live field writes. The completed copy
        does not mutate the already-open same Hangul window — open it afterward.
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
    @enveloped
    def list_styles(path: str) -> Dict[str, Any]:
        """List charPr/paraPr style definitions available in the document."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "charPr": [], "paraPr": []}
        return _list_styles(path)

    @mcp.tool()
    @enveloped
    def extract_hwp_text(path: str) -> Dict[str, Any]:
        """Headless .hwp text extraction gate; returns available:false until a verified non-COM reader lands."""
        return _extract_hwp_text_headless(path)

    @mcp.tool()
    @enveloped
    def validate_hwpx(path: str) -> Dict[str, Any]:
        """Validate HWPX package integrity (zip layout, mimetype, XML declarations); ok mirrors valid."""
        result = _validate_hwpx(path)
        return {**result, "ok": bool(result.get("valid"))}

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

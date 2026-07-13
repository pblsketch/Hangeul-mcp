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
    def inspect_editable_regions(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "regions": [], "counts": {"regions": 0}}
        return _inspect_editable_regions(path)

    @mcp.tool()
    def get_paragraph_map(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "paragraphs": [], "counts": {"paragraphs": 0}}
        return _get_paragraph_map(path)

    @mcp.tool()
    def find_text_occurrences(path: str, query: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "query": query, "count": 0, "occurrences": []}
        return _find_text_occurrences(path, query)

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
            return {"error": str(exc), "verified": False, "results": []}
        return _verify_targets(path, list(expected_targets))

    @mcp.tool()
    def plan_template_completion(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "state": "failed", "addressable_regions": []}
        return _plan_template_completion(path)

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

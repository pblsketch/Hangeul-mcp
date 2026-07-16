from __future__ import annotations

import importlib.util
import sys
from typing import Any, Dict, List

from hangeul_core import delegate
from hangeul_core.hwp import HwpBridge
from hangeul_core.hwp.live import live_available
from hangeul_core.hwp_headless import headless_status
from hangeul_core.render import render_available
from hangeul_core.runtime_info import feature_flags, runtime_identity


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _capability(
    name: str,
    available: bool,
    tools: List[str],
    *,
    requires: List[str] | None = None,
    note: str | None = None,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "name": name,
        "mode": name,
        "available": available,
        "tools": tools,
    }
    if requires:
        item["requires"] = requires
    if note:
        item["note"] = note
    return item


def describe_capabilities() -> Dict[str, Any]:
    delegate_available = delegate.hwpx_available()
    can_render, render_note = render_available()
    hwp_headless = headless_status()
    return {
        "product": "Hangeul-mcp",
        "mode": "byo_ai_local_harness",
        "server_side_llm": False,
        "privacy_boundary": "local document tools only; the MCP client decides what it sends to its AI model",
        "privacy": {
            "server_side_llm": False,
            "boundary": "local document tools only; the MCP client decides what it sends to its AI model",
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            **runtime_identity(),
        },
        "feature_flags": feature_flags(),
        "capabilities": [
            _capability(
                "file_hwpx",
                True,
                [
                    "detect_format",
                    "analyze_form",
                    "analyze_formfit",
                    "fill_form",
                    "extract_text",
                    "find_text",
                    "find_text_occurrences",
                    "get_document_outline",
                    "get_table_map",
                    "inspect_editable_regions",
                    "get_paragraph_map",
                    "find_cell_by_label",
                    "list_styles",
                    "verify_fill",
                    "verify_targets",
                    "plan_template_completion",
                    "validate_hwpx",
                    "scan_pii",
                    "search_and_replace",
                    "batch_replace",
                    "mail_merge",
                    "preview_search_and_replace",
                    "preview_batch_replace",
                    "preview_addressed_edits",
                    "apply_addressed_edits",
                    "complete_addressed_template",
                    "apply_edit_session",
                    "restore_edit_session",
                    "preview_assessment",
                    "apply_assessment",
                ],
                note="Core HWPX analysis, byte-preserving fill, validation, and safety gates.",
            ),
            _capability(
                "delegate_hwpx",
                delegate_available,
                [
                    "hwpx_to_html",
                    "hwpx_to_markdown",
                    "add_paragraph",
                    "add_table",
                    "merge_table_cells",
                    "set_cell_shading",
                    "add_image",
                    "emphasize_text",
                    "set_header",
                    "set_footer",
                    "split_merged_cell",
                    "set_page_size",
                    "set_page_margins",
                    "set_columns",
                    "set_page_number",
                    "create_hwpx_table",
                    "create_official_document",
                    "create_document_from_blocks",
                    "create_hwpx_from_markdown",
                    "create_document_from_spec",
                ],
                requires=["python-hwpx"],
                note="Commodity editing and generation delegated to python-hwpx.",
            ),
            _capability(
                "render",
                can_render,
                ["render_preview"],
                requires=["python-hwpx", "playwright", "chromium"],
                note=render_note or "PNG preview is optional and browser-backed.",
            ),
            _capability(
                "live_hwp",
                HwpBridge.available() or live_available(),
[
    "hwp_status",
    "open_in_hwp",
    "apply_to_open_hwp",
    "preview_small_live_label_cells",
    "apply_small_live_label_cells",
    "resolve_current_hwp_document",
    "preview_current_hwp_document",
    "apply_to_current_hwp_document",
    "live_delete_table_rows",
],
requires=["Windows", "Hangul", "pywin32", "pyhwpx"],
note=(
    "Open Hangul document control is optional and never required for file-mode "
    "HWPX work. Live tools insert VALUE content only; formatting/styling edits stay "
    "in file-mode tools. hwp_status and preview are side-effect-free, and connected:false "
    "is the normal idle state. Safe live attach is exact-path based: use open_in_hwp(path) "
    "before apply, or use the saved-.hwpx current-document resolve/preview/apply flow "
    "for tokenized pathless UX. Worker timeout isolation is currently wired only for "
    "open_in_hwp(timeout_seconds=...)."
)
            ),
            _capability(
                "hwp_headless",
                False,
                ["extract_hwp_text"],
                requires=list(hwp_headless["checked"].keys()),
                note="Adapter gate only; extraction stays unavailable until a concrete non-COM reader is selected and verified.",
            ),
        ],
        "recommended_workflows": [
            "file_form_fill",
            "file_document_generation",
            "live_hwp_cell_fill",
            "render_and_verify",
        ],
    }

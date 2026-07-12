from __future__ import annotations

import importlib.util
import sys
from typing import Any, Dict, List

from hangeul_core import delegate
from hangeul_core.hwp import HwpBridge
from hangeul_core.hwp.live import live_available
from hangeul_core.hwp_headless import headless_status
from hangeul_core.render import render_available


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
        },
        "capabilities": [
            _capability(
                "file_hwpx",
                True,
                [
                    "detect_format",
                    "analyze_form",
                    "fill_form",
                    "extract_text",
                    "find_text",
                    "get_document_outline",
                    "get_table_map",
                    "find_cell_by_label",
                    "verify_fill",
                    "validate_hwpx",
                    "scan_pii",
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
                    "create_hwpx_table",
                    "create_official_document",
                    "create_document_from_blocks",
                    "create_hwpx_from_markdown",
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
    "preview_cells_to_open_hwp",
    "apply_cells_to_open_hwp",
    "resolve_current_hwp_document",
    "preview_current_hwp_document",
    "apply_to_current_hwp_document",
],
requires=["Windows", "Hangul", "pywin32", "pyhwpx"],
note=(
    "Open Hangul document control is optional and never required for file-mode "
    "HWPX work. Live tools insert VALUE content only; formatting/styling edits stay "
    "in file-mode tools. hwp_status and preview are side-effect-free, and connected:false "
    "is the normal idle state. Safe live attach is exact-path based: use open_in_hwp(path) "
    "before apply, or use the saved-.hwpx current-document resolve/preview/apply flow "
    "for tokenized pathless UX."
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

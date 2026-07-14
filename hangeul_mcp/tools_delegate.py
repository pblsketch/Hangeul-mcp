from __future__ import annotations

from typing import Any, Dict

from hangeul_core import delegate as _delegate
from hangeul_core.convert import ensure_hwpx
from hangeul_core.mailmerge import mail_merge as _mail_merge
from hangeul_core.render import render_preview as _render_preview
from hangeul_mcp.envelope import enveloped


def _unavailable() -> Dict[str, Any]:
    return {"available": False, "error": "python-hwpx not installed (extra 'delegate')"}


def _delegate_op(extra_key: str, fn, *args, **kwargs) -> Dict[str, Any]:
    try:
        out = fn(*args, **kwargs)
        if isinstance(out, dict):
            return {"available": True, **out}
        return {"available": True, extra_key: out}
    except Exception as exc:
        return {"available": True, "ok": False, "error": str(exc)}


def _hwpx_path(path: str) -> tuple[str | None, Dict[str, Any] | None]:
    try:
        return ensure_hwpx(path), None
    except RuntimeError as exc:
        return None, {"available": True, "error": str(exc)}


def register_delegate_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def hwpx_to_html(path: str) -> Dict[str, Any]:
        """Convert HWPX to HTML via python-hwpx (delegate extra required)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("html", _delegate.to_html, path)

    @mcp.tool()
    def hwpx_to_markdown(path: str) -> Dict[str, Any]:
        """Convert HWPX to Markdown via python-hwpx (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("markdown", _delegate.to_markdown, path)

    @mcp.tool()
    def add_paragraph(path: str, text: str, out_path: str, section_index: int = -1) -> Dict[str, Any]:
        """Append a text paragraph and write a NEW file (python-hwpx delegate; reserialized, re-validate after)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        idx = None if section_index < 0 else section_index
        return error or _delegate_op("", _delegate.add_paragraph, path, text, out_path, section_index=idx)

    @mcp.tool()
    def merge_table_cells(path: str, table_index: int, cell_range: str, out_path: str) -> Dict[str, Any]:
        """Merge a table cell range (e.g. A1:B2) and write a NEW file (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.merge_table_cells, path, table_index, cell_range, out_path)

    @mcp.tool()
    def set_cell_shading(path: str, table_index: int, row: int, col: int, fill_color: str, out_path: str) -> Dict[str, Any]:
        """Set a table cell fill color and write a NEW file (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.set_cell_shading, path, table_index, row, col, fill_color, out_path)

    @mcp.tool()
    @enveloped
    def mail_merge(template_path: str, records: list, out_dir: str, mask_pii: bool = False) -> Dict[str, Any]:
        """Generate one output per record from a template using the OWN byte-preserving fill engine."""
        try:
            template_path = ensure_hwpx(template_path)
        except RuntimeError as exc:
            return {"error": str(exc), "count": 0}
        return _mail_merge(template_path, list(records), out_dir, mask_pii=mask_pii)

    @mcp.tool()
    def emphasize_text(path: str, find: str, out_path: str, bold: bool = False, italic: bool = False, underline: bool = False, color: str = "", size: float = 0.0) -> Dict[str, Any]:
        """Apply bold/italic/underline/color/size to matched text and write a NEW file (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.emphasize_text, path, find, out_path, bold=bold, italic=italic, underline=underline, color=(color or None), size=(size or None))

    @mcp.tool()
    def set_header(path: str, text: str, out_path: str, page_type: str = "BOTH") -> Dict[str, Any]:
        """Set the page header text (page_type: BOTH/EVEN/ODD as accepted by python-hwpx) to a NEW file."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.set_header, path, text, out_path, page_type=page_type)

    @mcp.tool()
    def set_footer(path: str, text: str, out_path: str, page_type: str = "BOTH") -> Dict[str, Any]:
        """Set the page footer text (page_type: BOTH/EVEN/ODD as accepted by python-hwpx) to a NEW file."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.set_footer, path, text, out_path, page_type=page_type)

    @mcp.tool()
    def split_merged_cell(path: str, table_index: int, row: int, col: int, out_path: str) -> Dict[str, Any]:
        """Split a previously merged table cell apart and write a NEW file (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.split_merged_cell, path, table_index, row, col, out_path)

    @mcp.tool()
    def set_page_size(path: str, out_path: str, width: int = 0, height: int = 0, orientation: str = "") -> Dict[str, Any]:
        """Set paper width/height/orientation (e.g. PORTRAIT/LANDSCAPE) and write a NEW file (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op(
            "",
            _delegate.set_page_size,
            path,
            out_path,
            width=(width or None),
            height=(height or None),
            orientation=(orientation or None),
        )

    @mcp.tool()
    def set_page_margins(path: str, out_path: str, left: int = -1, right: int = -1, top: int = -1, bottom: int = -1, header: int = -1, footer: int = -1, gutter: int = -1) -> Dict[str, Any]:
        """Set page margins (left/right/top/bottom/header/footer/gutter, HWPUNIT) to a NEW file (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)

        def unset(v: int):
            return None if v < 0 else v

        return error or _delegate_op(
            "",
            _delegate.set_page_margins,
            path,
            out_path,
            left=unset(left),
            right=unset(right),
            top=unset(top),
            bottom=unset(bottom),
            header=unset(header),
            footer=unset(footer),
            gutter=unset(gutter),
        )

    @mcp.tool()
    def set_columns(path: str, out_path: str, col_count: int = 2) -> Dict[str, Any]:
        """Set the body column count and write a NEW file (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.set_columns, path, out_path, col_count)

    @mcp.tool()
    def set_page_number(path: str, out_path: str, position: str = "BOTTOM_CENTER") -> Dict[str, Any]:
        """Place page numbers (position e.g. BOTTOM_CENTER, as accepted by python-hwpx) to a NEW file."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.set_page_number, path, out_path, position=position)

    @mcp.tool()
    def create_official_document(fields: Dict[str, str], out_path: str, doc_type: str = "공문") -> Dict[str, Any]:
        """Create a Korean official-document (gongmun) skeleton HWPX from fields (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        return _delegate_op("", _delegate.create_official_document, dict(fields), out_path, doc_type=doc_type)

    @mcp.tool()
    def create_hwpx_table(rows: list, out_path: str) -> Dict[str, Any]:
        """Create a new HWPX containing one table from headers/rows (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        return _delegate_op("", _delegate.create_table_from_rows, rows, out_path)

    @mcp.tool()
    def create_document_from_blocks(blocks: list, out_path: str) -> Dict[str, Any]:
        """Create an HWPX from ordered content blocks (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        return _delegate_op("", _delegate.create_document_from_blocks, blocks, out_path)

    @mcp.tool()
    def create_document_from_spec(spec: Dict[str, Any], out_path: str) -> Dict[str, Any]:
        """Create an HWPX from a DocumentSpec v1 payload (validated template union; delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        return _delegate_op("", _delegate.create_document_from_spec, spec, out_path)

    @mcp.tool()
    def create_hwpx_from_markdown(markdown: str, out_path: str) -> Dict[str, Any]:
        """Create an HWPX from Markdown content (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        return _delegate_op("", _delegate.create_from_markdown, markdown, out_path)

    @mcp.tool()
    def add_image(path: str, image_path: str, out_path: str, width_mm: float = 0.0, height_mm: float = 0.0) -> Dict[str, Any]:
        """Insert an image file into the document and write a NEW file (delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.add_picture, path, image_path, out_path, width_mm=(width_mm or None), height_mm=(height_mm or None))

    @mcp.tool()
    def add_table(path: str, rows: int, cols: int, out_path: str) -> Dict[str, Any]:
        """Append a rows x cols table and write a NEW file (python-hwpx delegate)."""
        if not _delegate.hwpx_available():
            return _unavailable()
        path, error = _hwpx_path(path)
        return error or _delegate_op("", _delegate.add_table, path, rows, cols, out_path)

    @mcp.tool()
    def render_preview(path: str, out_path: str, format: str = "png", width: int = 1280, height: int = 1800) -> Dict[str, Any]:
        """Render page PNG previews via python-hwpx + Playwright/Chromium (render extra)."""
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "ok": False, "error": str(exc)}
        return _render_preview(path, out_path, format=format, width=width, height=height)

    return {name: obj for name, obj in locals().items() if callable(obj) and not name.startswith("_")}

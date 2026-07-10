from __future__ import annotations

from hangeul_core.delegate_base import hwpx_available, to_html, to_markdown, to_text_rich
from hangeul_core.delegate_edit import (
    add_paragraph,
    add_picture,
    add_table,
    emphasize_text,
    merge_table_cells,
    set_cell_shading,
    set_columns,
    set_footer,
    set_header,
    set_page_margins,
    set_page_number,
    set_page_size,
)
from hangeul_core.delegate_generate import (
    create_document_from_blocks,
    create_from_markdown,
    create_official_document,
    create_table_from_rows,
)

__all__ = [
    "add_paragraph",
    "add_picture",
    "add_table",
    "create_document_from_blocks",
    "create_from_markdown",
    "create_official_document",
    "create_table_from_rows",
    "emphasize_text",
    "hwpx_available",
    "merge_table_cells",
    "set_cell_shading",
    "set_columns",
    "set_footer",
    "set_header",
    "set_page_margins",
    "set_page_number",
    "set_page_size",
    "to_html",
    "to_markdown",
    "to_text_rich",
]

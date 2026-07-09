"""US-056 / BC1: python-hwpx delegate API-surface contract (ADR D13).

Existence of SUPPORTED methods is a HARD gate — it is the real contract behind
the header/footer, page-setup and split-merged-cell delegate tools.

Absence checks for UNSUPPORTED methods are a SOFT TRIPWIRE only: if a future
python-hwpx release adds row/column or TOC APIs, that is good news, not a
failure — the test emits a warning telling us to revisit US-060 / ADR D13 and
must NEVER turn the suite red (BC1).
"""

import warnings

import pytest

pytest.importorskip("hwpx")

from hwpx.document import HwpxDocument  # noqa: E402
from hwpx.oxml import HwpxOxmlTable  # noqa: E402

SUPPORTED_DOCUMENT = [
    "set_header_text",
    "set_footer_text",
    "remove_header",
    "remove_footer",
    "set_page_size",
    "set_page_margins",
    "set_page_number",
    "set_columns",
]
SUPPORTED_TABLE = [
    "merge_cells",
    "split_merged_cell",
    "get_cell_map",
    "set_cell_shading",
    "set_cell_text",
    "set_column_widths",
]
# Documented as unsupported in ADR D13; reclassified to OWN research (US-060).
UNSUPPORTED = {
    HwpxOxmlTable: ["add_row", "remove_row", "add_column", "remove_column", "split_cell"],
    HwpxDocument: ["generate_toc", "add_toc", "toc"],
}


def test_supported_document_surface_exists():
    missing = [m for m in SUPPORTED_DOCUMENT if not callable(getattr(HwpxDocument, m, None))]
    assert not missing, (
        f"python-hwpx no longer exposes {missing}; delegate tools relying on them "
        "break — check the installed version against the delegate extra floor (>=2.24,<3)"
    )


def test_supported_table_surface_exists():
    missing = [m for m in SUPPORTED_TABLE if not callable(getattr(HwpxOxmlTable, m, None))]
    assert not missing, (
        f"python-hwpx no longer exposes table methods {missing}; "
        "check the installed version against the delegate extra floor (>=2.24,<3)"
    )


def test_unsupported_surface_tripwire_soft():
    """BC1: never assert absence — only warn when upstream grows the surface."""
    appeared = [
        f"{cls.__name__}.{m}"
        for cls, names in UNSUPPORTED.items()
        for m in names
        if hasattr(cls, m)
    ]
    if appeared:  # pragma: no cover - fires only on future python-hwpx releases
        warnings.warn(
            "python-hwpx now exposes previously-unsupported APIs: "
            f"{appeared} — revisit US-060 / ADR D13 (row-col/TOC delegate feasibility)",
            UserWarning,
            stacklevel=1,
        )
    # deliberately no assert: upstream improvement must not redden the suite

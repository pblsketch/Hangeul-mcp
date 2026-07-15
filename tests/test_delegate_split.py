"""US-059: split_merged_cell delegate tool.

G1 (binding condition): the input must PROVABLY contain a merged cell before
split is exercised — the precondition is asserted loudly so the test can never
vacuously pass on a fixture without merges. The merged input is built
deterministically in-test (create 3x3 table -> merge A1:B2).
"""

import pytest

pytest.importorskip("hwpx")

from hangeul_core.delegate import create_table_from_rows
from hangeul_core.delegate_edit import merge_table_cells, split_merged_cell
from hangeul_core.owpml import HwpxPackage
from hangeul_mcp import server


def _section0(path) -> str:
    return HwpxPackage.open(path).read("Contents/section0.xml").decode("utf-8")


def _merged_fixture(tmp_path):
    base = tmp_path / "table.hwpx"
    merged = tmp_path / "merged.hwpx"
    create_table_from_rows([["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]], str(base))
    res = merge_table_cells(base, 0, "A1:B2", merged)
    assert res["ok"] is True
    # G1 loud precondition: a real merged cell (span > 1) must exist
    xml = _section0(merged)
    assert 'colSpan="2"' in xml and 'rowSpan="2"' in xml, (
        "precondition failed: merged fixture has no rowSpan/colSpan>1 cell — "
        "split test would be vacuous"
    )
    return merged, xml


def test_split_merged_cell_unmerges_region(tmp_path):
    merged, before_xml = _merged_fixture(tmp_path)
    out = tmp_path / "split.hwpx"
    res = split_merged_cell(merged, 0, 0, 0, out)
    assert res["ok"] is True
    # observable contract: the span>1 attributes disappear (the merge is undone).
    # python-hwpx's tc bookkeeping on unmerge changed across 2.24->2.29 (2.24 keeps
    # the 6 merged-layout slots, 2.29 restores all 9 individual cells), so assert the
    # merge is gone without pinning the count — an unmerge must never LOSE cells (BC1:
    # tolerate minor delegate drift instead of over-pinning the version).
    after_xml = _section0(out)
    assert 'colSpan="2"' not in after_xml and 'rowSpan="2"' not in after_xml
    assert after_xml.count("<hp:tc") >= before_xml.count("<hp:tc")


def test_split_non_merged_cell_is_structured_error(tmp_path):
    base = tmp_path / "plain.hwpx"
    create_table_from_rows([["a", "b"], ["c", "d"]], str(base))
    res = server.split_merged_cell(str(base), 0, 0, 0, str(tmp_path / "o.hwpx"))
    assert res.get("ok") is False
    assert res.get("error")


def test_split_tool_registered():
    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    assert "split_merged_cell" in {t.name for t in tools}

"""US-058: page-setup delegate tools (size/margins/columns/page-number).

BC2: validate_hwpx alone can pass on a no-op, so every test RE-OPENS the saved
package and asserts the actual section-XML properties changed
(<hp:pagePr>, <hp:margin>, <hp:colPr>, <hp:pageNum> — empirically verified).
"""

import re

import pytest

pytest.importorskip("hwpx")

from pathlib import Path

from hangeul_core.delegate_edit import (
    set_columns,
    set_page_margins,
    set_page_number,
    set_page_size,
)
from hangeul_core.owpml import HwpxPackage
from hangeul_mcp import server

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def _section0(path) -> str:
    return HwpxPackage.open(path).read("Contents/section0.xml").decode("utf-8")


def test_set_page_size_changes_pagepr(tmp_path):
    out = tmp_path / "size.hwpx"
    res = set_page_size(FIXTURE, out, width=50000, height=70000)
    assert res["ok"] is True
    pagepr = re.search(r"<hp:pagePr[^>]*>", _section0(out)).group(0)
    assert 'width="50000"' in pagepr and 'height="70000"' in pagepr


def test_set_page_margins_changes_margin_attrs(tmp_path):
    out = tmp_path / "margin.hwpx"
    res = set_page_margins(FIXTURE, out, left=4321, right=1234, top=999, bottom=888)
    assert res["ok"] is True
    margin = re.search(r"<hp:margin[^>]*/?>", _section0(out)).group(0)
    for frag in ('left="4321"', 'right="1234"', 'top="999"', 'bottom="888"'):
        assert frag in margin


def test_set_columns_adds_colpr(tmp_path):
    out = tmp_path / "col.hwpx"
    res = set_columns(FIXTURE, out, col_count=2)
    assert res["ok"] is True
    assert 'colCount="2"' in _section0(out)


def test_set_page_number_adds_pagenum_field(tmp_path):
    out = tmp_path / "pn.hwpx"
    res = set_page_number(FIXTURE, out)
    assert res["ok"] is True
    assert re.search(r"<hp:pageNum[^>]*pos=\"BOTTOM_CENTER\"", _section0(out))


def test_invalid_args_return_structured_error(tmp_path):
    out = tmp_path / "bad.hwpx"
    assert set_page_size(FIXTURE, out, width=-5)["ok"] is False
    assert set_page_margins(FIXTURE, out, left=-1)["ok"] is False
    assert set_page_margins(FIXTURE, out)["ok"] is False  # nothing to change
    assert set_columns(FIXTURE, out, col_count=0)["ok"] is False
    assert not out.exists()  # rejected inputs must not write output


def test_page_setup_tools_registered():
    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"set_page_size", "set_page_margins", "set_columns", "set_page_number"} <= names

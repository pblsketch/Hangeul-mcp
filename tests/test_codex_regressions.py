"""Regression tests for QA findings (codex gpt-5.6-sol review, 2026-07-15).

Each locks a concrete bug the review surfaced. The synthetic-XML cases need no
template fixture; the multi-table case is guarded on the fixture's presence.
"""

import re
import tempfile
import zipfile
from pathlib import Path

import pytest

from hangeul_core.addressed import _blank_paragraph_like, _delete_table_at, complete_addressed_template
from hangeul_core.charpr import ensure_char_pr, header_charpr_order_ok, set_runs_bold
from hangeul_mcp.tools_file_edit import AddressedEdit, _normalize_addressed_edits

FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"

_HDR = (
    '<hh:charProperties itemCnt="{n}">{body}</hh:charProperties>'
)


def _charpr(cid, *, italic=False, bold=False):
    mid = ("<hh:bold/>" if bold else "") + ("<hh:italic/>" if italic else "")
    return f'<hh:charPr id="{cid}" height="1000"><hh:fontRef hangul="1"/><hh:offset hangul="0"/>{mid}<hh:underline type="NONE"/></hh:charPr>'


def _block_of(header, cid):
    return re.search(r'<hh:charPr id="' + cid + r'".*?</hh:charPr>', header, re.S).group(0)


def test_bold_inserted_before_italic():  # finding #5
    header = _HDR.format(n=1, body=_charpr("5", italic=True))
    new_header, cid = ensure_char_pr(header, "5", bold=True)
    assert "<hh:bold/><hh:italic/>" in _block_of(new_header, cid)


def test_order_check_flags_bold_after_italic():  # finding #5
    bad = _HDR.format(n=1, body='<hh:charPr id="5"><hh:offset hangul="0"/><hh:italic/><hh:bold/><hh:underline type="NONE"/></hh:charPr>')
    ok, errors = header_charpr_order_ok(bad)
    assert not ok and errors


def test_self_closing_run_does_not_steal_bold():  # finding #8
    header = _HDR.format(n=2, body=_charpr("15") + _charpr("14", bold=True))
    block = '<hp:p><hp:run charPrIDRef="13"/><hp:run charPrIDRef="15"><hp:t>Alpha</hp:t></hp:run></hp:p>'
    new_block, _ = set_runs_bold(block, header, True)
    assert 'charPrIDRef="14"><hp:t>Alpha' in new_block  # text run bolded
    assert 'charPrIDRef="13"/>' in new_block  # empty self-closing run untouched


def test_itemcnt_bumped_with_extra_attributes():  # finding #11
    header = '<hh:charProperties otherAttr="x" itemCnt="1">' + _charpr("0") + "</hh:charProperties>"
    new_header, _ = ensure_char_pr(header, "0", bold=True)
    assert 'itemCnt="2"' in new_header


def test_paired_bold_element_removed():  # finding #12
    header = _HDR.format(n=1, body='<hh:charPr id="0"><hh:offset hangul="0"/><hh:bold></hh:bold><hh:underline type="NONE"/></hh:charPr>')
    new_header, cid = ensure_char_pr(header, "0", bold=False)
    assert "<hh:bold" not in _block_of(new_header, cid)


def test_blank_paragraph_drops_image_keeps_style():  # finding #4
    block = '<hp:p paraPrIDRef="7"><hp:run charPrIDRef="3"><hp:t>cap</hp:t><hp:pic><hp:img/></hp:pic></hp:run></hp:p>'
    blank = _blank_paragraph_like(block)
    assert "<hp:pic" not in blank and 'paraPrIDRef="7"' in blank and "<hp:t></hp:t>" in blank


def test_delete_table_keeps_same_run_caption():  # finding #3
    section = (
        '<hp:p><hp:run charPrIDRef="6"><hp:t>Cap</hp:t>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr><hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="6"><hp:t>x</hp:t></hp:run></hp:p></hp:subList>'
        "</hp:tc></hp:tr></hp:tbl></hp:run></hp:p>"
    )
    new_section, _ = _delete_table_at(section, 1)
    assert "<hp:tbl" not in new_section and "Cap" in new_section


@pytest.mark.skipif(not FIXTURE.exists(), reason="template fixture not present")
def test_multiple_delete_table_bottom_up():  # finding #1
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "o.hwpx"
        res = complete_addressed_template(
            FIXTURE,
            _normalize_addressed_edits([
                AddressedEdit(target="t2", operation="delete_table"),
                AddressedEdit(target="t3", operation="delete_table"),
            ]),
            out,
        )
        assert res["ok"] and res["state"] == "complete", res
        remaining = zipfile.ZipFile(out).read("Contents/section0.xml").decode().count("<hp:tbl")
        assert remaining == 1  # both t2 and t3 removed, header table remains

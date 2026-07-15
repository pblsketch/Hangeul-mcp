"""Unit tests for byte-preserving bold charPr resolution (S1)."""

import re
import zipfile
from pathlib import Path
import pytest

from hangeul_core.charpr import ensure_char_pr, set_runs_bold

FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="template fixture not present in this checkout"
)
_HEADER_ENTRY = "Contents/header.xml"


def _header() -> str:
    with zipfile.ZipFile(FIXTURE) as z:
        return z.read("Contents/header.xml").decode("utf-8")


def _item_cnt(header: str) -> int:
    return int(re.search(r'<hh:charProperties itemCnt="(\d+)"', header).group(1))


def _block(header: str, cid: str) -> str:
    return re.search(
        r'<hh:charPr id="' + cid + r'"(?:(?!</hh:charPr>).)*</hh:charPr>', header, re.S
    ).group(0)


def test_reuse_existing_bold_variant():
    # charPr 14 is charPr 15 + <hh:bold/>: ensure(base=15, bold=True) must REUSE 14.
    header = _header()
    before_cnt = _item_cnt(header)
    new_header, cid = ensure_char_pr(header, "15", bold=True)
    assert cid == "14"
    assert new_header == header  # reuse => header untouched
    assert _item_cnt(new_header) == before_cnt


def test_noop_when_already_matches():
    header = _header()
    new_header, cid = ensure_char_pr(header, "14", bold=True)
    assert cid == "14"
    assert new_header == header


def test_append_new_charpr_bumps_itemcnt_and_places_bold_at_slot():
    header = _header()
    before_cnt = _item_cnt(header)
    ids_before = set(re.findall(r'<hh:charPr id="(\d+)"', header))
    # charPr 0 is normal with a distinct fontRef/borderFill not shared by any
    # bold charPr, so its bold variant must be freshly appended.
    new_header, cid = ensure_char_pr(header, "0", bold=True)
    assert cid not in ids_before
    assert _item_cnt(new_header) == before_cnt + 1
    block = _block(new_header, cid)
    # bold sits between offset and underline (fixed OWPML slot).
    assert "<hh:bold/>" in block
    assert re.search(r"<hh:offset\b[^>]*/><hh:bold/><hh:underline\b", block)
    # every pre-existing charPr kept its exact bytes.
    for old in ids_before:
        assert _block(header, old) == _block(new_header, old)


def test_remove_bold():
    header = _header()
    new_header, cid = ensure_char_pr(header, "14", bold=False)
    # charPr 15 == charPr 14 minus bold, so removal reuses 15.
    assert cid == "15"
    assert new_header == header


def test_missing_base_fails_closed():
    header = _header()
    new_header, cid = ensure_char_pr(header, "9999", bold=True)
    assert cid is None
    assert new_header == header


def test_set_runs_bold_retargets_text_runs_but_not_control_runs():
    header = _header()
    block = (
        '<hp:p paraPrIDRef="31">'
        '<hp:run charPrIDRef="13"/>'  # self-closing control run: keep
        '<hp:run charPrIDRef="15"><hp:t>1. 문항 본문</hp:t></hp:run>'
        '<hp:run charPrIDRef="15"><hp:t></hp:t></hp:run>'  # emptied paired run: cleaned
        "</hp:p>"
    )
    new_block, new_header = set_runs_bold(block, header, True)
    # text run bolded (14); the empty run stays non-bold (15) -> no bold shell.
    assert 'charPrIDRef="14"><hp:t>1. 문항 본문' in new_block
    assert 'charPrIDRef="15"><hp:t></hp:t>' in new_block
    assert 'charPrIDRef="13"/>' in new_block  # control run untouched


def test_set_runs_bold_multiline_clones_all_bolded():
    header = _header()
    # Two cloned choice paragraphs both non-bold -> both must become bold.
    block = (
        '<hp:p paraPrIDRef="31"><hp:run charPrIDRef="15"><hp:t>① 선지 하나</hp:t></hp:run></hp:p>'
        '<hp:p paraPrIDRef="31"><hp:run charPrIDRef="15"><hp:t>② 선지 둘</hp:t></hp:run></hp:p>'
    )
    new_block, _ = set_runs_bold(block, header, True)
    assert new_block.count('charPrIDRef="14"') == 2
    assert 'charPrIDRef="15"' not in new_block


# --- Integration: full preview -> apply pipeline (S0 header lane + S1 bold) ---

import zipfile as _zip

from hangeul_core.addressed import apply_addressed_edits, preview_addressed_edits
from hangeul_mcp.tools_file_edit import AddressedEdit, _normalize_addressed_edits


def _preview(edits: list[dict]):
    """Normalize like the MCP tool layer does before previewing."""
    return preview_addressed_edits(
        FIXTURE, _normalize_addressed_edits([AddressedEdit(**e) for e in edits])
    )


def _run_charpr_for_text(hwpx_path: Path, text_fragment: str) -> str:
    with _zip.ZipFile(hwpx_path) as z:
        sec = z.read("Contents/section0.xml").decode("utf-8")
    m = re.search(
        r'<hp:run\b[^>]*\bcharPrIDRef="(\d+)"[^>]*>(?:(?!</hp:run>).)*?'
        + re.escape(text_fragment),
        sec,
        re.S,
    )
    assert m, f"run carrying {text_fragment!r} not found"
    return m.group(1)


def test_pipeline_bold_stages_header_and_repoints_run(tmp_path):
    prev = _preview(
        [{"target": "b2", "value": "① 정확해야 한다.", "bold": True}],
    )
    assert prev["ok"], prev.get("unresolved")
    # S0: header.xml flows into the session change set.
    assert _HEADER_ENTRY in prev["changed_entries"]
    out = tmp_path / "bold_out.hwpx"
    res = apply_addressed_edits(prev["session_id"], out)
    assert res["ok"], res
    # b2's choice run is now bold (reused charPr 14).
    assert _run_charpr_for_text(out, "정확해야 한다") == "14"
    # reuse path => header bytes unchanged from source.
    with _zip.ZipFile(FIXTURE) as z:
        src_header = z.read("Contents/header.xml")
    with _zip.ZipFile(out) as z:
        out_header = z.read("Contents/header.xml")
    assert out_header == src_header


def test_pipeline_unbold_appends_charpr(tmp_path):
    prev = _preview(
        [{"target": "b1", "value": "1. 기사문의 특징으로 옳은 것은? [3점]", "bold": False}],
    )
    assert prev["ok"], prev.get("unresolved")
    assert _HEADER_ENTRY in prev["changed_entries"]
    out = tmp_path / "unbold_out.hwpx"
    res = apply_addressed_edits(prev["session_id"], out)
    assert res["ok"], res
    cid = _run_charpr_for_text(out, "기사문의 특징")
    with _zip.ZipFile(out) as z:
        header = z.read("Contents/header.xml").decode("utf-8")
    block = _block(header, cid)
    assert "<hh:bold/>" not in block  # stem is now non-bold


def test_pipeline_no_bold_leaves_header_untouched(tmp_path):
    prev = _preview(
        [{"target": "b2", "value": "① 정확해야 한다."}],
    )
    assert prev["ok"], prev.get("unresolved")
    assert _HEADER_ENTRY not in prev["changed_entries"]


# --- S1 validation gate ---

from hangeul_core import charpr as _charpr
from hangeul_core.addressed import complete_addressed_template
from hangeul_core.charpr import header_charpr_order_ok


def test_order_check_flags_misplaced_bold():
    header = _header()
    block = _block(header, "15")
    bad = header.replace(block, block.replace("</hh:charPr>", "<hh:bold/></hh:charPr>"))
    ok, errors = header_charpr_order_ok(bad)
    assert not ok and errors


def test_complete_bold_passes_gate(tmp_path):
    out = tmp_path / "gated_ok.hwpx"
    res = complete_addressed_template(
        FIXTURE,
        _normalize_addressed_edits(
            [AddressedEdit(target="b2", value="① 정확해야 한다.", bold=True)]
        ),
        out,
    )
    assert res["ok"] and res["state"] == "complete", res


def test_complete_refuses_misordered_bold(tmp_path, monkeypatch):
    # Force ensure_char_pr to append <hh:bold/> at the WRONG slot (schema-invalid);
    # the gate must refuse rather than report complete.
    orig = _charpr._with_bold

    def bad_with_bold(block, bold):
        if bold and not _charpr._has_bold(block):
            return block.replace("</hh:charPr>", "<hh:bold/></hh:charPr>")
        return orig(block, bold)

    monkeypatch.setattr(_charpr, "_with_bold", bad_with_bold)
    out = tmp_path / "gated_bad.hwpx"
    res = complete_addressed_template(
        FIXTURE,
        _normalize_addressed_edits(
            [AddressedEdit(target="b2", value="① 정확해야 한다.", bold=True)]
        ),
        out,
    )
    assert not res["ok"] and res["state"] == "invalid_output", res

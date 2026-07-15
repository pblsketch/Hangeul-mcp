"""S6 e2e: one batch fixes the three original 형성평가 complaints.

Reproduces the failing scenario (bold stems / non-bold choices, an orphaned
<보기> box, and missing spacing) and asserts the corrected structure end-to-end
through complete_addressed_template, gated on validation.
"""

import re
import zipfile
from pathlib import Path
import pytest

from hangeul_core.addressed import complete_addressed_template, inspect_editable_regions
from hangeul_core.charpr import bold_charpr_ids, count_stray_empty_bold_runs
from hangeul_mcp.tools_file_edit import AddressedEdit, _normalize_addressed_edits

FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="template fixture not present in this checkout"
)


def _section(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def _header(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("Contents/header.xml").decode("utf-8")


def _charpr_for(section: str, text_fragment: str) -> str:
    m = re.search(
        r'<hp:run\b[^>]*\bcharPrIDRef="(\d+)"[^>]*>(?:(?!</hp:run>).)*?' + re.escape(text_fragment),
        section,
        re.S,
    )
    assert m, f"run for {text_fragment!r} not found"
    return m.group(1)


def test_e2e_bold_choices_bogi_and_spacing(tmp_path):
    out = tmp_path / "fixed.hwpx"
    tbl_before = _section(FIXTURE).count("<hp:tbl")
    # the template itself ships a few empty bold runs; our edits must not add any.
    base_stray = count_stray_empty_bold_runs(_section(FIXTURE), _header(FIXTURE))

    edits = _normalize_addressed_edits([
        # complaint #2: stem bold, choices non-bold
        AddressedEdit(target="b1", value="1. 기사문의 특징으로 옳은 것은? [3점]", bold=True),
        AddressedEdit(target="b2", value="  ① 정확해야 한다.", bold=False),
        AddressedEdit(target="b3", value="  ② 간결해야 한다.", bold=False),
        # complaint #1: remove the orphaned <보기> box (t2)
        AddressedEdit(target="t2", operation="delete_table"),
        # complaint #3: add a blank spacer after the last choice
        AddressedEdit(target="b6", operation="insert_blank_after"),
    ])
    res = complete_addressed_template(FIXTURE, edits, out)

    # gate passed, no schema damage, and we didn't add any bold blank lines
    assert res["ok"] and res["state"] == "complete", res
    assert res["structure_report"]["stray_empty_bold_runs"] <= base_stray

    section = _section(out)
    header = _header(out)
    bold_ids = bold_charpr_ids(header)

    # #2: stem bold, choices not bold
    assert _charpr_for(section, "기사문의 특징") in bold_ids
    assert _charpr_for(section, "정확해야 한다") not in bold_ids
    assert _charpr_for(section, "간결해야 한다") not in bold_ids

    # #1: 보기 box gone
    assert section.count("<hp:tbl") == tbl_before - 1
    regions = str(inspect_editable_regions(out, compact=True))
    assert "학년" in regions  # header title table survived

    # #3: a blank spacer paragraph now sits immediately after choice ⑤ (b6).
    tail = section[section.index("구성 방식을 취한다"):]
    after_b6 = tail[tail.index("</hp:p>") + len("</hp:p>"):]
    next_p = re.search(r"<hp:p\b.*?</hp:p>", after_b6, re.S)
    assert next_p is not None
    assert not re.search(r"<hp:t>\s*[^\s<]", next_p.group(0))  # the following paragraph is blank

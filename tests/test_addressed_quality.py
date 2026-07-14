"""편집 품질 회귀 3종 — 실기기 증상 고정.

1) lineseg 캐시: 텍스트만 바꾸고 줄배치 캐시를 남기면 한글이 옛 줄틀에 긴 텍스트를
   구겨 넣어 글자가 겹친다 → 편집한 문단의 캐시는 제거되어야 한다.
2) 멀티라인 값: 개조식 "1. …\n2. …"는 실제 문단 분리로 저장되어야 한다.
3) 마커: 다문단 셀은 문단별 텍스트/마커를 노출하고, ▶/-/□/○/▷/• 마커는
   preserve_marker_replace_tail로 보존한 채 채울 수 있어야 한다.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

import pytest

from hangeul_core.addressed import (
    _paragraph_marker,
    complete_addressed_template,
    inspect_editable_regions,
    preview_addressed_edits,
)

TEMPLATE = Path(__file__).parent / "hwpx template" / "14_교수학습 지도안 양식.hwpx"


def _section(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def _cell_xml(xml: str, table: int, row: int, col: int) -> str:
    tables = re.findall(r"<hp:tbl .*?</hp:tbl>", xml, re.S)
    cells = re.findall(r"<hp:tc .*?</hp:tc>", tables[table - 1], re.S)
    for cell in cells:
        addr = re.search(r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"', cell)
        if addr and addr.group(1) == str(col) and addr.group(2) == str(row):
            return cell
    raise AssertionError(f"cell t{table}.r{row}.c{col} not found")


def _para_blocks(cell_xml: str) -> list[str]:
    return re.split(r"(?=<hp:p )", cell_xml)[1:]


def _para_texts(cell_xml: str) -> list[str]:
    texts = []
    for block in _para_blocks(cell_xml):
        block = block.split("</hp:p>")[0]
        texts.append("".join(re.findall(r"<hp:t>([^<]*)</hp:t>", block)))
    return texts


def _find_region(regions, target):
    return next(r for r in regions if r["target"] == target)


def test_inspection_exposes_per_paragraph_markers():
    ins = inspect_editable_regions(str(TEMPLATE), compact=True)
    mixed = _find_region(ins["regions"], "t2.r5.c2")
    paras = mixed.get("paragraphs")
    assert paras, "multi-paragraph cells must expose per-paragraph detail"
    assert [p["text"] for p in paras] == ["▶", "-", "", "▶", "-"]
    assert [p["marker"].strip() for p in paras] == ["▶", "-", "", "▶", "-"]
    assert [p["target"] for p in paras] == mixed["paragraph_targets"]


@pytest.mark.parametrize(
    ("text", "marker"),
    [
        ("□ 항목", "□ "),
        ("○ 내용을 적는다", "○ "),
        ("▷ 하위 항목", "▷ "),
        ("• 요점", "• "),
        ("- 세부 사항", "- "),
        ("▶ 활동", "▶ "),
        ("▶", "▶"),
        ("-", "-"),
        ("일반 산문 문장이다", ""),
        ("3 - 4교시", ""),
        ("", ""),
    ],
)
def test_official_document_marker_charset(text, marker):
    assert _paragraph_marker(text) == marker


def test_multiline_value_creates_real_paragraphs(tmp_path):
    src = tmp_path / "form.hwpx"
    shutil.copyfile(TEMPLATE, src)
    out = tmp_path / "form.done.hwpx"
    ins = inspect_editable_regions(str(src), compact=True)
    goal = _find_region(ins["regions"], "t1.r4.c1")
    res = complete_addressed_template(
        str(src),
        [{
            "target": "t1.r4.c1",
            "kind": "cell",
            "operation": "replace_text",
            "value": "1. 영상 언어의 표현 특성을 이해할 수 있다.\n2. 매체 특성을 고려하여 기획할 수 있다.",
            "expected_text": goal["text"],
        }],
        str(out),
        verify=True,
    )
    assert res["ok"] is True, res
    cell = _cell_xml(_section(out), 1, 4, 1)
    assert _para_texts(cell) == [
        "1. 영상 언어의 표현 특성을 이해할 수 있다.",
        "2. 매체 특성을 고려하여 기획할 수 있다.",
    ]
    para_prs = re.findall(r'<hp:p [^>]*paraPrIDRef="(\d+)"', cell)
    assert len(para_prs) == 2 and len(set(para_prs)) == 1, "clones must keep the original paragraph style"
    assert "<hp:linesegarray" not in cell, "edited cell must not keep stale layout cache"


def test_multiline_requires_exclusive_cell(tmp_path):
    src = tmp_path / "form.hwpx"
    shutil.copyfile(TEMPLATE, src)
    res = preview_addressed_edits(
        str(src),
        [
            {"target": "t2.r5.c2.p1", "kind": "paragraph", "operation": "replace_text", "value": "줄1\n줄2"},
            {"target": "t2.r5.c2.p4", "kind": "paragraph", "operation": "replace_text", "value": "다른 편집"},
        ],
    )
    assert res["ok"] is False
    reasons = {item.get("reason") for item in res["unresolved"]}
    assert "multiline_requires_exclusive_cell" in reasons


def test_lineseg_cache_dropped_only_on_edited_paragraphs(tmp_path):
    src = tmp_path / "form.hwpx"
    shutil.copyfile(TEMPLATE, src)
    out = tmp_path / "form.done.hwpx"
    res = complete_addressed_template(
        str(src),
        [{
            "target": "t2.r5.c2.p1",
            "kind": "paragraph",
            "operation": "replace_text",
            "value": "▶ 영상 언어 4요소를 개별 워크시트에 정리한 뒤 모둠 내에서 공유한다",
            "expected_text": "▶",
        }],
        str(out),
        verify=True,
    )
    assert res["ok"] is True, res
    paras = _para_blocks(_cell_xml(_section(out), 2, 5, 2))
    assert "<hp:linesegarray" not in paras[0], "edited paragraph must drop the stale lineseg cache"
    assert all("<hp:linesegarray" in p for p in paras[1:]), "untouched paragraphs keep their bytes"


def test_preserve_marker_replace_tail_fills_marker_items(tmp_path):
    src = tmp_path / "form.hwpx"
    shutil.copyfile(TEMPLATE, src)
    out = tmp_path / "form.done.hwpx"
    res = complete_addressed_template(
        str(src),
        [
            {"target": "t2.r5.c2.p2", "kind": "paragraph", "operation": "preserve_marker_replace_tail",
             "value": "모둠 결과를 공유한다", "expected_text": "-"},
            {"target": "t2.r5.c2.p1", "kind": "paragraph", "operation": "preserve_marker_replace_tail",
             "value": "핵심 개념을 정리한다", "expected_text": "▶"},
        ],
        str(out),
        verify=True,
    )
    assert res["ok"] is True, res
    texts = _para_texts(_cell_xml(_section(out), 2, 5, 2))
    assert texts[0] == "▶ 핵심 개념을 정리한다"
    assert texts[1] == "- 모둠 결과를 공유한다"
    assert texts[2] == "" and texts[3] == "▶" and texts[4] == "-", "other paragraphs untouched"


def test_body_paragraph_edit_drops_lineseg(tmp_path):
    src = tmp_path / "form.hwpx"
    shutil.copyfile(TEMPLATE, src)
    out = tmp_path / "form.done.hwpx"
    res = complete_addressed_template(
        str(src),
        [{"target": "b1", "kind": "body_para", "operation": "replace_text",
          "value": "국어과 교수-학습 과정안"}],
        str(out),
        verify=True,
    )
    assert res["ok"] is True, res
    xml = _section(out)
    idx = xml.find("국어과 교수-학습 과정안")
    assert idx != -1
    p_start = xml.rfind("<hp:p ", 0, idx)
    p_end = xml.find("</hp:p>", idx)
    assert "<hp:linesegarray" not in xml[p_start:p_end]

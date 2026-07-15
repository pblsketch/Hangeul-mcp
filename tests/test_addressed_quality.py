"""편집 품질 회귀 3종 — 실기기 증상 고정 (합성 픽스처, CI-safe).

1) lineseg 캐시: 텍스트만 바꾸고 줄배치 캐시를 남기면 한글이 옛 줄틀에 긴 텍스트를
   구겨 넣어 글자가 겹친다 → 편집한 문단의 캐시는 제거되어야 한다.
2) 멀티라인 값: 개조식 "1. …\n2. …"는 실제 문단 분리로 저장되어야 한다.
3) 마커: 다문단 셀은 문단별 텍스트/마커를 노출하고, ▶/-/□/○/▷/• 마커는
   preserve_marker_replace_tail로 보존한 채 채울 수 있어야 한다.

픽스처는 HANDOFF 불변식 6에 따라 PII 없는 합성 HWPX만 사용한다(사용자 템플릿 비의존).
합성 문단에는 실제 한글이 저장하는 <hp:linesegarray> 줄배치 캐시를 심어, "캐시가
제거되는가"를 실제 스플라이스 경로로 검증한다.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from hangeul_core.addressed import (
    _paragraph_marker,
    complete_addressed_template,
    inspect_editable_regions,
    preview_addressed_edits,
)

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)
_LSEG = '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" horzsize="28788" flags="393216"/></hp:linesegarray>'


def _p(pid: str, text: str, *, para_pr: int = 5, char_pr: int = 0) -> str:
    run = (
        f'<hp:run charPrIDRef="{char_pr}"><hp:t>{text}</hp:t></hp:run>'
        if text
        else f'<hp:run charPrIDRef="{char_pr}"/>'
    )
    return f'<hp:p id="{pid}" paraPrIDRef="{para_pr}">{run}{_LSEG}</hp:p>'


def _cell(row: int, col: int, *paras: str) -> str:
    return (
        f'<hp:tc><hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        f'<hp:subList>{"".join(paras)}</hp:subList></hp:tc>'
    )


def _build_fixture(dst: Path) -> None:
    """Body marker para + one table: r0 = single goal para, r1 = 5-para marker cell."""
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        + _p("10", "▶ 본문 안내")
        + '<hp:tbl rowCnt="2" colCnt="1">'
        + f'<hp:tr>{_cell(0, 0, _p("20", "{목표}"))}</hp:tr>'
        + '<hp:tr>'
        + _cell(1, 0, _p("21", "▶"), _p("22", "-"), _p("23", ""), _p("24", "▶"), _p("25", "-"))
        + '</hp:tr>'
        + '</hp:tbl>'
        + '</hs:sec>'
    )
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0.encode("utf-8"))


@pytest.fixture
def form(tmp_path: Path) -> Path:
    src = tmp_path / "form.hwpx"
    _build_fixture(src)
    return src


def _section(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def _cell_xml(xml: str, table: int, row: int, col: int) -> str:
    tables = re.findall(r"<hp:tbl\b.*?</hp:tbl>", xml, re.S)
    for cell in re.findall(r"<hp:tc\b.*?</hp:tc>", tables[table - 1], re.S):
        addr = re.search(r"<hp:cellAddr\b([^>]*)/>", cell)
        if not addr:
            continue
        attrs = dict(re.findall(r'(\w+)="(\d+)"', addr.group(1)))
        if attrs.get("colAddr") == str(col) and attrs.get("rowAddr") == str(row):
            return cell
    raise AssertionError(f"cell t{table}.r{row}.c{col} not found")


def _para_blocks(cell_xml: str) -> list[str]:
    return re.split(r"(?=<hp:p )", cell_xml)[1:]


def _para_texts(cell_xml: str) -> list[str]:
    return ["".join(re.findall(r"<hp:t>([^<]*)</hp:t>", b.split("</hp:p>")[0])) for b in _para_blocks(cell_xml)]


def _find_region(regions, target):
    return next(r for r in regions if r["target"] == target)


def test_inspection_exposes_per_paragraph_markers(form):
    ins = inspect_editable_regions(str(form), compact=True)
    mixed = _find_region(ins["regions"], "t1.r1.c0")
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


def test_multiline_value_creates_real_paragraphs(form, tmp_path):
    out = tmp_path / "form.done.hwpx"
    res = complete_addressed_template(
        str(form),
        [{
            "target": "t1.r0.c0",
            "kind": "cell",
            "operation": "replace_text",
            "value": "1. 영상 언어의 표현 특성을 이해할 수 있다.\n2. 매체 특성을 고려하여 기획할 수 있다.",
            "expected_text": "{목표}",
        }],
        str(out),
        verify=True,
    )
    assert res["ok"] is True, res
    cell = _cell_xml(_section(out), 1, 0, 0)
    assert _para_texts(cell) == [
        "1. 영상 언어의 표현 특성을 이해할 수 있다.",
        "2. 매체 특성을 고려하여 기획할 수 있다.",
    ]
    para_prs = re.findall(r'<hp:p [^>]*paraPrIDRef="(\d+)"', cell)
    assert len(para_prs) == 2 and len(set(para_prs)) == 1, "clones must keep the original paragraph style"
    assert "<hp:linesegarray" not in cell, "edited cell must not keep stale layout cache"


def test_multiline_requires_exclusive_cell(form):
    res = preview_addressed_edits(
        str(form),
        [
            {"target": "t1.r1.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "줄1\n줄2"},
            {"target": "t1.r1.c0.p4", "kind": "paragraph", "operation": "replace_text", "value": "다른 편집"},
        ],
    )
    assert res["ok"] is False
    assert "multiline_requires_exclusive_cell" in {item.get("reason") for item in res["unresolved"]}


def test_lineseg_cache_dropped_only_on_edited_paragraphs(form, tmp_path):
    out = tmp_path / "form.done.hwpx"
    res = complete_addressed_template(
        str(form),
        [{
            "target": "t1.r1.c0.p1",
            "kind": "paragraph",
            "operation": "replace_text",
            "value": "▶ 영상 언어 4요소를 개별 워크시트에 정리한 뒤 모둠 내에서 공유한다",
            "expected_text": "▶",
        }],
        str(out),
        verify=True,
    )
    assert res["ok"] is True, res
    paras = _para_blocks(_cell_xml(_section(out), 1, 1, 0))
    assert "<hp:linesegarray" not in paras[0], "edited paragraph must drop the stale lineseg cache"
    assert all("<hp:linesegarray" in p for p in paras[1:]), "untouched paragraphs keep their bytes"


def test_preserve_marker_replace_tail_fills_marker_items(form, tmp_path):
    out = tmp_path / "form.done.hwpx"
    res = complete_addressed_template(
        str(form),
        [
            {"target": "t1.r1.c0.p2", "kind": "paragraph", "operation": "preserve_marker_replace_tail",
             "value": "모둠 결과를 공유한다", "expected_text": "-"},
            {"target": "t1.r1.c0.p1", "kind": "paragraph", "operation": "preserve_marker_replace_tail",
             "value": "핵심 개념을 정리한다", "expected_text": "▶"},
        ],
        str(out),
        verify=True,
    )
    assert res["ok"] is True, res
    texts = _para_texts(_cell_xml(_section(out), 1, 1, 0))
    assert texts[0] == "▶ 핵심 개념을 정리한다"
    assert texts[1] == "- 모둠 결과를 공유한다"
    assert texts[2] == "" and texts[3] == "▶" and texts[4] == "-", "other paragraphs untouched"


def test_body_paragraph_edit_drops_lineseg(form, tmp_path):
    out = tmp_path / "form.done.hwpx"
    res = complete_addressed_template(
        str(form),
        [{"target": "b1", "kind": "body_para", "operation": "replace_text", "value": "국어과 교수-학습 과정안"}],
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

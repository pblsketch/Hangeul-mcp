"""US-065: inline blanks live via the file-fill mirror (PURE parts — no COM).

The live application (cell text replacement in the open window) is desktop-only;
what IS headless-testable is the mirror computation: run the file fill engine,
diff cell texts, and produce full-cell replacement targets.
"""

from pathlib import Path

from hangeul_core.hwp.live import preview_cells_to_open
from hangeul_core.hwp.live_inline import compute_cell_text_replacements

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_inline_values_become_cell_text_targets():
    targets, skipped = compute_cell_text_replacements(
        FIXTURE, {"은행명": "농협", "계좌번호": "123-456", "프로그램명": "AI 활용 연수"}
    )
    assert skipped == []
    joined = ["\n".join(t["lines"]) for t in targets]
    bank_cells = [txt for txt in joined if "농협" in txt and "123-456" in txt]
    assert len(bank_cells) == 1  # 은행명+계좌번호 share one cell -> ONE replacement
    assert any("AI 활용 연수" in txt for txt in joined)
    for t in targets:
        assert t["mode"] == "cell_text"
        assert isinstance(t["table"], int) and t["table"] >= 1
        assert t["labels"], "each replacement must say which value keys it carries"


def test_inline_replacement_preserves_label_text():
    targets, _ = compute_cell_text_replacements(FIXTURE, {"은행명": "농협"})
    assert len(targets) == 1
    text = "\n".join(targets[0]["lines"])
    assert "은행명" in text and "농협" in text  # labels around the blank survive


def test_unknown_key_is_skipped_not_dropped():
    targets, skipped = compute_cell_text_replacements(FIXTURE, {"없는라벨XYZ": "v"})
    assert targets == []
    assert skipped and skipped[0]["key"] == "없는라벨XYZ"


def test_preview_mixes_direct_and_inline_targets():
    res = preview_cells_to_open(FIXTURE, {"성명": "홍길동", "은행명": "농협"})
    assert res["count"] == 2
    assert len(res["targets"]) == 1 and len(res["text_targets"]) == 1
    assert res["skipped"] == []

"""US-005: inline-blank detection on the blank 강사카드 fixture."""

from pathlib import Path

from hangeul_core.inline import MARKERS, detect_inline
from hangeul_core.schema import KIND_INLINE_BLANK, label_key

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_marker_cells_detected():
    fields = detect_inline(FIXTURE)
    markers = [f for f in fields if f.insert_after in MARKERS]
    # 학력, 경력x3, 현직, 프로그램명, 강의주제, 저서논문 -> at least 4 marker blanks
    assert len(markers) >= 4


def test_narrative_label_and_tail_template():
    fields = detect_inline(FIXTURE)
    hak = [f for f in fields if label_key(f.label) == "학력"]
    assert hak, "학력 inline blank not detected"
    # template carries the sentence tail so an LLM can fit grammar
    assert "졸업" in (hak[0].template or "")


def test_colon_blanks_detected():
    fields = detect_inline(FIXTURE)
    labels = {f.label for f in fields}
    assert "은행명" in labels
    assert "계좌번호" in labels


def test_colon_insert_anchor():
    fields = detect_inline(FIXTURE)
    bank = next(f for f in fields if f.label == "은행명")
    assert bank.insert_after.endswith(":")


def test_all_inline_kind():
    fields = detect_inline(FIXTURE)
    assert fields
    assert all(f.kind == KIND_INLINE_BLANK for f in fields)

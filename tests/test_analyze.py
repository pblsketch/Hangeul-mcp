"""US-003: form analyzer golden test on the blank 강사카드 fixture."""

from pathlib import Path

from hangeul_core.analyze import analyze

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def _norm(s: str) -> str:
    return s.replace(" ", "").replace(" ", "")


def test_finds_tables():
    res = analyze(FIXTURE)
    assert res.tables, "no tables found"


def test_main_form_has_many_rows():
    res = analyze(FIXTURE)
    main = max(res.tables, key=lambda t: len(t.cells))
    distinct_rows = len({c.row for c in main.cells})
    assert main.rows >= 16 or distinct_rows >= 15


def test_known_labels_present():
    res = analyze(FIXTURE)
    norm_texts = {_norm(c.text) for c in res.all_cells()}
    for label in ["성명", "주민등록번호", "학력", "경력", "현직", "프로그램명"]:
        assert label in norm_texts, f"missing label: {label}"


def test_empty_cells_detected():
    res = analyze(FIXTURE)
    empties = [c for c in res.all_cells() if c.is_empty]
    assert len(empties) >= 5


def test_char_spacing_resolved():
    res = analyze(FIXTURE)
    spac = [c.char_spacing for c in res.all_cells() if c.char_spacing is not None]
    assert spac, "no charPr spacing resolved"


def test_span_captured():
    res = analyze(FIXTURE)
    # the form has merged cells (colSpan/rowSpan > 1) somewhere
    assert any(c.col_span > 1 or c.row_span > 1 for c in res.all_cells())


def test_field_id_format():
    res = analyze(FIXTURE)
    cell = res.all_cells()[0]
    fid = cell.field_id
    assert fid.startswith("t") and ".r" in fid and ".c" in fid

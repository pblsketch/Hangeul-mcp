"""US-004: 2D label-value mapping (merged-cell aware)."""

from pathlib import Path

from hangeul_core.schema import label_key
from hangeul_core.understand import understand

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_produces_fields():
    fs = understand(FIXTURE)
    assert fs.fields


def test_value_cells_not_labels():
    """성명/직위/휴대전화 values are the empty cells (row 2), not adjacent labels."""
    fs = understand(FIXTURE)
    seong = fs.by_label("성명")
    jikwi = fs.by_label("직위")
    hp = fs.by_label("휴대전화")
    assert seong and ".r2.c3" in seong.field_id
    assert jikwi and ".r2.c2" in jikwi.field_id
    assert hp and ".r2.c7" in hp.field_id


def test_value_field_ids_are_distinct():
    fs = understand(FIXTURE)
    ids = [f.field_id for f in fs.fields]
    assert len(ids) == len(set(ids)), "a value cell was mapped to two labels"


def test_label_alias_matching_is_space_insensitive():
    fs = understand(FIXTURE)
    # '주민등록번호' label present and resolvable via label_key
    assert any(label_key(f.label) == "주민등록번호" for f in fs.fields)

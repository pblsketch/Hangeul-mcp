"""S3: body paragraph insert-blank / delete ops with drift-free batch ordering."""

import zipfile
from pathlib import Path
import pytest

from hangeul_core.addressed import (
    apply_addressed_edits,
    inspect_editable_regions,
    preview_addressed_edits,
)
from hangeul_mcp.tools_file_edit import AddressedEdit, _normalize_addressed_edits

FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="template fixture not present in this checkout"
)


def _apply(edits: list[dict], out: Path):
    prev = preview_addressed_edits(
        FIXTURE, _normalize_addressed_edits([AddressedEdit(**e) for e in edits])
    )
    assert prev["ok"], prev.get("unresolved")
    res = apply_addressed_edits(prev["session_id"], out)
    assert res["ok"], res
    return prev, res


def _section(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def _body_text(path: Path) -> dict[str, str]:
    r = inspect_editable_regions(path, compact=True)
    items = next(v for v in r.values() if isinstance(v, list) and v and isinstance(v[0], dict))
    return {it["target"]: (it.get("text") or "") for it in items if str(it.get("target", "")).startswith("b")}


def test_insert_blank_after_adds_one_empty_paragraph(tmp_path):
    before = _section(FIXTURE).count("<hp:p ")
    out = tmp_path / "ins.hwpx"
    _apply([{"target": "b1", "operation": "insert_blank_after"}], out)
    after = _section(out).count("<hp:p ")
    assert after == before + 1
    # bN ordinals count only non-empty paragraphs, so a blank must NOT shift them.
    texts = _body_text(out)
    assert texts["b1"].startswith("1. 기사문")
    assert "정확해야" in texts["b2"]


def test_delete_paragraph_shifts_following_ordinals(tmp_path):
    out = tmp_path / "del.hwpx"
    _apply(
        [{"target": "b2", "operation": "delete_paragraph", "expected_text": "  ① 정확해야 한다."}],
        out,
    )
    texts = _body_text(out)
    # b2 ("① 정확해야 한다.") gone -> old b3 ("② 간결해야 한다.") slides up into b2.
    assert "정확해야" not in " ".join(texts.values())
    assert "간결해야" in texts["b2"]


def test_batch_deletes_apply_bottom_up_without_drift(tmp_path):
    out = tmp_path / "batch.hwpx"
    # delete b2 and b4 in one batch; bottom-up ordering keeps both anchors valid.
    _apply(
        [
            {"target": "b2", "operation": "delete_paragraph", "expected_text": "  ① 정확해야 한다."},
            {"target": "b4", "operation": "delete_paragraph", "expected_text": "  ③ 주관적이어야 한다."},
        ],
        out,
    )
    joined = " ".join(_body_text(out).values())
    assert "정확해야" not in joined  # b2 deleted
    assert "주관적이어야" not in joined  # b4 deleted
    assert "간결해야" in joined  # b3 survived (not shifted into a deleted slot)
    assert "육하원칙" in joined  # b5 survived


def test_expected_text_mismatch_fails_closed(tmp_path):
    prev = preview_addressed_edits(
        FIXTURE,
        _normalize_addressed_edits(
            [AddressedEdit(target="b2", operation="delete_paragraph", expected_text="WRONG")]
        ),
    )
    assert not prev["ok"]
    assert prev["unresolved"][0]["reason"] == "expected_text_mismatch"

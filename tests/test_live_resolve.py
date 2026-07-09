"""US-029: live cell-fill target resolution (PURE part — no COM).

The COM driving of the open Hangul window (apply_cells_to_open) can only run in
an interactive Windows session with Hangul, so it is validated in the client
(e.g. Claude Desktop), not here. What IS testable is the pure mapping of value
keys to table-cell addresses, plus graceful degradation when pyhwpx is absent.
"""

from pathlib import Path

from hangeul_core.hwp.live import apply_cells_to_open, resolve_cell_targets

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_resolve_targets_maps_label_to_cell_address():
    targets, skipped = resolve_cell_targets(FIXTURE, {"성명": "홍길동"})
    assert len(targets) == 1
    t = targets[0]
    assert t["label"].replace(" ", "") == "성명"
    assert t["value"] == "홍길동"
    # a real cell address: 1-based table index + 0-based row/col
    assert isinstance(t["table"], int) and t["table"] >= 1
    assert isinstance(t["row"], int) and isinstance(t["col"], int)
    assert t["field_id"] == f"t{t['table']}.r{t['row']}.c{t['col']}"


def test_resolve_targets_by_field_id():
    # first resolve by label to learn the address, then target it by field_id
    targets, _ = resolve_cell_targets(FIXTURE, {"성명": "X"})
    fid = targets[0]["field_id"]
    targets2, skipped2 = resolve_cell_targets(FIXTURE, {fid: "홍길동"})
    assert len(targets2) == 1 and targets2[0]["field_id"] == fid


def test_resolve_targets_unknown_key_skipped():
    targets, skipped = resolve_cell_targets(FIXTURE, {"없는라벨ZZZ": "v"})
    assert targets == [] and skipped and skipped[0]["reason"] == "no matching cell field"


def test_apply_cells_degrades_gracefully_without_substrate():
    # In headless/CI (no pyhwpx or non-Windows) this must not raise; it reports
    # available:false rather than crashing.
    res = apply_cells_to_open(FIXTURE, {"성명": "홍길동"})
    assert "available" in res
    if res["available"] is False:
        assert "error" in res

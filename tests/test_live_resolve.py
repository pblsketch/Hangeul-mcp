"""US-029: live cell-fill target resolution (PURE part — no COM).

The COM driving of the open Hangul window (apply_cells_to_open) can only run in
an interactive Windows session with Hangul, so it is validated in the client
(e.g. Claude Desktop), not here. What IS testable is the pure mapping of value
keys to table-cell addresses, plus graceful degradation when pyhwpx is absent.
"""

from pathlib import Path

from hangeul_core.hwp.live import apply_cells_to_open, preview_cells_to_open, resolve_cell_targets
from hangeul_mcp import server

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


def test_apply_cells_degrades_gracefully_without_substrate(monkeypatch):
    # Simulate absent pyhwpx deterministically. With the live extra installed,
    # a real call would attach to Hangul (auto-open fallback) — unit tests must
    # never drive COM, so the absent branch is forced instead.
    import sys

    monkeypatch.setitem(sys.modules, "pyhwpx", None)
    res = apply_cells_to_open(FIXTURE, {"성명": "홍길동"})
    assert res["available"] is False
    assert "error" in res


def test_preview_cells_to_open_is_pure_and_returns_targets():
    res = preview_cells_to_open(FIXTURE, {"성명": "홍길동"})
    assert res["available"] is True
    assert res["count"] == 1
    assert res["targets"][0]["label"].replace(" ", "") == "성명"
    assert res["apply_tool"] == "apply_cells_to_open_hwp"


def test_hwp_status_never_dispatches_com(monkeypatch):
    """US-052: hwp_status must stay side-effect-free — no COM dispatch, ever.

    On machines with pywin32 installed this is a live tripwire: if status()
    ever starts dispatching, EnsureDispatch would raise here.
    """
    try:
        import win32com.client as w
    except ImportError:
        pass  # without pywin32, dispatching is impossible by construction
    else:
        def boom(*a, **k):  # pragma: no cover - only fires on regression
            raise AssertionError("hwp_status dispatched COM")

        monkeypatch.setattr(w.gencache, "EnsureDispatch", boom)
    st = server.hwp_status()
    assert st.get("connected") is False


def test_runbook_values_mapping_resolves_documented_targets():
    """US-052: the live-QA runbook's value mapping resolves to cell targets.

    Inline-blank/append labels (학력/은행명) are file-mode only by design (D11);
    the live cell path handles label:value empty_cell fields.
    """
    res = preview_cells_to_open(FIXTURE, {"성명": "홍길동", "직위": "교사"})
    assert res["count"] == 2
    labels = {t["label"].replace(" ", "") for t in res["targets"]}
    assert labels == {"성명", "직위"}


def test_server_preview_rejects_hwp_without_conversion(tmp_path):
    fake = tmp_path / "form.hwp"
    fake.write_bytes(b"HWP binary placeholder")
    res = server.preview_cells_to_open_hwp(str(fake), {"성명": "홍길동"})
    assert res["ok"] is False
    assert "only accepts .hwpx" in res["error"]

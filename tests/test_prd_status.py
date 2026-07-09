"""Machine-readable PRD status invariants (US-047, BC3).

docs/prd.json is the story ledger; `status` is the evidence-level truth
(complete / optional-gated / desktop-live-pending / spike-pending / planned)
while `passes` stays the boolean the README pass count is defined on.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NOTE_REQUIRED = {"desktop-live-pending", "spike-pending"}


def _prd():
    return json.loads((ROOT / "docs" / "prd.json").read_text(encoding="utf-8"))


def test_status_model_is_declared():
    d = _prd()
    model = d.get("statusModel")
    assert model, "prd.json must declare statusModel (BC3)"
    assert set(model["enum"]) == {
        "complete",
        "optional-gated",
        "desktop-live-pending",
        "spike-pending",
        "planned",
    }
    assert "passes==true" in model["passCountDefinition"]


def test_every_story_has_valid_status():
    d = _prd()
    valid = set(d["statusModel"]["enum"])
    for s in d["stories"]:
        assert s.get("status") in valid, f"{s['id']}: invalid status {s.get('status')!r}"


def test_complete_iff_consistent_with_passes():
    for s in _prd()["stories"]:
        if s["status"] == "complete":
            assert s["passes"] is True, f"{s['id']}: status complete but passes!=true"
        if s["passes"] is False:
            assert s["status"] != "complete", f"{s['id']}: passes false but status complete"


def test_pending_statuses_carry_evidence_note():
    for s in _prd()["stories"]:
        if s["status"] in NOTE_REQUIRED:
            assert s.get("statusNote"), f"{s['id']}: {s['status']} requires statusNote"

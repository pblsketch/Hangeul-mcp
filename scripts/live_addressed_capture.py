"""P0-C desktop capture — in-place live addressed editing of the OPEN window.

Evidence for the live_addressed flag-promotion gate (PENDING_DESKTOP_LIVE_QA):
default-gated response, preview_ready over the token flow, tamper-injection
fail-closed skip (expected_text_mismatch without a destructive write), partial
recovery block, second-round full success, token single-use, and the on-disk
file staying byte-identical (the server never saves the window).

Run on the production runtime:  python scripts/live_addressed_capture.py
Opens real Hangul tabs on a TEMP COPY only; closes nothing.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hangeul_core.addressed import inspect_editable_regions  # noqa: E402
from hangeul_core.hwp.com import load_pyhwpx, normalize_live_path  # noqa: E402
from hangeul_core.hwp.live_attach import open_as_new_tab  # noqa: E402
import hangeul_mcp.live_current as live_current  # noqa: E402

FIXTURE = ROOT / "tests" / "hwpx template" / "14_교수학습 지도안 양식.hwpx"
EVIDENCE = ROOT / "docs" / "evidence" / "live-addressed-desktop-capture.json"

T0 = time.monotonic()
report: dict = {
    "capture": "live_addressed_desktop",
    "scenario": "in-place COM edit of the open window via the current-document token flow (P0-C)",
    "started_at": datetime.now(timezone.utc).isoformat(),
    "runtime": sys.executable,
    "steps": [],
}


def step(name: str, **payload):
    entry = {"step": name, "t": round(time.monotonic() - T0, 1), **payload}
    report["steps"].append(entry)
    print(f"[{entry['t']:7.1f}s] {name}: {json.dumps(payload, ensure_ascii=False, default=str)[:300]}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finish(outcome: str, **payload):
    report["outcome"] = outcome
    report.update(payload)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(report, ensure_ascii=False, indent=2)
    user = Path.home().name
    if user:
        raw = raw.replace(user, "USER")
    EVIDENCE.write_text(raw, encoding="utf-8")
    print(f"\nOUTCOME: {outcome}\nEVIDENCE: {EVIDENCE}")
    sys.exit(0 if outcome.startswith("pass") else 1)


def build_edits(path: Path) -> list[dict]:
    inspection = inspect_editable_regions(str(path), compact=True)
    edits: list[dict] = []
    for region in inspection.get("regions") or []:
        text = str(region.get("text") or "")
        if region.get("kind") == "cell" and text.startswith("{") and text.endswith("}"):
            target = (region.get("paragraph_targets") or [region.get("target")])[0]
            edits.append({
                "target": target,
                "kind": "paragraph",
                "operation": "replace_text",
                "value": f"라이브검증-{len(edits) + 1}",
                "expected_text": text,
            })
    return edits


workdir = Path(tempfile.mkdtemp(prefix="hangeul-p0c-capture-"))
copy = workdir / "교수학습지도안_라이브.hwpx"
shutil.copyfile(FIXTURE, copy)
sha_before = sha(copy)
EDITS = build_edits(copy)
step("fixture_copied", copy=str(copy), sha256=sha_before, edit_count=len(EDITS))
if len(EDITS) < 2:
    finish("fail-no-placeholder-regions")

opened = open_as_new_tab(copy, visible=True)
step("open_as_new_tab", state=opened.get("state"), ok=opened.get("ok"))
if not opened.get("ok"):
    finish("fail-open", open_state=opened.get("state"), error=opened.get("error"))

resolution = live_current.resolve_current_hwp_document()
candidate_id = None
for cand in resolution.get("candidates") or []:
    if normalize_live_path(str(cand.get("path") or "")) == normalize_live_path(str(copy)):
        candidate_id = cand.get("candidate_id")
step("resolve", state=resolution.get("state"), n_candidates=len(resolution.get("candidates") or []),
     found_candidate=bool(candidate_id))
if candidate_id is None:
    finish("fail-no-candidate", resolution_state=resolution.get("state"))

gated = live_current.preview_current_hwp_document({}, candidate_id=candidate_id, edits=EDITS, mode="live_addressed")
step("preview_gated_default", state=gated.get("state"))
gated_ok = gated.get("state") == "live_addressed_gated" and "preview_token" not in gated

# QA-only gate override: production flag stays False until the promotion commit
live_current.live_addressed_enabled = lambda: True
step("gate_override", note="live_addressed_enabled patched True in-process for QA; feature_flags unchanged")

preview = live_current.preview_current_hwp_document({}, candidate_id=candidate_id, edits=EDITS, mode="live_addressed")
step("preview", state=preview.get("state"), route=preview.get("route"),
     counts=(preview.get("preview") or {}).get("counts"))
if preview.get("state") != "preview_ready":
    finish("fail-preview", preview_state=preview.get("state"), unresolved=preview.get("unresolved"))

# tamper injection: simulate the user editing ONE target cell in the window
tamper_target = (preview["preview"]["targets"] or [])[0]
Hwp, err = load_pyhwpx()
if err:
    finish("fail-load-pyhwpx", error=str(err))
hwp = Hwp(new=False, visible=True, on_quit=False)
hwp.get_into_nth_table(tamper_target["table"] - 1)
hwp.goto_addr(tamper_target["row"] + 1, tamper_target["col"] + 1, select_cell=False)
hwp.insert_text("사용자수정")
tampered_text = "사용자수정" + tamper_target["expected_text"]
step("tamper_injected", target=tamper_target["target"], tampered_text=tampered_text)

applied = live_current.apply_to_current_hwp_document(preview["preview_token"])
step("apply_with_tamper", state=applied.get("state"), ok=applied.get("ok"),
     counts=applied.get("counts"), skipped=applied.get("skipped"),
     recovery=applied.get("recovery"), readback=applied.get("readback"))
replay = live_current.apply_to_current_hwp_document(preview["preview_token"])
step("token_replay", state=replay.get("state"))

skipped = applied.get("skipped") or []
tamper_skip_ok = (
    len(skipped) == 1
    and skipped[0].get("reason") == "expected_text_mismatch"
    and skipped[0].get("target") == tamper_target["target"]
    and skipped[0].get("actual_text") == tampered_text
)

# second round: correct expected_text for the tampered cell -> full success
second_edits = [{
    "target": tamper_target["target"],
    "kind": "paragraph",
    "operation": "replace_text",
    "value": "라이브검증-tamper-회복",
    "expected_text": tamper_target["expected_text"],
}]
# the file on disk still holds the ORIGINAL text (window-only edits are unsaved),
# so the PURE plan uses the file text while the live check sees the tampered cell —
# use a fresh cell-kind edit with the file-side expected and live-side actual:
second_edits[0]["expected_text"] = tamper_target["expected_text"]
second_preview = live_current.preview_current_hwp_document({}, candidate_id=candidate_id, edits=second_edits, mode="live_addressed")
step("second_preview", state=second_preview.get("state"))
second_apply = {}
if second_preview.get("state") == "preview_ready":
    # live text is tampered; fix the live expected via targets patch is NOT allowed —
    # instead un-tamper the cell first (user undo equivalent), then apply
    hwp.get_into_nth_table(tamper_target["table"] - 1)
    hwp.goto_addr(tamper_target["row"] + 1, tamper_target["col"] + 1, select_cell=False)
    hwp.HAction.Run("Cancel"); hwp.HAction.Run("MoveListBegin"); hwp.HAction.Run("MoveSelListEnd")
    hwp.HAction.Run("Delete")
    hwp.insert_text(tamper_target["expected_text"])
    step("tamper_reverted", target=tamper_target["target"])
    second_apply = live_current.apply_to_current_hwp_document(second_preview["preview_token"])
    step("second_apply", state=second_apply.get("state"), ok=second_apply.get("ok"),
         readback=second_apply.get("readback"))

sha_after = sha(copy)
checks = {
    "gated_by_default": gated_ok,
    "preview_ready_over_token_flow": preview.get("route") == "live_addressed",
    "tamper_skipped_fail_closed": tamper_skip_ok,
    "partial_state_with_recovery": applied.get("state") == "live_addressed_partial" and bool(applied.get("recovery")),
    "others_applied_with_fresh_readback": (applied.get("counts") or {}).get("applied") == len(EDITS) - 1
    and bool((applied.get("readback") or {}).get("verified")),
    "token_single_use": replay.get("state") == "stale_preview_token",
    "second_round_full_success": second_apply.get("state") == "applied_live_addressed"
    and bool((second_apply.get("readback") or {}).get("verified")),
    "file_on_disk_untouched": sha_after == sha_before,
}
step("checks", **checks)
finish(
    "pass" if all(checks.values()) else "fail-checks",
    checks=checks,
    sha_before=sha_before,
    sha_after=sha_after,
    note="tabs were left open on purpose (the server never closes user documents); close them manually",
)

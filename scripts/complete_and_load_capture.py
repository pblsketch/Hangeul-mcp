"""B1 desktop capture — complete_and_load on a Shell-opened (hand-opened) original.

Rider R1b evidence: (i) where the completed file opens, (ii) the original
document survives in XHwpDocuments (never closed), plus 0-touch SHA proof and
fresh read-back of the applied edits. Writes JSON to docs/evidence/.

Run on the production runtime:  python scripts/complete_and_load_capture.py
Opens real Hangul windows; touches only temp copies under %TEMP%.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hangeul_core.hwp.com import list_rot_instances, normalize_live_path  # noqa: E402
from hangeul_core.addressed import inspect_editable_regions, verify_targets  # noqa: E402
import hangeul_mcp.live_current as live_current  # noqa: E402

# a REAL Hangul-authored template: synthetic zip fixtures are rejected by the
# real app (hwp.open -> False), so desktop captures must use authored files.
FIXTURE = ROOT / "tests" / "hwpx template" / "14_교수학습 지도안 양식.hwpx"
EVIDENCE = ROOT / "docs" / "evidence" / "complete-and-load-desktop-capture.json"


def build_edits(path: Path, limit: int = 60) -> list[dict]:
    """Fill EVERY {placeholder} cell (full-form scale) so the capture proves 40-cell read-back."""
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
                "value": f"캡처검증-{len(edits) + 1}",
                "expected_text": text,
            })
        if len(edits) >= limit:
            break
    return edits

report: dict = {
    "capture": "complete_and_load_desktop",
    "scenario": "shell-opened (Explorer double-click equivalent) original; pathless current-document flow",
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


def rot_paths() -> list[dict]:
    docs = []
    for inst in list_rot_instances():
        for doc in inst.get("documents") or []:
            docs.append({
                "moniker": inst.get("moniker"),
                "slot": doc.get("slot"),
                "path": doc.get("path"),
                "is_active": doc.get("is_active"),
            })
    return docs


def finish(outcome: str, **payload):
    report["outcome"] = outcome
    report.update(payload)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    target = EVIDENCE.with_name(f"complete-and-load-desktop-capture-{report.get('mode', 'shell')}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(report, ensure_ascii=False, indent=2)
    user = Path.home().name
    if user:
        raw = raw.replace(user, "USER")  # keep personal account names out of committed evidence
    target.write_text(raw, encoding="utf-8")
    print(f"\nOUTCOME: {outcome}\nEVIDENCE: {target}")
    sys.exit(0 if outcome.startswith("pass") or outcome.startswith("conditional") else 1)


T0 = time.monotonic()
MODE = sys.argv[1] if len(sys.argv) > 1 else "shell"  # shell | automation
report["mode"] = MODE

workdir = Path(tempfile.mkdtemp(prefix="hangeul-b1-capture-"))
original = workdir / "교수학습지도안_원본.hwpx"
shutil.copyfile(FIXTURE, original)
original_sha_before = sha(original)
EDITS = build_edits(original)
step("fixture_copied", original=str(original), sha256=original_sha_before, edits=EDITS)
if len(EDITS) < 2:
    finish("fail-no-placeholder-regions")

step("rot_before_open", documents=rot_paths())
norm_original = normalize_live_path(str(original))

if MODE == "components":
    # B1 apply-side behavior at component level (rider R1b): open original in the
    # automation window, complete to a NEW file, open it as a new tab, then prove
    # (i) where it opened and (ii) the original tab survived, plus 0-touch SHA.
    from hangeul_core.addressed import complete_addressed_template
    from hangeul_core.hwp.live_attach import open_as_new_tab as automation_open

    opened = automation_open(original, visible=True)
    step("open_original", state=opened.get("state"), ok=opened.get("ok"))
    if not opened.get("ok"):
        finish("fail-open-original", open_state=opened.get("state"), error=opened.get("error"))
    output = original.with_name("교수학습지도안_완성본.hwpx")
    completion = complete_addressed_template(str(original), EDITS, str(output), verify=True)
    step("complete", ok=completion.get("ok"), state=completion.get("state"),
         counts=completion.get("counts"))
    if not completion.get("ok"):
        finish("fail-complete", completion_state=completion.get("state"))
    original_sha_after_complete = sha(original)
    opened_out = automation_open(output, visible=True)
    step("open_completed", state=opened_out.get("state"), ok=opened_out.get("ok"),
         active_document=opened_out.get("active_document"))
    rot_after = rot_paths()
    norm_output = normalize_live_path(str(output))
    original_still_open = any(normalize_live_path(str(d.get("path") or "")) == norm_original for d in rot_after)
    completed_entries = [d for d in rot_after if normalize_live_path(str(d.get("path") or "")) == norm_output]
    readback = verify_targets(str(output), [{"target": e["target"], "expected_text": e["value"]} for e in EDITS])
    checks = {
        "original_opened_in_automation_window": True,
        "completion_verified": completion.get("ok") is True,
        "original_sha_unchanged_0touch": original_sha_after_complete == original_sha_before,
        "completed_opened_ok": opened_out.get("ok") is True,
        "completed_is_active_new_tab": bool(any(d.get("is_active") for d in completed_entries)),
        "original_still_in_XHwpDocuments": original_still_open,
        "fresh_readback_verified": bool(readback.get("verified")),
    }
    step("rot_after", documents=rot_after)
    step("checks", **checks)
    finish(
        "pass-components" if all(checks.values()) else "fail-components",
        checks=checks,
        output_path=str(output),
        note="component-level B1 evidence; the pathless token flow is separately blocked on multi-instance desktops (see automation variant)",
    )

if MODE == "automation":
    from hangeul_core.hwp.live_attach import open_in_hwp as automation_open

    opened = automation_open(original, visible=True)
    step("automation_open", state=opened.get("state"), ok=opened.get("ok"),
         cold_start=opened.get("cold_start"), elapsed=opened.get("elapsed_seconds"))
    if not opened.get("ok"):
        finish("fail-automation-open", open_state=opened.get("state"), error=opened.get("error"))
    visible = True
else:
    os.startfile(str(original))  # ShellExecute — the double-click path
    step("shell_open_requested")
    visible = False
    for _ in range(120):
        time.sleep(1)
        docs = rot_paths()
        if any(normalize_live_path(str(d.get("path") or "")) == norm_original for d in docs):
            visible = True
            break
    step("rot_visibility_poll", automation_visible=visible, documents=rot_paths())

if not visible:
    finish(
        "conditional-not-visible",
        note=(
            "hand-opened original never became automation-visible in ROT within 120s — "
            "this is the documented R1 conditionality; complete_and_load pathless flow "
            "cannot target it. Fallback remains file-mode + open_in_hwp."
        ),
        original_sha_unchanged=sha(original) == original_sha_before,
    )

resolution = live_current.resolve_current_hwp_document()
step("resolve", state=resolution.get("state"), n_candidates=len(resolution.get("candidates") or []))
candidate_id = None
for cand in resolution.get("candidates") or []:
    if normalize_live_path(str(cand.get("path") or "")) == norm_original:
        candidate_id = cand.get("candidate_id")
        break
if candidate_id is None:
    finish("fail-no-candidate", resolution_state=resolution.get("state"))

preview = live_current.preview_current_hwp_document(values={}, candidate_id=candidate_id, edits=EDITS)
step("preview", state=preview.get("state"), route=preview.get("route"),
     output_path=(preview.get("preview") or {}).get("output_path"))
if not preview.get("ok"):
    finish("fail-preview", preview_state=preview.get("state"))

applied = live_current.apply_to_current_hwp_document(preview["preview_token"])
step("apply", state=applied.get("state"), ok=applied.get("ok"),
     output_path=applied.get("output_path"), open=applied.get("open"))

original_sha_after = sha(original)
rot_after = rot_paths()
norm_output = normalize_live_path(str(applied.get("output_path") or ""))
original_still_open = any(normalize_live_path(str(d.get("path") or "")) == norm_original for d in rot_after)
completed_open_entries = [d for d in rot_after if normalize_live_path(str(d.get("path") or "")) == norm_output]
step("rot_after_apply", documents=rot_after,
     original_still_open=original_still_open, completed_entries=completed_open_entries)

readback = {}
if applied.get("output_path") and Path(applied["output_path"]).exists():
    readback = verify_targets(
        applied["output_path"],
        [{"target": e["target"], "expected_text": e["value"]} for e in EDITS],
    )
    step("fresh_readback", verified=readback.get("verified"), counts=readback.get("counts"))

checks = {
    "apply_state_completed_and_loaded": applied.get("state") == "completed_and_loaded",
    "original_sha_unchanged_0touch": original_sha_after == original_sha_before,
    "response_claims_original_untouched": applied.get("original_untouched") is True,
    "original_still_in_XHwpDocuments": original_still_open,
    "completed_file_open_in_automation": bool(completed_open_entries),
    "fresh_readback_verified": bool(readback.get("verified")),
}
step("checks", **checks)
finish(
    "pass" if all(checks.values()) else ("pass-partial-open" if applied.get("state") == "completed_open_failed" and checks["original_sha_unchanged_0touch"] else "fail-checks"),
    checks=checks,
    original_sha_before=original_sha_before,
    original_sha_after=original_sha_after,
    note="windows were left open on purpose (the server never closes user documents); close them manually",
)

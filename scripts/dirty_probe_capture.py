"""Track B prerequisite capture — IsModified/Modified dirty-probe on real Hangul.

Proves on real hardware that ``probe_document_dirty`` distinguishes a clean
window from one holding unsaved typing (ADR D19 prerequisite 2). Read-only
except for typing into OUR OWN temp-copy tab; nothing is saved or closed.
Evidence: docs/evidence/dirty-probe-desktop-capture.json (sanitized).
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

from hangeul_core.hwp.com import load_pyhwpx  # noqa: E402
from hangeul_core.hwp.dirty_probe import probe_document_dirty  # noqa: E402
from hangeul_core.hwp.live_attach import open_as_new_tab  # noqa: E402

FIXTURE = ROOT / "tests" / "hwpx template" / "14_교수학습 지도안 양식.hwpx"
EVIDENCE = ROOT / "docs" / "evidence" / "dirty-probe-desktop-capture.json"

T0 = time.monotonic()
report: dict = {
    "capture": "dirty_probe_desktop",
    "started_at": datetime.now(timezone.utc).isoformat(),
    "runtime": sys.executable,
    "steps": [],
}


def step(name: str, **payload):
    entry = {"step": name, "t": round(time.monotonic() - T0, 1), **payload}
    report["steps"].append(entry)
    print(f"[{entry['t']:7.1f}s] {name}: {json.dumps(payload, ensure_ascii=False, default=str)[:280]}")


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


workdir = Path(tempfile.mkdtemp(prefix="hangeul-dirty-probe-"))
copy = workdir / "dirty_probe_대상.hwpx"
shutil.copyfile(FIXTURE, copy)
sha_before = hashlib.sha256(copy.read_bytes()).hexdigest()
step("fixture_copied", copy=str(copy), sha256=sha_before)

opened = open_as_new_tab(copy, visible=True)
step("open_as_new_tab", state=opened.get("state"), ok=opened.get("ok"))
if not opened.get("ok"):
    finish("fail-open", open_state=opened.get("state"), error=opened.get("error"))

clean = probe_document_dirty(copy)
step("probe_clean", **{k: clean.get(k) for k in ("state", "ok", "dirty", "modified_flags")})

missing = probe_document_dirty(workdir / "없는문서.hwpx")
step("probe_not_attached", **{k: missing.get(k) for k in ("state", "ok", "dirty")})

# type into OUR temp-copy tab (it is active after open_as_new_tab)
Hwp, err = load_pyhwpx()
if err:
    finish("fail-load-pyhwpx", error=str(err))
hwp = Hwp(new=False, visible=True, on_quit=False)
hwp.insert_text("미저장 타이핑")
step("typed_unsaved_text")

dirty = probe_document_dirty(copy)
step("probe_dirty", **{k: dirty.get(k) for k in ("state", "ok", "dirty", "modified_flags")})

sha_after = hashlib.sha256(copy.read_bytes()).hexdigest()
checks = {
    "clean_probe_reports_not_dirty": clean.get("state") == "probed" and clean.get("dirty") is False,
    "missing_document_fails_closed": missing.get("state") == "document_not_attached" and missing.get("dirty") is None,
    "unsaved_typing_reports_dirty": dirty.get("state") == "probed" and dirty.get("dirty") is True,
    "probe_is_read_only_on_disk": sha_after == sha_before,
}
step("checks", **checks)
finish(
    "pass" if all(checks.values()) else "fail-checks",
    checks=checks,
    note="the typed tab holds intentional unsaved text; close it WITHOUT saving. The server saved/closed nothing.",
)

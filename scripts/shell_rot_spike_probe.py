"""Track D spike probe — can a Shell-opened Hangul window be detected/promoted?

Measures, on real hardware, the three ADR options for Explorer/Shell-opened
windows that never register in the COM ROT:
  (a) Win32 window enumeration — is DETECTION (title -> basename match) viable?
  (b) promotion to automation-visible — OBJID_NATIVEOM accessibility and DDE
      service handshake attempts on the found windows;
  (c) status quo baseline — ROT polling + what a generic pyhwpx reconnect sees
      (the historical misjudgment: attaching to an unrelated/empty instance).

Detection-only probe: NOTHING is written to any document. Evidence JSON goes to
docs/evidence/shell-rot-spike-probe.json (usernames sanitized).
"""

from __future__ import annotations

import ctypes
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

FIXTURE = ROOT / "tests" / "hwpx template" / "14_교수학습 지도안 양식.hwpx"
EVIDENCE = ROOT / "docs" / "evidence" / "shell-rot-spike-probe.json"

report: dict = {
    "capture": "shell_rot_spike_probe",
    "started_at": datetime.now(timezone.utc).isoformat(),
    "runtime": sys.executable,
    "steps": [],
}
T0 = time.monotonic()


def step(name: str, **payload):
    entry = {"step": name, "t": round(time.monotonic() - T0, 1), **payload}
    report["steps"].append(entry)
    print(f"[{entry['t']:7.1f}s] {name}: {json.dumps(payload, ensure_ascii=False, default=str)[:280]}")


def rot_paths() -> list[str]:
    out = []
    for inst in list_rot_instances():
        for doc in inst.get("documents") or []:
            out.append(str(doc.get("path") or ""))
    return out


def enum_hwp_windows() -> list[dict]:
    user32 = ctypes.windll.user32
    found: list[dict] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _lparam):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if "한글" in title.value or cls.value.lower().startswith("hwp"):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.append({"hwnd": int(ctypes.cast(hwnd, ctypes.c_void_p).value or 0),
                          "class": cls.value, "title": title.value, "pid": pid.value})
        return True

    user32.EnumWindows(cb, 0)
    return found


def probe_nativeom(hwnd: int) -> str:
    """AccessibleObjectFromWindow(OBJID_NATIVEOM=0xFFFFFFF0, IID_IDispatch)."""

    class _GUID(ctypes.Structure):
        _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort), ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]

    try:
        iid = _GUID(0x00020400, 0, 0, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
        ptr = ctypes.c_void_p()
        hr = ctypes.windll.oleacc.AccessibleObjectFromWindow(
            ctypes.c_void_p(hwnd), ctypes.c_ulong(0xFFFFFFF0), ctypes.byref(iid), ctypes.byref(ptr)
        )
        return f"hr=0x{hr & 0xFFFFFFFF:08X} ptr={'null' if not ptr.value else hex(ptr.value)}"
    except Exception as exc:  # pragma: no cover
        return f"error: {exc}"


def probe_dde() -> list[dict]:
    results = []
    try:
        import win32ui
        import dde
        assert win32ui  # win32ui must be loaded before pywin32's dde module works
    except Exception as exc:
        return [{"service": "*", "result": f"dde module unavailable: {exc}"}]
    for service, topic in [("Hwp", "System"), ("HwpFrame", "System"), ("Hancom", "System"), ("HwpApp", "System")]:
        try:
            server = dde.CreateServer()
            server.Create(f"probe{int(time.monotonic()*1000)%100000}")
            conv = dde.CreateConversation(server)
            conv.ConnectTo(service, topic)
            results.append({"service": service, "topic": topic, "result": "CONNECTED"})
            server.Destroy()
        except Exception as exc:
            results.append({"service": service, "topic": topic, "result": f"failed: {exc}"})
    return results


workdir = Path(tempfile.mkdtemp(prefix="hangeul-rot-spike-"))
copy = workdir / "spike_shell_open.hwpx"
shutil.copyfile(FIXTURE, copy)
norm_copy = normalize_live_path(str(copy))
step("fixture_copied", copy=str(copy))
step("rot_before", documents=rot_paths())

os.startfile(str(copy))  # ShellExecute — Explorer double-click equivalent
step("shell_open_requested")

visible = False
for _ in range(30):
    time.sleep(1)
    if any(normalize_live_path(p) == norm_copy for p in rot_paths()):
        visible = True
        break
step("rot_poll_30s", shell_doc_in_rot=visible, documents=rot_paths())

windows = enum_hwp_windows()
detected = [w for w in windows if copy.name in w["title"]]
step("enum_windows", total_hwp_windows=len(windows), windows=windows[:8],
     shell_doc_window_detected=bool(detected), detected=detected)

nativeom = []
for w in windows[:6]:
    nativeom.append({"hwnd": w["hwnd"], "class": w["class"], "result": probe_nativeom(w["hwnd"])})
step("nativeom_probe", results=nativeom)

dde_results = probe_dde()
step("dde_probe", results=dde_results)

# generic reconnect hazard: what does a fresh pyhwpx attach actually see?
reconnect_docs = []
reconnect_state = "skipped"
try:
    from hangeul_core.hwp.com import load_pyhwpx
    Hwp, err = load_pyhwpx()
    if err:
        reconnect_state = f"pyhwpx unavailable: {err}"
    else:
        hwp = Hwp(new=False, visible=True, on_quit=False)
        count = int(hwp.XHwpDocuments.Count)
        for i in range(count):
            doc = hwp.XHwpDocuments.Item(i)
            reconnect_docs.append(str(getattr(doc, "FullName", "") or ""))
        reconnect_state = "connected"
except Exception as exc:
    reconnect_state = f"error: {exc}"
sees_shell_doc = any(normalize_live_path(p) == norm_copy for p in reconnect_docs)
step("generic_reconnect", state=reconnect_state, documents=reconnect_docs, sees_shell_doc=sees_shell_doc)

report["conclusions"] = {
    "rot_invisible_reconfirmed": not visible,
    "win32_detection_viable": bool(detected),
    "nativeom_promotion_viable": any("ptr=0x" in n["result"] for n in nativeom),
    "dde_promotion_viable": any(r.get("result") == "CONNECTED" for r in dde_results),
    "generic_reconnect_sees_shell_doc": sees_shell_doc,
}
report["finished_at"] = datetime.now(timezone.utc).isoformat()
EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
raw = json.dumps(report, ensure_ascii=False, indent=2)
user = Path.home().name
if user:
    raw = raw.replace(user, "USER")
EVIDENCE.write_text(raw, encoding="utf-8")
print(f"\nCONCLUSIONS: {json.dumps(report['conclusions'], ensure_ascii=False)}")
print(f"EVIDENCE: {EVIDENCE}")
print("note: the shell-opened window was NOT written to and stays open; close it manually")

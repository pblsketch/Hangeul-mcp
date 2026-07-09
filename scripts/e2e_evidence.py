"""File-mode BYO-AI e2e evidence driver (US-050).

Runs the fixed file-mode chain on the PII-free fixture and writes every
observed result to ``build/evidence/`` (gitignored):

    describe_capabilities -> analyze_form -> scan_pii -> fill_form(dry_run)
    -> fill_form -> verify_fill -> validate_hwpx -> render_preview

Exit code is non-zero if a REQUIRED gate fails (analyze/fill/verify/validate,
dry-run purity, byte preservation). ``render_preview`` may legitimately be
``available:false`` on machines without the render extra — that is recorded
as the observed result, never counted as a pass or a failure of rendering.

Regenerate any time with:  python scripts/e2e_evidence.py
"""

from __future__ import annotations

import json
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hangeul_mcp import server  # noqa: E402  (registers all 35 tools)

FIXTURE = ROOT / "tests" / "fixtures" / "sample_form.hwpx"
EVIDENCE = ROOT / "build" / "evidence"
VALUES = {"성명": "홍길동", "직위": "교사", "은행명": "농협"}


def dump(name: str, obj) -> None:
    (EVIDENCE / name).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def png_info(path: Path) -> dict:
    data = path.read_bytes()
    ok = data[:8] == b"\x89PNG\r\n\x1a\n"
    width = height = None
    if ok and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
    return {"bytes": len(data), "png_signature": ok, "width": width, "height": height}


def changed_entries(src: Path, dst: Path) -> list[str]:
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(dst) as b:
        names_a, names_b = a.namelist(), b.namelist()
        if names_a != names_b:
            return ["<entry list differs>"]
        return [n for n in names_a if a.read(n) != b.read(n)]


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    out = EVIDENCE / "sample_form.e2e-out.hwpx"
    if out.exists():
        out.unlink()

    caps = server.describe_capabilities()
    dump("01_describe_capabilities.json", caps)
    if caps.get("server_side_llm") is not False:
        failures.append("capabilities: server_side_llm must be False")

    analyzed = server.analyze_form(str(FIXTURE))
    dump("02_analyze_form.json", analyzed)
    if not analyzed.get("fields"):
        failures.append("analyze_form: no fields recognized")

    pii = server.scan_pii(str(FIXTURE))
    dump("03_scan_pii.json", pii)
    if pii.get("count", -1) != 0:
        failures.append("scan_pii: fixture must be PII-free")

    dry = server.fill_form(str(FIXTURE), VALUES, str(out), dry_run=True)
    dump("04_fill_form_dry_run.json", dry)
    if out.exists():
        failures.append("dry_run: output file was written")
    if not dry.get("filled"):
        failures.append("dry_run: nothing would be filled")

    real = server.fill_form(str(FIXTURE), VALUES, str(out))
    dump("05_fill_form.json", real)
    if not out.exists() or not real.get("filled"):
        failures.append("fill_form: output missing or nothing filled")

    changed = changed_entries(FIXTURE, out)
    dump("06_byte_preservation.json", {"changed_entries": changed})
    if not all(n.startswith("Contents/section") for n in changed):
        failures.append(f"byte preservation: unexpected entries changed: {changed}")

    verify = server.verify_fill(str(out), VALUES)
    dump("07_verify_fill.json", verify)
    if verify.get("missing"):
        failures.append(f"verify_fill: missing values {verify['missing']}")

    validated = server.validate_hwpx(str(out))
    dump("08_validate_hwpx.json", validated)
    if validated.get("valid") is not True:
        failures.append(f"validate_hwpx: invalid output {validated.get('errors')}")

    png = EVIDENCE / "preview.png"
    render = server.render_preview(str(out), str(png))
    if isinstance(render, dict) and render.get("available") is False:
        # honest record: render extra absent on this machine, not a render pass
        dump("09_render_preview.json", {"observed": render})
    else:
        info = png_info(png) if png.exists() else {"error": "no png written"}
        dump("09_render_preview.json", {"observed": render, "png": info})
        if not info.get("png_signature"):
            failures.append("render_preview: png missing or bad signature")

    dump("summary.json", {
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "values": VALUES,
        "failures": failures,
        "ok": not failures,
    })
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

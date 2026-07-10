from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from hangeul_core.body import detect_body_fields
from hangeul_core.capabilities import describe_capabilities as _describe_capabilities
from hangeul_core.checkbox import detect_checkbox
from hangeul_core.convert import ensure_hwpx
from hangeul_core.extract import extract_text as _extract_text
from hangeul_core.fill import fill as _fill
from hangeul_core.formfield import detect_form_fields
from hangeul_core.formfit import analyze_formfit as _analyze_formfit
from hangeul_core.inline import detect_inline
from hangeul_core.locate import detect_placeholders
from hangeul_core.markpen import detect_markpen
from hangeul_core.owpml import HwpxPackage
from hangeul_core.pii import scan_text as _scan_pii
from hangeul_core.understand import understand


def _field_dict(f) -> Dict[str, Any]:
    return {
        "field_id": f.field_id,
        "label": f.label,
        "kind": f.kind,
        "insert_after": f.insert_after,
        "template": f.template,
        "para_bullet": f.para_bullet,
        "char_spacing": f.char_spacing,
        "options": f.options,
        "capacity_hint": f.capacity_hint,
    }


def register_core_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def describe_capabilities() -> Dict[str, Any]:
        return _describe_capabilities()

    @mcp.tool()
    def detect_format(path: str) -> Dict[str, Any]:
        p = Path(path)
        if not p.exists():
            return {"format": "unknown", "ok": False, "reason": "file not found"}
        try:
            pkg = HwpxPackage.open(p)
            if pkg.is_mimetype_ok():
                return {"format": "hwpx", "ok": True}
        except Exception:
            pass
        if p.suffix.lower() == ".hwp":
            return {"format": "hwp", "ok": False, "note": "binary HWP; convert to HWPX first"}
        return {"format": "unknown", "ok": False}

    @mcp.tool()
    def analyze_form(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "format": "hwp", "fields": []}
        fields = (
            understand(path).fields
            + detect_inline(path)
            + detect_placeholders(path)
            + detect_markpen(path)
            + detect_checkbox(path)
            + detect_form_fields(path)
            + detect_body_fields(path)
        )
        return {"format": "hwpx", "fields": [_field_dict(f) for f in fields]}

    @mcp.tool()
    def fill_form(
        path: str,
        values: Dict[str, str],
        out_path: str,
        normalize_spacing: bool = False,
        respect_bullets: bool = True,
        checkbox_exclusive: bool = True,
        auto_fit: bool = False,
        mask_pii: bool = False,
        dry_run: bool = False,
        backup: bool = False,
    ) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "filled": [], "skipped": []}
        result = _fill(
            path,
            values,
            out_path,
            normalize_spacing=normalize_spacing,
            respect_bullets=respect_bullets,
            checkbox_exclusive=checkbox_exclusive,
            auto_fit=auto_fit,
            mask_pii=mask_pii,
            dry_run=dry_run,
            backup=backup,
        )
        return {
            "filled": result.filled,
            "skipped": result.skipped,
            "shrunk": result.shrunk,
            "masked": result.masked,
            "overflow": result.overflow,
            "pii_warnings": result.pii_warnings,
            "out_path": result.out_path,
            "dry_run": dry_run,
        }

    @mcp.tool()
    def scan_pii(path: str) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "findings": [], "count": 0}
        findings = _scan_pii(_extract_text(path))
        return {
            "findings": [{"type": f["type"], "masked": f["masked"]} for f in findings],
            "count": len(findings),
        }

    @mcp.tool()
    def analyze_formfit(path: str, values: Dict[str, str]) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"error": str(exc), "warnings": [], "checked": 0}
        return _analyze_formfit(path, values)

    @mcp.tool()
    def extract_text(path: str) -> str:
        return _extract_text(path)

    return {
        "describe_capabilities": describe_capabilities,
        "detect_format": detect_format,
        "analyze_form": analyze_form,
        "fill_form": fill_form,
        "scan_pii": scan_pii,
        "analyze_formfit": analyze_formfit,
        "extract_text": extract_text,
    }

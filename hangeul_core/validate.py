"""HWPX validation: well-formedness, container invariants, optional XSD.

Complements the byte-preserving fill engine with an output check. The core
checks are dependency-free:

* every XML entry parses (``ET.fromstring``),
* ``mimetype`` is the first, STORED entry with the correct value,
* each ``Contents/section*.xml`` starts with an XML declaration.

If ``python-hwpx`` is installed (soft dependency, per DECISIONS D1) its XSD
schema validation is run and folded into the result; otherwise ``xsd.available``
is ``False`` and the core checks still stand.
"""

from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List

from hangeul_core.owpml import HwpxPackage

_XML_SUFFIXES = (".xml", ".rdf", ".hpf")
_DECL = re.compile(rb"<\?xml[^>]*\?>")
# quote-agnostic: OWN byte-splice keeps double quotes, python-hwpx re-serializes
# with single quotes; both must retain standalone=yes (HANDOFF invariant).
_STANDALONE_YES = re.compile(rb"standalone\s*=\s*['\"]yes['\"]")


def _xsd_check(path: str | Path) -> Dict:
    """Package validation via python-hwpx if importable (validate_package)."""
    if importlib.util.find_spec("hwpx") is None:
        return {"available": False, "note": "python-hwpx not installed"}
    try:  # pragma: no cover - only runs where python-hwpx is present
        import hwpx  # type: ignore

        validator = getattr(hwpx, "validate_package", None) or getattr(hwpx, "validate", None)
        if validator is None:
            return {"available": False, "note": "python-hwpx has no validate_package()"}
        report = validator(str(path))
        ok = getattr(report, "ok", bool(report))
        return {
            "available": True,
            "valid": bool(ok),
            "errors": [str(e) for e in (getattr(report, "errors", None) or [])],
            "warnings": [str(w) for w in (getattr(report, "warnings", None) or [])],
        }
    except Exception as exc:  # pragma: no cover
        return {"available": False, "error": str(exc)}


def validate_hwpx(path: str | Path) -> Dict:
    """Validate an HWPX file. Returns a structured report (never raises)."""
    errors: List[str] = []
    try:
        pkg = HwpxPackage.open(path)
    except (zipfile.BadZipFile, OSError) as exc:
        return {
            "valid": False,
            "well_formed": False,
            "mimetype_ok": False,
            "declaration_ok": False,
            "errors": [f"not a readable HWPX/ZIP: {exc}"],
            "xsd": {"available": False},
        }

    mimetype_ok = pkg.is_mimetype_ok()
    if not mimetype_ok:
        errors.append("mimetype is not the first STORED entry with value application/hwp+zip")

    well_formed = True
    for name in pkg.names():
        if name.endswith(_XML_SUFFIXES):
            try:
                ET.fromstring(pkg.read(name))
            except ET.ParseError as exc:
                well_formed = False
                errors.append(f"{name}: XML parse error: {exc}")

    declaration_ok = True
    for name in pkg.names():
        if name.startswith("Contents/section") and name.endswith(".xml"):
            decl = _DECL.match(pkg.read(name).lstrip())
            if decl is None:
                declaration_ok = False
                errors.append(f"{name}: missing XML declaration")
            elif not _STANDALONE_YES.search(decl.group(0)):
                # HANDOFF invariant: re-serialization must not drop standalone=yes
                declaration_ok = False
                errors.append(f'{name}: XML declaration missing standalone="yes"')

    xsd = _xsd_check(path)
    # `valid` = container structural integrity (well-formed + mimetype + declaration).
    # Package/XSD validation is reported separately under `xsd` (minimal/partial
    # packages are structurally valid but not full OPC packages); delegated edits
    # additionally require xsd.valid via their own gate (delegate._edit_result).
    valid = well_formed and mimetype_ok and declaration_ok
    return {
        "valid": valid,
        "well_formed": well_formed,
        "mimetype_ok": mimetype_ok,
        "declaration_ok": declaration_ok,
        "errors": errors,
        "xsd": xsd,
    }

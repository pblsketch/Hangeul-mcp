"""누름틀(form field) headless detection + fill — no COM.

HWPX represents a 누름틀 / cell field as a paired control in the section XML::

    <hp:ctrl><hp:fieldBegin type="CLICKHERE" name="성명" .../></hp:ctrl>
    <hp:run charPrIDRef="0"><hp:t>기존텍스트</hp:t></hp:run>
    <hp:ctrl><hp:fieldEnd .../></hp:ctrl>

The field's display text lives in the runs *between* the begin and end controls;
its name is the ``name`` attribute on ``fieldBegin`` (the same name the COM path
uses via ``GetFieldList`` / ``PutFieldText`` — so ``fill_form`` and
``apply_to_open_hwp`` accept the *same* name-keyed values dict).

We fill a field by replacing the text between its controls headlessly, leaving
``fieldBegin`` / ``fieldEnd`` intact. Fields sharing a name are all filled (COM
``PutFieldText`` behaves the same). Non-fillable field types (e.g. HYPERLINK) are
ignored.

Note: with no ``python-hwpx`` available to spike a real sample, this targets the
documented OWPML shape and is attribute-order robust; validating against a real
누름틀 file is tracked as a follow-up (see docs/ROADMAP.md tech-debt).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hangeul_core.analyze import _section_names
from hangeul_core.owpml import HwpxPackage
from hangeul_core.schema import KIND_FORMFIELD, Field

# fieldBegin/fieldEnd may be self-closing or carry children (parameterset).
_BEGIN = r"<hp:fieldBegin\b[^>]*?(?:/>|>.*?</hp:fieldBegin>)"
_END = r"<hp:fieldEnd\b[^>]*?(?:/>|>.*?</hp:fieldEnd>)"
_FIELD = re.compile(rf"({_BEGIN})(.*?)({_END})", re.S)
_NAME_ATTR = re.compile(r'\bname="([^"]*)"')
# fallback: a nested parameter carrying the field name (best-effort)
_NAME_PARAM = re.compile(r'name="(?:FieldName|Name)"[^>]*?val(?:ue)?="([^"]*)"')
_TYPE_ATTR = re.compile(r'\btype="([^"]*)"')
_T = re.compile(r"<hp:t>(.*?)</hp:t>", re.S)
_T_ANY = re.compile(r"<hp:t\s*/>|<hp:t>(.*?)</hp:t>", re.S)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _open_tag(begin: str) -> str:
    """The ``<hp:fieldBegin ...>`` opening tag only (excludes any children)."""
    end = begin.find(">")
    return begin[: end + 1] if end != -1 else begin


def _field_name(begin: str) -> Optional[str]:
    m = _NAME_ATTR.search(_open_tag(begin))  # own attribute only
    if m and m.group(1):
        return m.group(1)
    m = _NAME_PARAM.search(begin)  # fallback: a nested name parameter
    return m.group(1) if m else None


def _fillable(begin: str) -> bool:
    """True unless the field type is clearly non-fillable (e.g. hyperlink)."""
    t = _TYPE_ATTR.search(_open_tag(begin))
    if not t:
        return True
    tu = t.group(1).upper()
    if "CLICK" in tu or "CELL" in tu or tu in ("", "UNKNOWN"):
        return True
    return False


def _current_text(region: str) -> str:
    return "".join(t or "" for t in _T.findall(region))


def form_field_names(path: str | Path) -> List[str]:
    names: List[str] = []
    pkg = HwpxPackage.open(path)
    for sname in _section_names(pkg):
        section = pkg.read(sname).decode("utf-8")
        for m in _FIELD.finditer(section):
            if not _fillable(m.group(1)):
                continue
            name = _field_name(m.group(1))
            if name and name not in names:
                names.append(name)
    return names


def detect_form_fields(path: str | Path) -> List[Field]:
    """Detect 누름틀 named fields as KIND_FORMFIELD fields (deduped by name)."""
    pkg = HwpxPackage.open(path)
    fields: List[Field] = []
    seen: set = set()
    for sname in _section_names(pkg):
        section = pkg.read(sname).decode("utf-8")
        for m in _FIELD.finditer(section):
            if not _fillable(m.group(1)):
                continue
            name = _field_name(m.group(1))
            if not name or name in seen:
                continue
            seen.add(name)
            fields.append(
                Field(
                    field_id=f"field:{name}",
                    label=name,
                    kind=KIND_FORMFIELD,
                    template=_current_text(m.group(2)) or None,
                )
            )
    return fields


def _set_field_text(region: str, value: str) -> str:
    """Replace the field's inner text with *value* (first <hp:t>, else insert)."""
    esc = _esc(value)
    tm = _T_ANY.search(region)
    if tm:
        return region[: tm.start()] + "<hp:t>" + esc + "</hp:t>" + region[tm.end():]
    # self-closing run -> expand
    m = re.search(r"<hp:run\b([^>]*?)/>", region)
    if m:
        return (
            region[: m.start()]
            + "<hp:run" + m.group(1) + "><hp:t>" + esc + "</hp:t></hp:run>"
            + region[m.end():]
        )
    # empty open/close run -> inject <hp:t>
    m = re.search(r"(<hp:run\b[^>]*>)(</hp:run>)", region)
    if m:
        return region[: m.start()] + m.group(1) + "<hp:t>" + esc + "</hp:t>" + m.group(2) + region[m.end():]
    # no run at all -> insert one after any leading </hp:ctrl>
    ins = re.match(r"\s*</hp:ctrl>", region)
    at = ins.end() if ins else 0
    run = '<hp:run charPrIDRef="0"><hp:t>' + esc + "</hp:t></hp:run>"
    return region[:at] + run + region[at:]


def replace_form_fields(section: str, name_values: Dict[str, str]) -> Tuple[str, List[str]]:
    """Fill every named field whose name is in *name_values* (all occurrences)."""
    applied: List[str] = []

    def repl(m: "re.Match") -> str:
        begin, region, end = m.group(1), m.group(2), m.group(3)
        if not _fillable(begin):
            return m.group(0)
        name = _field_name(begin)
        if name is None or name not in name_values:
            return m.group(0)
        applied.append(name)
        return begin + _set_field_text(region, name_values[name]) + end

    new = _FIELD.sub(repl, section)
    # de-dup preserving order
    seen: List[str] = []
    for n in applied:
        if n not in seen:
            seen.append(n)
    return new, seen

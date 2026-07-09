"""PII detection + masking gate.

The SKILL previously only *advised* stripping personal data. This turns that
advice into a real, code-level gate: detect Korean-context PII (주민등록번호/
외국인등록번호, 전화번호, 신용카드, 계좌번호(heuristic), 이메일) and optionally
mask it before a value is written into a form.

Two entry points:

* :func:`scan_text` — find PII spans with a suggested masked form (audit only),
* :func:`mask_value` — return the text with every detected span masked.

``fill(mask_pii=True)`` masks provided values before writing; the MCP tool
``scan_pii`` audits an existing document's text. Detection is deliberately
conservative and format-preserving (keeps separators; hides sensitive digits).
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Tuple

# 주민등록번호(1-4) / 외국인등록번호(5-8): YYMMDD[-]Gxxxxxx (13 digits).
# Trailing \b prevents matching inside a longer digit run (e.g. a 16-digit card).
_RRN = re.compile(r"\b\d{6}[-\s]?[1-8]\d{6}\b")
# 신용카드: 16 digits in four groups.
_CARD = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
# 전화번호: separated (01x/area code, 3-4 then 4 digits) OR separatorless mobile.
# The separatorless form uses strict digit boundaries so it never matches inside a
# longer digit run (e.g. a 13-digit RRN or 16-digit card).
_PHONE = re.compile(
    r"\b(?:01[016789]|0\d{1,2})[-\s.]\d{3,4}[-\s.]\d{4}\b"
    r"|(?<!\d)01[016789]\d{7,8}(?!\d)"
)
# 이메일.
_EMAIL = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
# 계좌번호(heuristic): 2-3 hyphenated numeric groups. Lowest priority.
_ACCOUNT = re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,7}(?:-\d{1,6})?\b")


def _mask_keep(s: str, keep_first: int, keep_last: int) -> str:
    """Mask digits of *s*, keeping the first/last N digits; keep separators."""
    n = sum(c.isdigit() for c in s)
    out: List[str] = []
    di = 0
    for ch in s:
        if ch.isdigit():
            di += 1
            out.append(ch if (di <= keep_first or di > n - keep_last) else "*")
        else:
            out.append(ch)
    return "".join(out)


def _mask_rrn(s: str) -> str:
    return _mask_keep(s, keep_first=7, keep_last=0)  # hide the 뒷 6 digits


def _mask_card(s: str) -> str:
    return _mask_keep(s, keep_first=4, keep_last=4)


def _mask_phone(s: str) -> str:
    return _mask_keep(s, keep_first=3, keep_last=4)


def _mask_account(s: str) -> str:
    return _mask_keep(s, keep_first=2, keep_last=3)


def _mask_email(s: str) -> str:
    local, at, domain = s.partition("@")
    if not at or not local:
        return s
    masked = local[0] + "*" * max(1, len(local) - 1)
    return masked + "@" + domain


# (type, pattern, masker) in priority order — earlier claims win on overlap.
_SPEC: List[Tuple[str, re.Pattern, Callable[[str], str]]] = [
    ("resident_registration_number", _RRN, _mask_rrn),
    ("credit_card", _CARD, _mask_card),
    ("phone", _PHONE, _mask_phone),
    ("email", _EMAIL, _mask_email),
    ("account", _ACCOUNT, _mask_account),
]


def scan_text(text: str) -> List[Dict]:
    """Return non-overlapping PII findings: type, start, end, match, masked."""
    claimed: List[Tuple[int, int]] = []
    findings: List[Dict] = []
    for typ, pat, masker in _SPEC:
        for m in pat.finditer(text):
            s, e = m.start(), m.end()
            if any(not (e <= cs or s >= ce) for cs, ce in claimed):
                continue  # overlaps a higher-priority finding
            claimed.append((s, e))
            findings.append(
                {"type": typ, "start": s, "end": e, "match": m.group(0), "masked": masker(m.group(0))}
            )
    findings.sort(key=lambda f: f["start"])
    return findings


def mask_value(text: str) -> str:
    """Return *text* with every detected PII span replaced by its masked form."""
    findings = scan_text(text)
    out = text
    for f in sorted(findings, key=lambda f: f["start"], reverse=True):
        out = out[: f["start"]] + f["masked"] + out[f["end"]:]
    return out

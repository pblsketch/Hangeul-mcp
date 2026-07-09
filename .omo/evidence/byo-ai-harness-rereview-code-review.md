# BYO-AI harness re-review

## Result

- codeQualityStatus: BLOCK
- recommendation: REQUEST_CHANGES
- reportPath: `.omo/evidence/byo-ai-harness-rereview-code-review.md`
- blockers:
  - `hangeul_mcp/server.py` and `hangeul_core/delegate.py` remain over the loaded `programming` / `remove-ai-slops` 250 pure-LOC ceiling after this change set.

## Skill-perspective check

- `omo:remove-ai-slops` consulted: yes. Remaining blocker is oversized production modules; no remaining blocker from deletion-only tests, tautological tests, or implementation-mirroring tests in the focused re-review scope.
- `omo:programming` consulted: yes, including Python-specific guidance. The diff still violates the programming/code-smell perspective for touched production files over 250 pure LOC.

## CRITICAL

- None.

## HIGH

1. `hangeul_mcp/server.py` and `hangeul_core/delegate.py` remain oversized touched production files. Current pure LOC counts: `hangeul_mcp/server.py: 577`, `hangeul_core/delegate.py: 310`. The loaded `programming` and `remove-ai-slops` criteria treat files over 250 pure LOC as an architectural defect, and this change set still adds tool wiring/delegate functionality to those files instead of splitting by responsibility. This was a prior blocker and remains unresolved.

## MEDIUM

- None in the focused remaining-blocker re-review. The prior `.hwp` preview side-effect issue, render browser-missing issue, and hwp-headless capability mismatch were rechecked and are no longer blockers.

## LOW

1. `README.md:8` still reports `185 passed / 1 skipped`, while current full verification reports `186 passed, 1 skipped`. This is non-blocking documentation drift but should be corrected before handoff if the README is intended to carry current verification evidence.

## Verification evidence reviewed

- `./.venv/Scripts/python.exe -m pytest tests/test_capabilities.py tests/test_live_resolve.py tests/test_render_preview.py -q` -> `11 passed in 8.13s`
- `./.venv/Scripts/python.exe -m pytest -q` -> `186 passed, 1 skipped in 21.51s`
- `./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests` -> exit 0
- `./.venv/Scripts/python.exe -m json.tool docs/prd.json` -> exit 0
- `git diff --check` -> exit 0 with CRLF replacement warnings only
- Focused probe: `server.preview_cells_to_open_hwp("x.hwp", ...)` returned `ok:false` without conversion.
- Focused probe: synthetic `PlaywrightError` from browser launch made `render_available()` return `available:false` with setup hint.

## Resolved prior blockers

- `preview_cells_to_open_hwp` no longer calls `ensure_hwpx()` for `.hwp`; it rejects `.hwp`/non-`.hwpx` before any conversion path.
- `render_available()` now probes Chromium launch and `render_preview()` returns structured `available:false` for missing browser cases covered by Playwright errors.
- `describe_capabilities()` now uses `render_available()` and reports `hwp_headless` unavailable until a concrete reader adapter exists.

# BYO-AI harness code review

## Result

- codeQualityStatus: BLOCK
- recommendation: REQUEST_CHANGES
- reportPath: `.omo/evidence/byo-ai-harness-code-review.md`
- blockers:
  - `preview_cells_to_open_hwp` can still route `.hwp` inputs through COM conversion despite the documented side-effect-free guarantee.
  - `render_preview` and `describe_capabilities` treat Playwright importability as render availability and do not handle missing Chromium/browser-launch failures as structured `available:false`.
  - The change adds substantial code to already-oversized Python modules (`hangeul_mcp/server.py`, `hangeul_core/delegate.py`), violating the loaded programming/code-smell perspective.

## Skill-perspective check

- `omo:remove-ai-slops` consulted: yes. The diff has no deletion-only tests, no tests that merely assert a removed feature is absent, and no obvious tautological mocks. It does have coverage gaps where tests assert tool registration or happy-path shape while missing the safety/availability failures below.
- `omo:programming` consulted: yes, including Python and code-smell references. The diff violates the programming perspective by adding to files over the 250 pure-LOC ceiling and by leaving optional-dependency/browser errors insufficiently parsed at the boundary.

## CRITICAL

- None found.

## HIGH

1. `hangeul_mcp/server.py:647` calls `ensure_hwpx()` inside `preview_cells_to_open_hwp`, but the tool is documented as side-effect-free and never dispatching COM. For `.hwp` input, `ensure_hwpx()` calls `hangeul_core/convert.py:21`, which calls `hwp_to_hwpx()`, and that path connects to Hangul COM and opens/saves the document at `hangeul_core/convert.py:39`. This violates the BYO-AI/live-preview safety contract and `docs/prd.json` acceptance for US-045. Existing tests only call the pure core helper on an `.hwpx` fixture (`tests/test_live_resolve.py:48`); they do not cover the MCP wrapper or `.hwp` input.

2. `hangeul_core/render.py:59` does not catch browser-launch failures, while `hangeul_core/capabilities.py:35` marks render as available based only on `playwright` importability. This misses the common installed-package-but-no-Chromium state documented in `README.md:97` and required by `docs/prd.json:573`. I reproduced the behavior with a synthetic patched `p.chromium.launch()` failure: `render_preview()` raised `RuntimeError: browser missing` instead of returning structured `available:false` with a setup hint. Existing coverage (`tests/test_render_preview.py:9`) only simulates a missing import, not missing browser binaries.

3. The change adds to already oversized production modules: `hangeul_mcp/server.py` grew from 494 to 572 pure LOC, and `hangeul_core/delegate.py` grew from 275 to 310 pure LOC. The loaded programming/code-smell perspective treats >250 pure LOC as a defect and specifically rejects adding lines to an already oversized touched unit without splitting by responsibility. This is a maintainability blocker because the MCP server has become a large tool registry plus adapter/error-normalization layer, and delegate generation/table/markdown routing continue accumulating in one module.

## MEDIUM

1. `hangeul_core/capabilities.py:105` reports `hwp_headless.available` from `headless_status()` whenever any candidate module is importable, but `hangeul_core/hwp_headless.py:30` always returns `available:false` when a substrate is detected because no adapter has been selected. A client using the manifest can be routed to a tool that is guaranteed to decline. Either the manifest should report adapter readiness, or the tool should distinguish "candidate detected" from "usable capability".

2. `hangeul_core/blocks.py:110` catches all `Exception` during block assembly and converts it to `{"ok": false}`. This is close to a public boundary, but the broad catch also hides implementation bugs from tests and violates the loaded programming perspective's "catch specific expected exceptions" rule. If kept, tests should cover the expected user-input errors specifically and unexpected library/programmer errors should not be silently flattened.

## LOW

1. `README.md:8` reports "181 passed / 1 skipped", while current verification is `185 passed, 1 skipped`. This is documentation drift and weakens the verification trail.

## Verification evidence reviewed

- `./.venv/Scripts/python.exe -m pytest -q` -> `185 passed, 1 skipped in 19.71s`
- `./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests` -> exit 0
- `./.venv/Scripts/python.exe -m json.tool docs/prd.json` -> exit 0
- `git diff --check` -> exit 0 with CRLF replacement warnings only
- Additional synthetic check: patched `p.chromium.launch()` to raise and observed unhandled `RuntimeError: browser missing`

## Residual risk

- The current green tests are relevant for baseline regression, registration, and happy-path behavior, but they are not sufficient for the new safety/availability guarantees because they miss the server wrapper path for live preview and the missing-browser state for render.

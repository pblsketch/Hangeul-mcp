# Codex QA review — v0.1.0

Independent QA by `codex exec` (reasoning: xhigh) against docs/prd.json acceptance
criteria. All findings were reproduced by codex, then fixed with regression tests.
Final state: **55 passed, 1 skipped (live COM); pyflakes clean.**

## Findings & resolutions

**HIGH-1 — multi-section fill.** `analyze()` reads all `Contents/section*.xml`, but
`fill()` only read/wrote `section0.xml`, so fields in section1+ were skipped.
→ Fixed: `Cell` now carries `section` + `table_in_section`; `fill()` loads and
rewrites each field's own section. Test: `test_qa_regress.test_multi_section_fill`.

**HIGH-2 — inline marker double-marker.** An inline marker value beginning with the
cell's own marker (`"∘ ABC"`) produced `∘ ∘ ABC`.
→ Fixed: `_apply_inline` strips a leading duplicate of *this cell's* anchor marker
only (not other content like `○○대학교`). Tests: `test_inline_marker_no_double...`,
plus the original `test_inline_marker_no_duplicate`.

**MED-3 — merged covered coordinates.** Label→value mapping used a top-left-only
index, missing value cells whose adjacency coordinate is a *covered* coordinate of
a merged cell.
→ Fixed: `understand._occupancy` maps every covered (row,col) to its owner cell.
Test: `test_qa_regress.test_occupancy_resolves_merged_covered_coordinate`.

**MED-4 — .hwp conversion error path.** A generic COM exception during `.hwp`→`.hwpx`
conversion propagated instead of degrading gracefully in the MCP tools.
→ Fixed: `hwp_to_hwpx` normalizes COM errors to `RuntimeError`, which the server
tools already catch. Test: `test_qa_regress.test_convert_wraps_com_exception...`.

**LOW-5 — byte-preservation wording.** Clarified that the guarantee is *entry payload*
byte-identical (the archive is rewritten; raw ZIP framing may differ).

## First-round findings (also fixed)

- `_find_cell_span` sibling-table spillover (stop at target table close).
- CRLF/`\r` left in text nodes (normalize line breaks before split).
- Unused imports removed; `available()` uses `importlib.util.find_spec`.

## Reviewer's forward suggestion

For maximum robustness, build a namespace-aware (Expat/SAX) index of
`section + table stack + cellAddr + byte spans` at analyze time and splice only those
spans at fill time, instead of re-scanning raw XML with regex. Deferred (current
approach is covered by regression tests); tracked for a future refactor.

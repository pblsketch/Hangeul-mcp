# Independent QA Review: Phase A-D / US-013..US-037

Date: 2026-07-09
Scope: `hangeul_core` modules added/expanded in US-013..US-037 and `hangeul_mcp/server.py`.

## Verification Run

- Command: `./.venv/Scripts/python.exe -m pytest -q`
- Result: `159 passed, 1 skipped in 19.05s`
- Fixture PII spot-check: `scan_text(extract_text("tests/fixtures/sample_form.hwpx")) == []`

## Invariant Summary

- OWN mutation paths mostly avoid `ElementTree.write`; mutation is string/byte splice through `HwpxPackage.replace`.
- `HwpxPackage.save` preserves entry order/compression and keeps the existing first `mimetype` entry STORED.
- Delegated mutation paths consistently call `_edit_result()` after `_save()`, but the validation gate is currently weaker than documented because it does not call the installed `python-hwpx` validation API and does not verify `standalone="yes"`.
- Server tools generally keep value/prose generation client-side, except the recipe document generation path, which hardcodes document prose/skeleton lines.

## Findings

### High 1. Delegated validate gate is not using the installed `python-hwpx` validation API

- Location: `hangeul_core/validate.py:28`, `hangeul_core/validate.py:35`, `hangeul_core/delegate.py:77`
- Issue: `_xsd_check()` only looks for `hwpx.validate`. In the installed package, `hwpx.validate` is absent and `hwpx.validate_package(source)` is present. As a result, `validate_hwpx()` reports `xsd.available: false` even when `python-hwpx` is installed, so delegated edits can be marked `ok` using only the lightweight XML/mimetype/declaration checks.
- Evidence:
  - `validate_hwpx("tests/fixtures/sample_form.hwpx")["xsd"]` returned `{"available": False, "note": "python-hwpx has no validate()"}`.
  - Installed API inspection showed `validate_package(source: str | Path | bytes | BinaryIO) -> PackageValidationReport`, with `.ok`, `.errors`, `.warnings`.
- Risk: Phase C/D delegated edits re-serialize XML and rely on `validate_hwpx` as the integrity gate. A package-level issue caught by `python-hwpx` will currently be missed.
- Concrete fix: In `_xsd_check`, prefer `hwpx.validate_package(path)` when present and set `available: true`, `valid: report.ok`, plus serialized `errors`/`warnings`. Keep a fallback for older `hwpx.validate` if needed. Add a regression asserting that when `hwpx` is importable, `validate_hwpx(...).xsd.available is True` and package warnings/errors are surfaced.

### High 2. `validate_hwpx` accepts section XML declarations that lost `standalone="yes"`

- Location: `hangeul_core/validate.py:72`, `hangeul_core/validate.py:75`
- Issue: `declaration_ok` only checks that section bytes start with `<?xml`; it does not enforce the project invariant that section declarations preserve `standalone="yes"`.
- Evidence: Removing ` standalone="yes"` from `Contents/section*.xml` in a copy of `tests/fixtures/sample_form.hwpx` still returned `valid=True`, `declaration_ok=True`, `errors=[]`.
- Risk: This is exactly the corruption mode called out in `HANDOFF.md`: XML reserialization can keep an XML declaration while dropping `standalone="yes"`. Delegated edits and any future mutation path can pass the gate despite violating the invariant.
- Concrete fix: Parse only the XML declaration bytes up to `?>` for every `Contents/section*.xml` and require `standalone="yes"` (and preferably the expected UTF-8 encoding). Add a regression with a synthetic HWPX missing `standalone="yes"` that must return `valid=False`.

### High 3. Split-run 누름틀 replacement leaves stale old text after the new value

- Location: `hangeul_core/formfield.py:118`, `hangeul_core/formfield.py:121`, `hangeul_core/formfield.py:143`
- Issue: `_set_field_text()` replaces only the first `<hp:t>` inside the field region. If the displayed field value is split across two or more runs, later `<hp:t>` nodes remain unchanged.
- Evidence: `replace_form_fields()` on a field region containing `<hp:t>old</hp:t><hp:t>tail</hp:t>` with value `new` produced `<hp:t>new</hp:t><hp:t>tail</hp:t>`.
- Risk: Real HWPX editors frequently split text across runs for styling. A filled form field can display `newtail`, leaking template/example text and corrupting the value while still producing well-formed XML.
- Concrete fix: Replace the first text node with the escaped value and clear every subsequent `<hp:t>` in the same field region, or replace the entire textual span between `fieldBegin` and `fieldEnd` with a single run cloned from the first run. Add a regression for multi-run form-field text and for styled split runs.

### High 4. Recipe document generation hardcodes prose/skeleton text in the server

- Location: `hangeul_core/delegate.py:192`, `hangeul_core/delegate.py:221`, `hangeul_core/delegate.py:249`, `hangeul_core/delegate.py:275`, `hangeul_core/delegate.py:282`, `hangeul_mcp/server.py:411`
- Issue: `create_official_document()` inserts hardcoded lines such as `보도자료`, `제목`, `담당자:`, `1. 목적`, `2. 내용`, and falls back from unknown `doc_type` to `공문`.
- Risk: `HANDOFF.md` says the server never generates content/prose and all values are client-provided. These recipe builders generate document text not supplied in `fields`, which weakens the brain/hand separation and makes server-side prose decisions invisible to clients.
- Concrete fix: Treat recipes as client-provided templates or client-provided ordered blocks. The server should only place strings explicitly supplied by the client (for example `lines: list[str]` or `sections: list[{heading, body}]`). If fixed labels are intentionally allowed as layout chrome, document that exception in `DECISIONS.md` and require the client to select an explicit template version rather than falling back silently.

### Medium 1. Live cell-fill can target the wrong live table/cell for nested or merged tables

- Location: `hangeul_core/analyze.py:122`, `hangeul_core/analyze.py:125`, `hangeul_core/hwp/live.py:65`, `hangeul_core/hwp/live.py:109`, `hangeul_core/hwp/live.py:112`
- Issue: `analyze()` indexes every `<hp:tbl>` from `root.iter()`, including nested tables, then `apply_cells_to_open()` calls `pyhwpx.get_into_nth_table(t["table"] - 1)` and `goto_addr(row + 1, col + 1)`. The code assumes the XML global table index and pyhwpx live table-control index have identical ordering, and that `goto_addr` accepts the same merged-cell covered coordinates after a +1 conversion.
- Risk: On a document with nested tables or merged cells, the live COM path can enter the wrong table or fail/reach the wrong cell, then `Delete` and `insert_text` mutate the currently selected cell in the user's open Hangul window.
- Concrete fix: Make the mapping contract explicit before live mutation: store top-level table ordinal separately from nested table ordinal, add synthetic nested-table resolver tests, and add an opt-in live smoke test that verifies `get_into_nth_table` ordering and `goto_addr` behavior on merged cells before enabling `clear=True`. Prefer selecting by an exported control/table identifier if pyhwpx exposes one.

### Medium 2. `replace_literals` does not implement the documented "longer finds win on overlap"

- Location: `hangeul_core/locate.py:165`, `hangeul_core/locate.py:171`
- Issue: Spans are sorted by `(start, -length)` and then claimed left-to-right. A shorter earlier match wins over a longer overlapping match that starts one character later.
- Evidence: `replace_literals("<hp:t>abcde</hp:t>", {"ab": "X", "bcde": "Y"})` returned `<hp:t>Xcde</hp:t>` and `{"ab": 1}`.
- Risk: `batch_replace()` can produce different edits than the API contract says, especially for replacement dictionaries with prefixes/suffixes or overlapping terms.
- Concrete fix: Resolve all overlaps by global priority, for example sort candidate spans by `(-(end-start), start)` to claim longer spans first, then apply claimed spans in document order. Add tests for same-start and different-start overlaps.

### Medium 3. Form-fit overflow checks underestimate appended non-empty-cell fills

- Location: `hangeul_core/fill.py:377`, `hangeul_core/fill.py:383`, `hangeul_core/fill.py:400`, `hangeul_core/fill.py:208`
- Issue: For regular cell fills, overflow warning and auto-fit scale are computed from `value` alone before `_apply_cell()`. But `_apply_cell()` appends to existing non-empty cell text (`base + sep + value`) for non-empty cells.
- Risk: A cell that appears safe for the new value alone can overflow after the existing prefix/template text is included. `auto_fit=True` can also shrink too little because the scale is based on the shorter string.
- Concrete fix: Compute the effective rendered text that will be present after `_apply_cell()` before calling `overflow_ratio()` / `overflow_scale()`, or run the estimate after building `newp` by extracting its first-line text. Add a regression with a non-empty value cell where `base + value` crosses the threshold but `value` alone does not.

### Medium 4. PII scanner misses common unseparated Korean phone numbers

- Location: `hangeul_core/pii.py:29`
- Issue: `_PHONE` requires a separator between groups. Common inputs such as `01012345678` and `021234567` are not detected, while `010-1234-5678` is detected.
- Evidence: `scan_text("01012345678") == []`; `scan_text("010-1234-5678")` returned a phone finding.
- Risk: `fill(mask_pii=True)` can write unmasked mobile/area phone numbers if the client supplies digits without separators.
- Concrete fix: Add separatorless alternatives with strict digit boundaries, e.g. mobile `(?<!\d)01[016789]\d{7,8}(?!\d)` and area-code patterns if desired. Add masking tests for separatorless mobile numbers and ensure they do not overlap credit-card/RRN matches.

### Medium 5. Text locate/replacement works on raw XML entity text, not user-visible text

- Location: `hangeul_core/locate.py:52`, `hangeul_core/locate.py:98`, `hangeul_core/locate.py:155`, `hangeul_core/checkbox.py:127`, `hangeul_core/markpen.py:41`
- Issue: The locate paths concatenate raw `<hp:t>` inner XML. Text containing XML entities is searched as `&amp;`, `&lt;`, `&gt;`, not as user-visible `&`, `<`, `>`.
- Evidence: `replace_literals("<hp:t>A &amp; B</hp:t>", {"A & B": "X"})` returned no replacement.
- Risk: `search_and_replace`, placeholder detection/fill, checkbox labels, and nearby markpen labels can miss or expose escaped labels for valid document text containing `&`, `<`, or `>`. Multibyte Korean characters are safe under Python `str`, but XML entity boundaries are not user-visible character boundaries.
- Concrete fix: Build the concat/index map over XML-unescaped logical text while retaining raw spans for each entity. Replacements must splice the raw XML span and escape only replacement values. Add tests for `&`, `<`, `>` in literals, placeholder names, and checkbox labels.

### Low 1. `live_available()` reports true when `pyhwpx` imports fail due transitive dependencies

- Location: `hangeul_core/hwp/live.py:32`
- Issue: `live_available()` checks only `importlib.util.find_spec("pyhwpx")`. In this environment it returned `True`, but `from pyhwpx import Hwp` failed with `ModuleNotFoundError: No module named 'numpy'`.
- Risk: Any future status UI using `live_available()` can overstate readiness. `apply_cells_to_open()` itself catches the import failure and returns `available: false`, so this is not a current mutation bug.
- Concrete fix: Make `live_available()` perform the same guarded import used by `apply_cells_to_open()` or return a structured status with the import error.

### Low 2. Delegated server tools do not normalize operation exceptions into structured tool results

- Location: `hangeul_mcp/server.py:339`, `hangeul_mcp/server.py:378`, `hangeul_mcp/server.py:411`, `hangeul_mcp/server.py:457`, `hangeul_mcp/server.py:489`
- Issue: The server checks `available:false` before delegated calls, but once the substrate is present, operation errors from file I/O, `_save()`, or python-hwpx methods propagate instead of returning `{available: true, ok: false, error: ...}`.
- Risk: A bad image path, invalid out path, or substrate exception can fail the MCP request abruptly. This does not violate byte preservation, but it weakens the error handling contract for optional delegate tools.
- Concrete fix: Wrap each delegated operation in a narrow `try` at the server boundary and return structured errors while preserving `available:true` for installed-but-failed substrate cases. Add one test for missing image path or unwritable output directory.

## Areas Audited Without Separate Findings

- `HwpxPackage.save()` keeps unmodified entry payloads byte-identical and preserves the first STORED `mimetype` entry for OWN paths.
- `checkbox.toggle_checkbox()` edits glyph offsets inside `<hp:t>` text only for the normal synthetic cases; the remaining concern is the raw-entity label mapping covered above.
- `markpen.replace_markpen()` preserves `markpenBegin`/`markpenEnd` and skips inline-markup spans rather than corrupting them; the remaining concern is raw-entity label extraction covered above.
- `delegate.py` mutation functions do call `_edit_result()` after saving; the main gate problem is `validate_hwpx()` implementation, not missing calls.

## Resolution (2026-07-09, follow-up commits)

All findings addressed; suite 167 passed / 1 skipped after fixes.

- High-1 ✅ `validate._xsd_check` now uses `hwpx.validate_package`; delegated edits gated by real package validation (`delegate._edit_result` requires `xsd.valid`).
- High-2 ✅ declaration check enforces `standalone=yes` (quote-agnostic); `valid` = structural integrity, package/XSD reported separately; regression added (missing/single-quote standalone).
- High-3 ✅ `_set_field_text` clears trailing `<hp:t>` in the field region; split-run regression added.
- High-4 ✅ documented as an intentional layout-chrome exception (DECISIONS D6); content values stay client-provided.
- Med-2 ✅ `replace_literals` global longest-first interval scheduling.
- Med-3 ✅ overflow estimate uses effective post-fill text (defensive; empty_cell targets are value-only).
- Med-4 ✅ separatorless mobile phone detection with strict digit boundaries.
- Med-5 ✅ `replace_literals` matches the escaped needle (XML entities).
- Med-1 🟡 documented mapping caveat (DECISIONS D7); deep fix pending live validation.
- Low-1 ✅ `live_available()` guarded import.
- Low-2 ✅ delegated tools return structured errors via `_delegate_op`.

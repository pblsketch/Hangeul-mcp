# RALPLAN — Hangeul-mcp unfinished optional extensions

Status: planning handoff, not implementation.

Repository: `E:/github/Hangeul-mcp`

Context snapshot: `.omx/context/hangeul-mcp-unfinished-extensions-20260709T074538Z.md`

## 1. Outcome

Implement the still-unfinished optional extension set without weakening the existing Hangeul-mcp invariants:

1. existing-table merge and cell shading
2. `create_document_from_blocks`
3. structure-preserving markdown → HWPX
4. `render_preview` PNG
5. `.hwp` headless reading

The end state must expose MCP tools where appropriate, include tests and documentation, and avoid overstating support for dependencies that are not actually available.

## 2. RALPLAN-DR summary

### Principles

1. **No overclaiming**: a feature is not marked complete until a real tool path, tests, and observable output exist.
2. **Brain/hand separation**: clients provide content; Hangeul-mcp only assembles, edits, validates, renders, or extracts.
3. **Delegate commodity breadth**: table formatting, document construction, and rendering may use `python-hwpx` or optional extras; do not reimplement mature substrate behavior unless the substrate is missing or unsafe.
4. **Validation gate remains mandatory**: every generated/edited HWPX must pass `validate_hwpx`; every optional dependency failure must return structured `available:false` or `ok:false`.
5. **Real surfaces only**: PNG preview must render through an actual browser/screenshot path; `.hwp` headless reading must use a real `.hwp` fixture and non-COM path.

### Decision drivers

1. User value: remove the biggest gap between “core form fill” and “full HWP/HWPX document tool.”
2. Risk containment: isolate optional dependency and rendering risks behind narrow tools.
3. Implementation leverage: use `python-hwpx 2.24.0` capabilities already installed (`merge_table_cells`, `ensure_border_fill`, `set_paragraph_format`, `export_rich_markdown`) where possible.

### Viable options

#### Option A — One large “complete all gaps” pass

Pros:

- Single milestone narrative.
- Can update docs once.

Cons:

- High risk of blocked `.hwp` headless reading delaying smaller shippable wins.
- Harder to review and debug.

Verdict: rejected for execution. Too much dependency uncertainty.

#### Option B — Staged implementation lanes with dependency gates

Pros:

- Table/block/markdown work can ship while `.hwp` headless and PNG rendering are spiked.
- Each lane has concrete tests.
- Matches existing optional-extra pattern.

Cons:

- Requires careful docs so “partial” lanes are not overstated.

Verdict: chosen.

#### Option C — Only update docs, defer implementation

Pros:

- Safest and fastest.

Cons:

- Does not satisfy the goal of implementing missing functionality.

Verdict: rejected.

## 3. ADR

### Decision

Implement the missing optional extensions as five staged lanes:

1. table editing extension
2. block document builder
3. markdown-to-blocks import
4. PNG render preview
5. headless `.hwp` reading spike and implementation gate

### Drivers

- `python-hwpx` already provides enough substrate for table merge and formatting-adjacent work.
- `create_document_from_blocks` is the cleanest escape hatch for DECISIONS D6: fixed recipe chrome can remain, but users who need total control can supply every block explicitly.
- `render_preview` is required before form-fit can be visually validated.
- `.hwp` headless reading currently has no installed substrate, so it must be treated as a gated lane, not assumed implementation.

### Alternatives considered

- Continue extending `create_official_document` recipes only: rejected because it keeps adding server-side chrome exceptions.
- Make markdown import fully CommonMark-compliant immediately: rejected as too broad; use a predictable supported subset first.
- Use COM for `.hwp` reading and call it headless: rejected because current requirement is specifically headless/non-COM.

### Consequences

- New optional extras may be needed, likely `render` and `hwp-headless`.
- Some lanes will be implemented as `available:false` until dependencies are installed or chosen.
- Documentation must distinguish “implemented,” “partial,” and “dependency-gated.”

### Follow-ups

- After implementation, update `docs/prd.json` with new stories, likely US-038 onward.
- Update README status so Phase C/D no longer sounds broader than it is.
- Consider a future “document operations matrix” listing tool support by `.hwpx`, `.hwp via COM`, `.hwp headless`.

## 4. Work plan

### Milestone 0 — PRD and dependency spike

Deliverables:

- Add new PRD stories for the unfinished extensions:
  - US-038 table merge and cell shading
  - US-039 `create_document_from_blocks`
  - US-040 structure-preserving markdown import
  - US-041 `render_preview` PNG
  - US-042 `.hwp` headless text extraction
- Record dependency findings:
  - `python-hwpx 2.24.0` methods available.
  - no local `pyhwp/hwp5/rhwp/kordoc`.
- Decide optional extras names:
  - `render` for Playwright/browser screenshot support.
  - `hwp-headless` for whichever `.hwp` reader is selected after spike.

Acceptance:

- `docs/prd.json` contains concrete acceptance criteria for every new story.
- `README.md` and `docs/ROADMAP.md` still mark unimplemented lanes as pending until code lands.
- No runtime code changes yet except optional metadata if needed.

Verification:

- `python -m json.tool docs/prd.json`
- `git diff --check`

### Milestone 1 — Existing-table merge and cell shading

Scope:

- Add delegate functions in `hangeul_core/delegate.py`:
  - `merge_table_cells(path, table_index, cell_range, out_path)`
  - `set_cell_shading(path, table_index, row, col, fill_color, out_path)`
- Add MCP tools in `hangeul_mcp/server.py` with structured errors:
  - `merge_table_cells`
  - `set_cell_shading`
- Use `python-hwpx` public API where possible:
  - `HwpxDocument.merge_table_cells(table, "A1:C1")`
  - `HwpxDocument.ensure_border_fill(fill_color=...)`
- If cell shading cannot be applied cleanly through public API, implement the smallest adapter over the python-hwpx oxml table/cell object, not a broad raw XML rewriter.

Acceptance:

- Merge works on an existing table in a fixture and output validates.
- Shading changes the target cell fill/borderFill reference and output validates.
- Wrong table index, invalid range, and invalid color return structured `ok:false`.
- Existing text and non-target cells remain present.

Tests:

- `tests/test_delegate_table_ops.py`
  - merge `A1:B1` on a generated/fixture table.
  - shade cell `(0, 0)` with `#FFF2CC`.
  - invalid `cell_range` returns structured error through server tool.
  - `validate_hwpx(out)["valid"] is True`.

Manual QA:

- Generate a sample HWPX with table ops.
- Reopen with `python-hwpx` and inspect table map / borderFill reference.
- If feasible on Windows desktop, open the output in Hangul manually in a later live QA pass; do not require that for CI.

### Milestone 2 — `create_document_from_blocks`

Scope:

- Add `hangeul_core/blocks.py`.
- Define a deterministic block schema:
  - `{"type": "heading", "level": 1..6, "text": "..."}`
  - `{"type": "paragraph", "text": "..."}`
  - `{"type": "bullet_list", "items": ["..."]}`
  - `{"type": "numbered_list", "items": ["..."]}`
  - `{"type": "table", "rows": [[...], ...]}`
  - `{"type": "image", "image_path": "...", "width_mm": optional, "height_mm": optional}`
  - `{"type": "page_break"}`
- Add delegate/builder function:
  - `create_document_from_blocks(blocks, out_path)`
- Add MCP tool:
  - `create_document_from_blocks(blocks, out_path)`

Design constraints:

- No server-generated prose.
- No fallback to 공문/보도자료 labels.
- Unknown block type returns structured error.
- Keep schema small; do not create a full layout DSL in this pass.

Acceptance:

- Blocks create a valid HWPX preserving block order.
- Heading level maps to paragraph formatting or a deterministic style marker.
- Lists create list-like paragraphs, not literal markdown markers when substrate supports it.
- Table block creates table with data.
- Image block uses existing `add_image` substrate or shared helper.

Tests:

- `tests/test_blocks.py`
  - paragraph + heading + list + table order.
  - invalid block type.
  - empty blocks rejected.
  - output validates.
- Extend `tests/test_client_stdio.py` or server tests to confirm MCP tool listing/call shape.

Manual QA:

- Create a small “lesson plan” style document from blocks and extract text/order with existing read tools.

### Milestone 3 — Structure-preserving markdown → HWPX

Scope:

- Add `hangeul_core/markdown.py` or a parser function near `blocks.py`.
- Implement a supported markdown subset by converting markdown to blocks, then calling `create_document_from_blocks`.
- Update existing `create_hwpx_from_markdown(markdown, out_path)` to use the block builder while keeping the same public signature.

Supported subset for this pass:

- ATX headings `#` through `######`
- paragraphs
- blank-line separation
- unordered lists `-`, `*`
- ordered lists `1.`
- pipe tables
- optional simple inline emphasis if cheap through `ensure_run_style`; otherwise document as not supported yet

Non-goals:

- Full CommonMark compliance.
- Nested lists.
- Complex inline HTML.

Acceptance:

- Headings are not flattened into plain paragraphs.
- Lists are not stored as literal `- item` text when list formatting is available.
- Pipe tables become HWPX tables.
- Existing simple markdown tests continue to pass.
- README accurately says “supported subset,” not full markdown.

Tests:

- `tests/test_markdown_structure.py`
  - heading/list/table fixture.
  - existing marker-stripping behavior replaced by structure checks.
  - invalid/empty markdown behavior defined.

Manual QA:

- Create a HWPX from a small markdown document and verify with `get_document_outline`, `extract_text`, and `validate_hwpx`.

### Milestone 4 — `render_preview` PNG

Scope:

- Add optional render module:
  - `hangeul_core/render.py`
- Add MCP tool:
  - `render_preview(path, out_path, format="png", width=1280, height=1800)`
- Use existing `hwpx_to_html` / `python-hwpx.export_html` as the HTML source.
- For PNG, render HTML via Playwright or another browser backend.
- Because Playwright cannot reliably render local files via `file://` in this environment, use a temporary local HTTP server and navigate to `http://127.0.0.1:<port>/...`.

Dependency behavior:

- If Playwright/browser is unavailable, return:
  - `available:false`
  - clear install/setup hint
  - no partial PNG file
- Add optional extra `render` if dependency is added to `pyproject.toml`.

Acceptance:

- `render_preview(sample_form.hwpx, out.png)` creates a non-empty PNG.
- Output dimensions are reported.
- HTML source is preserved optionally for debugging only if requested.
- Errors from browser startup or screenshot are structured.

Tests:

- Unit test dependency-missing behavior by monkeypatching import.
- Integration test can be marked/skip if Playwright browser is unavailable.
- At least one local run must produce a PNG and verify file signature / dimensions.

Manual QA:

- Open the generated PNG or inspect with an image library.
- Use the PNG to visually confirm a filled sample form.

### Milestone 5 — `.hwp` headless reading

Scope:

- Run a dependency spike before writing production code:
  - evaluate `rhwp`, `pyhwp/hwp5`, `kordoc`, or another Windows-compatible headless reader.
  - verify license, installability, Python integration or CLI shape.
- Add optional extra or adapter only after one substrate can extract text from a real `.hwp` fixture without COM.
- Add module:
  - `hangeul_core/hwp_headless.py`
- Extend `extract_text` / `detect_format` handling, or add explicit tool:
  - `extract_hwp_text(path)`

Acceptance if substrate is viable:

- A PII-free `.hwp` fixture extracts text without COM and without launching Hangul.
- The server returns structured `available:false` when the optional reader is absent.
- `.hwpx` behavior is unchanged.
- COM conversion remains available but is not mislabeled as headless reading.

Acceptance if no substrate is viable in this environment:

- Add a documented spike result and keep the tool unavailable with a precise reason.
- Do not mark `.hwp` headless reading complete.

Tests:

- `tests/test_hwp_headless.py`
  - dependency missing path.
  - real extraction path if fixture and substrate are present.
- Keep existing `tests/test_convert.py` for COM conversion policy.

Manual QA:

- Run extraction on a real PII-free `.hwp`.
- Confirm no Hangul COM process is launched.

### Milestone 6 — Documentation and status correction

Scope:

- Update `README.md`.
- Update `docs/ROADMAP.md`.
- Update `docs/prd.json`.
- If needed, add `docs/DECISIONS.md` entry:
  - block schema is the “complete-control” path for D6.
  - render preview is optional and not a layout guarantee unless browser render succeeds.
  - `.hwp` headless support is dependency-gated.

Acceptance:

- README no longer implies optional extensions are done before they are.
- Every new tool has a short usage description and dependency note.
- ROADMAP distinguishes completed, partial, deferred, and dependency-gated items.

Verification:

- `python -m json.tool docs/prd.json`
- `python -m pytest -q`
- `python -m pyflakes hangeul_core hangeul_mcp tests`
- Stdio MCP client test confirms new tools list correctly.

## 5. Suggested execution order

1. Milestone 0: PRD/dependency spike.
2. Milestone 1: table merge/shading.
3. Milestone 2: `create_document_from_blocks`.
4. Milestone 3: structure-preserving markdown via blocks.
5. Milestone 4: render preview PNG.
6. Milestone 5: `.hwp` headless spike/implementation.
7. Milestone 6: docs/status correction and full verification.

Rationale: table and block/markdown lanes are most directly enabled by current dependencies. PNG render is valuable but has browser setup risk. `.hwp` headless reading has the largest unknown and must be gated.

## 6. Verification path

Minimum completion gate for each code milestone:

```powershell
& 'E:\github\Hangeul-mcp\.venv\Scripts\python.exe' -m pytest -q
& 'E:\github\Hangeul-mcp\.venv\Scripts\python.exe' -m pyflakes hangeul_core hangeul_mcp tests
```

Additional gates:

- For HWPX edit/generation tools: call the MCP server function directly and run `validate_hwpx`.
- For stdio surface: extend existing MCP stdio client test to list and call at least one new tool.
- For PNG: generate an actual PNG and verify signature, dimensions, and visual openability.
- For `.hwp` headless: use a real PII-free `.hwp` fixture; fake placeholder bytes do not count.

## 7. Risk register

### Risk 1 — cell shading public API gap

`python-hwpx` has `ensure_border_fill`, but applying it to an existing cell may need oxml work.

Mitigation:

- First spike one cell in a test fixture.
- If public API is insufficient, write a narrow adapter for cell `borderFillIDRef` only.

### Risk 2 — markdown scope creep

Full markdown support can balloon.

Mitigation:

- Implement a supported subset and document it.
- Route markdown through `create_document_from_blocks` so future expansion is incremental.

### Risk 3 — Playwright/browser availability

CI or user environment may not have browser binaries.

Mitigation:

- Optional dependency.
- Structured `available:false`.
- Integration test skips when browser unavailable, but one local/manual PNG proof is required before claiming done.

### Risk 4 — `.hwp` headless substrate unavailable or poor quality

No headless reader is installed now.

Mitigation:

- Treat as a spike with explicit go/no-go.
- Do not fake completion via COM conversion.

### Risk 5 — D6 brain/hand violation

More document generation can accidentally create content.

Mitigation:

- `create_document_from_blocks` is content-explicit.
- Recipes remain documented layout chrome only.
- Tests assert supplied text appears; no hidden body prose is inserted.

## 8. Agent roster and staffing guidance

Available agent types observed in this session:

- `plan`: strategic plan writer
- `metis`: pre-planning analyst
- `momus`: plan reviewer
- `explorer`: read-only codebase search
- `worker`: implementation worker
- `lazycodex-code-reviewer`: read-only code review
- `lazycodex-qa-executor`: manual QA executor
- `lazycodex-gate-reviewer`: final gate reviewer

### `$ralph` path

Use `$ralph` if one persistent executor should implement the plan sequentially.

Suggested prompt:

```text
$ralph E:/github/Hangeul-mcp/.omo/plans/hangeul-mcp-unfinished-extensions.md 계획대로 구현하라. Milestone 0부터 순서대로 진행하고, 각 milestone마다 테스트와 실제 MCP/tool surface 검증 증거를 남겨라. .hwp headless reading은 실제 비COM fixture 없이는 완료로 표시하지 말라.
```

Recommended reasoning: high.

### `$team` path

Use `$team` if parallelizing after Milestone 0.

Suggested lanes:

- Worker A: table merge/shading, owned files `hangeul_core/delegate.py`, `hangeul_mcp/server.py`, `tests/test_delegate_table_ops.py`.
- Worker B: block builder and markdown importer, owned files `hangeul_core/blocks.py`, `hangeul_core/markdown.py`, related tests.
- Worker C: render preview, owned files `hangeul_core/render.py`, render tests, optional dependency docs.
- Worker D: `.hwp` headless spike, owned files `hangeul_core/hwp_headless.py`, spike notes/tests.
- QA lane: stdio MCP and artifact verification after integration.

Team warning:

- Workers must not edit each other's files without coordination.
- Docs should be integrated after code lanes stabilize.

Recommended reasoning:

- Worker A/B: high
- Worker C/D: high because dependency and environment risk
- QA/review: xhigh

Suggested team launch:

```text
$team --plan E:/github/Hangeul-mcp/.omo/plans/hangeul-mcp-unfinished-extensions.md --lanes table,blocks-markdown,render,hwp-headless,qa
```

### Goal-mode follow-up suggestions

- `$ultragoal`: best default if this should become a tracked durable implementation goal.
- `$ultragoal` + `$team`: best if the user wants parallel execution with a central ledger.
- `$autoresearch-goal`: use only for the `.hwp` headless reader substrate research if implementation is blocked by library uncertainty.
- `$performance-goal`: not the right primary mode unless render speed or large-document throughput becomes the main objective.

## 9. Stop rules

Do not declare completion if any of these are true:

- New tools are documented but not exposed by `hangeul_mcp/server.py`.
- HWPX outputs are generated but not validated.
- PNG preview creates HTML only, not a PNG.
- `.hwp` reading silently uses COM conversion but is described as headless.
- Markdown import flattens headings/lists/tables while docs claim structure preservation.
- Tests pass only by skipping all optional dependency paths without at least one local/manual proof for the implemented optional feature.

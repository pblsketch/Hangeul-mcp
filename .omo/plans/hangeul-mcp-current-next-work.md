# RALPLAN — Hangeul-mcp current state and next work

Status: consensus-style planning handoff, not implementation.

Repository: `E:/github/Hangeul-mcp`

Remote: `https://github.com/pblsketch/Hangeul-mcp.git`

Context snapshot: `.omx/context/hangeul-mcp-current-next-work-20260709T122128Z.md`

## 1. Current verified baseline

### Evidence checked in this planning pass

- Worktree: clean.
- Branch/remote: local `master` is aligned with `origin/master`; remote master SHA is `df2f5a9aa91128531f67db502ce4abb11c9c6432`.
- Current HEAD: `df2f5a9 feat(harness): add BYO-AI live workflow and maintenance gates`.
- Tests: `189 passed, 1 skipped in 33.92s`.
- Lint: pyflakes clean.
- JSON/docs hygiene: `docs/prd.json` parses; `git diff --check` passes.
- Runtime MCP tool list: 35 tools.

### Grounded project summary

Hangeul-mcp is currently a local Python MCP server for HWP/HWPX work. Its core value is high-precision HWPX form understanding and byte-preserving form fill. It also exposes delegated editing/generation/rendering tools and first-round BYO-AI/live harness tools. It should be described as a BYO-AI local Hangul document engine, not as an AI model/API product.

### What is done enough to build on

- Headless HWPX analyze/fill core.
- Phase A form recognition/fill deepening.
- Phase B self-core reliability/read/validate/PII/formfit/render adapter paths.
- First-round Phase C/D delegated edit/generate breadth.
- First-round BYO-AI capability/workflow/live-preview/no-API guard.

### What must not be overclaimed

- Live COM still needs real desktop evidence.
- `.hwp` headless reading is still substrate-gated, not real extraction.
- `render_preview` is optional dependency based and should have artifact evidence for product QA.
- General editing breadth remains partial compared with large reference servers.

## 2. RALPLAN-DR summary

### Principles

1. **Evidence before status labels**: mark a capability complete only when code path, tests, and observable artifact or runtime output exist.
2. **BYO-AI boundary**: the server never generates prose through LLM APIs; the user's AI client generates content and Hangeul-mcp executes local document operations.
3. **File/live separation**: HWPX file mode stays stable and cross-platform; live Hangul mode remains optional and desktop-gated.
4. **Own the differentiator, delegate breadth**: form understanding/fill stays OWN; commodity edit/generate/render can be delegated with validation gates.
5. **Safety-first document operations**: preview, dry-run, backup, validate, render, and verify should be the default product flow.

### Decision drivers

1. Avoid misleading progress claims in a fast-moving project with stale historical docs.
2. Turn the current 35-tool implementation into a reliable product workflow, not only a tool collection.
3. Close the highest-risk gaps: live verification, `.hwp` headless substrate, render artifacts, and missing safety/maintenance operations.

### Viable options

#### Option A — Continue feature breadth immediately

Pros:
- More visible tools quickly.
- Matches broad reference MCP servers by tool count.

Cons:
- Increases risk of shallow or unverified features.
- Does not resolve live/headless/render status uncertainty.

Verdict: rejected for the next immediate pass.

#### Option B — Stabilize product truth and QA gates first, then add next breadth

Pros:
- Aligns docs, runtime, tests, and product promise.
- Makes future `/ralph` or `$team` execution safer.
- Reduces overclaiming risk around live COM and `.hwp`.

Cons:
- Slower visible feature count growth.

Verdict: chosen.

#### Option C — Focus only on live COM desktop validation

Pros:
- Resolves a major market-facing uncertainty.

Cons:
- Requires a suitable Windows + Hancom manual QA setup.
- Leaves docs/status/gap matrix stale.

Verdict: useful as a dedicated lane, not the only next plan.

## 3. ADR

### Decision

The next phase should be a stabilization and product-readiness phase:

1. make project status truthfully machine-checkable;
2. add artifact-backed QA for render/file workflows;
3. isolate and verify live desktop behavior;
4. decide `.hwp` headless substrate through a spike before claiming support;
5. then implement the next missing document-operation breadth.

### Drivers

- Current repo is green and broad enough to require quality gates rather than more unbounded expansion.
- Existing docs include stale historical counts and older handoff assumptions.
- Live COM and `.hwp` headless claims have higher reputational risk than ordinary HWPX delegated tools.

### Alternatives considered

- Tool-count parity sprint: deferred because it may produce shallow coverage.
- Live-only sprint: deferred unless the immediate user goal is public demo or field deployment.
- Documentation-only cleanup: insufficient because runtime/artifact QA is needed.

### Consequences

- The next implementation should include docs/status matrix changes and real e2e artifacts.
- Live desktop QA may remain pending if the required machine state is unavailable; if so, label it explicitly.
- `.hwp` headless remains adapter-gated until a substrate and fixture are proven.

## 4. Work plan

### Milestone 0 — Freeze the current baseline

Goal: create a trustworthy “as of now” baseline.

Tasks:

1. Update `HANDOFF.md` or replace it with a current handoff section so it no longer says 56 tests / old Phase A-D target as if current.
2. Add or update a status matrix in `README.md` or `docs/ROADMAP.md`:
   - implemented
   - optional dependency gated
   - desktop-live pending
   - research/spike pending
3. Ensure `docs/prd.json` has explicit status fields or another machine-readable status source; currently stories exist but do not expose `status`/`done` fields.

Acceptance:

- A new agent can read one file and know current status without relying on stale historical notes.
- The status matrix distinguishes `complete`, `partial`, `available:false gate`, and `desktop QA pending`.

Verification:

```powershell
Set-Location E:/github/Hangeul-mcp
./.venv/Scripts/python.exe -m json.tool docs/prd.json > $null
git diff --check
```

Manual QA:

- Read the top README status and compare it against runtime `mcp.list_tools()` output.

### Milestone 1 — Product workflow evidence pack

Goal: prove the BYO-AI file-mode workflow with real local artifacts.

Tasks:

1. Create a repeatable e2e driver or documented command sequence for:
   - `describe_capabilities`
   - `analyze_form`
   - `scan_pii`
   - `fill_form(dry_run=True)`
   - `fill_form(...)`
   - `verify_fill`
   - `validate_hwpx`
   - `render_preview` if render dependency is available
2. Store evidence under a clearly ignored/generated evidence path, or document how to regenerate it.
3. If Playwright/browser is unavailable, record `available:false` as the observed result and keep PNG artifact generation as an environment-specific QA step.

Acceptance:

- At least one HWPX fixture goes through analyze -> fill -> verify -> validate.
- If PNG render is available, a non-empty PNG is produced and inspected by file signature/dimensions.
- If PNG render is unavailable, the structured unavailable result is captured and not called a pass for visual rendering.

Verification:

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_client_stdio.py tests/test_render_preview.py -q
./.venv/Scripts/python.exe -m pytest -q
```

Manual QA:

- Open or inspect the generated preview PNG when available.

### Milestone 2 — Live desktop QA lane

Goal: turn live COM from code-complete into evidence-backed or explicitly pending.

Tasks:

1. Prepare a PII-free `.hwpx` live test fixture and a simple values mapping.
2. On Windows with Hancom installed and a document open, run:
   - `hwp_status`
   - `preview_cells_to_open_hwp`
   - `apply_to_open_hwp` or `apply_cells_to_open_hwp`
3. Capture the concrete output:
   - status result
   - preview target count
   - applied/skipped count
   - any COM error text
4. If desktop conditions are unavailable, add a `PENDING_DESKTOP_LIVE_QA.md` or status entry rather than marking live complete.

Acceptance:

- Live apply has real desktop evidence, or it is explicitly labeled pending.
- `hwp_status` remains side-effect-free and does not launch Hangul.
- Headless tests still pass when live dependencies are absent.

Verification:

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_com.py tests/test_live_resolve.py -q
```

Desktop-only verification:

```powershell
set HANGEUL_MCP_LIVE=1
./.venv/Scripts/python.exe -m pytest tests/test_com.py tests/test_live_resolve.py -q
```

### Milestone 3 — `.hwp` headless substrate decision

Goal: stop treating `.hwp` headless reading as an implementation detail that can be guessed later.

Tasks:

1. Compare candidate non-COM readers:
   - `rhwp`
   - `pyhwp` / `hwp5`
   - `kordoc`
   - other practical Windows-compatible options
2. Record license, installability, CLI/API shape, and test fixture requirements.
3. Add one PII-free `.hwp` fixture only if license/source is safe.
4. Implement real extraction only after a candidate extracts text from that fixture without COM.

Acceptance:

- If no candidate is proven, current `extract_hwp_text` remains an adapter gate and docs say so.
- If a candidate is proven, add a real non-COM test that fails without the substrate and passes with it.

Verification:

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_hwp_headless.py -q
```

Manual QA:

- Run extraction on the PII-free `.hwp` fixture and compare expected text.

### Milestone 4 — Safety and maintenance operations

Goal: close practical document-operation risks before more feature breadth.

Candidate tasks:

1. `copy_document` or standard safe-output helper for tools that modify documents.
2. Transaction/evidence conventions for out_path, backup, validate, verify.
3. Repair strategy:
   - only if a delegated substrate can repair a real broken fixture
   - otherwise document as unsupported.
4. Change tracking/undo:
   - implement only if a reliable substrate path exists
   - do not simulate undo with unsafe hidden state.

Acceptance:

- Any mutating tool has clear output/backup behavior.
- Repair/undo are not claimed until proven by fixtures.

Verification:

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_dryrun_backup.py tests/test_validate.py -q
```

### Milestone 5 — Next breadth after stabilization

Goal: add the next missing HWPX document operations in priority order.

Recommended order:

1. Table row/column add/remove and split cells.
2. Table compute for sums/averages if it can be defined deterministically.
3. Header/footer and page setup.
4. TOC generation.
5. Broader style operations.

Acceptance pattern for every new operation:

- MCP tool exposed.
- Optional dependency behavior is structured.
- Output validates.
- A fixture demonstrates the operation.
- Docs state exact scope and non-goals.

Verification:

```powershell
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests
```

## 5. Recommended execution paths

### `/ralph` path

Use when one agent should sequentially harden the project:

```text
/ralph E:/github/Hangeul-mcp/.omo/plans/hangeul-mcp-current-next-work.md 계획대로 Milestone 0부터 구현해줘. 완료 선언 전에 테스트, pyflakes, json.tool, diff --check, MCP tool listing, 그리고 가능한 e2e artifact QA까지 증거를 남겨줘.
```

### `$team` path

Use when parallel work is desired:

- Lane A: docs/status/PRD/handoff truth cleanup.
- Lane B: file-mode e2e evidence and render artifact QA.
- Lane C: live desktop QA preparation and gated evidence.
- Lane D: `.hwp` headless substrate research.
- Lane E: safety/maintenance operation design.

Team integration gate:

```powershell
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests
./.venv/Scripts/python.exe -m json.tool docs/prd.json > $null
git diff --check
```

### Goal-mode follow-up

- Default: `$ultragoal` for durable product-readiness tracking.
- Use `$autoresearch-goal` for the `.hwp` headless substrate decision.
- Use `$performance-goal` only if parse/render/live latency becomes the main task.

## 6. Stop rules

- Do not say live is complete without desktop evidence.
- Do not say `.hwp` headless reading is complete without a non-COM fixture pass.
- Do not add server-side LLM/API SDKs.
- Do not weaken byte-preserving fill tests.
- Do not mark render visual QA complete unless a PNG artifact exists or the unavailable state is explicitly recorded.
- Do not leave historical docs contradicting the current README/runtime baseline.


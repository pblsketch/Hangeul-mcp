# Ralph Implementation Brief — Addressed Editing, Occurrence Safety, and Runtime Reliability

## Goal
Implement the concrete P0/P1 gaps discovered from the real Claude Desktop lesson-plan and meeting-minutes transcripts. Work in this isolated branch only. Strict TDD, real execution, no fabricated Windows evidence.

## User outcomes
1. An existing original HWPX lesson-plan template can be completed without requiring `{}` fields.
2. Repeated markers such as `▶`, `○○○`, `-`, repeated labels, and repeated named fields can receive different values at different structural targets.
3. The original template structure/style is preserved as far as the selected substrate guarantees; no unnecessary full-document recreation.
4. Claude must not claim “impossible” before exhausting structural targets.
5. A four-minute COM hang must not make the whole stdio server unresponsive.

## Source evidence
- Product conversation findings in current chat.
- Full audits:
  - `/home/wnsdl/.hermes/cache/delegation/subagent-summary-0-20260713_150038_973724.txt`
  - `/home/wnsdl/.hermes/cache/delegation/subagent-summary-1-20260713_150038_987614.txt`
- Current repo docs/evidence and `PENDING_DESKTOP_LIVE_QA.md`.
- Current master must be inspected live; observed baseline around commit `d6b187e`, 51 tools, full extras suite 428 passed/1 skipped in leader environment. Re-measure.

## Existing foundations to reuse
- `analyze()` and `Cell.field_id` expose raw `tN.rR.cC` addresses.
- `get_table_map()` exposes all analyzed cells.
- `fill.py` has XML cell location and text-writing primitives.
- `body.py` supports `bN` top-level body slots, but addresses are transient.
- `find_text()` exposes some cell occurrences but not stable editable occurrence selectors.
- `EditPlan`/`EditSession` provide source SHA, preview/apply, snapshot/journal/restore for literal replacement.
- current-document flow provides exact candidate, one-use preview token, TTL, revalidation.
- live cell executor has table navigation but currently resolves only understood form fields.

## Required implementation slices

### Slice A — Structural target model and read APIs
Add a typed/common target identity, likely in a new focused module. Support at minimum:
- raw table cell: `tN.rR.cC`
- body paragraph compatibility alias `bN`
- section paragraph transient address such as `sN.pM`
- cell paragraph and occurrence IDs where parsable, e.g. `tN.rR.cC.pP.occK`

Addresses are valid only with source SHA/context digest. Do not claim permanent IDs.

Add or enhance MCP tools:
- `inspect_editable_regions(path)` (or equivalent clear name)
- `get_paragraph_map(path)` if not folded into inspect
- include editable/unsupported reason, container, section, table/row/col/span, paragraph ordinal/ID, text/snippet, occurrence candidates, source SHA.

Do not expose text boxes/special controls as editable unless proven. Return `unsupported_control` metadata.

### Slice B — Addressed preview/apply/restore
Add:
- `preview_addressed_edits(path, edits)`
- apply via existing `apply_edit_session(session_id, out_path)` if contract can be safely extended, otherwise `apply_addressed_edits(preview_token, out_path)`
- existing `restore_edit_session` must work for file-mode addressed edits.

Edit item contract:
```json
{
  "target": "t3.r2.c4",
  "kind": "cell",
  "operation": "replace_text",
  "value": "...",
  "expected_text": "▶"
}
```
Also support paragraph target and marker-tail preservation when proven. Explicit operations only (`replace_text`, optionally `append_text`, `preserve_marker_replace_tail`). Never silently append to non-empty raw cells.

Preview must include before/after, risk, source SHA, context digest, target metadata, changed entries. Apply must reject changed source/context, duplicate target edits, stale/missing/out-of-range target, unsupported nested live target. Preserve untouched ZIP entry payloads under own substrate where current architecture guarantees it.

### Slice C — Occurrence-aware search/edit
Enhance `find_text` or add `find_text_occurrences` to return occurrence IDs with section, container, paragraph/cell target, ordinal, snippet, source SHA/context digest.

Add selected occurrence preview/edit. Keep intentional global replace, but make ambiguous global replacement fail closed by default:
- 2+ matches require explicit `scope="all"` or an authoritative global preview token.
- one-shot `search_and_replace` must not silently replace all repeated markers by default. Preserve backward compatibility through explicit scope/deprecation strategy and tests.
- repeated slots may each receive different values; edit payload must be a list, not only `{find: replace}` mapping.

### Slice D — Duplicate label and repeated named-field safety
- Label-only resolution with multiple candidates must return `ambiguous_label`, all candidate `field_id`s/locations/snippets, and perform no write.
- Unique labels stay backward-compatible.
- Add repeated named-field occurrence selectors if Hancom API behavior can be proven. If not, return a structured unsupported/needs-selection result; do not fake per-occurrence control.

### Slice E — Completion analysis and result contract
Extend `analyze_form` or add `plan_template_completion` to report:
- all addressable regions
- directly fillable fields
- raw structural cell/paragraph targets
- repeated text candidates
- ambiguous labels
- unsupported controls
- coverage statistics
- recommended next workflow/tool

Standardize operation state/counts:
- `complete`, `partial`, `no_op`, `failed`, `stale_preview`, `ambiguous_target`
- requested/resolved/applied/verified/skipped/unresolved counts
- coverage ratio
- `user_attention_required`
- per-target unresolved reason and suggested tool.

Do not break existing return fields silently; additive fields or explicit versioning/deprecation.

### Slice F — Exact location verification
Add `verify_targets(path, expected_targets)` and live equivalent only where fresh read-back is actually proven.
- verify target A, not document-global presence
- report expected/actual/location/verified
- detect unexpected duplicates when relevant
- live apply must not claim complete before read-back.

### Slice G — Runtime/process observability
Add to `describe_capabilities()` and `hwp_status()`:
- package version/build identifier if available
- `server_instance_id`, pid, started_at
- tool schema version
- session scope (`this stdio process`), survives_restart false
- feature flags for body paragraph, raw cell editing, occurrence editing, live addressed editing
- attach ladder: window_detected (if implemented safely), rot_visible, com_object_acquired, document_identity_proven; do not conflate these.

Token/session IDs must identify server instance or return `wrong_server_instance` distinctly from expired/stale/already-used. Multiple MCP processes may be normal; do not impose a global singleton. Doctor should detect duplicate registration surfaces where feasible.

### Slice H — Timeout/cancellation
The transcript had a >4-minute call followed by hwp_status failure. Protect stdio responsiveness.
- bounded `timeout_seconds` for COM/open/apply operations
- use a separate worker process where required; do not pretend Python thread cancellation is safe for COM
- timeout result: `timeout_outcome_unknown`, `may_have_partially_applied:true`, no automatic retry, recommend read-back/new preview
- document single-writer-per-document behavior
- timeout/cancellation tests with a hanging fake worker
- after timeout, `hwp_status`/another simple call must still respond
- atomic promote for file outputs

If full live worker isolation is too large for one slice, deliver a tested bounded worker abstraction and wire at least one safe path, while marking remaining live paths pending. Do not overclaim.

## Tool guidance/skill docs
Update tool descriptions and skills:
- `{}` is not required.
- Never say arbitrary text is impossible solely because it is not a named field.
- Escalation: named/form field → label/empty cell → inline/body → raw structural address → occurrence selection → unsupported/new-file fallback.
- Do not use global search/replace to assign different values to repeated slots.
- New-file recreation is last resort.

## E2E fixtures and acceptance
Use or add PII-free copies/fixtures representing:

### Lesson plan
- fill 18 label/empty-cell headers
- title, period plan, two objectives
- distinct activity rows with repeated `▶`
- guidance notes
- repeated “자료” locations with distinct values if selector support is proven
- verify each target address and zero unintended targets

Source candidate exists at `tests/hwpx template/14_교수학습 지도안 양식.hwpx`; inspect path live and avoid mutating tracked fixture.

### Meeting minutes
- separate meeting-content items and decision items despite repeated `○○○`
- distinct values at distinct addresses
- preserve table/merge/border structure
- zero unintended replacements

Locate a suitable existing fixture or add a minimal PII-free regression fixture legally within repo.

## Safety / compatibility
- Strict TDD RED→GREEN.
- Preserve existing 51 tool contracts unless deprecation is explicit and tested.
- Exact-path and current-document fail-closed behavior must not weaken.
- Nested table live address mapping stays unsupported until real evidence.
- File substrate and live substrate remain separate; no false atomicity.
- No raw secrets/PII in logs/evidence.
- No product source changes outside isolated worktree until review.

## Verification
- focused tests for each slice
- full extras suite
- pyflakes
- docs/prd and evidence JSON parse
- runtime MCP discovery and exact tool count
- CLI/stdio smoke
- git diff --check
- Windows tests only when actually available; fake-COM is not desktop proof
- Architect + Critic independent review; fix blockers
- logical commits on branch

## Delivery
Implement via Ralph iterative loop until all feasible goals and quality gates are complete. If Windows/Hangul human evidence blocks a claim, commit the safe implementation/scaffold and report the exact pending gate. Do not merge canonical automatically.

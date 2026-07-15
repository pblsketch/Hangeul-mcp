# Plan (FINAL — pending approval) — Formatting & structure ops for addressed/live editing
Consensus: Planner → Architect → Critic (ITERATE) → revised. Incorporates all 10 critic required changes, 5 acceptance-criteria rewrites, and DR deliverables.

## Problem (evidence-grounded)
Filling a 6-slot 형성평가 template with 20 questions produced broken output. Root causes traced in XML + code:
- **Bold jumbled** — `_replace_text_nodes` ([addressed.py:88](hangeul_core/addressed.py#L88)) dumps the value into the first `<hp:t>` and empties the rest, inheriting whatever `charPrIDRef` was there. Appended Q7–Q20 (cloned from one non-bold base via `_multiline_paragraph_clones` :143) are 100% non-bold.
- **보기 box stranded** — the 보기 is a `<hp:tbl>` wrapped by `<hp:run charPrIDRef="15">`; the pipeline can only blank cell text, not remove the table. Empty box orphaned mid-Q4.
- **Spacing wrong** — no body-level insert-blank / delete-paragraph; spacers stranded; appended clones have zero separation.
- `AddressedEdit.operation` offers only `replace_text` / `preserve_marker_replace_tail`.

## Reference research (installed source)
- **python-hwpx 2.24.1** (offline XML, re-serializes only dirty parts): bold via `run.bold=True`→`ensure_run_style` find-or-create charPr + reassign `charPrIDRef` (`_document_impl.py:1885/1598/6241`); paragraphs `add_paragraph`/`insert_paragraphs(idx,[elem])`/`remove_paragraph`; **table row/col/delete: NONE**.
- **pyhwpx 1.7.2** (live COM): bold `CharShapeBold()`/`set_font(Bold=)`; paragraph `BreakPara`/`Delete`; table `TableAppendRow`/`TableSubtractRow`/`delete_ctrl` — live only.
- **Bottom line:** bold + paragraph ops solvable offline by copying python-hwpx's technique into our engine; **offline table-structure editing is the one true gap** neither lib covers.

## Constraints — D1 (own byte-preserving engine; libs are reference/validation only), D14 (python-hwpx 2.24 has no table-row API; revisit carefully with our own impl + tests), D7 (global vs section-local table-index reconciliation).

---

## RALPLAN-DR summary (revised)

**Principles**
1. **Byte-preservation at package-entry granularity** — every *untouched package entry* stays byte-identical; a bold edit makes `header.xml` a **touched entry** (append one `charPr` + bump `itemCnt`), and only the edited section/header change. (Restated per critic #1 — no longer claims run-local locality for bold.)
2. Own-engine core; python-hwpx/pyhwpx are reference implementations and optional test oracles, not the substrate.
3. **Fail-closed + XSD-gated** — any batch with bold/insert/delete/table ops must pass XSD validation before "complete"; ambiguous structural edits refuse rather than corrupt.
4. Verification covers formatting + structure, not just text.
5. Ship by ascending risk: header-lane → bold → paragraph → delete_table → (delete_row live-only).

**Decision drivers** — (1) D1 byte-preservation rules out re-serializing delegation on the hot path; (2) the unavoidable new code is offline table-structure editing; (3) formatting must be per-edit addressable (stem vs choice), applied per-clone.

**Viable options (evaluated per-capability, per critic/architect)**

| Capability | Option 1 (own engine) | Option 2 (python-hwpx delegate) | Option 3 (pyhwpx live) | Chosen |
|---|---|---|---|---|
| Bold | ensure_char_pr in header (byte-preserving) | borrow `ensure_run_style` for header only | `CharShapeBold` | **Own engine (offline) + live parity.** Narrow python-hwpx borrow considered but rejected: mixing its ET-serialized header entry into our string engine adds a serialization seam; our append is small and testable. |
| Paragraph | clone-and-splice `<hp:p>` | `insert_paragraphs`/`remove_paragraph` (re-serializes section → breaks D1) | `BreakPara`/`Delete` | **Own engine (offline) + live parity.** |
| delete_table | remove tbl-wrapping run (byte-preserving) | not supported | `delete_ctrl` | **Own engine.** |
| delete_row | offline grid recompute (hard, merge-corruption risk) | **not supported** | `TableSubtractRow` (Hangul recomputes merges/addr for free) | **Live-only this pass; offline deferred** (per critic #9 — this is the one place live wins outright). |

Global "own-engine for everything" is rejected as dishonest framing: delete_row's grid recompute is genuinely hard and merge-prone, so it ships live-only now.

**Pre-mortem (3 scenarios → mitigation)**
1. *XSD-invalid bold silently reported "complete."* A mis-ordered `<hh:bold/>` or un-bumped `itemCnt` produces a schema-invalid header, but text re-read passes → false success. → **Mitigation:** XSD gate in S1 (change #7); acceptance test asserts completion *refuses* on a deliberately mis-ordered `<hh:bold/>`.
2. *Body reindex drift corrupts later edits.* `body_index` precomputed from the original file; an insert/delete shifts every later `bN` in the same batch → wrong paragraphs edited. → **Mitigation:** body-aware bottom-up ordering by byte offset + post-op reindex (S3); test with a batch mixing inserts + a later `bN` edit.
3. *delete_row merge corruption.* Deleting a row spanned by a vertical merge leaves dangling `cellSpan`/`cellAddr`. → **Mitigation:** ship live-only (Hangul recomputes); offline deferred behind a dedicated grid model + merge-detection predicate + fail-closed.

**Expanded test-plan matrix**
| Layer | Coverage |
|---|---|
| unit | ensure_char_pr (itemCnt invariant, fixed bold-slot, find-or-reuse, byte-identity of other charPrs); bold anchor = run of first non-empty `<hp:t>`; per-clone bold in multiline; `<hp:p>` splice/delete offsets; body ordering+reindex; `tN`→table locator; delete_table caption guard |
| integration | header.xml flows preview→session→apply→journal; XSD gate refuses invalid batch; restore_edit_session round-trip with header entry |
| e2e | reproduce the 20-question 형성평가 fill; assert every stem bold, every 선지 non-bold, one blank between 문항 / none between 선지, no orphaned 보기 box, XSD-valid |
| observability | verify-report fields: stray-empty-bold-run count, stem/choice bold booleans, inter-문항 blank count, deleted-table delta, `xsd.valid` |

---

## Work plan (phased stories)

### S0 (pre-req) — header.xml session lane
Thread a `changed_header` (or generalize `changed_sections` → arbitrary package entries) through `preview_addressed_edits` → `_AddressedSession` → `apply_addressed_edits` → journal `changed_entries`. Today apply persists only `changed_sections` built from section reads ([addressed.py:1004-1005, 1048-1049](hangeul_core/addressed.py#L1004)); header never flows through.
- **Acceptance:** applying a bold edit makes `header.xml` appear in the session's `changed_entries`, persisted to `out_path` and recorded in the journal; a no-bold batch leaves header untouched (not in change set). Byte-diff: every non-header entry identical.
- **Tests (unit+integration):** header entry staged/persisted/journaled; restore_edit_session replays it.

### S1 — Offline bold via find-or-create charPr  (Capability A)
- `ensure_char_pr(header_xml, base_char_pr_id, *, bold) -> (header_xml', id)`: find an existing charPr identical to base except `<hh:bold/>` presence and **reuse** it; else clone base, insert/remove `<hh:bold/>` **at the fixed slot (after `<hh:offset>`, before `<hh:underline>`)**, allocate `max(id)+1`, append, and **increment `<hh:charProperties itemCnt>`**.
- Extend `AddressedEdit` with optional `bold: bool | None` (None = leave as-is).
- In apply, anchor on **the run owning the first non-empty `<hp:t>`** (not the first run — 2/8 fixture cells have multiple text-runs) and rewrite its `charPrIDRef`; drop leftover empty bold run shells. Apply the rewrite **inside `_multiline_paragraph_clones`** ([addressed.py:143-150](hangeul_core/addressed.py#L143)) so each clone (Q7–Q20) gets the bold id.
- **XSD gate (change #7, lands here):** `complete_addressed_template` runs `validate_hwpx` for any batch containing bold/structural ops and **fails closed** on `xsd.valid == False`. Reused by S3/S4.
- **Acceptance (machine-checkable):** edit `{target:b6, value:"1. …", bold:true}` → the surviving-text run's `charPrIDRef` points to a bold charPr; a 3-line bold value → 3 clones all bold; `{bold:false}` on a bold slot → non-bold; `itemCnt` incremented **iff** a new charPr appended (unchanged on reuse); `<hh:bold/>` sits between `<hh:offset>` and `<hh:underline>`; every other charPr byte-identical; result **XSD-valid**, and completion **refuses** if a mis-ordered `<hh:bold/>` is injected.
- **Tests:** `tests/test_addressed_bold.py` (unit) + XSD-gate integration. Optional oracle: python-hwpx opens result, `run.bold` matches.

### S2 — Live bold parity (COM)  (Capability A)
After setting a target's text in `live_addressed`, when `bold is not None`: select the run/cell text and call pyhwpx `set_font(Bold=bold)` (deterministic `HAction.Execute("CharShape")`).
- **Acceptance (machine-verifiable):** a **gated pytest** opens the template, applies bold stem + non-bold choices, then programmatically reads back `CharShape` bold state and asserts weights (not a manual eyeball). Windows/Hangul-gated; skipped in CI per existing gating. Manual desktop QA note is supplementary only.

### S3 — Paragraph structure ops  (Capability B)
Add `AddressedEdit.operation` = `insert_blank_after` / `insert_blank_before` / `delete_paragraph` for **body `bN` and cell paragraphs**.
- Offline: build a minimal empty `<hp:p>` cloning the sibling's paraPr (strip linesegs, empty text) and splice at the correct byte offset; delete = remove the `<hp:p>…</hp:p>` span.
- **Body-aware ordering + reindex (change #5):** `_ordered_edits` currently orders only `tN.rN.cN.pN` ([addressed.py:161-181](hangeul_core/addressed.py#L161)); add a `_BODY_TARGET`-aware bottom-up order by byte offset and reindex after each op so later `bN` in the same batch resolve correctly (`body_index` is precomputed and drifts otherwise, :839). *(Body spacing is required — the exam questions are body paragraphs — so bN is in-scope, not deferred.)*
- Live: `BreakPara` / select-para + `Delete`.
- **Acceptance:** insert adds exactly one empty para at the right position with the sibling's paraPr; a batch of two `bN` inserts + a later `bN` edit all land correctly; delete removes exactly the addressed paragraph; XSD-valid; untouched entries byte-identical.
- **Tests:** `tests/test_addressed_structure.py` — positioning, batch-drift, no lineseg cache on new para.

### S4 — delete_table / whole 보기 box  (Capability C)  ← high value, low risk
- New **`tN`→table locator** reconciling analyze's global table index with section-local order (D7, [live_addressed.py:6-8](hangeul_core/hwp/live_addressed.py#L6)); no such helper exists (`_find_cell_span` finds cells, not tables, fill.py:70-103).
- `delete_table` (target `tN`): remove **only the `<hp:run>` wrapping the `<hp:tbl>`**; delete the enclosing `<hp:p>` **only if it becomes text-empty** (guards caption loss, change #8).
- Live: pyhwpx `get_into_nth_table(n)` + select control + `delete_ctrl`.
- **Acceptance:** on the 형성평가 fixture (3 tables), `delete_table t2` removes the 보기 table; the other 2 tables and surrounding paragraphs stay byte-identical; a table paragraph carrying a caption keeps the caption; result **XSD-valid** and completion **refuses** if `validate_hwpx` reports invalid.
- **Tests:** `tests/test_addressed_table_delete.py`.

### S5 — delete_row (LIVE-ONLY this pass)  (Capability C)  ← highest risk, isolated
- Live: place caret via `get_into_nth_table` + cell block, `TableSubtractRow` (Hangul recomputes `rowCnt`/`cellAddr`/merges). Offline grid recompute **deferred** to a follow-up story with a dedicated grid model (reference python-hwpx `table_patch.build_grid`), an explicit **merge-detection predicate**, and a **fail-closed** condition.
- **Acceptance (live, gated):** deleting an unmerged row via COM yields a valid table on read-back (`rowCnt` −1). Offline delete_row is explicitly **not shipped** this pass; the follow-up's acceptance will enumerate invariants (`rowCnt`−1; all `cellAddr` row indices below the gap −1; no `cellSpan` crosses the gap; XSD-valid; merged-row → structured refusal).

### S6 — Formatting/structure-aware verify + discoverability  (Capability D)
- `complete_addressed_template` verify also reports (observability layer): stray-empty-bold-run count (== 0), per-run stem/choice bold booleans, inter-문항 blank-para count (== 1), deleted-table delta, and `xsd.valid`.
- `inspect_editable_regions` reports each paragraph's `charPrIDRef` + `isBold` and, when detectable, template stem/choice/spacer style ids + capacity.
- **Acceptance (e2e):** `tests/test_hyeongseong_e2e.py` reruns the 20-question fill and asserts: every 문항 stem bold, every 선지 non-bold, one blank between 문항 / none between 선지, no orphaned 보기 box, `xsd.valid == True`, stray-empty-bold-run count == 0.

---

## Scope boundaries / non-goals
- Not adopting python-hwpx as the editing substrate (D1); reference/oracle only.
- **Offline delete_row and all column ops are out of scope** this pass (delete_row ships live-only; offline follows).
- No new whole-document generator — this is addressed edits + structural cleanup of existing templates.
- Live (COM) parity is Windows/Hangul-gated; offline is the test source of truth.

## Sequencing & risk
S0 (header lane) unblocks S1. S1+S2 (bold) and S3 (paragraph) fix complaints #2/#3 at low risk. S4 (delete_table) fixes #1 at low risk. S5 is live-only, isolated. The XSD gate lands in S1 and guards every later op — highest-leverage safety fix.

## ADR
- **Decision:** Extend the own byte-preserving addressed/live engine with per-edit bold (via find-or-create charPr in a newly-threaded header lane), body/cell paragraph insert/delete (body-aware ordering), and offline delete_table; ship delete_row live-only via pyhwpx this pass. python-hwpx/pyhwpx are reference implementations + optional test oracles. All structural batches are XSD-gated and fail-closed.
- **Drivers:** D1 byte-preservation; the real gap is offline table-structure editing; formatting must be per-edit addressable and applied per-clone.
- **Alternatives considered:** delegate to python-hwpx (re-serializes sections → breaks D1, still no table rows); pyhwpx live-only for everything (no offline/CI path) — both rejected wholesale-for-everything but **accepted per-capability** for delete_row.
- **Consequences:** header.xml becomes a first-class session entry (Principle 1 restated at entry granularity); we own paragraph splice + delete_table + body reindex; an XSD gate now guards completion; delete_row correctness is borrowed from Hangul until an offline grid model is proven.
- **Follow-ups:** offline delete_row grid recompute + merge predicate; row insert / column ops; template-capacity heuristics; `role:"stem"|"choice"` styling sugar over `bold`.

**Status: PENDING APPROVAL** — no source edits, commits, or execution performed. On approval, recommended execution path: `/oh-my-claudecode:team` (parallel, S0→S1/S3 fan-out) or `/oh-my-claudecode:ralph` (sequential).

---

## QA pass (codex gpt-5.6-sol, 2026-07-15) — fixed vs. follow-ups

**Fixed + regression-tested** (`tests/test_codex_regressions.py`):
- Multiple `delete_table` in one batch used stale section-local indices → now ordered bottom-up by table number (`_ordered_edits`).
- `delete_table` dropped a caption sharing the table's run → now removes only the `<hp:tbl>` subtree, keeping run/paragraph when other content remains.
- `insert_blank_*` cloned images/controls (`<hp:pic>`, equations) → now emits a minimal empty paragraph (`_blank_paragraph_like`).
- Bold inserted after `<hh:italic>` (wrong OWPML slot) and order-check missed it → bold now precedes italic; `header_charpr_order_ok` checks it.
- `set_runs_bold` self-closing-run mis-parse (bolded the wrong run) → `_RUN_RE` matches self-closing runs first.
- `itemCnt` bump / `_delete_table_at` paragraph match were lexical-form-brittle → tolerant regexes (`itemCnt` any attr order; `<hp:p[ >]`).
- Paired `<hh:bold></hh:bold>` form now recognized/removed.
- Live row-delete planner dedups repeated `tN.rN`.
- New tests skip gracefully when the template fixture is absent (clean checkout).

**Deferred follow-ups** (documented, lower-risk/live-gated):
- `delete_table` + `bN` edits where a *preserved caption* becomes a new counted body paragraph can shift later `bN` — order table deletes after body edits or recompute `body_index`; today mitigated by bottom-up ordering, edge remains.
- Validation gate is weaker when optional `python-hwpx` (XSD) is absent — the charPr-order check still covers the bold case; add a stronger structural check for the no-XSD install.
- Multi-run text replace can leave an empty bold run shell (`count_stray_empty_bold_runs` reports it but the gate doesn't fail on it) — add empty-shell cleanup.
- `delete_row` has no MCP tool yet (offline path returns actionable `delete_row_is_live_only`); wire a gated live tool after desktop QA.
- charPr/run regexes assume canonical Hancom output (double-quoted, `id` first) — add attr-order-independent lookup if non-canonical inputs appear.

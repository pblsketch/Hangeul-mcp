# Safe Full-Editor Expansion RALPLAN — Best-Version Consolidated Plan

Status: Best available revision after five consensus passes. The last successful review pass before the stage-05 clarifications was Architect WATCH / Critic ITERATE on stage-04. Stage-05 resolves those cited `blocks_template` issues, but the final architect/critic re-review subagents failed to return usable output on retry, so this artifact is preserved as the best consolidated plan, not as fabricated review approval.

## Consolidated baseline (stage-04 revision)

# Safe Full-Editor Expansion RALPLAN — Stage-04 Revision (Priorities 1–6)

## Summary
This stage-04 revision keeps the stage-03 architecture and resolves the last remaining `DocumentSpec` ambiguities called out by the architect and critic. The control plane remains stage-based, substrate-owned, file-first, and wrapper-compatible. The final clarifications are:

1. `DocumentSpec` is now an explicit **tagged union** with two legal families:
   - `blocks_template` for `school.*`
   - `recipe_template` for `official.*`
2. `DocumentSpec` v1 is constrained to **repo-backed semantics only**:
   - no template-owned image/assets in v1,
   - no centered-heading/alignment promises in v1,
   - no visual placement promises beyond what current blocks/delegate tests prove.
3. Delegate follow-on stage granularity is now fixed against real `delegate_edit.py` operations:
   - one re-preview may authorize one **layout delegate batch stage** for `set_page_size`, `set_page_margins`, `set_header`, `set_footer`, `set_page_number`, `set_columns`,
   - image insertion is excluded from `DocumentSpec` v1 and therefore does not share that stage.

This is the recommended conservative path: constrain v1 to behavior the repository already proves, rather than leaving room for executor-side invention.

## Korean executive summary
이번 4차 수정안은 남아 있던 `DocumentSpec`의 애매함을 없애는 최종 정리입니다.  
가장 중요한 결정은 두 가지입니다. 첫째, `DocumentSpec`는 이제 **명확한 tagged union**입니다. 학교용 템플릿(`school.*`)은 blocks 기반 계약만, 공문/보도자료/기안문(`official.*`)은 recipe 기반 계약만 허용합니다. 둘째, v1에서는 **현재 저장소가 증명한 범위만 약속**합니다. 따라서 템플릿 전용 이미지 배치, centered heading, 임의 정렬 같은 시각 약속은 v1에서 제거하거나 거절합니다.  
또한 `page_setup`, `header/footer`, `page_number`, `columns`처럼 이미 `delegate_edit.py`에 있는 기능은 생성 단계와 섞지 않고, **create → validate/read-back → re-preview → 하나의 delegate layout stage** 순서로만 실행하도록 고정했습니다. 이렇게 해서 구현자가 더 이상 배치 경계나 템플릿 시각 의미를 추측하지 않아도 됩니다.

## Intent Diff
- **Preserved from stage-03**
  - substrate/stage ownership
  - no-mix rule
  - wrapper compatibility including `hwp_status()` and `open_in_hwp()`
  - dedicated pathless-wrapper rollout gate
  - live undo deferral
  - per-live-family proof matrix
  - feature-flag and verification matrix
- **Added in stage-04**
  - explicit tagged-union `DocumentSpec` legality model
  - removal of template-owned assets/images from `DocumentSpec` v1
  - removal of unproven centered/alignment semantics from `DocumentSpec` v1
  - fixed delegate follow-on stage granularity tied to concrete `delegate_edit.py` ops

## Principles
1. One control plane, multiple honest substrates.
2. Exact identity before mutation.
3. Immutable preview, single-use apply.
4. No mixed-substrate batch without re-analysis and re-preview.
5. v1 template semantics must be repo-backed, not aspirational.

## Decision Drivers
1. Remove executor guesswork from `DocumentSpec` legality and stage routing.
2. Constrain v1 promises to behaviors current blocks/delegate paths actually prove.
3. Preserve all prior live/file safety boundaries while finalizing document-generation scope.

## Options
### Option 1 — Tagged-union `DocumentSpec` + repo-backed v1 constraints (**recommended**)
**Pros**
- Eliminates schema conflict between school and official templates.
- Removes ambiguous asset/alignment behavior.
- Gives executors exact stage boundaries for follow-on delegate layout work.

**Cons**
- Narrows `DocumentSpec` v1 visual ambition.
- Defers template-owned image placement to later revisions.

**Verdict**: Choose.

### Option 2 — Keep one generic `DocumentSpec` shape and explain exceptions in prose
**Pros**
- Less schema churn.
- More superficially flexible.

**Cons**
- Leaves field legality ambiguous.
- Encourages per-executor interpretation.
- Fails the critic’s “no guessing” bar.

**Verdict**: Reject.

### Option 3 — Keep assets/alignment in v1 with planner-level placement rules
**Pros**
- Richer initial template promises.
- More attractive demos.

**Cons**
- Current repo does not prove deterministic placement/alignment semantics for template-owned visuals.
- Would invent behavior not grounded by existing blocks/delegate tests.

**Verdict**: Reject.

## In scope / out of scope
### In scope
- Tagged-union `DocumentSpec` contract.
- Seven concrete template contracts under that union.
- One delegate layout batch stage rule for proven layout operations.
- Conservative rejection of template-owned assets/images and unproven visual alignment semantics.

### Out of scope
- Template-owned image placement in `DocumentSpec` v1.
- Centered headings or other alignment promises not explicitly backed by current create/delegate proof.
- Any mixing of create and delegate layout mutations in one stage.

---

# Architecture decisions A–H

## A. Cohesive domain model with explicit substrate/stage ownership
No change from stage-03 except that `DocumentSpec` legality is now formalized as a union, not a single permissive object with per-template exceptions.

## B. Transaction semantics
No change from stage-03. File restore/session semantics remain planned Phase-3 control-plane functionality, not already shipped behavior.

## C. File mode vs live mode
No change from stage-03.

## D. New-document wizard (`DocumentSpec`) grounded to ADR D6/D8

### D1. Final schema strategy: explicit tagged union
`DocumentSpec` v1 is **not** one generic object accepted for all templates. It is a tagged union keyed by `template_kind`:

```json
DocumentSpec = BlocksTemplateSpec | RecipeTemplateSpec
```

```json
BlocksTemplateSpec {
  "spec_version": 1,
  "template_kind": "blocks_template",
  "template_id": "school.minutes.v1|school.family-letter.v1|school.report.v1|school.application.v1",
  "title": "string",
  "metadata": {...},
  "sections": [DocumentSection],
  "page_setup": PageSetupSpec | null,
  "header_footer": HeaderFooterSpec | null,
  "defaults": DefaultsSpec | null
}
```

```json
RecipeTemplateSpec {
  "spec_version": 1,
  "template_kind": "recipe_template",
  "template_id": "official.notice.v1|official.press-release.v1|official.draft.v1",
  "metadata": {...},
  "page_setup": PageSetupSpec | null,
  "header_footer": HeaderFooterSpec | null,
  "defaults": DefaultsSpec | null
}
```

```json
DocumentSection {
  "section_id": "string",
  "blocks": [
    {"type": "heading", "level": 1, "text": "..."},
    {"type": "paragraph", "text": "..."},
    {"type": "bullet_list", "items": ["...", "..."]},
    {"type": "numbered_list", "items": ["...", "..."]},
    {"type": "table", "rows": [["...", "..."]] },
    {"type": "page_break"}
  ]
}
```

#### Legality rules
- `blocks_template`:
  - `title` is required.
  - `sections` is required.
  - recipe-only Korean metadata keys such as `제목`, `본문`, `수신`, `참조` have no special meaning and MUST NOT be required by planner.
- `recipe_template`:
  - top-level `title` is forbidden.
  - `sections` is forbidden.
  - required keys live in `metadata` exactly as mapped to the current recipe surface in `hangeul_core/delegate_generate.py`.
- Any object mixing both families is rejected with `invalid_template_kind_shape`.

This resolves the stage-03 schema mismatch: no executor has to guess whether `title`/`sections` are global, duplicated, or ignored.

### D2. Repo-backed semantics only
`DocumentSpec` v1 intentionally constrains itself to primitives already evidenced by:
- `hangeul_core/blocks.py`
- `hangeul_core/delegate_generate.py`
- `hangeul_core/delegate_edit.py`
- `tests/test_blocks.py`
- `tests/test_delegate_recipe.py`
- `tests/test_delegate_headers.py`
- `tests/test_delegate_pagesetup.py`

#### Therefore, v1 explicitly does **not** promise:
- centered headings
- custom paragraph alignment semantics in base create stages
- template-owned image/logo placement
- per-template visual placement rules beyond block order and delegate post-processing already proven

If a caller needs those later, they belong in a future revision with explicit substrate/tests, not in v1.

### D3. Asset/image policy — final v1 decision
`DocumentSpec` v1 **rejects template-owned assets/images for all seven templates**.

#### Why
- Current blocks path supports generic `image` blocks in `hangeul_core/blocks.py`, but the plan does not have a proven template-placement contract for where a logo/report asset should land.
- Current delegate image support (`add_picture` in `hangeul_core/delegate_edit.py`, `tests/test_delegate_image.py`) proves insertion and validation, but not deterministic template placement or anchor semantics.
- The architect specifically flagged image placement as under-specified.

#### v1 rule
- `assets` field is removed from both union members.
- Any supplied asset/image payload is rejected with `unsupported_template_assets_v1`.
- `DocumentSection.blocks` in `blocks_template` MUST NOT include `{"type":"image"...}` in `DocumentSpec` v1.
- Image insertion remains possible elsewhere in the product as a separate delegate editing workflow, but **not** as part of `create_document_from_spec` v1.

This fully resolves asset ambiguity by choosing the conservative branch.

### D4. Layout follow-on stage routing — fixed granularity
After a base creation stage (`new_document_blocks` or `new_document_recipe`) completes and passes validation/read-back, the planner MAY emit exactly one follow-on **layout delegate batch stage** if and only if layout-affecting fields are present.

#### Allowed operations in the single layout delegate batch stage
Mapped directly to real `delegate_edit.py` operations:
- `set_page_size(...)`
- `set_page_margins(...)`
- `set_header(...)`
- `set_footer(...)`
- `set_page_number(...)`
- `set_columns(...)`

#### Batch rule
- These six operations MAY share one `delegate_file` stage after one re-preview.
- The stage is valid only because all six are:
  - same substrate: `delegate_file`
  - same target file identity
  - same verification family: reopened XML/read-back
  - same rollback family: file-side discard/replace-before-commit, with Phase-3 session receipts later

#### Ordering inside the delegate layout batch stage
Apply in this fixed order to reduce diff ambiguity:
1. `set_page_size`
2. `set_page_margins`
3. `set_columns`
4. `set_header`
5. `set_footer`
6. `set_page_number`

#### Image rule
- `add_picture(...)` is **not** part of `DocumentSpec` v1.
- Therefore it does **not** share the layout delegate batch stage.
- Future support would require its own explicit stage contract and template anchor semantics.

This resolves the critic’s stage granularity concern with a single concrete rule.

### D5. Follow-on stage legality table
| Field | Allowed in base create stage? | Allowed in v1? | Follow-on stage rule |
|---|---|---:|---|
| `title` (`blocks_template`) | Yes | Yes | base create only |
| `sections` (`blocks_template`) | Yes | Yes | base create only |
| recipe `metadata` (`recipe_template`) | Yes | Yes | base create only |
| `page_setup.size/orientation` | No | Yes | layout delegate batch stage |
| `page_setup.margins` | No | Yes | layout delegate batch stage |
| `header_footer.header_text` | No | Yes | layout delegate batch stage |
| `header_footer.footer_text` | No | Yes | layout delegate batch stage |
| `header_footer.page_number` | No | Yes | layout delegate batch stage |
| `header_footer.columns` | No | Yes | layout delegate batch stage |
| any image/asset payload | No | No | reject in v1 |
| centered/alignment hint | No | No | reject in v1 |

### D6. Template-by-template final contracts

#### 1. `school.minutes.v1` (`blocks_template`)
**Required**
- `title`
- `metadata.organization`
- `metadata.meeting_date`
- `metadata.location`
- `metadata.attendees[]`
- `metadata.agenda_items[]`
- `metadata.decisions[]`
- `sections`

**Optional**
- `metadata.absentees[]`
- `metadata.recorder`
- `metadata.next_meeting`
- `page_setup`
- `header_footer`
- `defaults`

**Default skeleton requirement**
Sections MUST serialize these block groups in order:
1. heading(title)
2. paragraph(summary)
3. table(attendance)
4. heading(`안건`)
5. bullet_list(agenda)
6. heading(`결정 사항`)
7. table(decisions)
8. optional paragraph(next meeting)

**Reject**
- empty attendees
- empty agenda_items
- malformed decision rows
- image/asset payload
- centered/alignment directives

**Acceptance proof**
- base create analogous to `tests/test_blocks.py`
- optional layout batch analogous to `tests/test_delegate_headers.py` / `tests/test_delegate_pagesetup.py`

#### 2. `school.family-letter.v1` (`blocks_template`)
**Required**
- `title`
- `metadata.organization`
- `metadata.recipient_group`
- `metadata.body_paragraphs[]`
- `metadata.sender_name`
- `sections`

**Optional**
- `metadata.date`
- `metadata.contact`
- `metadata.attachments[]`
- `page_setup`
- `header_footer`
- `defaults`

**Default skeleton requirement**
1. heading(title)
2. paragraph(organization)
3. paragraph(recipient greeting)
4. paragraphs(body)
5. optional bullet_list(attachments/notices)
6. paragraph(sender/date/contact)

**Reject**
- empty body_paragraphs
- image/asset payload
- alignment directives

**Acceptance proof**
- blocks create/read-back
- optional layout batch read-back

#### 3. `school.report.v1` (`blocks_template`)
**Required**
- `title`
- `metadata.organization`
- `metadata.report_date`
- `metadata.summary`
- `metadata.report_sections[]`
- `sections`

**Optional**
- `metadata.author`
- `metadata.tables[]`
- `metadata.appendix_items[]`
- `page_setup`
- `header_footer`
- `defaults`

**Default skeleton requirement**
1. heading(title)
2. paragraph(org/date/author)
3. paragraph(summary)
4. repeated heading + paragraph groups from `report_sections`
5. optional table blocks
6. optional bullet_list appendix

**Reject**
- empty `report_sections`
- empty section paragraphs
- image/asset payload
- alignment directives

**Acceptance proof**
- blocks create/read-back
- optional layout batch read-back

#### 4. `school.application.v1` (`blocks_template`)
**Required**
- `title`
- `metadata.applicant_name`
- `metadata.application_date`
- `metadata.purpose`
- `metadata.fields[]`
- `sections`

**Optional**
- `metadata.approver`
- `metadata.contact`
- `metadata.notes`
- `page_setup`
- `header_footer`
- `defaults`

**Default skeleton requirement**
1. heading(title) **as plain heading only**
2. paragraph(date/applicant)
3. table(label/value rows)
4. paragraph(purpose)
5. optional paragraph(notes)
6. paragraph(approval/signature text)

**Reject**
- empty fields
- malformed field rows
- checkbox/custom-control requests
- image/asset payload
- any centered/alignment directive; stage-03 “centered heading” promise is removed in v1

**Acceptance proof**
- blocks create/read-back
- optional layout batch read-back

#### 5. `official.notice.v1` (`recipe_template`)
**Required**
- `metadata.기관명`
- `metadata.제목`
- `metadata.본문`

**Optional**
- `metadata.수신`
- `metadata.참조`
- `metadata.날짜`
- `metadata.발신명의`
- `metadata.담당자`
- `page_setup`
- `header_footer`
- `defaults`

**Reject**
- top-level `title`
- `sections`
- image/asset payload
- alignment directives

**Acceptance proof**
- recipe output analogous to `tests/test_delegate_recipe.py`
- optional layout batch read-back

#### 6. `official.press-release.v1` (`recipe_template`)
**Required**
- `metadata.기관명`
- `metadata.제목`
- `metadata.본문`

**Optional**
- `metadata.배포일`
- `metadata.담당`
- `metadata.연락처`
- `metadata.부제`
- `metadata.문의`
- `page_setup`
- `header_footer`
- `defaults`

**Reject**
- top-level `title`
- `sections`
- image/asset payload
- alignment directives

**Acceptance proof**
- recipe output analogous to current recipe tests
- optional layout batch read-back

#### 7. `official.draft.v1` (`recipe_template`)
**Required**
- `metadata.제목`
- at least one of `metadata.목적` or `metadata.내용`

**Optional**
- `metadata.기안자`
- `metadata.기안일`
- `metadata.시행일`
- `metadata.수신`
- `metadata.붙임`
- `page_setup`
- `header_footer`
- `defaults`

**Reject**
- top-level `title`
- `sections`
- empty `목적` and `내용`
- image/asset payload
- alignment directives

**Acceptance proof**
- recipe output analogous to current recipe tests
- optional layout batch read-back

### D7. Global rejection rules
Reject at preview time if:
- `template_kind` does not match `template_id`
- `blocks_template` omits `title` or `sections`
- `recipe_template` includes `title` or `sections`
- image/asset payload appears anywhere
- any alignment/centering hint appears
- unsupported construct or mixed-family field appears
- layout fields are present but planner cannot emit the single allowed layout delegate batch stage

## E. Rich live editing scope and substrate table
No change from stage-03.

## F. Human-readable document/window picker
No change from stage-03.

## G. Edit-plan preview / change report contract
No change from stage-03, except `DocumentSpec` previews must now surface the union branch (`blocks_template` or `recipe_template`) and whether a second delegate layout stage will be emitted.

## H. Windows regression automation
No change from stage-03.

---

# Wrapper-compatibility appendix (mandatory)
No change from stage-03. `hwp_status()`, `open_in_hwp()`, current-document wrappers, and exact-path wrappers remain part of the preserved migration contract.

---

# Feature flags tied to rollout ownership
No flag removals from stage-03. `document_spec_v1` remains the Phase-4 flag, but its promotion gate is tightened:
- all seven template union branches must pass deterministic validation,
- image/asset payload rejection must be covered by tests,
- alignment/centering rejection must be covered by tests,
- optional layout delegate batch stage must be tested as one batch, not inferred ad hoc.

---

# Per-operation verification / rollback matrix
Stage-03 matrix remains valid. Add one `DocumentSpec`-specific clarification:
- `DocumentSpec` base create verification is only about validated package + ordered text/structure read-back.
- `DocumentSpec` optional layout verification is only about reopened XML/read-back for the six allowed layout delegate ops.
- No `DocumentSpec` image/alignment verification exists in v1 because those semantics are rejected, not implemented.

---

# Phased sequencing and dependencies

## Phase 0 — Contract lock
- freeze tagged-union schema
- freeze image/alignment rejection rules
- freeze single layout delegate batch-stage rule

## Phase 1 — Shared control plane skeleton
- wrapper parity unchanged

## Phase 2 — File executor and reports
- no change

## Phase 3 — Picker + planned file restore sessions
- no change

## Phase 4 — `DocumentSpec` v1 full implementation
Implementation scope is now exact:
1. support tagged-union validation
2. support seven template contracts
3. reject image/assets/alignment hints
4. emit at most one follow-on layout delegate batch stage after base create+validate+re-preview
5. prove the batch with existing delegate read-back patterns

## Phase 5A+ / Phase 6
- unchanged from stage-03

---

# Risks and mitigations
1. **Risk:** executor reintroduces generic `DocumentSpec` handling.  
   **Mitigation:** tagged union with hard legality rules.
2. **Risk:** one implementer adds image placement while another rejects it.  
   **Mitigation:** v1 rejects all template-owned assets/images.
3. **Risk:** visual alignment semantics drift.  
   **Mitigation:** centered/alignment promises removed from v1.
4. **Risk:** delegate stage boundaries vary by implementer.  
   **Mitigation:** single layout delegate batch stage rule with fixed allowed op list and order.

# Open questions with recommended defaults
1. Should `DocumentSpec` v1 ever allow image blocks for school templates behind the same flag?  
   **Default:** no; only in a later revision with its own explicit contract.
2. Should alignment controls be allowed through `DocumentSpec` before a proven create/delegate contract exists?  
   **Default:** no.
3. If a future revision adds images, should they batch with layout ops?  
   **Default:** no assumption now; require a separate future stage contract.

# Verification Plan
- Unit:
  - tagged-union legality validation
  - rejection of mismatched `template_kind`/`template_id`
  - rejection of assets/images and alignment hints
  - emission of one layout delegate batch stage only when allowed fields are present
- Integration:
  - school templates generate via blocks path and read back ordered content
  - official templates generate via recipe path and read back fixed chrome + provided content
  - optional layout batch verified using reopened XML/read-back patterns from existing delegate tests
- Migration:
  - wrapper compatibility unchanged from stage-03
- Docs/PRD/capabilities:
  - `document_spec_v1` promotion blocked until union/rejection semantics are documented consistently

# Deliberate-mode pre-mortem
1. **A caller sends `official.notice.v1` with top-level `title` and `sections`, and different executors interpret it differently.**  
   Fix: tagged union rejects mixed-family shape.
2. **A school template quietly inserts a logo in inconsistent places across implementations.**  
   Fix: template-owned assets/images rejected in v1.
3. **One executor batches header/footer/page setup together while another emits six stages.**  
   Fix: fixed single layout delegate batch stage with ordered allowed op list.

# Architect verdict response
Addressed:
- visual-placement semantics are now constrained to repo-backed behavior only
- template-owned assets are removed from v1
- centered-heading/alignment promise is removed from v1

# Critic verdict response
Addressed:
- `DocumentSpec` schema-shape mismatch resolved via explicit tagged union
- asset/image ambiguity resolved by rejecting template-owned assets/images in v1
- delegate follow-on stage granularity fixed against concrete `delegate_edit.py` ops

# Status
Stage-04 revision resolves the remaining stage-03 critic issues and architect WATCH comment while preserving all earlier fixes; ready for parent persistence as the next revision artifact.


---

## Stage-05 authoritative overrides

The following section supersedes conflicting `DocumentSpec` details in the stage-04 baseline above.

# Safe Full-Editor Expansion RALPLAN — Stage-05 Revision (Priorities 1–6)

## Summary
This revision resolves the last remaining stage-04 review issues by removing the dual-source ambiguity in `blocks_template`, fixing the school-template field contracts, and pinning `columns` to one schema path. Everything from stage-04 remains in force except where this document explicitly replaces it.

The decisive change is simple and conservative:
- `recipe_template` stays metadata-driven.
- `blocks_template` becomes **section-authoritative** and D8-aligned.
- The server does **not** synthesize block content from school-template metadata in v1.
- School templates validate section structure; they do not invent section prose.
- `columns` lives only at `page_setup.columns`.

## Korean executive summary
최종 수정안의 핵심은 학교용 `blocks_template`에서 **무엇이 실제 내용의 원천인지**를 하나로 고정하는 것입니다. v1에서는 `sections`가 유일한 본문 권위 데이터이며, 서버는 여기서 문단·목록·표 내용을 새로 만들어 내지 않습니다. 템플릿은 `section_id`와 블록 타입 규칙으로만 구조를 검증합니다. 이로써 `metadata`와 `sections`가 서로 다른 내용을 들고 있을 때 어느 쪽이 이기는지 추측할 필요가 없어집니다. 또한 `columns`는 `page_setup.columns` 하나로 고정하고, 학교용 템플릿의 summary/agenda/body 같은 항목도 모두 `sections` 안에서 명시적으로 제공하도록 바꿉니다.

## Final authoritative `DocumentSpec` model

### 1) `recipe_template` remains metadata-driven
No change from stage-04 for:
- `official.notice.v1`
- `official.press-release.v1`
- `official.draft.v1`

Those templates continue to route through `create_official_document(...)`-style recipe generation plus optional follow-on layout delegate batch.

### 2) `blocks_template` is section-authoritative
This replaces the stage-04 `blocks_template` contract.

```json
BlocksTemplateSpec {
  "spec_version": 1,
  "template_kind": "blocks_template",
  "template_id": "school.minutes.v1|school.family-letter.v1|school.report.v1|school.application.v1",
  "title": "string",
  "sections": [DocumentSection],
  "page_setup": PageSetupSpec | null,
  "header_footer": HeaderFooterSpec | null
}
```

#### Hard rules
- `sections` is the **only authoritative content source** for emitted school-template document content.
- `title` is a validation/display field only.
- School-template metadata content fields from stage-04 are removed from the v1 contract.
- If future revisions want metadata-driven synthesis, that is a new contract version, not a hidden v1 behavior.

#### Conflict rule
- If the first required title-bearing section does not begin with a heading whose text equals top-level `title`, preview rejects with `title_section_mismatch`.
- No other content precedence rule exists, because `sections` alone owns document content.

### 3) Exact flattening into the real substrate
`create_document_from_spec(...)` for `blocks_template` MUST flatten `DocumentSection[]` into the flat `blocks` list consumed by `hangeul_core/blocks.py:create_document_from_blocks(...)` using this exact rule:

1. Iterate `sections` in array order.
2. For each section, append `section.blocks` to the output list in order.
3. Do **not** synthesize implicit headings, paragraphs, page breaks, lists, or tables.
4. If a page break is desired between sections, the caller must include an explicit `{ "type": "page_break" }` block at the desired position.
5. The flattened list is passed as-is to `create_document_from_blocks(...)`.

That keeps v1 aligned with ADR D8 and the current substrate: client-authored structure in, flat blocks out.

## Pinned shared helper shapes

### `PageSetupSpec`
```json
PageSetupSpec {
  "size": "A4",
  "orientation": "portrait|landscape",
  "margins": {"left": 0, "right": 0, "top": 0, "bottom": 0},
  "columns": 1
}
```

### `HeaderFooterSpec`
```json
HeaderFooterSpec {
  "header_text": "string|null",
  "footer_text": "string|null",
  "page_number": "BOTTOM_CENTER|BOTTOM_RIGHT|TOP_RIGHT|null"
}
```

#### Columns path
- `columns` appears **only** at `page_setup.columns`.
- It is removed from `header_footer` everywhere.
- All routing, validation, preview, and follow-on delegate stage prose must use only `page_setup.columns`.

## Final school-template contracts
These replace the stage-04 school-template field lists.

### `school.minutes.v1`
**Required**
- `title`
- `sections`

**Required sections and allowed leading blocks**
1. `meeting_overview` — first block must be `heading(title)` and it must be followed by at least one paragraph block in the same section.
2. `attendance` — must contain at least one `table` block.
3. `agenda` — must contain at least one `bullet_list` or `numbered_list` block.
4. `decisions` — must contain at least one `table` or paragraph/list combination.

**Optional sections**
- `next_meeting`
- `signatures`
- `attachments`

**Removed from v1 contract**
- `metadata.summary`
- `metadata.attendees[]`
- `metadata.agenda_items[]`
- `metadata.decisions[]`

Those may still be used by the client to compose `sections`, but they are not part of the server-side `DocumentSpec` v1 contract.

### `school.family-letter.v1`
**Required**
- `title`
- `sections`

**Required sections**
1. `letter_header` — the section must be exactly one plain `heading(title)` block.
2. `recipient_intro` — paragraph blocks.
3. `body` — one or more paragraph/list blocks.
4. `sender_footer` — paragraph blocks.

**Optional sections**
- `attachments`
- `notices`

**Removed from v1 contract**
- `metadata.body_paragraphs[]`
- `metadata.recipient_group`
- `metadata.sender_name`

### `school.report.v1`
**Required**
- `title`
- `sections`

**Required sections**
1. `report_header` — the section must be exactly one plain `heading(title)` block.
2. `summary` — paragraph blocks.
3. `report_body` — one or more heading/paragraph/table groups.

**Optional sections**
- `appendix`
- `data_tables`

**Removed from v1 contract**
- `metadata.report_sections[]`
- `metadata.summary`
- `metadata.tables[]`

### `school.application.v1`
**Required**
- `title`
- `sections`

**Required sections**
1. `application_header` — the section must be exactly one plain `heading(title)` block.
2. `applicant_info` — paragraph and/or table blocks.
3. `application_body` — paragraph blocks.
4. `fields_table` — at least one `table` block.
5. `approval_footer` — paragraph blocks.

**Removed from v1 contract**
- `metadata.fields[]`
- `metadata.purpose`
- any centered/alignment hint

## Validation rules for `blocks_template`
Preview rejects with:
- `invalid_template_kind_shape` when a school template carries recipe shape or vice versa.
- `missing_required_section` when a required `section_id` is absent.
- `section_order_mismatch` when required sections are out of required order.
- `title_section_mismatch` when the first title-bearing heading does not match top-level `title`.
- `invalid_block_type_for_section` when a section lacks the required block family.
- `unsupported_template_assets_v1` for any asset/image payload.
- `unsupported_alignment_hint_v1` for any centered/alignment hint.

## Delegate follow-on layout batch rule
Stage-04’s layout batch rule remains in force, with the pinned field path applied.

A `blocks_template` or `recipe_template` create flow MAY emit one follow-on `delegate_file` layout batch stage after create + validate/read-back + re-preview, containing any subset of these operations in this fixed order:
1. `set_page_size` / `set_page_margins` from `page_setup`
2. `set_columns` from `page_setup.columns`
3. `set_header` from `header_footer.header_text`
4. `set_footer` from `header_footer.footer_text`
5. `set_page_number` from `header_footer.page_number`

No image operation participates in this batch because `DocumentSpec` v1 rejects image/asset payloads.

## What stays unchanged from stage-04
Still unchanged and in force:
- substrate/stage ownership and no-mix rule
- wrapper compatibility including `hwp_status()` and `open_in_hwp()`
- dedicated saved-current-document rollout gate
- live undo deferral
- live family proof matrix
- conservative v1 rejection of assets/images/alignment promises
- `recipe_template` routing and acceptance strategy

## Acceptance proof adjustments
For `blocks_template` v1, acceptance now proves:
1. tagged-union legality
2. required section presence/order
3. deterministic flattening from `DocumentSection[]` to flat blocks
4. content read-back from the flat block sequence
5. optional layout delegate batch read-back when `page_setup` / `header_footer` fields are present

## Status
Stage-05 revision resolves the remaining stage-04 architect/critic ambiguity by making `blocks_template` section-authoritative, removing dual-source school metadata contracts, pinning `page_setup.columns`, and defining exact flattening into `create_document_from_blocks(...)`.

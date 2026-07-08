# 갭 분석 — 선행사례(2-2) 지원 vs Hangeul-mcp 미지원

> `docs/research-strategy.md` 2-2절의 AI 에이전트/MCP/Skill 선행사례들이 지원하지만
> **Hangeul-mcp v0.1.0이 아직 안 하는 것**을 정밀 목록화. (조사일 2026-07-09)

## 0. 비교 대상

- **claw-hwp** (DoHyun468) — rhwp WASM 기반 Claude Skill. read/create/edit + 서식·표·차트·도장·프리뷰.
- **hwpx-mcp-server** (airmang) — python-hwpx 기반 MCP, **60+ 툴**(가장 방대). read/edit/form/generate/validate/repair/render.
- **hwpx-skill** (airmang) — 위 서버의 Skill 래퍼. 누름틀 fill·전역치환·문서생성·검증·수리·PII 마스킹.
- **hwpx-skill** (jkf87) — md/txt/URL→HWPX 생성기, 기안문/보도자료/계획서/시험지, 체크박스 fill, 수식·도장.
- **hwp-mcp** (jkf87) — COM 라이브(생성/열기/저장/텍스트/폰트/표생성·채우기/배치). Windows+한글.
- **hwpilot** (devxoul) — CLI, read/edit/inline서식(범위)/이미지/표/HWP5→HWPX 변환.

## 1. Hangeul-mcp가 현재 지원 (v0.1.0)

- `detect_format`, `analyze_form`(understand+inline), `fill_form`(바이트보존: set/append/inline·멀티섹션·자간정규화), `extract_text`
- `hwp_status`, `apply_to_open_hwp`(COM 라이브 원샷, 스캐폴드)
- `.hwp → .hwpx` 자동변환(COM, 데스크톱 전용)
- **고유 강점(대부분 선행사례에 없음)**: inline-blank(문장중간 빈칸), 병합셀 2D occupancy 매핑, review→COM 원샷 반영, 클라이언트 무관 설계

---

## 2. 미지원 목록 (선행사례엔 있음)

### A. 양식 인식·채우기 (우리 핵심 영역인데도 갭 존재)

- [ ] **누름틀(form field) 헤드리스 fill** — airmang `list_form_fields`/`fill_form_field`/`fill_by_path`, jkf87 preservation-fill. 우리는 COM `put_field_text`만 있고 **HWPX 헤드리스에서 누름틀 이름 기반 채우기 없음**.
- [ ] **{placeholder} 전역 치환** — `{학교명}`,`{담당자}` 같은 템플릿 변수 치환(표·중첩 포함). airmang/jkf87 모두 지원. 우리 없음.
- [ ] **형광펜(markpen) placeholder 교체 kind** — 실양식 테스트에서 발견. 예시값을 강조표시한 템플릿의 교체. 우리 스키마에 kind 미정의.
- [ ] **체크박스 필드(☑/□) 탐지·선택** — jkf87 체크박스 fill. 우리 `KIND_CHECKBOX` 정의만 있고 탐지·채우기 미구현.
- [ ] **form-fit 분석 / 자동 글꼴 축소** — airmang `analyze_template_formfit`/`apply_template_formfit`, 셀 auto-fit font shrink. 우리 없음(쪽수 드리프트 방지 로직 미구현).
- [ ] **verify_fill** — 채운 뒤 값이 실제 반영됐는지 검증 툴. 우리 없음.
- [ ] **find_cell_by_label / get_table_map** — 라벨로 셀 조회, 표 구조 맵. 우리 analyze는 있으나 MCP 툴로 미노출.

### B. 읽기·추출 (우리 extract_text만 있음)

- [ ] `get_document_outline` / `get_document_map`(개요+표+폼+앵커 한 번에)
- [ ] `find_text` (문서 내 텍스트 검색)
- [ ] `hwpx_to_html`, 구조화 JSON 추출(`extract_json`)
- [ ] `list_styles` (스타일 목록)
- [ ] **`.hwp` 바이너리 헤드리스 읽기** — airmang/hwpilot/kordoc은 .hwp 읽기 가능. 우리는 COM 변환 없이 .hwp 못 읽음.

### C. 편집 (우리는 "채우기"만, 일반 편집 없음)

- [ ] `search_and_replace` / `batch_replace` (전역 텍스트 치환)
- [ ] 문단: `add_heading`/`add_paragraph`/`insert`/`delete`/`add_page_break`
- [ ] 표: create/merge/split/format, add/remove rows·cols, `table_compute`(합계·평균)
- [ ] 리치 서식: bold/italic/underline/color/size/font, 문단정렬·줄간격·들여쓰기, `create_custom_style`
- [ ] 이미지: insert/replace, 도장/서명 배치(seal), 수식(equation), 차트(20종), 도형, 텍스트박스
- [ ] 머리말/꼬리말, 페이지 설정, 목차(TOC) 자동생성
- [ ] inline 서식 범위 지정(hwpilot `--start/--end`)

### D. 문서 생성 (우리는 생성 안 함 — "두뇌·손 분리" 철학)

- [ ] `create_document_from_plan` / builder / markdown→HWPX
- [ ] 공식문서 레시피: **기안문·보도자료·계획서·시험지** (jkf87), proposal/exam (airmang)
- [ ] `mail_merge` (CSV/JSON 대량 생성)

### E. 안전·품질·복구 (우리는 바이트보존·well-formed 검증만)

- [ ] **XSD 스키마 검증** — D1 결정에서 python-hwpx로 하려 했으나 미통합.
- [ ] **원자적 트랜잭션 / dry-run / undo / rollback** — airmang `apply_edits`·`undo_last_edit`.
- [ ] **change tracking(redline)** — `add_tracked_edit`.
- [ ] **repair_hwpx** — 안 열리는 파일 복구.
- [ ] **render_preview (HTML/PNG)** — 시각 프리뷰. claw-hwp 라이브 프리뷰, airmang render_preview. 우리 없음.
- [ ] **PII 마스킹 게이트** — jkf87/airmang secure-fill. 우리 SKILL.md 권고만 있고 코드 게이트 없음.
- [ ] **lint / 품질 게이트** — `lint_text_conventions`, 공식문서 스타일 검사.
- [ ] `mcp_server_health`, `copy_document`(편집 전 복사 강제).

### F. 포맷 확장

- [ ] PDF/DOCX/XLSX ingestion (airmang `[ingest]`, kordoc).

---

## 3. 전략적 판단 (중요)

**airmang/hwpx-mcp-server가 이미 편집·생성·표·이미지·검증 breadth를 60+툴로 포괄한다.**
그걸 그대로 따라잡는 건 비효율. Hangeul-mcp의 존재 이유는 **양식 인식 + inline-blank + review→apply**다.

→ 따라서 우선순위는 **breadth 경쟁(C·D)이 아니라 우리 차별점을 깊게(A)** 파는 것:
- A(양식 인식·채우기)의 갭이 최우선 — 특히 실양식이 요구한 형광펜 placeholder·체크박스·누름틀 헤드리스·form-fit.
- E(안전·검증)는 신뢰성 필수 기반 — XSD 검증·dry-run·repair·render.
- B(읽기)는 저비용 고효용 — outline/find/html.
- C·D(편집·생성)는 **선택적** — 필요시 python-hwpx를 substrate로 위임(재발명 금지, D1 결정과 일치).

우선순위 상세는 [`ROADMAP.md`](ROADMAP.md).

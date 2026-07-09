# ROADMAP — 다음에 개발/수정할 것

> v0.1.0 이후. 실양식 3종 테스트 발견 + 선행사례 갭([`gap-analysis.md`](gap-analysis.md)) 종합.
> **범위: 선행사례가 하는 것 전부를 커버한다.** 단, 재발명 금지(D1) — 차별점(양식 인식·채우기)은
> 직접 깊게, commodity breadth(편집·생성)는 **`python-hwpx`를 substrate로 위임하되 Hangeul-mcp
> MCP 툴로 노출**해 제품을 완성한다.

## 접근 원칙 (own vs delegate)

- **OWN (우리가 직접)** — 양식 인식·서식보존 채우기·inline-blank·병합셀·review→apply. 바이트보존 raw-XML splice.
- **DELEGATE (python-hwpx 위임 + 우리 툴로 노출)** — 문단/표/이미지/서식 편집, 문서 생성, XSD 검증, repair, render. 얇은 어댑터로 감싸 `hangeul_mcp` 툴로 제공. 위임 결과도 바이트보존/검증 게이트를 통과시킨다.
- 두 경로 모두 **두뇌·손 분리** 유지: 값·문안 *생성*은 클라이언트 LLM. 서버는 실행 도구.
- **BYO-AI local harness** — Hangeul-mcp 자체는 AI/API 과금 앱이 아니다. 사용자의 AI 클라이언트가 MCP로 호출하는 로컬 한글 문서 엔진이며, `describe_capabilities`로 file/render/live/headless-HWP 기능 가용성을 먼저 노출한다.
- **FILE vs LIVE 분리** — HWPX 파일 직접 처리와 열린 한글 창 제어는 같은 UX에서 연결될 수 있지만 구현 경계는 분리한다. live status/preview는 side-effect-free, live apply만 열린 창을 조작한다.

## 실양식 테스트가 드러낸 것 (근거)

- **강사카드(.hwpx)** — 라벨:값 + inline-blank(∘/콜론). ✅ 완성.
- **교수학습·평가 계획(.hwp)** — 반복 템플릿 블록·중첩 채점기준표·체크박스(☑논술 □구술). COM 변환 데스크톱 전용 확인.
- **평가 운영 계획(.hwpx)** — 형광펜(markpen) placeholder 템플릿. → `analyze` markpen 미독 **버그 수정 완료**(itertext).

---

## Phase A (P0) — 양식 인식·채우기 심화 [OWN] ✅ 완료 (US-013~017)

1. **형광펜(markpen) placeholder kind** ✅ — 강조 예시값을 필드로 탐지, markpen 안쪽만 치환·서식보존. (`markpen.py`, US-014)
2. **체크박스 필드(☑/□) 탐지·선택** ✅ — 옵션 목록 인식(`options`), 지정 라벨 `□`→`☑`, exclusive/multi. `KIND_CHECKBOX` 구현. (`checkbox.py`, US-015)
3. **`{placeholder}` 전역 치환** ✅ — `{학교명}` 등, 표·중첩·run 분할 포함. 바이트보존 splice. (`locate.py`, US-013)
4. **누름틀(form field) 헤드리스 fill** ✅ — HWPX 필드 이름 인식·채우기(COM 없이). `apply_to_open_hwp`와 이름 스키마 공유. (`formfield.py`, US-016)
5. **form-fit / 쪽수 드리프트 가드** ✅ — 셀 오버플로 추정(휴리스틱) + 선택적 auto-fit(글꼴 축소, 하한 보장). `analyze_formfit` 툴 신설. (`formfit.py`, US-017)
- 수용: ✅ 각 kind 골든/회귀 테스트(81 passed), 바이트보존 유지, `analyze_form`/`fill_form` 스키마 확장, `analyze_formfit` 툴 추가.
- 남은 검증: 누름틀(US-016)·form-fit(US-017)은 실양식(PII 없는) 샘플로 재검증 권장(현재 합성 픽스처 기반). form-fit은 렌더러 없는 추정 → Phase B `render_preview`로 시각 검증 보완.

## Phase B (P1) — 신뢰성·검증·읽기 [OWN + DELEGATE] 🟢 자체코어 완료 (US-018~021)

1. **XSD 스키마 검증 통합** ✅ — `validate_hwpx` 툴: 모든 XML well-formed·mimetype·XML 선언 검증. python-hwpx XSD는 설치 시 선택 적용(soft dep). (`validate.py`, US-021)
2. **dry-run / 백업 / repair** ✅(부분) — `fill(dry_run=True)`·`backup=True`(덮어쓰기 전 `.bak`) 완료. `repair_hwpx`(안 열리는 파일 복구)는 DELEGATE로 보류. (US-019)
3. **render_preview (HTML/PNG)** ✅ — `render_preview` PNG 도구 추가. HWPX→HTML을 로컬 HTTP 서버로 띄우고 Playwright Chromium으로 screenshot. optional `render` extra 필요. "정적검사≠렌더확인" 보완. (`render.py`, US-041)
4. **PII 마스킹 게이트(코드화)** ✅ — 주민번호·전화·카드·계좌·이메일 탐지·마스킹. `fill(mask_pii=True)` + `scan_pii` 툴. SKILL 권고 → 실제 게이트. (`pii.py`, US-018)
5. **`.hwp` 헤드리스 읽기** 🟡 adapter gate 완료 — `extract_hwp_text`는 COM을 쓰지 않고 headless reader 후보를 점검해 substrate 미설치 시 `available:false` 반환. 실제 `.hwp` 추출은 reader 선정·PII 없는 실파일 fixture 확보 후 완료 가능. (`hwp_headless.py`, US-042)
6. **읽기 확장(저비용)** ✅(부분) — `find_text`·`get_document_outline`·`list_styles` 완료. `get_document_map`·`hwpx_to_html`는 후속. (`read.py`, US-020)

## Phase C (P2) — 일반 편집 [DELEGATE: python-hwpx substrate]

python-hwpx를 얇게 감싸 Hangeul-mcp 툴로 노출(재발명 금지). 편집 후 XSD/바이트무결성 게이트 통과.
단, 텍스트 치환은 위임보다 우리 바이트-splice 엔진이 불변식(바이트보존)에 부합 → OWN으로 선행 구현.

1. **텍스트/치환** ✅ — `search_and_replace`·`batch_replace`. **OWN 바이트보존**(`locate.replace_literals`, run 분할·셀 경계 가드). python-hwpx 위임 아님. (`edit.py`, US-022)
2. **문단** ✅(부분) — `add_paragraph` 위임 완료(`delegate.py`, US-024). `add_heading`/`insert`/`delete`/`add_page_break`는 후속.
3. **표** ✅(부분) — `add_table`(생성)·`create_hwpx_table`·기존 표 `merge_table_cells`·`set_cell_shading` 완료. split·행/열 추가삭제·`table_compute`는 후속. (`delegate.py`, US-024/035/038)
4. **서식** 🔲 후속 — 글자(bold/italic/underline/color/size/font)·문단(정렬/줄간격/들여쓰기)·`create_custom_style` (python-hwpx `ensure_run_style`/`char_properties` 위임).
5. **객체** ✅(부분) — 이미지 삽입·도장/서명(`add_image`) 위임 완료(US-027). replace·머리말/꼬리말·페이지 설정·목차(TOC)는 후속. 리치 내보내기(`hwpx_to_html`/`hwpx_to_markdown`)는 ✅ 완료(US-023).
- 수용: ✅ 위임 편집이 python-hwpx 경유 + 우리 `validate_hwpx` 게이트 통과, 회귀 테스트(importorskip). 위임 편집은 재직렬화이므로 바이트동일 아님 — 게이트 통과가 무결성 기준.

## Phase D (P3) — 문서 생성 [DELEGATE + 우리 레시피]

1. **빌더/변환** ✅(부분) — `create_document_from_blocks` 완전제어 빌더, markdown subset(heading/paragraph/list/pipe table)→HWPX 완료. `create_document_from_plan`·full CommonMark·중첩 목록은 후속. (`blocks.py`, `markdown.py`, US-025/039/040)
2. **공식문서 레시피** — 기안문·보도자료·계획서·시험지(문제+답안) 템플릿 생성. 우리 템플릿 + 위임 조립.
3. **mail_merge** ✅ — 대량 생성(우리 fill 엔진 + 레코드 반복, **OWN 바이트보존**). CSV/JSON 파싱은 클라이언트(records 전달). (`mailmerge.py`, US-026)
- 원칙: 문안 *생성*은 클라이언트 LLM, 서버는 구조 조립·채우기만.

## 기술 부채 / 리팩터

- **fill 위치탐색 견고화**(codex 제안): 정규식 raw-XML 재스캔 → **Expat/SAX 기반 `section+table stack+cellAddr+byte-span` 인덱스**를 analyze에서 1회 구축, fill은 span만 splice.
- **occupancy grid를 fill에도** 적용(현재 understand만).
- 표 셀 넘치는 다행 inline 케이스 추가 테스트.

## 실행 순서 권장

Phase A(차별점) → Phase B(신뢰성) → Phase C(편집, python-hwpx 위임) → Phase D(생성) → Phase E(BYO-AI/live harness).
A·B는 우리 코어라 먼저, C·D는 위임 어댑터라 병렬화 가능. 각 Phase는 `/ralplan`으로 PRD 분해 후 `/ralph` 구현.

## Phase E (P4) — BYO-AI / live harness

1. **Capability manifest** ✅ — `describe_capabilities`가 서버 자체 LLM 없음, file_hwpx/delegate/render/live/headless-HWP 가용성, optional dependency 요구사항을 반환.
2. **BYO-AI workflow 문서** ✅ — `docs/byo-ai-harness.md`에 파일 양식 채우기, 새 문서 생성, 열린 한글 live 셀 채우기 흐름을 명시.
3. **Live preview gate** ✅ — `preview_cells_to_open_hwp`가 COM 호출 없이 target table/row/col을 계산해 apply 전 확인 경로 제공.
4. **No-API guard** ✅ — dev dependency와 테스트에서 서버가 LLM API SDK에 의존하지 않는다는 경계를 확인.

## 이미 완료 (v0.1.0)

라벨:값 fill · inline-blank(마커/콜론) · 병합셀 2D occupancy · 멀티섹션 · 바이트보존 · 자간정규화 ·
MCP 서버(6툴) · 클라이언트무관 · `.hwp` COM 변환(데스크톱) · COM 라이브 스캐폴드 · markpen 텍스트 독해 수정 · codex QA 하드닝.

# ROADMAP — 다음에 개발/수정할 것

> v0.1.0 이후. 실양식 3종 테스트 발견 + 선행사례 갭([`gap-analysis.md`](gap-analysis.md)) 종합.
> **범위: 선행사례가 하는 것 전부를 커버한다.** 단, 재발명 금지(D1) — 차별점(양식 인식·채우기)은
> 직접 깊게, commodity breadth(편집·생성)는 **`python-hwpx`를 substrate로 위임하되 Hangeul-mcp
> MCP 툴로 노출**해 제품을 완성한다.

## 접근 원칙 (own vs delegate)

- **OWN (우리가 직접)** — 양식 인식·서식보존 채우기·inline-blank·병합셀·review→apply. 바이트보존 raw-XML splice.
- **DELEGATE (python-hwpx 위임 + 우리 툴로 노출)** — 문단/표/이미지/서식 편집, 문서 생성, XSD 검증, repair, render. 얇은 어댑터로 감싸 `hangeul_mcp` 툴로 제공. 위임 결과도 바이트보존/검증 게이트를 통과시킨다.
- 두 경로 모두 **두뇌·손 분리** 유지: 값·문안 *생성*은 클라이언트 LLM. 서버는 실행 도구.

## 실양식 테스트가 드러낸 것 (근거)

- **강사카드(.hwpx)** — 라벨:값 + inline-blank(∘/콜론). ✅ 완성.
- **교수학습·평가 계획(.hwp)** — 반복 템플릿 블록·중첩 채점기준표·체크박스(☑논술 □구술). COM 변환 데스크톱 전용 확인.
- **평가 운영 계획(.hwpx)** — 형광펜(markpen) placeholder 템플릿. → `analyze` markpen 미독 **버그 수정 완료**(itertext).

---

## Phase A (P0) — 양식 인식·채우기 심화 [OWN]

1. **형광펜(markpen) placeholder kind** — 강조 예시값을 필드로 탐지, markpen 안쪽만 치환·서식보존.
2. **체크박스 필드(☑/□) 탐지·선택** — 옵션 목록 인식, 지정 라벨 `□`→`☑`. `KIND_CHECKBOX` 구현.
3. **`{placeholder}` 전역 치환** — `{학교명}` 등, 표·중첩 포함. 바이트보존 splice.
4. **누름틀(form field) 헤드리스 fill** — HWPX 필드 이름 인식·채우기(COM 없이). `apply_to_open_hwp`와 스키마 공유.
5. **form-fit / 쪽수 드리프트 가드** — 셀·페이지 오버플로 감지, auto-fit(글꼴/자간 축소) 옵션. 프로토타입 `page_guard` 이식.
- 수용: 각 kind 골든/회귀 테스트, 바이트보존 유지, `analyze_form`/`fill_form` 스키마 확장.

## Phase B (P1) — 신뢰성·검증·읽기 [OWN + DELEGATE]

1. **XSD 스키마 검증 통합** — python-hwpx/OWPML XSD로 출력 검증. `validate_hwpx` 툴. (D1 미이행분)
2. **dry-run / 백업 / repair** — `fill(dry_run=True)`, 편집 전 원본 백업, `repair_hwpx`(안 열리는 파일 복구, DELEGATE).
3. **render_preview (HTML/PNG)** — 채운 결과 시각 확인(헤드리스 HTML/SVG 또는 COM/한컴독스 캡처). "정적검사≠렌더확인" 교훈.
4. **PII 마스킹 게이트(코드화)** — 주민번호·계좌 패턴 탐지·마스킹 옵션. SKILL 권고 → 실제 게이트.
5. **`.hwp` 헤드리스 읽기** — COM 없이 .hwp 텍스트/구조(pyhwp/hwp-rs 또는 kordoc 위임). 최소 detect+extract.
6. **읽기 확장(저비용)** — `get_document_outline`/`get_document_map`/`find_text`/`hwpx_to_html`/`list_styles` 툴.

## Phase C (P2) — 일반 편집 [DELEGATE: python-hwpx substrate]

python-hwpx를 얇게 감싸 Hangeul-mcp 툴로 노출(재발명 금지). 편집 후 XSD/바이트무결성 게이트 통과.

1. **텍스트/치환** — `search_and_replace`, `batch_replace`.
2. **문단** — `add_heading`/`add_paragraph`/`insert`/`delete`/`add_page_break`.
3. **표** — create/merge/split/format, add·remove rows·cols, `table_compute`(합계·평균).
4. **서식** — 글자(bold/italic/underline/color/size/font)·문단(정렬/줄간격/들여쓰기)·`create_custom_style`.
5. **객체** — 이미지 insert/replace, 도장/서명 배치, 머리말/꼬리말, 페이지 설정, 목차(TOC). (수식/차트/도형은 후순위)
- 수용: 각 편집 툴이 python-hwpx 위임 + 결과 검증 게이트 통과, 회귀 테스트.

## Phase D (P3) — 문서 생성 [DELEGATE + 우리 레시피]

1. **빌더/변환** — `create_document_from_plan`, markdown/text→HWPX (python-hwpx builder 위임).
2. **공식문서 레시피** — 기안문·보도자료·계획서·시험지(문제+답안) 템플릿 생성. 우리 템플릿 + 위임 조립.
3. **mail_merge** — CSV/JSON 대량 생성(우리 fill 엔진 + 레코드 반복).
- 원칙: 문안 *생성*은 클라이언트 LLM, 서버는 구조 조립·채우기만.

## 기술 부채 / 리팩터

- **fill 위치탐색 견고화**(codex 제안): 정규식 raw-XML 재스캔 → **Expat/SAX 기반 `section+table stack+cellAddr+byte-span` 인덱스**를 analyze에서 1회 구축, fill은 span만 splice.
- **occupancy grid를 fill에도** 적용(현재 understand만).
- 표 셀 넘치는 다행 inline 케이스 추가 테스트.

## 실행 순서 권장

Phase A(차별점) → Phase B(신뢰성) → Phase C(편집, python-hwpx 위임) → Phase D(생성).
A·B는 우리 코어라 먼저, C·D는 위임 어댑터라 병렬화 가능. 각 Phase는 `/ralplan`으로 PRD 분해 후 `/ralph` 구현.

## 이미 완료 (v0.1.0)

라벨:값 fill · inline-blank(마커/콜론) · 병합셀 2D occupancy · 멀티섹션 · 바이트보존 · 자간정규화 ·
MCP 서버(6툴) · 클라이언트무관 · `.hwp` COM 변환(데스크톱) · COM 라이브 스캐폴드 · markpen 텍스트 독해 수정 · codex QA 하드닝.

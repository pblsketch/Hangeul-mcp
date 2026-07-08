# ROADMAP — 다음에 개발/수정할 것

> v0.1.0 이후. 실양식 3종 테스트 발견 + 선행사례 갭([`gap-analysis.md`](gap-analysis.md)) 종합.
> 전략: breadth 경쟁 대신 **우리 차별점(양식 인식·채우기)을 깊게**. 편집/생성 breadth는 필요시 python-hwpx 위임.

## 실양식 테스트가 드러낸 것 (근거)

- **강사카드(.hwpx)** — 라벨:값 + inline-blank(∘/콜론). ✅ 완성.
- **교수학습·평가 계획(.hwp)** — 반복 템플릿 블록·중첩 채점기준표·체크박스(☑논술 □구술). COM 변환은 데스크톱 전용(샌드박스 불가) 확인.
- **평가 운영 계획(.hwpx)** — 형광펜(markpen) placeholder 템플릿. → `analyze` markpen 텍스트 미독 **버그 발견·수정 완료**(itertext). 채울 대상이 "빈 칸"이 아니라 "강조된 예시값"인 새 패턴.

---

## P0 — 차별점 심화 (양식 인식·채우기의 실양식 갭)

### P0-1. 형광펜(markpen) placeholder 필드 kind
- 문제: 실 템플릿은 예시값을 노란 형광펜으로 감싸 두고 사용자가 교체. 우리는 "빈 셀"만 채움.
- 작업: `inline.py`/새 모듈에 markpen-감싼 텍스트를 `kind="placeholder"` 필드로 탐지(라벨=강조 텍스트 또는 인접 헤더). `fill`은 markpen **안쪽 텍스트만 치환**하고 형광펜 태그·서식 보존.
- 수용: 형광펜 placeholder를 필드로 인식, 교체 시 markpen 유지·바이트보존, 회귀 테스트.

### P0-2. 체크박스 필드(☑/□) 탐지·선택
- 문제: `☑ 논술 □ 구술·발표 □ 토의·토론` 형태. `KIND_CHECKBOX` 정의만 있고 미구현.
- 작업: `□`/`☑`/`■`/`○` 토큰과 라벨 페어 탐지 → 필드화. `fill`은 지정 라벨의 `□`→`☑`(또는 역) 치환. 다중 선택/단일 선택 옵션.
- 수용: 체크박스 옵션 목록 인식, 선택 반영, 회귀 테스트.

### P0-3. {placeholder} 전역 치환
- 문제: `{학교명}`,`{담당자}` 템플릿 변수(표·중첩 포함). 선행사례 공통 기능인데 우리 없음.
- 작업: `fill`에 `{키}` 패턴 전역 치환 모드(모든 섹션·중첩 셀). 바이트보존 splice 재사용.
- 수용: 표/중첩 안 `{키}`까지 치환, 미매칭 `skipped` 리포트.

### P0-4. 누름틀(form field) 헤드리스 fill
- 문제: 우리는 COM `put_field_text`만. HWPX의 `hp:ctrl`/필드(누름틀) 이름 기반 헤드리스 채우기 없음.
- 작업: `analyze`가 누름틀(field name) 인식 → `fill`이 이름 매칭 채우기(COM 없이). airmang `fill_by_path` 개념.
- 수용: 누름틀 있는 HWPX에서 이름 기반 채우기, `apply_to_open_hwp`와 동일 필드 스키마 공유.

### P0-5. form-fit / 쪽수 드리프트 가드
- 문제: 긴 값이 셀·페이지를 넘쳐 레이아웃 깨짐. 선행사례는 auto-fit font shrink.
- 작업: 채운 값이 셀 폭 초과 시 (a) 경고, (b) 옵션으로 글꼴/자간 축소. 프로토타입 `page_guard` 철학 이식.
- 수용: 셀 오버플로 감지, shrink 옵션 동작, 쪽수 비교 테스트.

## P1 — 신뢰성·검증 기반

### P1-1. XSD 스키마 검증 통합 (D1 미이행분)
- python-hwpx(또는 OWPML XSD)로 출력 검증 게이트. `validate_hwpx` MCP 툴 노출.

### P1-2. dry-run / 백업 / 복구
- `fill(dry_run=True)`(변경 계획만), 편집 전 원본 백업, `repair_hwpx`(안 열리는 파일 복구).

### P1-3. render_preview (HTML/PNG)
- 채운 결과 시각 확인. 헤드리스 SVG/HTML 렌더 또는 COM/한컴독스 캡처. (교훈: 정적 검사≠렌더 확인)

### P1-4. PII 마스킹 게이트 (코드화)
- 주민번호·계좌 패턴 탐지·마스킹 옵션. 현재 SKILL.md 권고만 → 실제 게이트.

### P1-5. .hwp 헤드리스 읽기
- COM 없이 .hwp 바이너리 텍스트/구조 읽기(pyhwp/hwp-rs 또는 kordoc 위임). 최소 `detect+extract_text`까지.

## P2 — 저비용 읽기 확장 & 선택적 breadth

- **읽기**: `get_document_outline`/`get_document_map`/`find_text`/`hwpx_to_html`/`list_styles` MCP 툴.
- **편집/생성(선택)**: search_and_replace, 문단/표 편집, 문서 생성(기안문/계획서). → **python-hwpx substrate 위임** 검토(재발명 금지, D1 일치). 우리 코어는 인식·채우기 유지.

## 기술 부채 / 리팩터

- **fill 위치탐색 견고화** (codex QA 제안): 정규식 raw-XML 재스캔 → **Expat/SAX 기반 `section+table stack+cellAddr+byte-span` 인덱스**를 analyze 단계에서 1회 구축, fill은 span만 splice. 성능·정확도·유지보수성 개선.
- **occupancy grid를 fill에도** 적용(현재 understand만). 병합 covered 좌표 채우기 일관성.
- **inline 값에 raw 개행 방지** 이미 처리했으나, 표 셀 넘치는 다행 inline 케이스 추가 테스트.

## 이미 완료 (v0.1.0)

라벨:값 fill · inline-blank(마커/콜론) · 병합셀 2D · 멀티섹션 · 바이트보존 · 자간정규화 · MCP 서버(6툴) · 클라이언트무관 · .hwp COM 변환(데스크톱) · COM 라이브 스캐폴드 · markpen 텍스트 독해 수정 · codex QA 하드닝.

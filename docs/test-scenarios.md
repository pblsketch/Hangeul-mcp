# 테스트 시나리오 — Hangeul-mcp 수동 인수 테스트

> 자동 스위트(`pytest -q`, 214 passed/1 skipped)가 코드 레벨을 검증한다면, 이 문서는
> **MCP 클라이언트(Claude Desktop/Codex 등)에서 실제 사용자가 겪는 흐름**과
> **자동화가 불가능한 데스크톱 라이브 경로**를 사람 손으로 검증하기 위한 시나리오다.
> 각 시나리오는 전제 → 단계 → 기대 결과(관측 가능) → 증거 캡처 순으로 기술한다.

## 0. 공통 준비

### 설치 매트릭스 (시나리오 그룹별 요구 extra)

| 프로파일 | 설치 | 검증 대상 그룹 |
|---|---|---|
| P0 코어 | `pip install -e ".[dev]"` | A(파일 모드), E(폴백) |
| P1 위임 | P0 + `pip install -e ".[delegate]"` | B(위임 편집/생성) |
| P2 렌더 | P1 + `pip install -e ".[render]"` + `python -m playwright install chromium` | C(렌더) |
| P3 라이브 | P2 + `pip install -e ".[live]"` (Windows + 한글 필수) | D(라이브) |

### 공통 규칙

- 입력은 항상 `tests/fixtures/sample_form.hwpx`(PII 없는 빈 강사카드)의 **사본**을 사용한다. 원본 fixture를 덮어쓰지 않는다.
- 실측된 fixture 필드(시나리오에서 그대로 사용):
  - empty_cell: `소속` `직위` `성명` `주민등록번호` `근무처` `휴대전화` `전자우편` `강의일시`
  - inline_blank: `은행명:` `계좌번호:`(같은 셀 내 콜론 2개), `∘ 프로그램명` `∘ 강의주제` `∘ 학 력` `∘ 경 력`(마커)
  - checkbox: `개인정보 수집·이용 동의`(예/아니요), `사진·영상 촬영 및 활용 동의`(예/아니요)
- MCP 클라이언트에서 실행 시: 클라이언트에 자연어로 지시하고("이 양식 분석해서 성명=홍길동으로 채워줘"), 클라이언트가 실제로 어떤 툴을 호출했는지 확인한다. 직접 호출로 재현할 때는 아래 표기된 툴/인자를 쓴다.
- **판정 원칙**: "에러가 없다"가 아니라 **관측 가능한 결과**(반환 JSON 필드, 산출 파일, XML 속성)로 판정한다.

---

## A. 파일 모드 핵심 (P0)

### TS-A1. capability 자기소개
- 단계: `describe_capabilities()`
- 기대: `server_side_llm: false` · `capabilities[]`에 file_hwpx(available:true), delegate/render/live는 **설치 상태와 일치하는** available 값 · `mode: "byo_ai_local_harness"`
- 증거: 반환 JSON 저장

### TS-A2. 양식 인식
- 단계: `analyze_form(사본경로)`
- 기대: 필드 21개 내외 — empty_cell 8 · inline_blank 10 · checkbox 3(옵션 목록 포함). `성명`의 field_id가 `t2.r2.c3` 형식의 셀 주소
- 증거: kind별 개수, 필드 목록

### TS-A3. 채우기 — 세 kind 동시
- 단계: `fill_form(사본, values, out.hwpx)`
  ```json
  {"성명": "홍길동", "직위": "교사", "은행명": "농협", "계좌번호": "123-456",
   "프로그램명": "AI 활용 연수", "개인정보 수집·이용 동의": "예"}
  ```
- 기대: `filled` 6건, `skipped` 0건 · out.hwpx가 한글(또는 hwpx_to_html)에서 열리고 각 값이 **정확한 위치**에 있음: 성명 셀, `은행명: 농협 계좌번호: 123-456`(콜론 뒤 삽입), `∘ AI 활용 연수`(마커 뒤·마커 중복 없음), 동의 항목 `예`에 ☑ + `아니요`는 □ 유지(exclusive)
- 증거: 반환 JSON + 열람 스크린샷(또는 `verify_fill` 결과)

### TS-A4. dry-run은 쓰지 않는다
- 단계: TS-A3와 동일하되 `dry_run=true`, out 경로는 **존재하지 않는 새 이름**
- 기대: 반환 `filled`는 동일하게 계산되지만 **out 파일이 생성되지 않음**, `out_path: null`
- 증거: 파일 부재 확인(ls)

### TS-A5. 검증 체인
- 단계: TS-A3의 out에 대해 `verify_fill(out, 같은 values)` → `validate_hwpx(out)`
- 기대: verify `present`에 6개 키 전부, `missing: []` · validate `valid: true` (xsd는 python-hwpx 설치 시 함께 보고)
- 증거: 두 JSON

### TS-A6. 바이트보존 확인 (스모크)
- 단계: `python scripts/e2e_evidence.py`
- 기대: `{"ok": true, "failures": []}` · `build/evidence/06_byte_preservation.json`의 changed_entries가 `Contents/section*.xml`뿐
- 증거: build/evidence/ 산출물 일체

### TS-A7. PII 경고와 마스킹
- 단계: ① `fill_form(사본, {"주민등록번호": "900101-1234567"}, out1)` — mask 없이
  ② 같은 값으로 `mask_pii=true`, out2 ③ `scan_pii(out1)` / `scan_pii(out2)`
- 기대: ① `pii_warnings`에 rrn 유형 경고(**mask 여부와 무관하게 항상 경고**) ② `masked` 1건, out2의 값은 `900101-*******` 형태 ③ out1은 count≥1, out2는 rrn 미검출
- 증거: 세 JSON

### TS-A8. 셀 넘침 경고
- 단계: `analyze_formfit(사본, {"성명": "매우 긴 이름을 일부러 넣어 셀 폭을 초과시키는 문자열"})`
- 기대: 해당 셀에 대한 overflow 경고(ratio>1.0). **휴리스틱 추정치**이므로 경고 존재만 판정(픽셀 정확도 아님)
- 증거: warnings JSON

### TS-A9. mail_merge 대량 생성
- 단계: `mail_merge(사본, [{"성명":"A"},{"성명":"B"},{"성명":"C"}], out_dir)`
- 기대: 번호 매긴 hwpx 3개 생성, 각각 verify_fill로 해당 성명 present
- 증거: 산출 파일 목록 + 1건 verify

---

## B. 위임 편집/생성 (P1 — python-hwpx ≥2.24)

### TS-B1. 미설치 폴백 (P0 환경에서 먼저)
- 단계: P0 프로파일에서 `hwpx_to_html(사본)` 호출
- 기대: 크래시 없이 `{"available": false, "error": "...extra 'delegate'..."}`
- 증거: 반환 JSON

### TS-B2. 머리말/꼬리말
- 단계: `set_header(사본, "2026 연수 운영", out)` → `set_footer(out, "교육청", out2)`
- 기대: 두 호출 모두 `ok:true` · out2를 한글로 열면 머리말/꼬리말 표시(또는 패키지 XML에 텍스트 존재)
- 증거: 열람 스크린샷 또는 XML grep

### TS-B3. 페이지 설정
- 단계: `set_page_margins(사본, out, left=8504, right=8504)`(≈30mm) → `set_page_number(out, out2)`
- 기대: `ok:true` · out2 열람 시 여백 변화 + 하단 중앙 쪽번호. 음수 여백(`left=-1`이 아닌 core 직접 호출 시 음수)은 `ok:false` + 파일 미생성
- 증거: 열람 스크린샷, 에러 JSON

### TS-B4. 병합셀 분할 — 비병합 거부 포함
- 단계: ① `create_hwpx_table([[...3x3...]], base)` → `merge_table_cells(base, 0, "A1:B2", merged)` → `split_merged_cell(merged, 0, 0, 0, out)`
  ② 비병합 표에 `split_merged_cell(base, 0, 0, 0, x)`
- 기대: ① `ok:true`, 열람 시 병합 해제 ② **`ok:false` + "not merged" 에러**(조용한 no-op 금지 — 이 거부가 우리 래퍼의 추가 가치)
- 증거: 두 JSON

### TS-B5. 문서 생성 레시피
- 단계: `create_official_document({"제목":"연수 안내","수신":"각급학교장","본문":"..."}, out, doc_type="공문")`
- 기대: `ok:true` · 열람 시 공문 골격 + **본문 내용은 전부 내가 준 값**(서버가 문안을 지어내지 않음 — D6 경계 확인)
- 증거: 열람 스크린샷

---

## C. 렌더 (P2)

### TS-C1. PNG 미리보기
- 단계: `render_preview(TS-A3의 out, preview.png)`
- 기대: P2 환경 — `ok:true` + PNG 시그니처/치수(기본 1280×1800), 채운 값이 이미지에 보임. P0/P1 환경 — `available:false`(이것이 **정상 관측**이며 실패가 아님)
- 증거: preview.png 또는 폴백 JSON

---

## D. 라이브 데스크톱 (P3 — Windows + 한글, 수동 전용)

> 자동화 불가 영역. 완료 시 [PENDING_DESKTOP_LIVE_QA.md](../PENDING_DESKTOP_LIVE_QA.md)를 닫는 증거가 된다.
> 절차 상세는 [live-qa-runbook.md](live-qa-runbook.md).

### TS-D1. 부작용 없음 확인 (한글을 켜기 전에)
- 단계: 한글이 **실행되지 않은 상태**에서 `hwp_status()` → `preview_cells_to_open_hwp(사본, {"성명":"홍길동","직위":"교사"})`
- 기대: 두 호출 후에도 **한글 프로세스가 뜨지 않음**(작업관리자 확인) · status `connected:false` · preview `count:2`, targets = 성명→t2.r2.c3, 직위→t2.r2.c2
- 증거: 반환 JSON + 프로세스 목록

### TS-D2. 라이브 셀 채우기 (핵심 미검증 경로)
- 전제: 한글에서 fixture **사본**을 열어둔 상태
- 단계: `hwp_status()` → `preview_cells_to_open_hwp(...)` → `apply_cells_to_open_hwp(사본경로, {"성명":"홍길동","직위":"교사"})`
- 기대: status `connected:true`(버전·문서 수 포함) · apply `applied` 2건 == preview `count` · **열린 창에서 성명/직위 셀에 값이 즉시 보이고 창이 닫히지 않음** · 저장 전 Ctrl+Z로 복구 가능
- 증거: status/apply JSON 전문, 채워진 창 스크린샷 → **이 증거로 US-029 승격 + PENDING 문서 삭제**

### TS-D3. D7 경계 — 중첩 표 문서
- 전제: 중첩 표가 있는 임의 양식(PII 없는 것)을 열어둠
- 단계: preview로 target 확인 → 의심스러우면 `clear=false`로 apply
- 기대: preview target과 실제 삽입 위치가 일치하면 pass. **불일치가 관찰되면 그 자체가 유효한 결과** — D7에 기록된 best-effort 한계의 실증이므로 문서/스크린샷으로 캡처해 이슈화
- 증거: 불일치 시 before/after 스크린샷

### TS-D4. 누름틀 원샷 반영
- 전제: 누름틀(양식 필드)이 있는 문서를 열어둠 (fixture에는 누름틀 없음 — 별도 문서 필요)
- 단계: `apply_to_open_hwp({"필드명": "값"})`
- 기대: 누름틀 있음 — `applied`에 반영. 누름틀 없음 — `needs_field_registration: true` + cell 방식 안내
- 증거: 반환 JSON

---

## E. 폴백/에러 경로 (P0)

| ID | 단계 | 기대 (관측 가능) |
|---|---|---|
| TS-E1 | `extract_hwp_text(아무.hwp)` | `available:false` + 후보 모듈 점검 결과(`checked`) — COM 변환으로 위장하지 않음 |
| TS-E2 | `detect_format(없는파일.hwpx)` | `{"format":"unknown","ok":false,"reason":"file not found"}` — 크래시 없음 |
| TS-E3 | `fill_form(사본, {"없는라벨XYZ":"v"}, out)` | `skipped: [{"key":"없는라벨XYZ","reason":"no matching field"}]`, filled는 영향 없음 |
| TS-E4 | `.hwp` 파일을 `analyze_form`에 입력 (한글 미설치 환경) | 구조화 에러(변환 백엔드 부재 안내) — 예외 아님 |
| TS-E5 | `preview_cells_to_open_hwp(x.hwp, ...)` | `ok:false` + ".hwpx만 허용" 안내 (side-effect-free 유지) |

---

## F. 회귀 게이트 (모든 수동 세션의 시작과 끝)

```powershell
./.venv/Scripts/python.exe -m pytest -q            # 기대: 214 passed, 1 skipped
./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests
./.venv/Scripts/python.exe scripts/e2e_evidence.py  # 기대: {"ok": true}
```

---

## 결과 기록 템플릿

| ID | 일시 | 환경(프로파일/OS/한글버전) | 결과(P/F) | 증거 경로 | 비고 |
|---|---|---|---|---|---|
| TS-A1 | | | | | |
| … | | | | | |

> 기록 원칙: **F(실패)도 산출물이다.** 특히 TS-D3의 매핑 불일치, TS-A8의 오탐/미탐은
> 각각 D7 재설계와 formfit 보정의 입력이 되므로 재현 절차와 함께 남긴다.

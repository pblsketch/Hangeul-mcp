# PENDING: 데스크톱 라이브 QA (US-029 / US-053)

> **상태의 진실**: 라이브 셀 채우기(`apply_cells_to_open_hwp`)와 누름틀 원샷 반영(`apply_to_open_hwp`)은
> **코드·순수부 테스트 완료, 실기기(열린 한글 창) 증거 미확보**다. 이 문서가 존재하는 동안
> `docs/prd.json`의 US-029는 complete로 승격하지 않는다.

## 이번 안정화 패스에서 관측한 것 (2026-07-10, 헤드리스 세션 — side-effect-free 경로만)

```json
hwp_status()                       -> {"available": true, "connected": false}
preview_cells_to_open_hwp(fixture) -> {"available": true, "live_available": false, "count": 2, "skipped": []}
targets                            -> 성명 → t2.r2.c3, 직위 → t2.r2.c2
```

- `available:true` = Windows + pywin32 존재(COM *가능* 환경). `connected:false` = 어떤 한글 창에도 접속하지 않았음(부작용 없음 확인).
- `live_available:false` = pyhwpx(extra `live`) 미설치 — 이 세션에서는 apply가 구조화 폴백으로만 동작.
- pure 타깃 해석은 COM 없이 정확히 동작(위 targets). 라이브 apply만 미검증으로 남는다.

## 실기기 라이브 관측 (2026-07-10 오후, 데스크톱 세션 — Hwp 창 열린 상태)

실제 사용 중 라이브 실패 리포트("라이브로 입력이 안 돼")를 계기로 이 머신에서 실측한 결과.

**1) 사용자가 손으로 연 한글 창에는 어떤 COM 클라이언트도 붙지 못한다 (전제 반증)**

- 열린 창: `Hwp.exe`(sample_form1.hwpx) + 자식 `HwpApi.exe`(부모=Hwp, 창 없음).
- ROT 열거 결과 `!HwpObject.*` 모니커는 **1개뿐이며 빈 문서(FullName='')를 가진 HwpApi 인스턴스** — 사용자가 연 창 자체는 ROT에 미등록.
- 따라서 `apply_to_open_hwp`(EnsureDispatch)와 `apply_cells_to_open_hwp`(pyhwpx ROT 스캔) 모두
  **빈 자동화 인스턴스에 `connected:true`로 붙는다** → 각각 `needs_field_registration`,
  `table not found live`로 귀결. connected:true가 "사용자의 창"을 의미하지 않음(오해 유발 지점).

**2) 자동화 인스턴스가 연 visible 창에서는 전체 경로 성공 (핵심 경로 실증)**

```json
open(사본)                     -> ok, active = sample_form1_live.hwpx (visible 창)
preview_cells_to_open_hwp     -> {"live_available": true, "count": 1, targets: 성명 → t2.r2.c3}
apply_cells_to_open_hwp       -> {"available": true, "connected": true, "applied": 1, "skipped": [], "count": 1}
read-back (별도 fresh 연결)    -> t2(=get_into_nth_table(1)) r2c3 셀 텍스트 == "홍길동"
```

- D7 매핑: analyze 전역 표 인덱스(t2) == pyhwpx 컨트롤 순서(index 1) — 표 7개짜리 이 문서에서 일치 확인(1건).
- 창은 닫히지 않고 미저장 상태 유지(Ctrl+Z 가능) — 라이브 UX 요건 충족.

**3) `live` extra 함정: pyhwpx 1.7.2는 numpy/pandas/pyperclip/pillow를 의존성으로 선언하지 않는다**

- pyhwpx 설치됨 + import 실패(ModuleNotFoundError 연쇄) → `live_available:false`로 위장됨.
- 이 머신에서는 4개 수동 설치로 해소(pytest 217 passed로 회귀 확인). **pyproject `live` extra에 명시 필요.**

**귀결(구현 반영됨 — US-062/US-063, 2026-07-10)**: "열려 있는 창에 붙는다"는 전제는 이 머신에서
불가로 관측되어, 라이브 UX를 **서버(자동화 인스턴스)가 문서를 열고 그 창에서 채우는 흐름**으로
재정의해 구현했다:

- `open_in_hwp(path)` 툴 신설(라이브 진입점, 저장·닫기 없음)
- `apply_cells_to_open_hwp`가 활성 문서==path 검증, 불일치 시 `open_if_needed`(기본 true) 자동 open
  — 무관 문서 오염 방지. 거절 시 `active_document` 포함 구조화 응답
- `hwp_status`가 ROT `instances`(모니커/문서수/활성문서)와 `attach_boundary`를 노출
- `live` extra가 pyhwpx 미선언 의존성(numpy/pandas/pyperclip/pillow)을 명시

**재정의 경로 실기기 증거(2026-07-10)**: `open_in_hwp(사본A)` → opened:true, active==A ·
타 문서 활성 상태에서 `apply_cells_to_open_hwp(사본B, {성명:홍길동})` → 자동 open + applied 1건 ·
fresh 연결 read-back == "홍길동". US-029(원래 시나리오: 사용자가 연 창) 승격 여부는 아래 미확보
증거와 함께 별도 판단한다 — 사용자가 연 창 자체는 접근 불가가 결론이므로, runbook 절차는
`open_in_hwp` 기반으로 수행한다.

## 라이브 확장 실기기 관측 (2026-07-11, 데스크톱 세션)

사용자 실사용 흐름(Claude Desktop)에서 두 가지가 드러나 구현·실증했다.

**A) 콜드 스타트 = "멈춤"이 아니다 (US-064)**
- 한글이 꺼진 상태의 첫 `open_in_hwp`는 한글 기동까지 포함해 수십 초 걸려 클라이언트에서 "멈춘 것처럼" 보였다.
- 응답에 `cold_start`/`elapsed_seconds`를 넣고 툴 설명·`hwp_status.first_call_hint`에 경고를 명시.
- 라이브 호출 동안 `SetMessageBoxMode(0x2FFF1)`로 모달 대화상자를 자동응답(finally 복원) — 보이지 않는 확인창에 매달리는 무한 대기 차단.

**B) 인라인 빈칸 라이브 채우기 (US-065) — 셀 클리어 방식이 핵심이었다**
- 콜론(`은행명:`)·마커(`∘ 프로그램명`)·체크박스는 라벨이 셀 텍스트 안에 있어, empty_cell처럼 clear+insert하면 안 된다.
- 파일 fill 엔진을 임시 산출에 돌려 셀별 최종 텍스트를 얻고(미러), 변경 셀만 라이브에서 전체 텍스트 대체.
- **실측 함정**: `goto_addr(select_cell=True)` + `Delete`(셀 객체 블록)는 원문 문단을 남긴다 → read-back에 값+원문 중복.
  `MoveListBegin` → `MoveSelListEnd`(셀 내용 리스트 텍스트 선택) → `Delete`로 교체해 해결.
- 증거: `apply_cells_to_open_hwp(사본, {은행명·계좌번호·프로그램명·강의주제·학력·경력})` → applied 5건, skipped 0,
  read-back `t2.r3.c1` == `" 은행명: 농협   계좌번호: 123-456-7890      "`(중복 없음).
- 경계(명시): 인라인 라이브는 셀 전체 텍스트를 재작성하므로 셀 내 리치서식이 평탄화된다. 서식 보존이 필요하면 파일 모드.

## 본문/라이브 QA 결함 수정 패스 (2026-07-11, FIX-FIRST — codex 독립 QA)

독립 QA(FIX-FIRST)가 실측 확인한 결함 5건을 수정하고 각 결함에 재현 테스트를 추가했다
(수정 전 red → 후 green, 전체 `pytest -q` = 249 passed / 1 skipped).

- **P1/HIGH-3** (`body.py`, 순수·헤드리스 검증 완료): 엔티티(`&amp; &lt; &gt;`)가 든 마커
  prefix를 **디코딩 길이**로 splice해 raw `<hp:t>`의 엔티티를 절단 → malformed XML.
  prefix 길이를 raw(`_esc`) 단위로 넘겨 해결. 회귀: `test_splice_*`(왕복 + `ET.fromstring` 통과).
- **P4/MEDIUM-8** (`body.py`, 순수·헤드리스 검증 완료): 유니코드 범주 단독 판정 → `:`/`-` 오탐,
  로마숫자/원문자/`(1)` 미탐. **마커 문법**(불릿·대시·참조표·번호마커 + 뒤 구분자 요구, prose
  구두점 제외)으로 교체. 회귀: `test_marker_prefix_*`. 정부 fixture □○―※ 탐지 유지.
- **P5/HIGH-4** (`fill.py`, 순수·헤드리스 검증 완료): 선행 placeholder/markpen/누름틀 패스가
  본문 문단을 비우면 `replace_body_paragraph`의 비어있지-않은 ordinal이 시프트. 본문 패스를
  section-wide 패스보다 **먼저** 적용해 원본 좌표(b_index)와 일치. 회귀: 빈 `ph:x`+`b1` 동시 fill.
- **P2/CRITICAL-2** (`hwp/live_body.py`, **fake-COM 단위검증 · 실기기 미확보**): 본문 라이브 채우기가
  `set_pos` 실패를 무시하고 `Delete`해 직전 문단 파괴 가능. `set_pos` 반환 검사 + **compare-before-write**
  (삭제 전 문단 재독해 → template 불일치 시 skip) 추가. 회귀: `tests/test_live_body.py`(실패 주입 시 Delete 미호출).
- **P3/CRITICAL-1** (`hwp/live.py`, **fake-COM 단위검증 · 실기기 미확보**): 자동 `open` 후 활성문서를
  재확인하지 않고 편집 → open이 True여도 활성이 안 바뀌면 무관 문서 오염. open 직후 `Active…FullName`을
  다시 읽어 `same_doc` 강제, 불일치면 편집 없이 구조화 거절. `open_in_hwp`도 `ok = opened and same_doc`.
  회귀: `tests/test_live_open.py`(open→True·활성불변 시 편집 없이 `ok:false`).

**실기기(Windows+한글) 미확보 — 이 패스에서 캡처해야 할 증거**:
1. `open_in_hwp(사본)` → `apply_cells_to_open_hwp(사본, {b_n: 값})` 본문 채우기 → fresh read-back 정확
2. 실패 주입(존재하지 않는 문단/변경된 문단)에서 파괴적 편집이 일어나지 않고 skip으로 귀결
3. P3: 타 문서 활성 상태에서 auto-open 후 active==path 확인되어야만 편집 진행

## 미확보 증거 (이 문서를 닫는 조건)

[`docs/live-qa-runbook.md`](docs/live-qa-runbook.md) 절차로 다음을 캡처하면 이 문서를 삭제하고
US-029/US-053 상태를 갱신한다:

1. 한글 창에 fixture 사본을 연 상태의 `hwp_status()` — `connected:true`, 버전, 문서 수
2. `apply_cells_to_open_hwp` 의 `applied[]`/`skipped[]`/count (preview target 수와 대조)
3. COM 에러 텍스트(있다면)
4. 채워진 창의 스크린샷 또는 저장본(PII 없는 fixture 사본만)

필요 환경: Windows + 한컴오피스 설치 + `pip install -e ".[live]"` + 대화형 세션(Claude Desktop 등).
pytest 라이브 레인: `$env:HANGEUL_MCP_LIVE=1; python -m pytest tests/test_com.py tests/test_live_resolve.py -q`

## D7 경계 재확인 (best-effort)

`apply_cells_to_open`은 analyze의 전역 표 인덱스 == pyhwpx `get_into_nth_table` 컨트롤 순서를
가정한다. **단일/최상위 표 양식에서만 성립 확인**되었으며 중첩 표·복잡 병합 문서에서는 어긋날 수
있다. 실기기 검증 전까지 라이브 셀 채우기는 best-effort로 표기하고, apply 전 preview 확인을
필수 절차로 유지한다.

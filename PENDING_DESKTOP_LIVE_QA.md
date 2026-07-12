# PENDING: 데스크톱 라이브 QA (US-029 / US-053)

> **상태의 진실**: raw probe/json과 2026-07-11 Windows Shell-open 최소 쓰기 실증은 safe-attach의 **resolver-path 존재 및 Shell-open 기존 문서 write/read-back 성공**을 보여 준다.
> 하지만 사람의 실제 Explorer 더블클릭 조건에서의 literal write-safe 증거는 아직 미확보다.
> 이 문서는 earlier failed generic-reconnect 맥락과 마지막 데스크톱 QA gate를 함께 보존한다. 이 문서가 존재하는 동안 `docs/prd.json`의 live stories(`apply_to_open_hwp`, `apply_cells_to_open_hwp`, saved `.hwpx` current-document pathless UX)는 complete로 승격하지 않는다.

## 2026-07-11 Windows Shell-open 최소 쓰기 실증

PII 없는 사본 `build/evidence/sample_form_hand_opened_live_qa.hwpx`를 COM이 아닌 Windows Shell `Start-Process`로 열었다.

```json
{
  "apply_state": "attached_existing",
  "open_if_needed": false,
  "values": {"성명": "홍길동", "직위": "교사"},
  "fresh_readback": {"contains_name": true, "contains_position": true},
  "success": true
}
```

- `open_if_needed=false`였으므로 apply 코드가 새 문서를 열어 만든 성공이 아니다.
- 별도 `Hwp(new=False)` fresh 연결의 `GetTextFile("TEXT", "")`에서 두 값을 다시 확인했다.
- 원자료: `docs/evidence/shell-open-live-write-qa.json`
- 한계: 실제 마우스 더블클릭이 아니라 같은 Windows 파일 연결을 이용한 Shell `Start-Process`였다.

## 이번 안정화 패스에서 관측한 것 (2026-07-10, 헤드리스 세션 — side-effect-free 경로만)

```json
hwp_status()                       -> {"available": true, "connected": false}
preview_cells_to_open_hwp(fixture) -> {"available": true, "live_available": false, "count": 2, "skipped": [], "attach_metadata": "resolver-path exists"}
targets                            -> 성명 → t2.r2.c3, 직위 → t2.r2.c2
```

- `available:true` = Windows + pywin32 존재(COM *가능* 환경). `connected:false` = 어떤 한글 창에도 접속하지 않았음(부작용 없음 확인).
- `live_available:false` = pyhwpx(extra `live`) 미설치 — 이 세션에서는 apply가 구조화 폴백으로만 동작.
- pure 타깃 해석과 attach metadata는 COM 쓰기 없이 정확히 동작(위 targets). **이것이 증명하는 것은 resolver-path 존재까지**이며, 라이브 apply의 write safety는 별도 미검증으로 남는다.

## 보수적 Batch A / 조건부 Batch B (감사용 고정 구분)

- **Batch A — 지금 승인된 범위**
  1. `connected:false`는 정상 idle pre-attach 상태다.
  2. 라이브 사용 안내는 **exact-path attach-first**여야 하고, named field 쓰기는 `open_in_hwp(path)` 뒤 `apply_to_open_hwp(path, values)` 또는 attach metadata가 이미 확보된 same-doc 조건에서의 동등한 exact-path 경로로 설명해야 한다.

  3. 서버가 연 문서 / exact-path가 확인된 active 문서에 대한 보수적 진입 정책과 preview attach metadata 노출은 구현·문서화 사실로 본다.
- **Batch B — 아직 조건부인 범위**
  1. 손으로 연 창까지 포함한 exact-path attach의 literal write-safe 승격.
  2. 추가 Windows 데스크톱 live-QA 캡처 없이 라이브 경로를 "충분히 증명됨"으로 승격하는 서술.

따라서 이 문서는 **Windows live-QA 공백을 숨기지 않고 유지**한다. Batch B 증거가 새로 캡처되기 전까지 README/PLAN/SKILL은 Batch A까지만 확정 사실로 간주한다.

## 실기기 라이브 관측 (2026-07-10 오후, 데스크톱 세션 — Hwp 창 열린 상태)

실제 사용 중 라이브 실패 리포트("라이브로 입력이 안 돼")를 계기로 이 머신에서 실측한 결과.

**1) 초기 실패는 '손으로 연 창이 원천적으로 unattainable'의 증거가 아니라, generic reconnect가 잘못된 증거였음을 보여 준다**

- 열린 창: `Hwp.exe`(sample_form1.hwpx) + 자식 `HwpApi.exe`(부모=Hwp, 창 없음).
- 당시 generic reconnect에서 본 ROT 결과 `!HwpObject.*` 모니커는 **1개뿐이며 빈 문서(FullName='')를 가진 HwpApi 인스턴스**였다.
- 따라서 당시 `apply_to_open_hwp`(EnsureDispatch)와 `apply_cells_to_open_hwp`(pyhwpx ROT 스캔)는 **빈 자동화 인스턴스에 `connected:true`로 붙는 오판**을 만들었고, 각각 `needs_field_registration`, `table not found live`로 귀결했다. 결론은 "손으로 연 창은 절대 불가"가 아니라 **generic reconnect/`connected:true`만으로는 같은 문서 증명이 안 된다**는 것이다.

**2) exact-path로 식별된 문서에서는 경로 자체가 성립한다 (resolver-path / 재정의 경로 실증)**

```json
open(사본)                     -> ok, active = sample_form1_live.hwpx (visible 창)
preview_cells_to_open_hwp     -> {"live_available": true, "count": 1, attach_metadata: "exact-path", targets: 성명 → t2.r2.c3}
apply_cells_to_open_hwp       -> {"available": true, "connected": true, "applied": 1, "skipped": [], "count": 1}
read-back (별도 fresh 연결)    -> t2(=get_into_nth_table(1)) r2c3 셀 텍스트 == "홍길동"
```

- D7 매핑: analyze 전역 표 인덱스(t2) == pyhwpx 컨트롤 순서(index 1) — 표 7개짜리 이 문서에서 일치 확인(1건).
- 창은 닫히지 않고 미저장 상태 유지(Ctrl+Z 가능) — 라이브 UX 요건 충족.

**3) `live` extra 함정: pyhwpx 1.7.2는 numpy/pandas/pyperclip/pillow를 의존성으로 선언하지 않는다**

- pyhwpx 설치됨 + import 실패(ModuleNotFoundError 연쇄) → `live_available:false`로 위장됨.
- 이 머신에서는 4개 수동 설치로 해소(pytest 217 passed로 회귀 확인). **pyproject `live` extra에 명시 필요.**

**귀결(구현 반영됨 — US-062/US-063, 2026-07-10)**: 증거 기준을 "generic reconnect"에서 **exact-path resolver-path + 별도 write-safe QA**로 재정의했다. 재현성이 가장 높은 흐름은 여전히 서버(자동화 인스턴스)가 문서를 열고 그 창에서 채우는 경로다:

- `open_in_hwp(path)` 툴 신설(라이브 진입점, 저장·닫기 없음; 이미 같은 문서면 `attached_existing` 상태가 핵심)
- `apply_cells_to_open_hwp`가 활성 문서==path 검증, 불일치 시 `open_if_needed`(기본 true) 자동 open
  — 무관 문서 오염 방지. 거절 시 `active_document` 포함 구조화 응답
- pathful `apply_to_open_hwp(path, values)`는 broker-targeted exact-path live apply이고, Batch A named-field 증거는 이 경로 또는 동등한 exact-path same-doc 경로의 실제 write/read-back으로 본다
- `preview_cells_to_open_hwp`가 `targets`뿐 아니라 attach metadata를 노출
- `hwp_status`가 ROT `instances`(모니커/문서수/활성문서)와 `attach_boundary`를 노출
- `live` extra가 pyhwpx 미선언 의존성(numpy/pandas/pyperclip/pillow)을 명시

**재정의 경로 실기기 증거(2026-07-10)**: `open_in_hwp(사본A)` → opened:true, active==A ·
타 문서 활성 상태에서 `apply_cells_to_open_hwp(사본B, {성명:홍길동})` → 자동 open + applied 1건 ·
fresh 연결 read-back == "홍길동". 이 실증이 보여 주는 것은 **재정의 경로의 write 가능성**이다. 다만 손으로 연 창까지 포함한 exact-path attach의 literal write-safe 증거는 이 세션에서 새로 캡처하지 않았으므로 승격 판단은 아래 QA gate를 따른다. runbook은 `open_in_hwp` 우선이되, hand-opened exact-path 후보를 배제 근거로 쓰지는 않는다.

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

**실기기(Windows+한글) 미확보 — 이 패스에서 캡처해야 할 증거(Resolver-path 존재와 write-safe proof를 분리해서 기록)**:
1. `hwp_status()`/`preview_cells_to_open_hwp(...)` raw probe/json — exact-path attach metadata가 어떤 resolver path로 잡혔는지 보존
2. `open_in_hwp(사본)` 또는 exact-path로 식별된 기존 창에서 `apply_cells_to_open_hwp(사본, {b_n: 값})` 본문 채우기 → fresh read-back 정확
3. 실패 주입(존재하지 않는 문단/변경된 문단)에서 파괴적 편집이 일어나지 않고 skip으로 귀결
4. P3: 타 문서 활성 상태에서 auto-open 후 active==path 확인되어야만 편집 진행

## 미확보 증거 (이 문서를 닫는 조건)

[`docs/live-qa-runbook.md`](docs/live-qa-runbook.md) 절차로 다음을 캡처하면 이 문서를 삭제하고
US-029/US-053 및 saved `.hwpx` current-document pathless UX의 desktop-live-pending 상태를 갱신한다:

1. `hwp_status()` 출력 — `instances`/`attach_boundary`/버전/문서 수
2. exact-path 경로: `preview_cells_to_open_hwp` 의 attach metadata + target 수
3. exact-path 경로: `apply_cells_to_open_hwp` 또는 (`open_in_hwp`/`preview_cells_to_open_hwp`로 attach 확인 후) `apply_to_open_hwp(path, values)` 의 `applied[]`/`skipped[]`/count (preview와 대조)
4. current-document 경로: `resolve_current_hwp_document()` → `preview_current_hwp_document(...)` → `apply_to_current_hwp_document(preview_token)` 의 JSON 전문 + fresh read-back
5. current-document 안전 경계: Explorer 더블클릭 current-doc 흐름, 같은 basename·다른 폴더 no-auto-select, explicit `candidate_id` selection_required 케이스의 캡처
6. COM 에러 텍스트(있다면)
7. 채워진 창의 스크린샷 또는 저장본(PII 없는 fixture 사본만)

필요 환경: Windows + 한컴오피스 설치 + `pip install -e ".[live]"` + 대화형 세션(Claude Desktop 등).
pytest 라이브 레인: `$env:HANGEUL_MCP_LIVE=1; python -m pytest tests/test_com.py tests/test_live_resolve.py tests/test_live_current_document.py -q`

## D7 경계 재확인 (best-effort)

`apply_cells_to_open`의 attach 증명은 **ROT 열거 → 모든 `XHwpDocuments` → 정규화한 `FullName` exact match**뿐이다. 그 다음에 analyze의 전역 표 인덱스 == pyhwpx `get_into_nth_table` 컨트롤 순서를 가정한다. **단일/최상위 표 양식에서만 성립 확인**되었으며 중첩 표·복잡 병합 문서에서는 어긋날 수 있다. 실기기 검증 전까지 라이브 셀 채우기는 best-effort로 표기하고, apply 전 preview attach metadata 확인을 필수 절차로 유지한다.

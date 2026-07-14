# Hangeul-mcp 사용성·라이브 풀폼 편집 개선 RALPLAN — 합의 승인본

> **상태: APPROVED & EXECUTED (2026-07-14 사용자 승인, ultragoal 8/8로 근-미래 출하 범위 집행 완료)**
> 잔여 트랙: P0-C(진짜 in-place)·P0-B2(원본 교체)는 desktop-live QA + ADR 게이트 뒤 대기.
> ralplan 합의 워크플로(Planner → Architect → Critic, 2회 반복) 산출물. Critic 최종 판정 **APPROVE**(rider R1–R3 부대조건, 본문에 반영 완료).
>
> - 합의 기록(2026-07-14): Planner v2 → Architect SOUND-WITH-CHANGES(변경요구 7건) + Critic ITERATE(수정지시 9건, 독립 발견 1건) → Planner v3 → Architect SOUND-WITH-CHANGES(7/7 반영 확인, 잔여 3건 non-blocking) → Critic **APPROVE**(rider R1–R3).
> - 관계 문서: `HANDOFF.md`(SSOT) · `PENDING_DESKTOP_LIVE_QA.md` · `.omo/plans/hangeul-mcp-stabilization-ralplan.md` · `SAFE_FULL_EDITOR_EXPANSION_RALPLAN.md` — 본 계획은 이들을 **대체하지 않고 활성화·연결**한다.

---

## 촉발 시나리오 (P0)

사용자가 `14_교수학습 지도안 양식.hwpx`(표 셀 ~40곳 풀폼)를 한글 창에 열어 두고 "현재 열려 있는 문서에 라이브로 채워줘"라고 요청 → 서버는 `hwp_status`에서 `live_addressed_editing:false`를 반환하고 `apply_small_live_label_cells` 안내문이 "풀폼은 파일 모드 `complete_addressed_template`를 쓰라"며 거부 → 사용자는 사본 파일을 만들어 따로 열어야 했다. **사용자가 원한 것: 사본 없이 열린 문서에 직접 채움.**

---

## A. 현황 평가

### A-1. 구조 평가

**강점**
- 명확한 2계층: `hangeul_core/`(순수 엔진, MCP 무의존 — `docs/architecture.md:5`) + `hangeul_mcp/`(얇은 FastMCP 어댑터). `server.py`는 30줄 파사드, 정적 등록.
- CI 강제 모듈 규율: `tests/test_maintainability.py:29-52`(엔트리 ≤80 LOC, 핫패스 14모듈 ≤250 LOC), `:79-88`(LLM SDK 의존 금지=D10), `:62-72`(README/HANDOFF 툴 카운트 드리프트 가드).
- 바이트보존 경계 격리 + `standalone="yes"` 검증(`hangeul_core/validate.py:90-93`).
- 라이브 계층의 실재하는 분리: resolve/preview는 PURE(COM 무관·단위테스트 가능), apply만 COM 구동. exact-path attach + `same_doc` fail-closed 안전 사다리(`hangeul_core/hwp/live_attach.py:35-87`).

**약점**
- 이질적 에러 계약 최소 3종: core/read `{"error",…}`(available/ok 없음, `hangeul_mcp/tools_core.py:60`) vs file_edit/delegate/live `{"available","ok","state"}` vs `mail_merge` 이탈(`hangeul_mcp/tools_delegate.py:74`). 공용 엔벨로프 헬퍼 부재.
- 복잡도 집중: `addressed.py` 944 LOC(≤250 가드 목록 제외), `client_config.py` 655, `fill.py` 541.
- 등록 관용구 불일치, `capabilities.py` 매니페스트 포맷 불일치.

### A-2. 기능별 완성도 평가

| # | 기능 그룹 | 등급 | 근거 |
|---|---|---|---|
| 1 | 파일모드 분석·채우기(OWN) | **A** | 바이트보존 splice; PRD 44 complete |
| 2 | 읽기·검색·검증(OWN) | **A** | find_text/outline/table_map/verify_* + 테스트 |
| 3 | Addressed/템플릿 편집(OWN, 차별점) | **A−** | inspect/plan/complete_addressed_template 신뢰성 슬라이스 구현. 감점: 944 LOC·장황 docstring |
| 4 | 텍스트 edit-session(OWN) | **A** | preview/apply/restore + journal/snapshot, 다중일치 fail-closed(`tools_file_edit.py:38-49`) |
| 5 | delegate 편집/생성 | **B** (optional-gated) | 구조화 `available:false`; 15 story |
| 6 | render(PNG) | **B** (optional-gated) | playwright 게이트 |
| 7 | 라이브 COM(Windows) | **C** (desktop-live-pending) | fake-COM 테스트 있음; 실기기 P2/P3 미확보; **구조 addressed 라이브 부재 = P0 갭** |
| 8 | 현재문서 pathless UX | **C** (desktop-live-pending) | token+picker; Explorer 더블클릭 프로브 E_FAIL(조건부) |
| 9 | .hwp 헤드리스 읽기 | **D** (spike-pending) | adapter-gate만, 항상 `available:false`(D12) |
| 10 | 관리 CLI/진단 | **A** | 8 서브커맨드 + 실제 MCP smoke test(`doctor.py:223-269`) + managed rollback |

PRD 실측: 67 story / 66 pass / 1 fail; complete 44 · optional-gated 15 · desktop-live-pending 5 · spike-pending 3.

### A-3. 사용성 평가 — 중심 사례: 라이브 풀폼 채우기 거부

**(a) 최종 사용자**: README 상태표 정직, `manage doctor` 강력, 라이브 한계 명시. 약점: 59도구+5 extra 개념 부담, `docs/gap-analysis.md` v0.1.0 stale, 명칭 드리프트(`apply_cells_to_open_hwp`).

**(b) MCP 클라이언트 LLM — P0 갭의 정확한 3분해** (검증 완료: field_id는 이미 1급 키(D2), apply 프리미티브는 이미 구조 좌표 tN.rN.cN을 소비 `live.py:203-206`)
- **(i) 입력 형태**: 라이브 진입점이 `values: Dict[str,str]`(`live.py:139`)라 파일모드가 받는 `AddressedEdit[]` 배열형을 표현 못 함.
- **(ii) granularity**: 라이브는 셀 통째 clear+insert(`live.py:209-211`)로 `pN`(셀 내 문단) 주소 부재.
- **(iii) 탐지 의존**: 해소가 `understand().fields`/`resolve_cell_targets`(`live.py:74-76,83-88`)를 거쳐 탐지된 채울-수-있는 셀로 blast radius가 한정됨.

그리고 거부가 계약으로 강제된다: `live_addressed_editing:false`(`hangeul_core/runtime_info.py:33`)를 `tests/test_capabilities.py:76` + `tests/test_live_guidance.py:92`가 이중 락, docstring 거부 문구를 `test_live_guidance.py:36-37`이 단언. **이 거부가 사용자를 파일모드로 밀어내고, 그 `out_path` 완성 파일이 "사본"의 진짜 원인이다.**

인과 정정(합의 확정): `live_reload.py:49`의 `{stem}.live-reload.hwpx` 사본은 P0 원인이 아니다 — `reload_if_unreached`는 휴면(프로덕션 호출자 0, 정의+테스트만). 하이브리드(B1)가 연결할 휴면 스캐폴딩으로 재프레이밍한다.

부수 갭: 매니페스트 드리프트(`describe_capabilities()`가 59개 중 48개만 노출, 정확히 10개 누락, 파리티 가드 부재) + 이질적 에러 shape가 LLM 도구 표면 사용성을 악화.

---

## B. RALPLAN-DR 요약 (SHORT 기본 · P0-C/B2는 DELIBERATE)

**Principles**
1. 평가·등급은 코드/문서 실측 근거에만(HANDOFF 불변식 #5).
2. 기존 소유 계획 재발명 금지 — 보완·연결(D1).
3. 불변식 절대 보존: 바이트보존은 파일모드 한정, 두뇌·손 분리(D10), file/live 분리(D11, `docs/DECISIONS.md:52-55`), preview-token 계약, 사용자가 연 문서 자동 저장/닫기/재열기 금지(`README.md:253`) — 예외는 ADR+실기기 QA 없이는 어떤 출하에도 넣지 않는다.
4. 사용자 의도 존중, 단 정직하게: 리터럴 "이 문서, 사본 0"은 오직 진짜 in-place COM(P0-C)만 충족 가능함을 인정하고, 근-미래 출하는 그 절반의 안전한 순이득만 약속한다.
5. 각 개선은 테스트 가능한 인수조건 + 드리프트 가드; 라이브 승격은 실기기 증거 게이트 통과 시에만.

**Decision Drivers (상위 3)**
1. 사용자 의도 충실도 ↔ 데이터 안전의 근본 긴장: 리터럴 in-place면서 동시에 byte-verified인 옵션은 존재하지 않음 → 안전한 절반(B1)만 즉시, 충실한 절반(P0-C)은 QA 뒤.
2. **탐지 불가 데이터 손실 회피(Critic MAJOR 발견)**: 열린 창의 dirty(미저장·경로 있음) 탐지 능력이 코드에 없음(`hangeul_core/hwp/com.py:80`의 `active_path_empty`는 무제 문서만 탐지; `IsModified`/dirty grep 0건) → 원본 창을 건드리는 어떤 근-미래 경로도 금지, 원본 0-touch만 출하.
3. 실기기 Windows+한글 QA 병목 → QA 불필요(B1·P1) 선행, QA 필요(P0-C·B2) 게이트 뒤.

**Options (P0 해소 방식)**

| 옵션 | 메커니즘 | Pros | Cons / 불변식 충돌 |
|---|---|---|---|
| (a) 진짜 in-place 라이브 addressed | 열린 창에 `AddressedEdit[]`를 COM 직접 적용, 파일 산출 0 | 사용자 의도 완전 충족. apply가 이미 tN.rN.cN 소비라 노력 하향 | 데이터 무결성 위험 높음 유지: D7 표인덱스 어긋남(`docs/DECISIONS.md:33-36`) + 탐지 가드 우회. 손으로 연 창 write-safety 미확보. 바이트보존 아님 |
| (b1) 하이브리드: 완성본 새 문서 자동 열기 | 파일모드 검증 완성 → 새 파일을 새 문서로 자동 열기, 원본 창 0-touch | 불변식 위반 0·데이터 손실 0. 검증된 파일모드 재사용. 수동 열기 → 검증된 자동 열기 순이득, 예외 비용 없음 | 완성본 새 파일 잔존 → 리터럴 "사본 없이" 미충족(정직 고지 필수) |
| (b2) 하이브리드: 원본 in-place 덮어쓰기+창 리로드 | 원본 경로 덮어쓰기 후 같은 창 리로드 | 동일 경로·사본 없음에 가장 근접 | 미저장 수동편집 조용히 폐기(리로드는 디스크를 읽음) = README:253 위반. dirty 탐지 부재로 막을 수 없음. ADR+신규 IsModified 프로브 필요 |

**선택: 단계적 — B1만 즉시 출하, (a)=P0-C·(b2)=P0-B2는 desktop-live QA + ADR 게이트 뒤.** (a)/(b2)는 무효가 아니라 증거 게이트로 이동. 부트랙 P1(도구 표면)은 non-blocking 병행.

---

## C. 개선 실행 계획

> 공통 게이트(모든 Phase): `./.venv/Scripts/python.exe -m pytest -q` → `pyflakes hangeul_core hangeul_mcp tests` → `python -m json.tool docs/prd.json` → `git diff --check`. 도구/스토리 카운트 변경 시 같은 커밋에서 가드 갱신. 라이브 apply 변경은 fake-COM 단위 + 실기기 캡처 2중 증거(HANDOFF 불변식 #5).

### ★ Track P0 — 라이브 풀폼 addressed 편집

**P0-A. 능력 신호·거부 UX 정직화 (순수/헤드리스, QA 불필요, 선행)**
- 목적: 풀폼 라이브 요청 시 dead-end 거부를 없애고 B1 하이브리드 경로를 실행 가능하게 제시. 단, `live_addressed_editing`는 **boolean 유지**(이중 테스트 락 파괴 금지).
- 방식: (1) `live_addressed_editing:false` 불변(진짜 in-place=P0-C landing 시에만 flip). (2) 하이브리드 가용성은 가산 신규 필드(예: `hwp_status.live_routes` = 사용 가능 라우트 목록)와 `hwp_status.next`/docstring 가이드로 표현. (3) 정직화 문구: "풀폼 라이브 직접 채움은 아직(진짜 in-place 미승격); 대신 검증 완성본을 새 창에 자동으로 열 수 있고, **원본 문서는 그대로 남고 새 문서 탭이 앞에 열리며(활성 뷰 전환), 새 파일이 생성된다**" [rider R2 반영]. (4) [rider R1a] "완성본은 원본이 automation-visible일 때만 같은 인스턴스에, 아니면 별도 창/새 인스턴스에 열릴 수 있으며 생성 파일 경로를 항상 응답에 반환한다"를 문구에 포함.
- 대상: `hangeul_core/runtime_info.py`(가산 필드만, 기존 4-boolean 불변), `hangeul_mcp/tools_live.py` docstring/`next`, `tests/test_live_guidance.py`·`tests/test_capabilities.py`(가산 단언 추가, 기존 `is False` 락 유지).
- 인수조건(모두 boolean 판정 가능):
  - 풀폼 라이브 요청 응답이 B1 라우트를 next-step으로 제시.
  - "새 파일이 생성되고 원본 문서는 미변경(새 탭이 앞에 열림)"이라는 한계 고지가 응답/docstring에 문자열로 존재.
  - `live_addressed_editing`는 여전히 `False`, 이중 락 테스트 무손상.
- 검증: `pytest tests/test_live_guidance.py tests/test_capabilities.py -q`(가산 red→green, 기존 green 유지).
- 리스크: 낮음(순수). 거부 계약 변경은 문서화.

**P0-B1. 하이브리드 "완성→새 문서로 자동 열기" (출하 목표)**
- 목적: 파일모드 `complete_addressed_template`로 검증 완성 후 한글에 새 문서로 자동 열기. **원본 창 0-touch** → 불변식·데이터 안전 무결(코드 정합 확인: `live_attach.py:95` "saves and closes nothing", `Hwp(new=False, on_quit=False)`, MDI 다중문서 모델 `com.py:71-146`).
- 방식: 현재문서 흐름을 **신규 라우트 값**으로 확장 — `plan_preview_route`에 `complete_and_load` 추가(`mode` 오버로드 금지; `mode`는 `live_current.py:247` dead-through, 디스패치는 route 기준 `:327-343`). preview는 token 발급, apply(token)는 완성 새 파일 산출 → `hwp.open(new_file)`으로 새 문서 열기. 원본 경로 덮어쓰기 없음, 원본 창 저장/닫기/재열기 없음. `preserve_original` bool 도입하지 않음(모호성 제거).
- 인수조건:
  - 원본 파일 SHA 불변(0-touch 증명), 완성본은 별도 새 파일, fresh read-back으로 40셀 값 확인.
  - preview-token 계약 유지(token 없이 apply 불가, 문서 변경/닫힘/재사용 시 fail-closed).
  - 신규 라우트 × 기존 `mixed`/`route_conflict` 상호작용 회귀 테스트(`current_document.py:247-249`).
  - 응답이 "새 문서 탭=검증 완성본, 원본 문서 그대로(뷰 전환), 새 파일 <path> 생성"을 명시.
  - [rider R3] 완성 파일은 생성됐으나 `hwp.open` 실패 시 응답이 `open_failed` + 생성 파일 경로 + 수동 열기 안내를 반환(`live_attach.py:138-151` 패턴 재사용).
  - [rider R1b] 실기기 캡처 1건은 **Explorer 더블클릭으로 연 원본** 시나리오로 지정하고, 그 캡처가 (i) 완성본이 어느 인스턴스/창에 열리는지 + (ii) 원본 문서가 `XHwpDocuments`에 잔존(닫히지 않음)함을 확인해야 한다 — (ii)는 B1의 0-touch 데이터 안전 주장을 실측으로 닫는 게이트.
- 검증: fake-COM 단위(라우트 분기·0-touch) + 위 실기기 캡처 1건(`docs/live-qa-runbook.md` 절차). `pytest -q`.
- 리스크: 낮음(원본 미접촉). [rider R1c] 단, 신규 리스크는 `hwp.open` 자체가 아니라 앞단 attach-target(broker) 선택 — hand-opened 원본이 ROT/automation 비가시이면(`PENDING_DESKTOP_LIVE_QA.md:13,75-76`) 완성본이 사용자가 보던 창이 아닌 별도 인스턴스에 열릴 수 있음(데이터 안전 무해, UX 조건부). 이 경우에도 생성 파일 경로가 항상 반환되므로 dead-end 없음.
- 관계: `live_reload.py`(휴면 스캐폴딩) 연결·현재문서 token 계약 확장. `PENDING_DESKTOP_LIVE_QA` 닫는 조건 #4와 정렬.

**P0-B2. 하이브리드 in-place 덮어쓰기+리로드 (게이트 뒤로 이동 — 근-미래 출하 제외)**
- 전제(모두 필요): (1) `README.md:253`/D11 예외 ADR, (2) 사용자 consent, (3) COM `IsModified` dirty-프로브 신규 구현(현재 부재 — `com.py:80` `active_path_empty`는 무제 문서만 탐지, dirty-저장경로 무탐지; PURE resolve 계약과 충돌하므로 desktop-live QA 대상 별도 스토리), (4) 백업. dirty 감지 시 거부.
- "미저장 감지" 완화책은 뒷받침 능력이 없으므로 **근거로 사용 금지**(Critic MAJOR 발견 확정).

**P0-C. 진짜 in-place 라이브 addressed 확대 (desktop-live QA 게이트 뒤, DELIBERATE)**
- 목적: 열린 창에 파일 산출 0으로 구조 `AddressedEdit[]` 직접 적용(사용자 의도 완전 충족).
- 방식: `_resolve_all_targets`/`_apply_cells_connected`가 `values:Dict` 대신 구조 주소 배열 소비(우선 단일/최상위 표), `pN` granularity 추가. 구현 노력 하향(apply가 이미 tN.rN.cN 내비게이션), **데이터 무결성 위험 "높음" 유지**.
- 리스크 명기: 구조 `AddressedEdit[]` 해소는 `understand().fields` 탐지 가드를 우회 → D7 표인덱스 어긋남이 의미 앵커 없이 잘못된 셀을 덮어쓸 수 있음.
- 인수조건:
  - **clear+insert 전 셀별 `expected_text` 대조 필수, 불일치 시 fail-closed**(파일모드 `tools_file_edit.py:71-74` 메커니즘의 라이브 포팅, 라이브에선 필수화) — D7 어긋남의 조용한 오작성 차단.
  - 부분실패 복구 경로(D17: `restore_edit_session`은 파일모드 전용): 40셀 중 N셀 후 실패 시 응답이 `applied[]`/`remaining[]` + 구조화 복구 지시("N/M 적용됨; 되돌리려면 Ctrl-Z ×N 또는 원본 재열기") 반환; 각 셀 편집은 단일 undoable COM 액션.
  - 단일/최상위 표에서 preview↔apply 대조 일치 + fresh read-back; 실패 주입 시 파괴적 편집 없이 skip; D7 매핑 불일치 문서 fail-closed.
- 검증: fake-COM 단위 + 실기기 증거 8종(`PENDING_DESKTOP_LIVE_QA.md:160-168`). 게이트 통과 시에만 `live_addressed_editing`를 boolean True로 flip(같은 커밋에서 이중 락 테스트 갱신).
- 관계: stabilization ③(M14) + `PENDING_DESKTOP_LIVE_QA` + `SAFE_FULL_EDITOR_EXPANSION_RALPLAN §E`를 실제로 활성화(재발명 아님).

### Track P1 — 도구 표면 일관성·발견성 (순수/헤드리스, non-blocking 병행)

- **P1-1 매니페스트 파리티 등식 가드**: 인수 = `set(manifest tools) == set(registered) − META_ALLOWLIST`(`META_ALLOWLIST={"describe_capabilities"}`). 누락 10개 각각 노출 의도 확인 후 버킷 배정: `analyze_formfit`(`tools_core.py:126`)→file_hwpx, `list_styles`(`tools_read.py:222`)→file_hwpx, `mail_merge`(`tools_delegate.py:70`)→버킷 소유 확인(OWN vs delegate), 레이아웃 7종(`tools_delegate.py:85-151`)→delegate_hwpx. `test_capabilities.py`의 subset(`<=`) 단언을 등식 파리티 테스트로 강화.
- **P1-2 에러 엔벨로프 표준화**: 공용 `{available, ok, state?, error?}`로 비파괴 수렴(키 추가만), core/read/`mail_merge` 정렬. 인수: 신규 `test_error_envelope.py`.
- **P1-3 docstring/스키마 정비**: garbled 조각(`tools_read.py:58-60,112-114`) 정리, delegate 무-docstring 해소, 열거형 파라미터 도메인 명시, 중복쌍(find_text↔find_text_occurrences 등) 선택 기준 1줄. 인수: "모든 도구 non-empty description" 테스트.
- **P1-4 stale 문서 정합**: `docs/gap-analysis.md` 현행화(또는 deprecated 아카이브 결정), 명칭 드리프트(`apply_cells_to_open_hwp`) 정정(`HANDOFF.md`, `pyproject.toml:37`). 인수: 코드 grep 0건.

### Deferred / 위임 (본 계획 미포함)
- .hwp headless substrate → stabilization ④ + D12.
- 편집기 breadth(행/열·TOC·rich 서식) → `SAFE_FULL_EDITOR_EXPANSION_RALPLAN` + stabilization ⑤ + D13/D14.
- `addressed.py` 944-LOC 분할 → 리팩터 백로그(관찰만).

### 시퀀싱

```
P0-A (즉시, 순수)
  → P0-B1 (출하: fake-COM + 실기기 캡처 1건[Explorer 더블클릭 시나리오])
  ∥ P1-1~4 (병행, 순수)
  → [desktop-live QA 게이트: PENDING_DESKTOP_LIVE_QA 8종]
  → P0-C (DELIBERATE)
  → P0-B2 (ADR + IsModified dirty-프로브 확보 시)
```

---

## D. 리스크·확정 결정·미해결 질문

**리스크**
- [MAJOR] dirty 탐지 능력 부재: 열린 창의 "미저장·경로 있음" 상태를 탐지할 코드 없음(`com.py:80` `active_path_empty`=무제만; `IsModified` grep 0) → 어떤 근-미래 경로도 원본 창을 건드리면 안 됨. B1은 원본 0-touch라 무관. B2는 dirty-프로브를 desktop-live QA 스토리로만.
- [높음·유지] P0-C 데이터 무결성: D7 매핑 어긋남 + 탐지 가드 우회 → `expected_text` 필수 fail-closed로 완화, B1이 항상 폴백이라 dead-end 없음.
- [중간·UX 한정] B1 broker/ROT-가시성 조건부: hand-opened 원본이 automation 비가시이면 완성본이 별도 인스턴스에 열림(데이터 안전 무해, 경로 항상 반환).
- 에러 엔벨로프 변경 호환 → 비파괴 키-추가만.
- `482 passed`는 문서값(본 계획 세션은 read-only) → 구현 단계 게이트에서 실측.
- 실기기 QA 병목: P0-C·B2·stabilization ③은 Windows+한글 인터랙티브 세션 없이는 승격 불가.

**확정된 결정 (합의로 open question에서 이동)**
- `live_addressed_editing`는 boolean 유지. 하이브리드 가용성은 가산 필드(`live_routes`)+`next` 가이드로 신호(per-capability 오브젝트 전환안 폐기 — 이중 테스트 락 보호).
- `preserve_original` bool 도입하지 않음(B1만 출하, B2 게이트 이동으로 모호성 제거).
- B1은 리터럴 "사본 없이"를 미충족(새 파일 잔존) — 정직 고지를 P0-A 인수조건에 포함.

**잔여 미해결 질문 (실행 시 open-questions에 등록)**
- B2용 ADR: `README.md:253`/D11 예외를 "consent+dirty거부+백업 시 원본 교체 허용"으로 문서화하는 문안과 승인 주체?
- `describe_capabilities` 10개 노출은 전부 의도인가(특히 `mail_merge` 버킷 위치 — OWN인데 delegate 파일)?
- 에러 계약 통일 시 core/read 관례 변경의 하위호환 정책(Pre-Alpha semver)?
- `docs/gap-analysis.md` 갱신 vs deprecated 아카이브?

---

## ADR (Architecture Decision Record)

- **Decision**: 라이브 풀폼 채우기 갭을 3트랙으로 해소한다 — (P0-A) 능력 신호·거부 UX 정직화 즉시, (P0-B1) "파일모드 검증 완성 → 새 문서 자동 열기" 하이브리드를 근-미래 출하, (P0-C) 진짜 in-place 라이브 addressed와 (P0-B2) 원본 교체 리로드는 desktop-live QA + ADR 게이트 뒤. 부트랙(P1)으로 매니페스트 파리티 등식·에러 엔벨로프·docstring·stale 문서를 병행 정비한다.
- **Drivers**: ① 사용자 의도 충실도 ↔ 데이터 안전의 비가환 긴장(리터럴 in-place ∧ byte-verified 옵션은 부재), ② dirty 탐지 능력의 코드상 부재(조용한 데이터 손실을 막을 수단 없음), ③ 실기기 QA 병목(QA 불필요 트랙 선행).
- **Alternatives considered**: (a) 즉시 in-place COM addressed 확대 — 탐지 가드 우회 + D7 어긋남 + write-safety 미확보로 기각(QA 게이트 뒤 P0-C로 이동). (b2) 원본 덮어쓰기+창 리로드 — dirty 탐지 불가로 미저장 편집을 조용히 폐기할 수 있어 기각(ADR+dirty-프로브 확보 시 P0-B2로 재개). 단일 boolean→per-capability 플래그 오브젝트 — 이중 테스트 락 파괴로 기각(가산 필드로 대체).
- **Why chosen**: 불안전한 중간(consent로 불변식을 우회하는 하이브리드)을 제거하고, 지금 출하 가능한 안전한 절반(원본 0-touch·검증된 파일모드 재사용·MDI 새 문서 열기)과 QA 증거가 필요한 절반(진짜 in-place)을 분리하면, 사용자 마찰(수동 열기)을 즉시 제거하면서 데이터 손실 시나리오를 0으로 유지할 수 있음이 코드로 확인됐다.
- **Consequences**: (+) 사용자는 즉시 "요청 → 검증 완성본이 자동으로 열림"을 얻는다. (+) 불변식·이중 테스트 락 무손상. (−) 리터럴 "사본 없이"는 P0-C 승격 전까지 미충족(정직 고지로 완화). (−) hand-opened 원본이 automation 비가시인 환경에서는 완성본이 별도 창에 열릴 수 있다(경로 항상 반환). 두 트랙(파일/라이브) 유지 비용.
- **Follow-ups**: P0-C 승격 시 `live_addressed_editing` flip + 이중 락 테스트 갱신(같은 커밋). B2 ADR 문안 작성. IsModified dirty-프로브 스파이크. `PENDING_DESKTOP_LIVE_QA` 8종 증거 수집. open questions 4건 해소.

---

## 승인 후 실행 경로 (참고)

- 병렬 실행: `/oh-my-claudecode:team` (권장 — P0-A·P1-1~4는 독립 순수 작업이라 병렬 적합)
- 순차 실행: `/oh-my-claudecode:ralph` (P0-B1처럼 단계 의존이 강한 트랙에 적합)
- 본 문서는 승인 전까지 계획일 뿐이며, 실행 승인은 사용자가 명시적으로 해야 한다.

# 핸드오프 프롬프트 — 라이브 게이트 트랙 4종 구현 (post-v0.4.0)

> 아래 전문을 새 세션에 그대로 붙여넣어 사용한다. 작성 시점: v0.4.0 게시 직후(2026-07-15).

---

당신은 Hangeul-mcp(`E:\github\Hangeul-mcp`, 로컬 MCP 서버, HWP/HWPX 양식 채우기)의 라이브 편집 게이트 트랙을 구현한다. v0.4.0에서 `complete_and_load`(파일모드 검증 완성 → 새 탭 자동 열기, 원본 0-touch)가 출하됐고, 아래 4개 트랙이 **의도적으로 게이트 뒤에 보류**되어 있다. 승인된 계획은 [.omo/plans/hangeul-mcp-usability-live-editing-ralplan.md](../plans/hangeul-mcp-usability-live-editing-ralplan.md)(P0-C/B2 절), 상태 SSOT는 `HANDOFF.md`다.

## 절대 불변식 (위반 금지 — HANDOFF.md와 동일)

1. 바이트보존은 파일모드 한정(raw-XML splice, 재직렬화 금지). 라이브 COM 편집은 바이트보존이 아님을 항상 명시.
2. **사용자가 연 문서를 자동 저장/닫기/재열기하지 않는다**(README "라이브 입력" 절). 예외는 ADR + 실기기 QA 없이는 어떤 형태로도 출하 금지.
3. preview-token 계약: 서버 인스턴스 스코프, 단일 사용, preview 시점 원본 SHA 결속(`stale_preview`), race fail-closed. 약화 금지.
4. 서버는 LLM/API를 호출하지 않는다(D10). optional dep은 구조화 폴백(`available:false`).
5. **증거 없이 완료 선언 금지**: 라이브 경로는 fake-COM 단위 테스트 + 실기기 캡처 2중 증거. 실기기 미확보면 명시적 pending 라벨.
6. 기존 테스트 락 약화 금지: `live_addressed_editing is False` 이중 락(`tests/test_capabilities.py:76`, `tests/test_live_guidance.py:92`)은 P0-C 승격 커밋에서만 True로 flip(같은 커밋에서 두 테스트 갱신). docstring 핀 문구(`tests/test_read_guidance.py`), 매니페스트 등식 파리티, LOC ≤250 가드(`tests/test_maintainability.py` — tools_read/tools_live는 헤드룸 0~1이므로 추가 시 모듈 분리 계획 필수), 툴 카운트 59 가드(도구 추가 시 README/HANDOFF 같은 커밋 갱신).

## 공통 게이트 (모든 스토리 완료 조건)

```powershell
python -m pytest -q          # 기준선: 506 passed / 1 skipped / 6 failed(사전 env: client_setup 2, inspection_cache 1, managed_runtime 3 — HEAD와 동일해야 함, 회귀 0)
python -m pyflakes hangeul_core hangeul_mcp tests
python -m json.tool docs/prd.json > $null
git diff --check
```
- python = `C:\Python314\python.exe`(프로덕션 런타임, 이 워크트리를 editable import — Claude Desktop이 이 인터프리터로 서버 실행).
- prd.json에 스토리를 추가하면 README `NN개 — MM pass` 수치를 같은 커밋에서 갱신(가드 강제).

## 실기기 QA 필수 지식 (이미 실측 확인된 함정 — 재발견에 시간 쓰지 말 것)

- **합성 zip 픽스처(`tests/fixtures/*.hwpx`)는 실제 한글이 열지 못한다**(`hwp.Open`→False). 데스크톱 캡처는 `tests/hwpx template/14_교수학습 지도안 양식.hwpx` 같은 실제 저작 파일 사용.
- **일반 `hwp.Open`은 새 탭을 만들지 않고 활성 탭을 내비게이션**(사실상 활성 문서 대체). 탭 보존이 필요하면 `hangeul_core/hwp/live_attach.py`의 `open_as_new_tab`(=`XHwpDocuments.Add(1)` 카운트 검증 후 Open, 실패 시 `new_tab_unavailable` fail-closed) 사용.
- 캡처 하네스: `scripts/complete_and_load_capture.py` (모드: `shell`/`automation`/`components`). 증거는 `docs/evidence/complete-and-load-desktop-capture-*.json`(개인 경로 자동 새니타이즈 내장). 절차 문서는 `docs/live-qa-runbook.md`, 요구 증거 목록은 `PENDING_DESKTOP_LIVE_QA.md`.
- 캡처 전 titleless 한글 좀비 정리: `Get-Process Hwp | Where {-not $_.MainWindowTitle} | Stop-Process`(창 있는 프로세스는 사용자 문서일 수 있으니 절대 제외). 과거 누수 근본원인(`ensure_hwpx`가 없는 `.hwp`로 COM 기동)은 v0.4.0에서 수정됨 — 재발 시 다른 원인.
- 보안모듈: `hwp.register_module("FilePathCheckDLL", "FilePathCheckerModule")` 동작 확인됨.
- 캡처가 연 탭/창은 닫지 않는다(서버는 문서를 닫지 않는 원칙). 사용자에게 정리 안내만.

## Track C — 다중 인스턴스 resolver 개선 (권장 착수 순서 1위: 헤드리스로 대부분 해결, 실사용 차단 해소)

**실측 결함**: 실기기에서 `resolve_current_hwp_document()`가 5개 후보 중 **열거 순서상 첫 `is_active` 문서**(경로 없는 빈 문서)를 잡아 `current_document_unsaved`로 전체 흐름을 차단했다(증거: `docs/evidence/complete-and-load-desktop-capture-automation.json`). 원인: `hangeul_core/hwp/current_document.py`의 `summarize_resolution()`이 `active = next(item for item in candidates if item.get("is_active"))` — 인스턴스마다 active가 하나씩 있는 다중 인스턴스 데스크톱에서 "전역 현재 문서" 가정이 깨진다. 사용자가 빈 문서 탭 하나만 열어 둬도 pathless UX 전체가 죽는 실사용 결함.

**수정 방향** (fail-closed 철학 유지 — 모호하면 자동 선택 금지):
1. `summarize_resolution`을 인스턴스별 active 집합 기준으로 재설계: 유효 후보(저장된 `.hwpx` active)가 1개면 `auto_selected`, 2개 이상이면 `selection_required`(picker metadata로 구분), **0개일 때만** 기존 차단 상태.
2. 다른 인스턴스의 빈 문서/미저장 active는 "차단 사유"가 아니라 후보 목록의 배지(`Unsaved`)로 강등.
3. `preview_current_hwp_document(candidate_id=...)`가 명시되면 그 후보의 상태만으로 판정(타 인스턴스 블로커 무시).
4. apply의 `refresh_candidate_state`(`current_document.py`)도 같은 원칙으로 재점검 — 후보 인스턴스 내 active/identity만 요구.

**검증**: 순수 헤드리스 — `tests/test_live_current_document.py`의 `_doc`/`_instance` 픽스처 패턴으로 다중 인스턴스 시나리오 추가(A인스턴스 active=빈문서 + B인스턴스 active=저장 hwpx → B가 auto_selected/selection_required; 기존 단일 인스턴스 시나리오 전부 무회귀). 마지막에 실기기 1캡처(automation 모드 재실행 → `preview_ready` 도달)로 봉인. 기존 `complete-and-load-desktop-capture-automation.json`의 실패 기록은 개선 후 재캡처로 갱신.

## Track A — P0-C 진짜 in-place 라이브 addressed 편집 (desktop-live QA 게이트)

**목표**: 열린 창에 파일 산출 0으로 구조 `AddressedEdit[]`(tN.rN.cN[.pN], bN) 직접 적용. 항상 하이브리드 B1이 폴백으로 존재하므로 dead-end 없음.

**현재 코드 사실** (재조사 불필요):
- 라이브 apply 계층은 **이미 구조 좌표를 소비**한다: `hangeul_core/hwp/live.py`의 `_apply_cells_connected`가 `get_into_nth_table(t["table"]-1)` + `goto_addr(row+1, col+1)`(live.py:203-206). 갭은 (i) 진입점 입력이 `values: Dict[str,str]`(label/field_id 매칭, live.py:83-88), (ii) `pN`(셀 내 문단) 단위 부재 — 셀 통째 clear+insert(live.py:209-211), (iii) 해소가 `understand().fields` 탐지 필드에 한정(blast radius 가드 — 이를 우회하는 것이 위험의 본질).
- D7(`docs/DECISIONS.md:33-36`): analyze 전역 표 인덱스 == pyhwpx `get_into_nth_table` 순서 가정은 **단일/최상위 표에서만** 성립. 중첩/병합 문서는 어긋날 수 있음.

**필수 인수조건** (승인된 계획 + Critic rider 그대로):
1. **셀별 `expected_text` 대조 필수**(옵션 아님): clear+insert 직전 현재 셀 텍스트가 edit의 expected_text와 불일치하면 해당 셀 fail-closed skip. 파일모드 `tools_file_edit.py`의 expected_text 의미론을 라이브로 포팅하되 라이브에선 필수화. D7 어긋남이 "조용한 오작성" 대신 실패로 드러나야 함.
2. **부분 실패 복구 경로**: N/M 적용 후 실패 시 응답에 `applied[]`/`remaining[]` + 구조화 복구 지시("Ctrl-Z ×N 또는 원본 재열기"). 각 셀 편집은 단일 undoable COM 액션. (`restore_edit_session`은 파일모드 전용 — D17 — 라이브에 쓸 수 없음.)
3. 스코프: **단일/최상위 표 문서부터**. 중첩 표 감지 시 fail-closed(`nested_tables_unsupported` 류 상태).
4. preview↔apply 대조 일치 + apply 후 fresh read-back(별도 연결로 재검증).
5. 실패 주입(존재하지 않는/변경된 셀)에서 파괴적 편집 없이 skip.
6. **플래그 승격은 실기기 증거 8종**(`PENDING_DESKTOP_LIVE_QA.md:160-168`) 통과 후에만: `hangeul_core/runtime_info.py`의 `live_addressed_editing`을 True로 flip + 이중 락 테스트 2곳 갱신 + `live_routes`/docstring/README 갱신을 **같은 커밋**에서.

**설계 힌트**: 진입은 새 도구 추가보다 현재문서 token 흐름에 라우트 추가(예: `live_addressed`)가 표면 증가 없이 깔끔(도구 카운트 가드 회피). preview는 COM-free로 유지(PURE 계약 — `live.py` 모듈 docstring), apply만 COM. tools_live/tools_read LOC 여유가 없으므로 신규 로직은 `hangeul_core/hwp/live_addressed.py` 같은 새 모듈로(유지보수 가드 목록에 추가).

## Track D — Explorer/Shell-open 창의 ROT 비가시성 (스파이크/ADR 트랙)

**실측 사실**: 깨끗한 환경에서도 Shell(탐색기 더블클릭 동등)로 연 창은 120초 내 ROT에 등록되지 않는다(`docs/evidence/complete-and-load-desktop-capture-shell.json`, `PENDING_DESKTOP_LIVE_QA.md:13,75-76` — generic reconnect는 빈 인스턴스에 `connected:true`로 붙는 오판 이력 있음).

**산출물은 코드가 아니라 ADR + 프로브 증거**: 옵션 (a) Win32 창 열거(EnumWindows/UIA)로 "감지"만 하고 쓰기는 exact-path COM identity 증명 유지, (b) 한컴 API/DDE로 기존 창을 automation-visible로 승격 가능한지 조사, (c) 현상 유지 — `open_in_hwp` 경유 안내 + B1 하이브리드(현 문서화 상태). 어떤 옵션이든 **쓰기 경로는 `live_attach.py`의 exact-path 사다리(`same_doc` + `_has_active_exact_path`) 미만으로 완화 금지**. 프로브는 `scripts/complete_and_load_capture.py`의 shell 모드 + `build/evidence/` 과거 프로브 패턴 재사용. 결론을 `docs/DECISIONS.md`에 D-번호로 기록하고 README 상태표 갱신.

## Track B — P0-B2 원본 교체 + 리로드 (최후순위, 전제 4종 전부 필요)

**위험의 본질**(Critic MAJOR, 코드로 확정): 리로드는 디스크를 읽으므로 창 안의 미저장 타이핑을 조용히 폐기한다. 그리고 **dirty(미저장·경로 있음) 탐지 능력이 코드에 없다** — `hangeul_core/hwp/com.py:80`의 `active_path_empty`는 무제 문서만 탐지, `IsModified`/dirty grep 0건. "미저장 감지" 완화책을 값싸게 재도입하지 말 것.

전제(모두 충족 전 출하 금지):
1. **ADR**: README "자동 저장/닫기/재열기 금지" 불변식의 명시적 예외 문안("consent + dirty 거부 + 백업 시 원본 교체 허용") — `docs/DECISIONS.md`에 신규 D-번호, README 동시 갱신.
2. **COM `IsModified` dirty-프로브 신규 구현** — 별도 desktop-QA 스토리. 주의: resolve/preview의 PURE(COM-free) 계약을 깨지 않도록 apply 직전 단계에만 배치.
3. 명시적 사용자 consent 파라미터(기본 거부).
4. 백업 필수(원본 SHA 기록 + 백업 파일) + dirty 감지 시 무조건 거부.
휴면 스캐폴딩 `hangeul_core/hwp/live_reload.py`(`reload_if_unreached` — 프로덕션 호출자 0)를 연결 대상으로 재활용 가능.

## 진행 방식

- 순서 권장: **C → A → D → B** (C는 헤드리스라 즉시 가치, A가 본체, D는 스파이크, B는 A/D의 QA 인프라와 ADR에 의존).
- 각 트랙은 ralplan(합의 계획)으로 세부 계획 후 ultragoal 원장으로 실행 추적(이 저장소의 기존 프로세스). 스토리 완료마다 공통 게이트 + 증거 체크포인트.
- 커밋 스타일: `feat:`/`fix:`/`release:` 접두어, 본문에 근거·게이트 결과. 배포는 태그 푸시 → release.yml → PyPI trusted publishing → **레지스트리 직접 검증 + SHA256 릴리스 노트**(워크플로 성공만으로 게시 성공 주장 금지).
- 실기기 캡처는 사용자 데스크톱에서 실행됨을 인지: 임시 사본만 사용, 사용자 창/문서 절대 미접촉, 작업 후 열린 탭 정리 안내.

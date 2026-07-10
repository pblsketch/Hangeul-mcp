# RALPLAN — Hangeul-mcp 안정화·제품화 실행 계획 (consensus FINAL)

**Status: PENDING APPROVAL — 사용자 실행 승인 전. 이 문서는 계획 아티팩트이며 코드 변경 없음.**

## Consensus 기록
- Planner v1 (US-047~US-059) → Architect 리뷰 1: SOUND-WITH-AMENDMENTS(6건 — 핵심: python-hwpx 2.24.0이 표 행/열 add·remove와 TOC API를 미노출, ⑤ 재구성 필요) → Critic 1: ITERATE(체크리스트 10건, G1~G3 추가).
- Planner v2 (US-047~US-060, ⑤ 재구성) → Architect 리뷰 2: SOUND-WITH-AMENDMENTS(경미 3건 A1~A3) → **Critic 2: APPROVE** (binding conditions BC1~BC3 필수 + Minor 1~2 권고).
- 실측 근거(양 리뷰어 독립 재검증): 189 passed/1 skipped(스킵=live COM 게이트), pyflakes clean, 런타임 MCP 툴 35(등록 정적·extras 독립), prd.json US-000~US-046(47개, US-029만 passes:false), python-hwpx 2.24.0 API 표면(header/footer ✓, page-setup ✓, split_merged_cell ✓, 행/열 add·remove ✗, TOC ✗).

## ADR (최종)
- **Decision**: 다음 패스는 안정화·제품신뢰 + "실지원 표면" breadth. ① 문서-런타임 진실화 → ② 파일모드 e2e 증거팩 → ③ live는 증거 또는 명시 pending → ④ .hwp headless는 스파이크→ADR(D12) 후에만 → ⑤ delegate breadth는 상류 API-표면 스파이크(US-056) 게이트 후 지원 기능만(머리/꼬리말·페이지설정·병합셀 분할). 행/열·TOC는 spike-pending OWN 리서치(US-060)로 재분류.
- **Drivers**: (1) 문서/런타임 불일치가 후속 에이전트를 오도할 최대 리스크. (2) live/render/.hwp는 "증거 없는 완료 선언"의 평판 리스크 최대. (3) breadth는 실지원 표면 안에서만 가시 가치.
- **Alternatives**: A) breadth 우선 + in-story 스파이크 — US-056(행/열)·US-059(TOC)가 미지원으로 붕괴, 기각. C) 미지원 기능 OWN raw-XML 구현 — D1·바이트보존 충돌, 기각.
- **Why chosen**: 불변식 무손상 + Option B의 "안정화 먼저" 유지 + breadth가 실기능 3~4개(header/footer·page-setup·split_merged_cell) 산출.
- **Consequences**: 가시적 신규 툴 수는 v1 초안 대비 감소(정직한 축소). live/.hwp는 pending 종결이 정상 결과일 수 있음.
- **Follow-ups**: BC1~BC3 반영(아래), US-060 리서치 결과에 따른 후속 ADR, 실기기 live QA 기회 확보 시 US-053 재개.

## Binding Conditions (Critic 승인 부대조건 — 실행 시 필수 반영)
- **BC1**: `tests/test_delegate_api_surface.py` — 지원 메서드 존재 assert는 hard 유지, **미지원 메서드 부재 검사는 xfail(strict=False)/soft tripwire로 강등**(suite red 금지). `>=2.24,<3` 상한은 minor 릴리스의 API 추가를 못 막으므로 보조 수단일 뿐 — soft 강등이 유일한 실질 방어. tripwire 메시지는 US-060 재검토 트리거로만 사용.
- **BC2**: US-058(페이지설정) acceptance에 **저장 패키지 재오픈 후 섹션 XML 프로퍼티(pageNum/margin/columns 값 변화) 직접 assert** 추가 — `validate_hwpx`만으로 pass 금지(read.py outline은 페이지 프로퍼티 미노출 실측). US-057(머리/꼬리말)도 관측 방법(export 포함 여부 확인, 미포함 시 header XML 재오픈 assert)을 acceptance에 명시.
- **BC3**: US-047/US-048에 계획 자기 스토리(US-047~US-060)의 prd.json 기록 여부 명문화. 기록 시 상태줄 카운트는 이동하는 출력값임을 명시하고 "pass 수" 정의(`passes==true` vs `status==complete`)를 확정.
- **Minor 1(권고)**: US-048 pass-count 대조는 기존 `passes==true` 기준으로 고정하면 US-047과 병렬 유지.
- **Minor 2(권고)**: §4 Risk에 "부재 assert의 forward-compat 마찰" 항목 추가, 완화=BC1.

---

# Hangeul-mcp 다음 작업 계획 v2 (consensus 루프 iteration 2 — Architect·Critic 반영 완료)

대상 리포: `E:/github/Hangeul-mcp` · 검증 기준선(양 리뷰어 독립 재실측): **35 tools**(등록 정적, extras 독립), **190 collected(189 pass + 1 skip)**, `docs/prd.json` **id 범위 US-000~US-046(갭 없음, passes:false는 US-029만)** → 신규 id **US-047~US-060**. python-hwpx **2.24.0** 설치.
모드: **①②⑤ SHORT / ③④ DELIBERATE**(pre-mortem + 확장 테스트 계획을 §6에 지금 명문화 — 연기하지 않음).

> 이 v2는 Architect(SOUND-WITH-AMENDMENTS 6개) + Critic(ITERATE 10-item 체크리스트, G1~G3 포함)을 전부 반영했다. 핵심 변경: **Phase ⑤를 python-hwpx 2.24.0 실측 API 표면에 맞춰 재구성** — 상류 단일 스파이크 신설, 지원 기능(머리/꼬리말·페이지설정·병합셀 분할)만 delegate 스토리로, **미지원(행/열 add·remove, TOC)은 delegate에서 제거해 `spike-pending` OWN 리서치로 재분류**.

---

## 1. RALPLAN-DR 요약

### Principles (원칙)
1. **상태 라벨 앞에 증거(반증이 있으면 커밋 금지)** — `complete`는 코드+테스트+관측 산출물이 모두 있을 때만. 미지원이 실측 확정된 기능에 "달성"을 acceptance로 커밋하지 않는다. 그 외는 `optional-gated` / `desktop-live-pending` / `spike-pending`.
2. **바이트보존·두뇌손분리 사수** — OWN fill은 raw-XML splice 유지, 재직렬화 금지, 기존 바이트보존 테스트 약화 금지. 서버는 LLM/API 미호출.
3. **차별점은 OWN, breadth는 위임(D1) — 단 "위임 가능한 것만" 위임** — python-hwpx가 API를 노출하지 않는 기능은 delegate 스토리가 될 수 없다. 위임 불가 항목을 OWN raw-XML로 재발명해 바이트보존을 깨는 것은 금지(Trade-off C 기각).
4. **선택 의존성은 항상 구조화 폴백 + 버전 게이트** — 미설치 시 `available:false`. 버전 미달(<2.24)은 `AttributeError`를 원인 은폐(`ok:false`)하지 말고 `requires >=2.24` 구조화 메시지로 반환.
5. **역사 문서가 현재 런타임과 모순되지 않게** — SSOT 하나로 수렴, 드리프트를 **파싱 대상이 특정된** 테스트로 차단.

### Decision Drivers (상위 3)
1. 문서/런타임 불일치(HANDOFF 56 passed·6툴·Phase A~D 미래작업 프레이밍, README 33 tools·167 tests·38개)가 다음 실행 에이전트를 오도할 최대 리스크.
2. live COM / render / `.hwp` headless 세 축은 "증거 없이 완료 선언"의 평판 리스크가 최대 → 증거 또는 명시적 pending으로만 종결.
3. breadth는 **실제 지원 표면(header/footer + page-setup + split_merged_cell)** 안에서만 가시적 가치를 낸다 — 미지원(행/열·TOC)을 "확정 산출물"로 프레이밍하면 Driver의 "얕은 미검증 기능 회피"를 스스로 배반한다.

### Viable Options
**Option A — Breadth 우선 + in-story 스파이크 (v1 초안 방식)**
- Pros: 계획 변경 최소.
- Cons: US-056(행/열)·US-059(TOC)가 미지원으로 붕괴, executor가 스토리 사이클을 통째로 소모한 뒤에야 발견, acceptance가 미지원 현실과 어긋난 채 커밋. Driver 3 위반.
- Verdict: 기각.

**Option B — Truth+Evidence 먼저 + ④의 research-first 게이트를 ⑤에도 복제, 지원표면으로 재편** ✅ 선택
- Pros: 문서·런타임·테스트·제품약속 정렬. ⑤가 **실기능 3~4개**(머리/꼬리말·페이지설정·병합셀 분할) 산출. 미지원 항목은 정직한 `spike-pending`. Option B의 "안정화 먼저"를 유지하면서 breadth가 실제 능력을 낸다.
- Cons: v1 대비 "가시적 신규 툴 수"는 감소(정직한 축소). 계획 재작성 비용.
- Verdict: 채택.

**Option C — 미지원(행/열·TOC)을 OWN raw-XML로 구현**
- Pros: 행/열·TOC를 실제 제공.
- Cons: D1(재발명 금지) 위반 + 바이트보존 회귀 위험 → 불변식과 정면 충돌.
- Verdict: 기각(불변식 우선).

**Decision seed (ADR 씨앗, 최종 확정은 실행 후):**
- 다음 패스 = 안정화·제품신뢰 + 지원표면 breadth. (1) 상태를 기계판독 진실로, (2) 파일모드 e2e 아티팩트, (3) live를 증거 또는 명시 pending으로 격리, (4) `.hwp` headless는 스파이크→ADR(D12) 후에만, (5) delegate breadth는 **상류 API-표면 스파이크(US-056)로 표면 확정 후** 지원 기능만.
- **명시 기록(하류 오인 방지):** python-hwpx 2.24.0은 표 **행/열 add·remove API와 TOC API를 노출하지 않는다**. 따라서 이 두 기능은 delegate로 제공 불가이며, `spike-pending` OWN 리서치(US-060)로 재분류한다. **OWN 구현 시에도 바이트보존을 약화하거나 D1을 위반하는 raw-XML 재발명은 금지**하며, 그 제약을 못 지키면 keep-out(미제공)이 정직한 결론이다. (`HwpxDocument.add_control/add_bookmark/add_hyperlink`가 존재하므로 컨트롤 기반 TOC 조립의 이론적 여지는 있으나 delegate 원라이너가 아니라 OWN 리서치 영역 — US-060에서 판정.)
- 대안 A/C는 위 사유로 무효화. 최종 ADR(Decision/Drivers/Alternatives/Why/Consequences/Follow-ups)은 Architect·Critic 재검토 반영 후 확정.

---

## 2. Story breakdown

> 공통 게이트(모든 스토리 DoD, PowerShell / 리포 루트):
> ```powershell
> Set-Location E:/github/Hangeul-mcp
> ./.venv/Scripts/python.exe -m pytest -q
> ./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests
> ./.venv/Scripts/python.exe -m json.tool docs/prd.json > $null
> git diff --check
> ```
> prd.json id 표기: 기존 **US-000~US-046**(최소 id는 US-000), 신규 **US-047~US-060**.

### Phase ① 문서-런타임 상태 일치화 — M12-Doc-Runtime-Truth

**US-047 — prd.json 기계판독 상태 매트릭스 도입**
- Scope: 각 story에 `status` enum(`complete`/`optional-gated`/`desktop-live-pending`/`spike-pending`) 추가, 기존 `passes`와 동기화. 예: US-029→`desktop-live-pending`(passes:false), US-023~US-041 위임/렌더→`optional-gated`, US-042→`spike-pending`, 나머지→`complete`.
- Acceptance (testable):
  - prd.json 파싱 성공, **47개 story(US-000~US-046)** 각각 유효 `status` 값 보유.
  - `status=="complete"` ↔ `passes==true` 정합; `desktop-live-pending`/`spike-pending` story는 증거 미확보 사유 노트 보유.
  - 새 테스트 `tests/test_prd_status.py`가 위 불변식을 검증.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m json.tool docs/prd.json > $null
  ./.venv/Scripts/python.exe -m pytest tests/test_prd_status.py -q
  ```
- Non-goals: story 내용/수용기준 재작성 금지(상태 필드만 추가).

**US-048 — README 카운트 동기화 + 파싱대상 특정 드리프트 가드 (G2 반영)**
- Scope: README stale 수치 교정 및 **드리프트 가드가 파싱·대조하는 출현을 명시적으로 특정**.
  - L182 repo-tree `33 tools` → `35 tools`.
  - L184 `167 tests` → `190 collected (189 pass + 1 skipped)`.
  - L150 상태줄 `38개 — 37 pass + 1` → `47개 — 46 pass + 1 desktop-live-pending`.
  - L95 `105+ passed` → 현행 수치로.
- Acceptance (testable):
  - `tests/test_maintainability.py` 확장 — 각 README 숫자를 **레이블드 정규식으로 특정**해 런타임/데이터 소스와 **동적** 대조(하드코딩 금지):
    - `N tools`(repo-tree 출현) == `len(mcp.list_tools())` (=35).
    - 상태줄 `N개 — M pass`의 story 수 == `len(prd stories)` (=47), pass 수 == prd `status==complete`(또는 passes==true) 개수 (=46).
  - **파싱 대상 명문화:** 가드는 위 두 출현을 **모두** 대조한다(한 곳만 가드해 다른 곳이 재드리프트하는 것 방지). 대안으로 카운트를 단일 SSOT 블록으로 통합 가능.
  - test-count(`190 collected`)는 `pytest --collect-only`와 대조하는 **회귀 가드(soft)**로 둔다(parametrize/skip 변동성 때문에 hard assert 부적합 — Architect 확인).
  - **⑤가 툴을 추가하면 같은 커밋에서 README `N tools` 수치를 갱신**해야 가드가 통과(가드가 이를 강제).
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -c "import asyncio; from hangeul_mcp import server; print(len(asyncio.run(server.mcp.list_tools())))"
  ./.venv/Scripts/python.exe -m pytest tests/test_maintainability.py -q
  ```
- Non-goals: 상태 산문 창작 금지, 관측 수치만 반영.

**US-049 — HANDOFF.md 대체 + 상태 매트릭스 SSOT (G/체크리스트 8 반영)**
- Scope: 완전 stale한 HANDOFF.md(56 passed·6툴·Phase A~D 미래작업 프레이밍)를 현재 기준선으로 재작성, 4상태 매트릭스 SSOT 섹션 추가. ROADMAP 완료 표기와 정합.
- Acceptance (testable):
  - 새 에이전트가 **한 파일만** 읽고 현재 상태(35 tools, 189/1, US-029 pending, `.hwp` spike-pending, 행/열·TOC spike-pending, render/delegate optional-gated)를 stale 노트 의존 없이 파악.
  - **HANDOFF.md에 실재하는 stale 토큰이 제거됨**(grep 0건): `56 passed`(L13), `6툴`(L24), `Phase A~D 전부`(L26).
  - README·ROADMAP·HANDOFF 세 문서의 tool/test/story 수치 상호 일치.
- Verification:
  ```powershell
  Select-String -Path HANDOFF.md -Pattern '56 passed','6툴','Phase A~D 전부'   # 0건이어야 함
  ```
- Non-goals: 새 기능 약속 추가 금지, 현행 사실만 기술.

---

### Phase ② 파일모드 e2e 증거팩 — M13-FileMode-Evidence

**US-050 — 재현 가능한 파일모드 e2e 드라이버 + 증거 산출물**
- Scope: `scripts/e2e_evidence.py`(또는 `tests/test_e2e_evidence.py`) 신설 — 고정 순서: `describe_capabilities`→`analyze_form`→`scan_pii`→`fill_form(dry_run=True)`→`fill_form`→`verify_fill`→`validate_hwpx`→`render_preview`. 입력 `tests/fixtures/sample_form.hwpx`(PII 없는 빈 강사카드). 산출물은 gitignore 경로(예 `build/evidence/`), 재생성법 docs 명문화. (8개 툴 전부 런타임 목록에 존재 — 양 리뷰어 확인.)
- Acceptance (testable):
  - 최소 1개 HWPX가 analyze→fill→verify→validate 통과(`verify_fill` present, `validate_hwpx.valid==True`).
  - `fill_form(dry_run=True)` 파일 미생성(관측), 실제 `fill_form`은 바이트보존(변경 외 엔트리 payload 동일).
  - render 가능 환경: 비어있지 않은 PNG + 시그니처/치수 기록. render 불가: `render_preview`의 `available:false`를 **관측 결과로 그대로 기록**(시각 pass 위장 금지).
  - 드라이버 결정적 재실행 가능 + 재생성 명령 docs 존재.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe scripts/e2e_evidence.py
  ./.venv/Scripts/python.exe -m pytest tests/test_client_stdio.py tests/test_render_preview.py -q
  ```
- Non-goals: 증거 산출물 git 커밋 금지(경로/재생성법만), 실 PII fixture 금지.

**US-051 — CI extras 레인 = dev+delegate+render (체크리스트 9 반영)**
- Scope: CI(`.[dev]`만)에서 importorskip으로 ~37개 delegate/render 테스트가 skip되는 사실 해소. **ubuntu 실행 가능 조합은 `dev+delegate+render`뿐**(`live`/`com`은 `sys_platform=='win32'` — 실측) → extras 레인을 이 범위로 고정.
- Acceptance (testable):
  - 새 CI job(또는 기존 매트릭스 확장)이 `pip install -e ".[dev,delegate,render]"` + `python -m playwright install chromium`으로 delegate/render 테스트를 green 실행.
  - **win32 전용 `live`/`com` 테스트를 ubuntu에서 강제 실행하지 않음**.
  - "189 passed"가 extras 설치 로컬 기준임을, CI 기본(`.[dev]`) 기준과 구분해 문서화.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest -q -rs   # skip 사유 목록
  ```
- Non-goals: win32-only(live COM) CI 강제 실행 금지.

---

### Phase ③ 라이브 데스크톱 QA 레인 — M14-Live-Desktop-QA (DELIBERATE, pre-mortem §6-A)

**US-052 — PII 없는 live fixture + 데스크톱 QA runbook(헤드리스 검증 가능 부분)**
- Scope: PII 없는 `.hwpx` live fixture + 값 매핑, `hwp_status`→`preview_cells_to_open_hwp`→`apply_cells_to_open_hwp` runbook. 순수 부분(`resolve_cell_targets`/`preview_cells_to_open`)은 헤드리스 단위테스트. `hwp_status`/preview는 side-effect-free(한글 미기동) 재확인.
- Acceptance (testable):
  - `preview_cells_to_open_hwp`가 COM 미호출로 table/row/col target 계산(순수), 단위테스트 green.
  - `hwp_status` side-effect-free(한글 프로세스 미기동) assert 회귀 테스트.
  - 라이브 부재 환경 `apply_cells_to_open_hwp` `available:false`(크래시 없음) 단위테스트.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest tests/test_com.py tests/test_live_resolve.py -q
  ```
- Non-goals: 실기기 없이 live apply 성공 주장 금지.

**US-053 — live apply 실기기 검증 또는 명시적 PENDING**
- Scope: Windows + 한컴 + 문서 열림에서 `HANGEUL_MCP_LIVE=1`로 라이브 셀 채우기, 구체 출력(status·preview target 수·applied/skipped·COM 에러) 캡처. 데스크톱 불가 시 `PENDING_DESKTOP_LIVE_QA.md` 명시 pending. US-029 `passes:false`+`desktop-live-pending` 유지. D7(중첩표 인덱스 best-effort) 재확인.
- Acceptance (testable):
  - 실기기 확보 시: applied[] 실채움 로그 + 헤드리스 테스트 여전히 green.
  - 실기기 불가 시: `PENDING_DESKTOP_LIVE_QA` 라벨 존재, US-029 complete 승격 안 됨.
- Verification (desktop-only):
  ```powershell
  $env:HANGEUL_MCP_LIVE=1
  ./.venv/Scripts/python.exe -m pytest tests/test_com.py tests/test_live_resolve.py -q
  ```
- Non-goals: 증거 없이 완료 선언 금지. **데스크톱 증거 미확보 시 pending 종결이 정상 결과.**

---

### Phase ④ .hwp headless substrate 스파이크 — M15-HWP-Headless-Spike (research-first, DELIBERATE, pre-mortem §6-B)

**US-054 — 후보 비교 스파이크 + ADR(D12)**
- Scope: 비COM `.hwp` reader 후보(`rhwp`/`pyhwp`·`hwp5`/`kordoc`/기타) 비교 — 라이선스·설치성·CLI/API 형태·fixture 요건. `hwp_headless.py` `CANDIDATES=("rhwp","kordoc","hwp5","pyhwp")` 기준. 결정 ADR(D12) 기록. 증명 전 adapter gate 유지.
- Acceptance (testable):
  - 후보별 라이선스·설치성·API·fixture 요건이 표로 기록 + go/no-go 판정.
  - "no viable substrate" 판정 시 사유 ADR 명시 + `extract_hwp_text` `available:false` adapter gate 유지(기존 `tests/test_hwp_headless.py` green).
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest tests/test_hwp_headless.py -q
  ```
- Non-goals: 미검증 substrate로 완료 주장 금지, COM 변환을 headless로 위장 금지(D9).

**US-055 — (조건부) 실 substrate 어댑터 구현**
- Scope: US-054가 실행 가능·라이선스 안전 substrate + PII 없는 `.hwp` fixture를 확정한 경우에만 실제 비COM **텍스트** 추출 구현. 없으면 "keep gate"로 명시 종결(구현 없음).
- Acceptance (testable):
  - substrate 확정 시: substrate 없으면 실패/있으면 통과하는 비COM 추출 테스트 + PII 없는 fixture 기대 텍스트 대조.
  - substrate 미확정 시: 코드 무변경, `spike-pending` 유지, ADR가 keep-gate 근거 보유.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest tests/test_hwp_headless.py -q
  ```
- Non-goals: 라이선스/PII 미확인 fixture 커밋 금지. **구조(표/양식) 파싱은 이 스토리 scope 아님**(텍스트 추출로 한정, 구조는 별도 후속).

---

### Phase ⑤ Breadth — M16-Breadth (상류 스파이크 게이트 + 지원표면만 delegate)

> 공통 delegate 패턴: MCP tool 노출(`hangeul_mcp/tools_delegate.py`) + optional-dep 구조화 폴백 + **버전 게이트(`>=2.24` feature-detect)** + `validate_hwpx` 게이트(valid==True) + fixture 데모(importorskip("hwpx")) + docs scope/non-goals. 위임은 python-hwpx 2.24.0 API를 얇게 감쌈(재발명 금지, 바이트동일 아님).

**US-056 — ⑤ 상류 단일 delegate API-표면 스파이크 (체크리스트 1, ④ US-054 패턴 복제)**
- Scope: ⑤ 착수 전 python-hwpx 2.24.0 delegate API 표면을 한 번에 확정. **실측 결과 pre-seed**(양 리뷰어 재확인):
  - `HwpxOxmlTable`: `cell, column_count, create, get_cell_map, iter_grid, mark_dirty, merge_cells, row_count, rows, set_cell_shading, set_cell_text, set_column_widths, split_merged_cell` → **행/열 add·remove·임의 split 부재**, `split_merged_cell`만.
  - `HwpxDocument`: `set_header_text/set_footer_text/set_header_content/set_footer_content/set_header_footer/remove_header/remove_footer` ✓, `set_page_number/set_page_size/set_page_margins/set_page_setup/set_columns` ✓, `add_control/add_bookmark/add_hyperlink` ✓, **`toc`/`generate_toc` 부재**.
- Acceptance (testable):
  - 스파이크 문서(ADR 부속 또는 `docs/DECISIONS.md` D13)가 위 표면을 지원/미지원으로 분류: 지원={header/footer, page-setup, split_merged_cell}, 미지원={row/col add·remove, TOC}.
  - `tests/test_delegate_api_surface.py`(importorskip hwpx)가 `getattr`/`hasattr`로 지원 메서드 존재 + 미지원 메서드 부재를 assert(회귀 시 fail).
  - python-hwpx `>=2.24` 요구가 명문화됨.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest tests/test_delegate_api_surface.py -q
  ```
- Non-goals: 이 스토리에서 툴 추가 안 함(표면 확정만). 미지원 메서드를 OWN으로 대체 구현 금지.

**US-057 — 머리말/꼬리말 (delegate, breadth 선두 승격 — 체크리스트 4)**
- Scope: `set_header`/`set_footer`(python-hwpx `set_header_text`/`set_footer_text` 위임) + validate 게이트 + optional-dep·버전 폴백 + fixture 데모. 텍스트는 클라이언트 제공(두뇌손분리).
- Acceptance (testable):
  - 설정 후 output `validate_hwpx.valid==True`이며 머리말/꼬리말 텍스트가 산출물에 존재(importorskip 테스트).
  - python-hwpx 미설치 `available:false`; `<2.24` 시 `requires >=2.24` 구조화 메시지.
  - 기존 바이트보존 테스트 불변, pyflakes clean.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest -q -k "header or footer"
  ```
- Non-goals: 서버가 머리말 문안 생성 안 함(클라이언트 텍스트만 배치).

**US-058 — 페이지 설정 (NEW, 체크리스트 4 — 공문 고가치)**
- Scope: `set_page_number`/`set_page_size`/`set_page_margins`/`set_columns`(전부 실지원 확인) 위임 MCP 툴 + validate 게이트 + optional-dep·버전 폴백 + fixture 데모. 공문 페이지번호·여백·단 설정 등 공공기관 고가치.
- Acceptance (testable):
  - 각 설정 후 output `validate_hwpx.valid==True`; 설정 반영이 재열람/outline로 관측 가능한 범위에서 확인(importorskip 테스트).
  - python-hwpx 미설치 `available:false`; `<2.24` 시 `requires >=2.24`.
  - 잘못된 인자(음수 여백 등)는 구조화 `ok:false`.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest -q -k "page"
  ```
- Non-goals: 렌더 의존 레이아웃(실제 렌더 페이지 수) 검증은 non-goal(설정값 반영·valid 게이트로 한정).

**US-059 — 병합셀 분할 split_merged_cell (delegate, 명칭·acceptance 정정 + G1 fixture 전제조건)**
- Scope: `table_split_merged_cell`(python-hwpx `split_merged_cell` 위임) + validate 게이트 + optional-dep·버전 폴백. **v1의 "임의 셀 split(셀 수 증가)"은 python-hwpx에 없으므로 폐기**; 실제 기능은 "이미 병합된 셀을 분할(병합 해제)".
- Acceptance (testable):
  - **fixture 전제조건(명시):** `tests/fixtures/merged_cells.hwpx`(또는 병합 영역이 확인된 강사카드)는 **rowSpan/colSpan>1 병합 셀을 최소 1개 포함**해야 한다. 테스트는 먼저 이 전제를 assert(병합셀 없으면 loud fail — **vacuous pass 방지**).
  - 병합셀 분할 후 `get_cell_map`(또는 get_table_map)에서 해당 영역이 언머지되어 셀 수가 증가 + `validate_hwpx.valid==True`(importorskip 테스트).
  - python-hwpx 미설치 `available:false`; `<2.24` 시 `requires >=2.24`.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest tests/test_delegate_table_ops.py -q
  ```
- Non-goals: 병합 안 된 셀을 임의 분할하는 기능은 python-hwpx 미지원 → non-goal 명문화. OWN raw-XML 분할 재발명 금지.

**US-060 — 표 행/열 add·remove + TOC → spike-pending OWN 리서치 재분류 (체크리스트 2)**
- Scope: python-hwpx 2.24.0이 **행/열 add·remove API와 TOC API를 미노출**함이 US-056으로 확정됨 → delegate 스토리에서 제거. 대신 OWN 구현 타당성 리서치(구현 아님). TOC는 `add_control/add_bookmark/add_hyperlink` 기반 컨트롤 조립의 이론적 여지를 조사(OWN 영역).
- Acceptance (testable):
  - ADR(D13 또는 별도)에 **python-hwpx 미지원 명시** + OWN 구현 타당성 판정(implement-later / keep-out) + 사유.
  - **미지원 기능의 실제 동작(행/열 수 변화·TOC 항목 반영)에 대한 acceptance를 커밋하지 않음** — 결과물은 ADR 결정뿐.
  - **불변식 제약 명시:** OWN 구현이 바이트보존을 약화하거나 D1을 위반하면 keep-out이 정직한 결론.
  - 코드 무변경(delegate 미추가), 상태 `spike-pending`.
- Verification:
  ```powershell
  ./.venv/Scripts/python.exe -m pytest -q   # 회귀 없음(코드 무변경) 확인
  ```
- Non-goals: 행/열·TOC 실기능 제공을 이 스토리에서 약속하지 않음. OWN raw-XML로 바이트보존 깨는 구현 금지.

**delegate 버전 플로어 상향 (체크리스트 5, US-057~059 횡단)**
- `pyproject.toml`의 `delegate = ["python-hwpx>=2.20"]` → **`>=2.24`**로 상향, **그리고** `delegate_base`/`delegate_edit`에 `getattr` feature-detect를 넣어 2.20 환경에서 `AttributeError`→`ok:false` 원인 은폐 대신 **`{"available":True,"ok":False,"error":"requires python-hwpx>=2.24"}`** 반환. US-057/058/059의 DoD에 포함.

---

## 3. Sequencing & dependencies

- **Lane A (docs truth, 병렬-safe):** US-047(prd.json) · US-048(README+가드) · US-049(HANDOFF) — 다른 파일이라 병렬. **가장 먼저**(진실 기준선). US-048 가드는 런타임 tool-count(35)·prd story-count(47)에 동적 의존.
- **Lane B (evidence, 병렬):** US-050(e2e 드라이버) · US-051(CI extras 레인) — Lane A와 병행.
- **③ 순차:** US-052(prep, 병렬-safe) → **US-053(live 실행)** — 데스크톱 증거 미확보 시 **pending 종결이 정상**. US-029 complete 승격 금지.
- **④ research-first 순차:** US-054(스파이크·ADR, 병렬-safe) → **US-055(조건부 구현)** — "no viable substrate" 시 keep-gate 종결.
- **⑤ 게이트 순차:** **US-056(상류 API 스파이크) 먼저** → 그 뒤 US-057·US-058·US-059 **병렬-safe**(서로 다른 API), **US-060은 US-056 결과 기반 재분류(리서치, 코드 무변경)**. ⑤는 chosen Option B에 따라 ①②안정화 이후 배치.
- **전역 게이트:** 각 스토리 완료 시 공통 게이트 통과. **US-057~059가 툴 추가 시 US-048 README 수치 동시 갱신**(가드가 강제).

병렬화 요약: {US-047,048,049} ∥ {US-050,051} ∥ {US-052,US-054,US-056}. 순차 의존: US-052→053, US-054→055, **US-056→{057,058,059,060}**.

---

## 4. Risks (top 6) + 완화

1. **⑤가 미지원 API에 acceptance 커밋(v1의 근본 결함).** 완화: US-056 상류 단일 스파이크가 표면을 착수 전 확정, US-060으로 행/열·TOC 재분류(acceptance 미커밋), US-059는 병합셀 분할로 정정+fixture 전제조건.
2. **바이트보존 회귀.** 완화: 위임 경로는 `validate_hwpx` 게이트로만 무결성 판정(바이트동일 요구 안 함), OWN fill 바이트보존 테스트 미접촉, US-060이 OWN raw-XML 재발명을 명시 금지.
3. **live 데스크톱 QA 이 실행에서 불가 → US-029/US-053 정체.** 완화: `PENDING_DESKTOP_LIVE_QA` 명시 라벨 + 상태 매트릭스, complete 승격 금지(pending 종결 정상). pre-mortem §6-A.
4. **`.hwp` substrate 후보 전부 부적합.** 완화: research-first 스파이크 + go/no-go, ADR keep-gate가 유효 결론, fixture 증명 전 코드 무변경. pre-mortem §6-B.
5. **버전 플로어 불일치(2.20에서 조용한 실패).** 완화: `delegate>=2.24` 상향 + getattr feature-detect로 `requires >=2.24` 구조화 반환.
6. **문서 드리프트 재발(파싱 대상 미특정).** 완화: US-048 가드가 `N tools`(repo-tree)·`N개 — M pass`(상태줄) **두 출현을 특정해 동적 대조**, ⑤ 툴 추가 시 같은 커밋 갱신 강제.

---

## 5. Files expected to change (phase별)

- **① Doc-Runtime:** `docs/prd.json`(status 필드), `tests/test_prd_status.py`(신규), `README.md`(L95·L150·L182·L184), `tests/test_maintainability.py`(파싱대상 특정 가드 확장), `HANDOFF.md`(전면 재작성), `docs/ROADMAP.md`(정합).
- **② Evidence:** `scripts/e2e_evidence.py`(신규) 또는 `tests/test_e2e_evidence.py`, `.gitignore`(증거 경로), `docs/byo-ai-harness.md`(재생성 절차), `.github/workflows/ci.yml`(extras 레인 `dev,delegate,render`), `README.md`(189=로컬 extras 기준 명시).
- **③ Live QA:** `tests/fixtures/`(PII 없는 live fixture), `tests/test_live_resolve.py`·`tests/test_com.py`(순수 부분 보강), `PENDING_DESKTOP_LIVE_QA.md`(조건부 신규), `docs/prd.json`(US-029 status), `docs/DECISIONS.md`(D7 재확인).
- **④ HWP Spike:** `docs/DECISIONS.md`(D12 ADR), `hangeul_core/hwp_headless.py`(조건부, substrate 확정 시만), `tests/test_hwp_headless.py`(조건부 실추출 테스트), `tests/fixtures/`(조건부 PII 없는 `.hwp`).
- **⑤ Breadth:**
  - 스파이크/ADR: `tests/test_delegate_api_surface.py`(신규), `docs/DECISIONS.md`(D13: delegate 표면 + 행/열·TOC 미지원·OWN 재분류).
  - delegate 구현: `hangeul_core/delegate_edit.py`(머리/꼬리말·페이지설정·병합셀 분할 위임 + getattr feature-detect), `hangeul_core/delegate_base.py`(버전 게이트 헬퍼), `hangeul_core/delegate.py`(re-export), `hangeul_mcp/tools_delegate.py`(툴 등록), `tests/test_delegate_table_ops.py`·신규 페이지/헤더 테스트, `tests/fixtures/merged_cells.hwpx`(병합셀 fixture).
  - 메타: `pyproject.toml`(`delegate = ["python-hwpx>=2.24"]`), `README.md`·`docs/ROADMAP.md`(scope/non-goals, 행/열·TOC=spike-pending).
  - 재분류(US-060): 코드 무변경, `docs/DECISIONS.md`·`docs/prd.json`(status만).

---

## 6. Pre-mortem & 확장 테스트 계획 (③④ deliberate 레인 — 체크리스트 7, 지금 명문화)

### 6-A. Lane ③ Live 데스크톱 QA (US-052/053)

**Pre-mortem (구체 실패 시나리오 4):**
1. **Session 0 격리로 COM attach 실패** — 비대화형 세션에서 Running Object Table에 사용자 Session 1 한글이 안 보여 `Hwp(new=False)` 실패. 관측: `{"available":True,"connected":False,"error":...}`. 완화: 데스크톱 대화형(Claude Desktop) 전용 실행 명시, headless CI는 pure resolve만.
2. **표 인덱스 매핑 오차(D7) → 열린 문서 오염** — 중첩표/병합셀 문서에서 `get_into_nth_table` 컨트롤 순서 ≠ analyze 전역 인덱스 → 엉뚱한 셀에 삽입. 완화: fixture를 단일/최상위 표로 제한, apply 전 `preview_cells_to_open_hwp`로 target 확인 강제, `clear=False` 검토, D7 best-effort 라벨 유지.
3. **clear 후 삽입 예외로 부분 손상** — `HAction.Run("Delete")` 성공 후 `insert_text` 예외 → 셀이 비워진 채 미채움. 완화: per-target try/except로 skipped 기록, 저장 전이면 Ctrl+Z 가능함을 runbook 명시.
4. **pyhwpx 전이 의존성(numpy) import 실패** — 사용자는 설치했다고 오인. 완화: `live_available()`이 실제 import까지 시도(구현됨), 진단에 누락 의존성 표시.

**확장 테스트 계획:**
- unit: `resolve_cell_targets`(단일표·라벨키·미매칭 skip), `live_available()` False 경로, `preview_cells_to_open` side-effect-free.
- integration: `apply_cells_to_open_hwp` non-win32/pyhwpx 부재 시 `available:false` 구조화(크래시 없음), 서버 툴 등록 확인.
- e2e (desktop-only, `HANGEUL_MCP_LIVE=1`): 실제 열린 강사카드 preview→apply, applied[]/skipped[] 캡처, 저장 없이 창 유지 확인.
- observability: apply 결과에 `connected`/applied count/skipped reason/COM error text 포함; 실기기 불가 시 `PENDING_DESKTOP_LIVE_QA.md`에 관측 산출물 경로·환경 기록.

### 6-B. Lane ④ .hwp headless substrate (US-054/055)

**Pre-mortem (구체 실패 시나리오 4):**
1. **모든 후보 라이선스/유지보수 부적합** — rhwp(WASM 번들)·pyhwp/hwp5(GPL·구버전·Python 호환)·kordoc(MCP 서버형, 라이브러리 아님) → 임포트 가능 substrate 없음. 완화: research-first go/no-go, ADR에 후보별 기각 사유, adapter gate 유지(keep-gate 정상 결론).
2. **텍스트는 나오나 구조 유실** — 리더가 평문만 뽑고 셀/라벨 구조 없음 → analyze/understand와 불연결. 완화: US-055 scope를 "텍스트 추출"로 한정, 구조 파싱은 별도 후속으로 분리.
3. **PII 없는 실 `.hwp` fixture 확보 실패** — COM 없이 합성 `.hwp` 생성 곤란 → 검증 입력 부재로 vacuous. 완화: fixture 확보를 US-055 명시 전제조건으로, 미확보 시 keep-gate 종결(구현 없음).
4. **substrate 설치가 CI/크로스플랫폼 파손** — win32 전용/네이티브 빌드 의존. 완화: optional extra 격리, 미설치 `available:false`, CI 기본 설치 미포함.

**확장 테스트 계획:**
- unit: `headless_status()`가 CANDIDATES find_spec 반환, substrate 부재 시 `extract_hwp_text` `available:false` + `checked` 딕셔너리.
- integration: `.hwp` 아닌 확장자 거부, 파일 부재 처리, 기존 COM 변환 정책(`test_convert.py`) 불변.
- e2e (조건부, substrate 확정 시): PII 없는 `.hwp` fixture에서 substrate 없으면 실패/있으면 통과하는 추출 테스트 + 기대 텍스트 대조.
- observability: ADR(D12)에 후보별 라이선스·설치성·API·fixture 요건 표 + go/no-go; keep-gate 시 근거 기록.
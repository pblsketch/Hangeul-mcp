# RALPLAN — Hangeul-mcp BYO-AI Live Harness

## 0. 한 줄 목표

Hangeul-mcp를 “자체 AI 앱”이 아니라 **사용자가 이미 구독 중인 AI가 한글/HWP/HWPX 문서 작업을 로컬에서 수행하게 해주는 BYO-AI 문서 하네스**로 재정렬한다.

## 1. Requirements Summary

### 제품 목표

사용자는 별도 API 결제를 하지 않고, 자신이 이미 구독하는 AI 클라이언트에서 Hangeul-mcp 도구를 호출한다. Hangeul-mcp는 로컬 PC에서 HWP/HWPX 문서를 읽고, 분석하고, 편집하고, 미리보기와 검증을 제공한다.

### 핵심 전환

기존 목표:

- HWPX 양식 인식·채우기 MCP
- 일부 COM live apply
- python-hwpx 위임으로 commodity breadth 확장

새 목표:

- BYO-AI 로컬 문서 하네스
- HWPX 파일 모드 + 열린 한글 라이브 모드 병행
- 사용자의 AI 구독을 전제로 한 MCP-first UX
- 서버 자체 LLM/API 호출 금지
- 한글 문서 작성·편집·양식 채우기·검증·미리보기 전체 경험 설계

### 현 코드 근거

- `hangeul_mcp/server.py:588-594` — `hwp_status`는 live COM 가용성 보고 도구다.
- `hangeul_mcp/server.py:597-622` — `apply_to_open_hwp`는 열린 한글 문서 누름틀에 `PutFieldText`로 반영한다.
- `hangeul_mcp/server.py:625-645` — `apply_cells_to_open_hwp`는 열린 한글 문서의 셀을 live로 채운다.
- `hangeul_core/hwp/com.py:1-9` — COM 브리지는 열린 한글 창을 채우는 유일 경로이며 status는 side-effect-free여야 한다.
- `hangeul_core/hwp/live.py:1-15` — 누름틀 없는 셀 기반 양식 live fill 경로가 이미 분리되어 있다.
- `tests/test_com.py:1-4` — 실제 COM 테스트는 `HANGEUL_MCP_LIVE=1`에서만 실행된다.
- `tests/test_live_resolve.py:1-7` — live apply 중 pure mapping은 unit test로 검증하고, COM 구동은 실기기에서 검증한다.
- `README.md:65-68` — 현재 v2 COM live 도구가 문서화되어 있다.
- `README.md:132-134` — live는 코드 완료이나 실기기 검증 대기 상태로 설명되어 있다.
- `docs/ROADMAP.md:4-12` — own-vs-delegate 원칙이 이미 있다.

## 2. RALPLAN-DR Summary

### Principles

1. **BYO-AI 우선**
   Hangeul-mcp는 LLM을 내장하지 않고, 사용자가 구독하는 AI 클라이언트가 호출하는 로컬 도구가 된다.

2. **파일 모드와 라이브 모드 분리**
   HWPX 파일 직접 편집과 열린 한글 COM 제어를 같은 개념으로 섞지 않는다.

3. **안전한 적용 흐름 우선**
   분석 → 초안/계획 → 미리보기 → 검증 → 백업 → 적용 순서를 기본 하네스로 만든다.

4. **HWPX breadth는 위임, 양식 이해는 직접 소유**
   일반 편집·생성은 python-hwpx 등 substrate에 위임하되, 빈칸/라벨/병합셀/검증은 Hangeul-mcp가 직접 소유한다.

5. **라이브는 공공기관 타깃의 장점이지만 optional이어야 함**
   Windows + 한컴오피스 의존성은 타깃 시장에서는 허용 가능하지만, headless 파일 모드를 깨면 안 된다.

### Decision Drivers

1. **사용자 비용과 도입성**
   별도 API 결제 없이 기존 AI 구독을 활용해야 한다.

2. **공공기관 한글 업무 적합성**
   HWP/HWPX, 한컴오피스, Windows 환경을 현실 전제로 삼는다.

3. **검증 가능성과 문서 손상 방지**
   자동 문서 편집은 실패 비용이 크므로 dry-run, backup, preview, verify가 우선이다.

### Viable Options

#### Option A — BYO-AI MCP 하네스 + optional live adapter 추천

**접근:** HWPX 파일 모드를 안정화하고, live COM 기능은 optional adapter로 분리한다. AI는 외부 클라이언트가 담당한다.

**장점**

- 사용자 API 비용 부담이 낮다.
- MCP 철학과 맞다.
- headless 파일 모드와 live 모드 모두 살릴 수 있다.
- 기존 코드 구조와 가장 잘 맞는다.

**단점**

- AI 클라이언트별 MCP 지원/UX 차이가 있다.
- 인라인AI처럼 하나의 통합 앱 경험은 처음부터 나오지 않는다.

#### Option B — 한글 내부 add-in/플러그인 중심

**접근:** 한글 프로그램 내부 UI에서 AI 작업을 제공한다.

**장점**

- 사용자는 문서 안에서 바로 작업하는 느낌을 받는다.
- 선택 영역/커서 컨텍스트 UX가 좋다.

**단점**

- 한컴 add-in 개발/배포/보안 난이도가 크다.
- 사용자가 구독하는 AI를 그대로 쓰기 어렵다.
- 초기 범위가 너무 커진다.

#### Option C — 자체 AI 데스크톱 앱

**접근:** Hangeul-mcp 위에 자체 AI UI와 API 과금 구조를 얹는다.

**장점**

- UX를 완전히 통제할 수 있다.
- 인라인AI와 유사한 제품 포장을 할 수 있다.

**단점**

- API 비용/과금/개인정보 책임이 커진다.
- 사용자의 “이미 구독하는 AI를 쓰고 싶다”는 목표와 충돌한다.

#### Option D — live-first COM MCP

**접근:** 파일 모드보다 열린 한글 문서 제어를 우선한다.

**장점**

- 공무원 실사용 체감이 빠르다.
- 현재 열려 있는 문서 반영이라는 강한 차별점이 있다.

**단점**

- Windows/한컴/pywin32/pyhwpx 변동성에 먼저 노출된다.
- 자동화 테스트가 어렵다.
- headless HWPX 안정성이 약해질 수 있다.

### Chosen option

**Option A를 선택한다.**
단, Milestone 2 이후부터 live adapter를 제품 핵심 경로로 끌어올리되, core와 optional dependency 경계는 유지한다.

## 3. Architect Review

### Strongest antithesis

인라인AI를 대체하려면 MCP 하네스만으로는 UX가 약할 수 있다. 사용자가 문서 안에서 바로 선택하고 수정안을 accept/reject하는 경험을 원한다면, 외부 AI 채팅창 + MCP 도구만으로는 부족할 수 있다. 또한 MCP 클라이언트마다 로컬 파일 접근, 도구 호출 노출, 미리보기 반환 UX가 다르면 제품 경험이 일관되지 않을 수 있다.

### Tradeoff tension

- **빠른 도입성:** BYO-AI MCP는 API 비용을 피하고 기존 구독을 활용한다.
- **통합 UX:** 자체 앱/한글 add-in은 UX가 좋지만 비용·보안·배포 부담이 커진다.

### Synthesis

초기에는 BYO-AI MCP 하네스를 제품 핵심으로 삼고, 이후 필요하면 얇은 companion UI를 붙인다. companion UI는 모델을 내장하지 않고, 파일 선택/미리보기/적용 승인만 담당한다. 즉 AI는 계속 사용자의 구독 AI가 맡고, Hangeul-mcp는 로컬 실행·검증·문서 반영을 맡는다.

## 4. Critic Review

### Verdict

APPROVE WITH IMPROVEMENTS.

### Required improvements applied

- “포괄”을 도구 개수 복제가 아니라 기능 영역 포괄으로 정의했다.
- 자체 API 호출 금지를 acceptance criteria에 넣었다.
- live 기능을 optional로 두되 공공기관 타깃의 핵심 UX로 발전시키는 순서를 명시했다.
- 실기기 live 테스트와 headless CI 테스트를 분리했다.
- 다음 `/ralph` 구현을 위해 Milestone 0부터 파일 touchpoint와 검증 명령을 구체화했다.

## 5. Non-goals

- 자체 LLM API 과금 시스템 구현.
- 인라인AI와 같은 완전한 데스크톱 앱 UI를 1차 구현에 포함.
- 한글 add-in 개발.
- `.hwp` binary 직접 쓰기.
- 검증 없는 live COM 자동 실행.

## 6. Acceptance Criteria

### BYO-AI / no-API 기준

- `pyproject.toml` 기본·선택 의존성에 OpenAI/Anthropic/Gemini 등 LLM API SDK가 새로 추가되지 않는다.
- Hangeul-mcp 서버 도구는 문안 생성용 외부 API를 호출하지 않는다.
- README에 “사용자의 AI 클라이언트가 문안을 생성하고, Hangeul-mcp는 로컬 문서 작업만 수행한다”는 원칙이 명시된다.
- MCP 클라이언트 연결 예시는 API 키가 아니라 local stdio command 중심으로 제공된다.

### Harness 기준

- 새 문서/설계에 “파일 모드”, “라이브 모드”, “검증/미리보기”, “사용자 승인” 흐름이 분리되어 설명된다.
- `describe_capabilities` 또는 동등한 capability manifest 도구가 추가되어 AI 클라이언트가 현재 사용 가능한 기능과 optional dependency 상태를 알 수 있다.
- capability manifest는 최소한 다음을 구분한다.
  - `mode: file_hwpx`
  - `mode: live_hwp`
  - `mode: render`
  - `mode: hwp_headless`
  - `requires: delegate/render/com/live`

### Live 기준

- `hwp_status`는 계속 side-effect-free다. 한글 창을 띄우지 않는다.
- live apply류 도구는 unavailable 환경에서 예외를 던지지 않고 `available:false` 또는 구조화된 error를 반환한다.
- live 실기기 검증은 `HANGEUL_MCP_LIVE=1` 명시 조건 아래에서만 수행된다.
- 열린 한글 문서에 대한 1차 live 목표는 “선택 영역 편집”이 아니라 현재 구현된 “누름틀/셀 채우기 + 상태/저장/백업 확장”으로 제한한다.

### Safety 기준

- 파일 편집 경로는 `dry_run`, `backup`, `validate_hwpx`, `render_preview` 중 가능한 게이트를 연결한다.
- live 경로는 적용 전 계획/targets를 반환하는 preview/dry-run 또는 equivalent를 제공해야 한다.
- 문서 손상 가능성이 큰 도구는 out_path 또는 backup 정책을 갖는다.

### Verification 기준

- `python -m pytest -q` 통과.
- `python -m pyflakes hangeul_core hangeul_mcp tests` 통과.
- `python -m json.tool docs/prd.json` 통과.
- `git diff --check` 통과.
- MCP 도구 목록 확인 시 새 capability 도구와 기존 live 도구가 함께 노출된다.
- Windows + 한컴 실기기에서는 `set HANGEUL_MCP_LIVE=1` 후 live smoke가 별도 증거를 남긴다.

## 7. Implementation Plan

### Milestone 0 — 현재 작업트리 기준선 고정

목표: 이전 선택 확장 작업이 섞인 상태에서 새 목표 계획을 덮어쓰지 않도록 기준선을 확보한다.

작업:

1. `git status --short`로 변경 파일을 재확인한다.
2. 현재 33 tools 목록을 저장하거나 README 상태와 대조한다.
3. 전체 테스트와 pyflakes를 재실행한다.
4. `.omo/plans/hangeul-mcp-byo-ai-live-harness.md` 계획이 현재 코드 상태를 기준으로 한다는 점을 README/ROADMAP 반영 전 확인한다.

검증:

```powershell
Set-Location E:/github/Hangeul-mcp
python -m pytest -q
python -m pyflakes hangeul_core hangeul_mcp tests
python -m json.tool docs/prd.json > $null
git diff --check
```

### Milestone 1 — 제품 방향 문서 재정렬

목표: Hangeul-mcp의 공식 설명을 “HWPX 양식 채우기 MCP”에서 “BYO-AI 로컬 한글 문서 하네스”로 확장한다.

작업:

1. `README.md` 상단 상태와 제품 설명 수정.
   - 별도 API 결제 없음.
   - 사용자의 구독 AI가 MCP로 호출.
   - Hangeul-mcp는 로컬 문서 엔진.
2. `docs/ROADMAP.md`에 새 상위 전략 추가.
   - BYO-AI harness
   - file mode
   - live mode
   - safety/approval loop
3. `docs/DECISIONS.md`에 ADR 추가.
   - “서버는 LLM/API 호출을 하지 않는다.”
   - “파일 모드와 라이브 모드는 분리한다.”
   - “공공기관 타깃에서 Windows+한컴은 허용 가능한 optional substrate다.”
4. `docs/prd.json`에 새 epic/user stories 추가.
   - BYO-AI MCP harness
   - capability manifest
   - live dry-run/preview
   - no server-side LLM

수용 기준:

- README만 읽어도 “이 프로젝트가 API 과금형 AI 앱이 아니라 로컬 MCP 도구”임을 알 수 있다.
- ROADMAP은 레퍼런스 HWPX MCP 기능 포괄과 live 목표를 동시에 설명한다.

### Milestone 2 — Capability Manifest / Harness Contract

목표: 사용자의 AI 클라이언트가 Hangeul-mcp를 안전하게 호출할 수 있도록 현재 가능한 기능, 필요한 optional dependency, 위험도를 구조화해서 알려준다.

작업:

1. 새 모듈 후보:
   - `hangeul_core/capabilities.py`
2. 새 서버 도구 후보:
   - `describe_capabilities()`
3. 반환 구조 예시:

```json
{
  "product": "Hangeul-mcp",
  "mode": "byo_ai_local_harness",
  "server_side_llm": false,
  "capabilities": [
    {
      "name": "file_hwpx",
      "available": true,
      "tools": ["analyze_form", "fill_form", "validate_hwpx"]
    },
    {
      "name": "live_hwp",
      "available": false,
      "requires": ["Windows", "Hangul", "pywin32", "pyhwpx"],
      "tools": ["hwp_status", "apply_to_open_hwp", "apply_cells_to_open_hwp"]
    }
  ]
}
```

4. optional dependency 상태는 import check와 platform check로 확인한다.
5. 기존 `hwp_status`, `delegate.hwpx_available`, `render_preview`, `extract_hwp_text`의 상태를 한 곳에서 요약한다.

수용 기준:

- MCP 클라이언트가 먼저 `describe_capabilities`를 호출하면 현재 가능한 작업과 불가능한 작업을 알 수 있다.
- unavailable 상태가 failure가 아니라 명시적 capability로 표현된다.

테스트:

- `tests/test_capabilities.py`
- `tests/test_server.py` 도구 등록 검증 확장

### Milestone 3 — BYO-AI Workflow Harness

목표: “사용자의 AI가 어떤 순서로 도구를 호출해야 하는지”를 코드와 문서로 고정한다.

작업:

1. workflow 문서 추가 후보:
   - `docs/byo-ai-harness.md`
2. 권장 호출 흐름 정의:
   - 파일 양식 채우기
   - 새 문서 생성
   - 기존 문서 편집
   - 열린 한글 문서 반영
3. 각 흐름에 최소 도구 sequence를 제시한다.

파일 양식 채우기 예:

```text
detect_format
scan_pii
analyze_form
analyze_formfit
fill_form(dry_run=true)
fill_form(backup=true)
verify_fill
render_preview
```

열린 한글 반영 예:

```text
hwp_status
apply_to_open_hwp or apply_cells_to_open_hwp
verify via exported/converted HWPX if available
```

4. MCP 클라이언트 설정 예시는 API 키가 아니라 local stdio command 위주로 둔다.
5. “AI 클라이언트가 생성, Hangeul-mcp가 실행” 원칙을 모든 workflow에 반복한다.

수용 기준:

- 사용자는 Claude/ChatGPT/Codex류 MCP 클라이언트에서 어떤 순서로 써야 하는지 알 수 있다.
- 서버 자체가 프롬프트 생성/LLM 호출 책임을 지지 않는다.

### Milestone 4 — Live Mode 하네스 강화

목표: live 기능을 “실험적 함수”가 아니라 안전한 optional mode로 승격한다.

작업:

1. live status 확장 검토:
   - 현재 connected 여부
   - open document count
   - active document name/path 가능 여부
   - supported live actions
2. `apply_cells_to_open_hwp`에 dry-run/preview 성격의 target resolution 도구 추가 검토.
   - 후보: `preview_cells_to_open_hwp(path, values)`
   - 또는 기존 도구에 `dry_run=True` 추가
3. live 대상 resolution 결과를 사용자가/AI가 확인할 수 있게 반환한다.
4. live apply 전후 검증 전략 문서화.
   - 열린 문서를 임시 HWPX로 저장 가능하면 `validate_hwpx`/`extract_text`/`verify_fill` 재사용
   - 불가능하면 applied/skipped/count와 COM 반환값을 최소 증거로 남김
5. live 테스트 정책 강화.
   - unit: no COM target resolution
   - integration: unavailable graceful degradation
   - desktop smoke: `HANGEUL_MCP_LIVE=1`

수용 기준:

- live apply 전에 “어느 표/어느 셀에 들어갈지”를 확인할 수 있다.
- unavailable/headless 환경에서도 테스트가 실패하지 않는다.
- 실기기 smoke 절차가 README에 최신화된다.

### Milestone 5 — 레퍼런스 HWPX MCP 기능 포괄 전략

목표: hwpx-mcp-server의 기능을 도구 개수로 복제하지 않고, 사용자가 필요한 기능 영역으로 포괄한다.

작업:

1. `docs/gap-analysis.md` 갱신.
   - 완료된 선택 확장 항목 반영
   - 아직 남은 범용 편집 기능 재분류
2. 기능 영역 분류:
   - read/search
   - form/fill
   - table ops
   - rich formatting
   - document generation
   - render/preview
   - repair/backup/undo
   - live hwp
3. 우선순위:
   - safety/copy/undo
   - page/header/footer/table row-col
   - style/page setup
   - repair
   - `.hwp` headless reader
4. python-hwpx substrate에 있는 것은 delegate wrapper로 추가한다.
5. Hangeul-mcp 차별점인 양식 이해/검증은 delegate하지 않는다.

수용 기준:

- “포괄”이 150개 tool clone이 아니라 기능 영역 coverage로 설명된다.
- 다음 구현 대상이 문서화된 gap에서 나온다.

### Milestone 6 — No-API / Local Privacy Guard

목표: 사용자가 API 비용과 개인정보 전송 걱정 없이 설치할 수 있게 보장한다.

작업:

1. dependency audit 테스트 추가.
   - 기본 dependencies에 LLM SDK가 없는지 검사
2. docs에 privacy boundary 추가.
   - Hangeul-mcp는 파일을 로컬에서 처리
   - AI 클라이언트가 어떤 데이터를 모델에 보낼지는 클라이언트 설정/사용자 책임
   - Hangeul-mcp는 자체 전송을 하지 않음
3. `scan_pii` workflow를 BYO-AI 문서에 연결.
4. 민감정보 포함 문서에서는 먼저 `scan_pii`를 호출하라는 client guidance 작성.

수용 기준:

- 사용자는 “별도 API 키가 필요 없다”와 “문서 전송 주체는 AI 클라이언트”를 구분해 이해할 수 있다.
- Hangeul-mcp가 몰래 외부 AI API를 부르지 않는다는 테스트/문서 근거가 생긴다.

### Milestone 7 — End-to-End BYO-AI 시나리오 검증

목표: 실제 사용 흐름을 샘플로 검증한다.

시나리오 A — HWPX 양식 채우기:

1. 샘플 HWPX 분석
2. AI가 values 생성
3. `fill_form(dry_run=true)`
4. `fill_form(backup=true)`
5. `verify_fill`
6. `render_preview`

시나리오 B — 새 공문/계획서 생성:

1. AI가 blocks 생성
2. `create_document_from_blocks`
3. `validate_hwpx`
4. `render_preview`

시나리오 C — 열린 한글 문서 live 채우기:

1. Windows + 한컴 + `HANGEUL_MCP_LIVE=1`
2. `hwp_status`
3. preview/dry-run target resolution
4. `apply_to_open_hwp` 또는 `apply_cells_to_open_hwp`
5. 결과 증거 기록

수용 기준:

- 각 시나리오는 명령, 입력, 출력, 검증 증거를 문서에 남긴다.
- live 시나리오는 headless CI 통과와 별개로 desktop evidence를 요구한다.

## 8. Risks and Mitigations

### Risk 1 — MCP 클라이언트별 UX 차이

완화:

- 서버는 도구 계약과 capability manifest를 안정화한다.
- 클라이언트별 문서는 별도 appendix로 분리한다.
- 특정 AI 제품 종속 표현을 피한다.

### Risk 2 — live COM 불안정성

완화:

- status는 side-effect-free 유지.
- live apply는 explicit action만 수행.
- unit/pure tests와 desktop smoke tests를 분리.
- unavailable 시 구조화된 error를 반환한다.

### Risk 3 — 문서 손상

완화:

- backup/out_path 기본화.
- dry-run/preview/validate/render 단계를 workflow에 넣는다.
- live는 apply 전 target preview를 먼저 구현한다.

### Risk 4 — “API 비용 없음” 오해

완화:

- Hangeul-mcp는 자체 API 비용이 없다는 뜻임을 명시한다.
- 사용자의 AI 구독/클라이언트 비용은 별개라고 문서화한다.

### Risk 5 — 목표 과대화

완화:

- 인라인AI 전체 UX 복제는 non-goal.
- 1차 성공 기준은 BYO-AI MCP 하네스 + HWPX/file + 안전한 live apply다.

## 9. Verification Plan

기본 검증:

```powershell
Set-Location E:/github/Hangeul-mcp
python -m pytest -q
python -m pyflakes hangeul_core hangeul_mcp tests
python -m json.tool docs/prd.json > $null
git diff --check
```

도구 등록 검증:

```powershell
python -c "import asyncio; from hangeul_mcp import server; print(len(asyncio.run(server.mcp.list_tools())))"
```

render 검증:

```powershell
python -m pytest tests/test_render_preview.py -q
```

live desktop 검증:

```powershell
Set-Location E:/github/Hangeul-mcp
pip install -e ".[com,live]"
set HANGEUL_MCP_LIVE=1
python -m pytest tests/test_com.py tests/test_live_resolve.py -q
```

주의:

- live desktop 검증은 Windows + 한컴 설치 + 열린 문서 조건에서만 완료 판정한다.
- headless CI에서 live substrate 부재는 실패가 아니라 `available:false` graceful degradation으로 판정한다.

## 10. ADR

### Decision

Hangeul-mcp는 자체 AI/API 과금 앱이 아니라 **BYO-AI 로컬 한글 문서 하네스**로 발전시킨다. HWPX 파일 모드는 core로 유지하고, 열린 한글 문서 live 기능은 optional adapter로 분리하되 공공기관 타깃의 핵심 확장 경로로 둔다.

### Drivers

- 사용자는 이미 구독하는 AI를 쓰고 싶어 한다.
- 별도 API 결제는 도입 장벽이다.
- 공무원/공공기관은 Windows + 한컴오피스 환경이 일반적이다.
- 문서 자동 편집은 검증·백업·미리보기가 필수다.

### Alternatives considered

- 한글 add-in 중심 제품
- 자체 AI 데스크톱 앱
- live-first COM MCP
- HWPX file-only MCP

### Why chosen

BYO-AI MCP 하네스는 현재 코드 구조, 사용자 비용 요구, 공공기관 환경, MCP 생태계 방향을 가장 잘 만족한다. 파일 모드와 live 모드를 분리하면 cross-platform 안정성과 Windows live 차별점을 모두 유지할 수 있다.

### Consequences

- Hangeul-mcp는 자체 LLM 호출을 하지 않는다는 원칙을 문서와 테스트로 지켜야 한다.
- capability manifest와 workflow 문서가 중요해진다.
- live 기능은 optional이지만 실사용 핵심이므로 별도 QA 체계가 필요하다.
- 향후 companion UI를 붙일 수 있지만, 1차 목표는 MCP 하네스다.

### Follow-ups

- capability manifest 구현
- BYO-AI workflow 문서화
- live preview/dry-run 추가
- gap-analysis 갱신
- no-API/privacy guard 테스트 추가
- desktop live smoke 증거 확보

## 11. Available-Agent-Types Roster

계획 이후 실행에 쓸 수 있는 역할:

- `explorer` — read-only 코드베이스 탐색, 파일/심볼 위치 확인
- `worker` — 구현 작업, 명확한 파일 ownership 필요
- `lazycodex-executor` — 작은 단위의 검증 포함 구현
- `lazycodex-code-reviewer` — diff와 테스트 근거 기반 코드 리뷰
- `lazycodex-qa-executor` — 실제 시나리오/manual QA 증거 수집
- `lazycodex-gate-reviewer` — 최종 승인 전 재감사
- `librarian` — 외부 레퍼런스/공식문서 조사
- `metis` — 계획 전 모순/리스크 점검
- `momus` — 계획 실행 가능성 리뷰

## 12. Follow-up Staffing Guidance

### Recommended `$ralph` path

단일 소유자가 Milestone 0부터 순차 구현한다.

권장 명령:

```text
/ralph E:/github/Hangeul-mcp/.omo/plans/hangeul-mcp-byo-ai-live-harness.md 계획대로 Milestone 0부터 구현해줘.
```

권장 순서:

1. Milestone 0 기준선 검증
2. Milestone 1 문서/PRD 정렬
3. Milestone 2 capability manifest 구현
4. Milestone 3 BYO-AI workflow 문서
5. Milestone 4 live dry-run/preview
6. Milestone 6 no-API/privacy guard
7. Milestone 7 e2e 시나리오 증거

권장 reasoning:

- 문서/PRD: medium
- capability manifest: medium
- live harness: high
- QA/gate: high

### Recommended `$team` path

병렬화가 필요하면 다음처럼 분리한다.

Lane A — Documentation/Product

- 담당: README, ROADMAP, DECISIONS, PRD, BYO-AI docs
- 위험: 제품 정의 과장
- 검증: 문서가 no-API/BYO-AI/local harness를 일관되게 설명

Lane B — Capability Manifest

- 담당: `hangeul_core/capabilities.py`, `hangeul_mcp/server.py`, tests
- 위험: optional dependency check가 side-effect를 만들 수 있음
- 검증: headless 환경에서 predictable output

Lane C — Live Harness

- 담당: `hangeul_core/hwp/live.py`, `hangeul_core/hwp/com.py`, server live tools, live tests
- 위험: COM dispatch 부작용
- 검증: status no-dispatch, apply graceful unavailable, desktop smoke

Lane D — Safety/Privacy QA

- 담당: dependency audit, scan_pii workflow, render/verify e2e
- 위험: “API 비용 없음” 오해
- 검증: no LLM SDK dependency, no outbound model calls in server code

Team verification path:

1. 각 lane은 변경 파일과 검증 명령 출력을 제출한다.
2. 통합자는 전체 `pytest`, `pyflakes`, `json.tool`, `diff --check`를 실행한다.
3. QA lane은 file-mode e2e 증거를 남긴다.
4. live lane은 실기기 검증이 불가능하면 `PENDING_DESKTOP_LIVE_QA`로 명확히 남기고 완료 선언하지 않는다.

## 13. Goal-Mode Follow-up Suggestions

- 기본 권장: `$ultragoal`
  장기 제품 전환 목표이므로 Milestone별 durable goal tracking에 적합하다.

- 연구가 필요한 경우: `$autoresearch-goal`
  `.hwp` headless reader substrate 선정이나 MCP 클라이언트별 UX 비교가 주 작업이면 적합하다.

- 성능 최적화가 중심이 될 때: `$performance-goal`
  render latency, large document parse throughput, live apply latency 목표가 생기면 사용한다.

권장 조합:

- 구현은 `$ralph`
- 큰 병렬 구현은 `$team`
- 장기 진행 관리는 `$ultragoal`

## 14. Stop Rules

- 기본 테스트가 깨진 상태에서 live 확장을 진행하지 않는다.
- `hwp_status`가 한글을 자동 실행하게 되는 변경은 중단한다.
- 서버 코드에 LLM API 호출이 들어가면 목표와 충돌하므로 중단하고 ADR 재검토한다.
- live desktop evidence 없이 “라이브 완성”이라고 문서화하지 않는다.
- `.hwp` headless adapter gate를 실제 reader 완성으로 표현하지 않는다.

## 15. Changelog

- 2026-07-09: 사용자 목표 변경 반영. 인라인AI 대체를 “자체 AI 앱”이 아니라 BYO-AI 로컬 한글 문서 하네스로 재정의.
- 2026-07-09: current codebase evidence 반영. server live tools, COM bridge, live tests, README/ROADMAP 상태를 기준으로 Milestone 구성.

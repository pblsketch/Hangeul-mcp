# Hangeul-mcp

> AI 클라이언트가 한글(HWP/HWPX) 문서를 **읽고, 양식을 찾고, 값을 채우도록 돕는 로컬 MCP 서버**입니다.

[![CI](https://github.com/pblsketch/Hangeul-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/pblsketch/Hangeul-mcp/actions/workflows/ci.yml)

Hangeul-mcp 자체에는 문장을 생성하는 AI가 없습니다. Claude Desktop, Codex처럼 사용자가 선택한 MCP 클라이언트가 문안과 값을 만들고, Hangeul-mcp는 로컬 PC에서 문서를 분석·편집·검증합니다.

## 지금 무엇이 되나요?

| 사용 상황 | 현재 상태 | 설명 |
|---|---|---|
| `.hwpx` 양식 분석·채우기 | **핵심 경로 구현·자동 테스트 완료** | Windows·macOS·Linux에서 한글 프로그램 없이 실행할 수 있습니다. |
| 텍스트 검색·검증·PII 검사 | **사용 가능** | 문서 구조, 표, 스타일, 예상 값 반영 여부를 확인합니다. |
| 표·이미지·문단·페이지 편집 | **선택 기능** | `python-hwpx`를 설치해야 합니다. 이 경로는 문서를 재직렬화하므로 바이트 동일성을 보장하지 않습니다. |
| PNG 미리보기 | **선택 기능** | Playwright와 Chromium이 필요합니다. |
| 열린 한글 창에 값 넣기 | **Windows 전용·검증 진행 중** | 한글과 COM 의존성이 필요합니다. exact-path 안전장치는 구현됐지만 일부 실제 데스크톱 시나리오는 아직 QA가 남았습니다. |
| 경로 없이 “현재 문서 채워줘” | **실기기 QA 통과(2026-07-15)** | 저장된 `.hwpx`만 지원합니다. 미리보기 토큰을 발급하고, 쓰기 직전에 같은 문서인지 다시 확인합니다. 다중 인스턴스/빈 탭 데스크톱에서도 차단되지 않습니다. |
| `.hwp` 헤드리스 읽기 | **아직 미지원** | 비COM reader가 확정되지 않아 `available:false`를 정직하게 반환합니다. Windows에서는 한글 COM으로 `.hwpx` 변환이 가능합니다. |

### 가장 안전하고 완성도가 높은 사용법

원본을 직접 수정하지 않는 **파일 모드 fast path**입니다.

```text
inspect_editable_regions("신청서.hwpx", compact=true)
→ 한 번만 구조를 검토
→ AI가 채울 모든 값과 addressed edits를 한 번에 생성
→ complete_addressed_template("신청서.hwpx", edits, "신청서_완성.hwpx")
→ 결과를 열기 전에 verify/validate가 통과했는지 확인
→ 검증된 "신청서_완성.hwpx" 열기
```

- 새 파일로 저장하므로 원본을 보존합니다.
- whole-template completion은 **값을 전부 모은 뒤 한 번에** `complete_addressed_template(...)`로 보내는 경로를 기준으로 설명합니다.
- 같은 문서가 이미 한글 창에 열려 있어도 이 fast path는 **그 창을 직접 수정하지 않고** `out_path` 새 파일만 만듭니다.
- 수동 검토가 더 중요하면 `preview_addressed_edits(path, edits)` → `apply_addressed_edits(session_id, out_path)`로 preview→apply session을 유지합니다.
- 표·페이지·이미지 같은 위임 편집은 `python-hwpx`가 문서를 재직렬화하므로 **바이트 보존이 아니라 재검증 통과**를 기준으로 합니다.

## 어떤 양식을 이해하나요?

- 라벨 옆이나 아래의 빈 셀
- 병합된 표의 실제 입력 셀
- `은행명: ___`, `∘ 프로그램명 ___` 같은 문장·셀 중간 빈칸
- `{학교명}` 같은 플레이스홀더
- 형광펜으로 표시한 예시 값
- 체크박스(☑/□)
- 한글 누름틀(form field)
- 표 밖 본문 문단과 목록형 마커

모든 문서를 완벽하게 자동 해석하는 것은 아닙니다. 특히 중첩 표, 복잡한 병합, 특수 컨트롤이 많은 문서는 `analyze_form` 결과를 먼저 검토한 뒤 채우는 것을 권장합니다.

## 빠른 시작

Python 3.10 이상이 필요합니다.

### 가장 간단한 설치: PyPI + 관리 CLI

`hangeul-mcp`는 PyPI에 게시되어 있습니다. Python 3.10 이상에서 다음 명령으로 설치합니다.

```bash
pip install --upgrade hangeul-mcp
```

Windows에서 열린 한글 문서에 연결하려면 live extra를 함께 설치합니다.

```powershell
py -m pip install --upgrade "hangeul-mcp[live]"
hangeul-mcp-manage setup --client all
hangeul-mcp-manage doctor
```

### Windows 관리형 설치와 자동 업데이트

자동 업데이트·rollback까지 사용하려면 **관리형 설치 스크립트를 먼저 내려받아 내용을 검토한 뒤** 게시된 버전을 지정해 실행합니다.

```powershell
# 1) 저장소에서 scripts/install.ps1를 로컬에 저장 또는 내려받기
# 2) 내용을 검토
# 3) 로컬 파일로 실행
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Version 0.4.0 -Client all
```

설치 뒤에는 관리 CLI로 MCP 등록과 상태 점검을 진행합니다.

```bash
hangeul-mcp-manage setup --client claude
hangeul-mcp-manage doctor
```

여러 클라이언트를 함께 등록하거나 변경 사항만 미리 확인할 수도 있습니다.

```bash
hangeul-mcp-manage setup --client all --dry-run
hangeul-mcp-manage setup --client codex
hangeul-mcp-manage setup --client antigravity
```

클라이언트별 공식 MCP 문서 기준 검증 결과와 자동화 범위는 `docs/clients/README.md`에 기록돼 있습니다. 특히 Codex의 project-local `.codex/config.toml`이 이미 존재하면, 관리 CLI는 임의로 scope를 고르지 않고 수동 단계로 fail closed 합니다. Antigravity는 global `~/.gemini/config/mcp_config.json`만 자동 수정하며, workspace-local `.agents/mcp_config.json`이 이미 존재하면 역시 수동 단계로 남겨 둡니다.

업데이트 확인은 관리 CLI로 수행합니다. PyPI 메타데이터를 읽지 못하면 성공한 것처럼 처리하지 않고 `not_published` 또는 구조화된 네트워크 오류를 반환합니다.

### 관리 CLI: 업데이트·정책·롤백

```bash
hangeul-mcp-manage update --check
hangeul-mcp-manage update
hangeul-mcp-manage update-config --auto notify --channel stable
hangeul-mcp-manage rollback
```

- `update --check`는 현재 runtime 기준 최신 버전 메타데이터만 조회합니다.
- `update`는 관리형 install state가 있을 때만 다음 versioned runtime을 설치·검증한 뒤 `current.json`을 전환합니다.
- `update-config --auto off|notify|daily --channel stable|beta`는 자동 정책을 저장합니다. `daily`는 launcher startup에서 24시간 TTL 기준으로 bounded background update를 스케줄합니다.
- `rollback`은 `previous_version`이 남아 있는 managed runtime에 대해서만 지원됩니다. 수동 삭제되었거나 손상된 이전 runtime까지 복구를 보장하지는 않습니다.
- `-Version 0.4.0`처럼 PyPI 버전을 지정한 관리형 설치에서 versioned update와 rollback을 사용할 수 있습니다. Git checkout이나 source bootstrap 설치는 자동으로 덮어쓰지 않으며 `unsupported_install_source`로 멈추는 것이 정상입니다.
### 수동 설치 / 수동 설정 fallback

관리형 설치를 쓰지 않는 경우에는 소스 기준으로 직접 설치하고, 클라이언트 설정에는 **절대 경로의 Python으로 서버 모듈을 호출하는 방식**을 권장합니다.

```bash
pip install git+https://github.com/pblsketch/Hangeul-mcp
```

기존 stdio 서버 진입점은 그대로 동작합니다.

```bash
hangeul-mcp
# 또는
python -m hangeul_mcp.server
```

수동 클라이언트 설정 예시는 다음 문서에 있습니다.

- [Claude Desktop](docs/clients/claude-desktop.md)
- [Codex](docs/clients/codex.md)
- [Antigravity 2.0](docs/clients/antigravity.md)
- [클라이언트 설정 모음](docs/clients/README.md)

Hangeul-mcp는 표준 MCP stdio를 지원하는 클라이언트에서 사용할 수 있습니다. 실제 stdio 기동·도구 호출은 `tests/test_client_stdio.py`로 검증합니다.

클라이언트를 재시작한 뒤에는 다음처럼 요청할 수 있습니다.

```text
이 HWPX 문서의 입력란을 분석해 줘.
분석 결과를 보여 준 뒤, 내가 확인한 값으로 새 파일을 만들어 줘.
```

Windows 라이브 기능을 설치한 환경에서는 다음과 같은 요청도 가능합니다.

```text
지금 열려 있는 한글 문서를 분석하고, 실제 반영 전에 어디에 무엇을 넣을지 먼저 보여 줘.
```

## 선택 기능 설치

```bash
# 개발·테스트
pip install -e ".[dev]"

# 표·문단·이미지·페이지 편집 및 문서 생성
pip install -e ".[delegate]"

# PNG 미리보기
pip install -e ".[render]"
python -m playwright install chromium

# Windows 한글 COM
pip install -e ".[com]"

# Windows 열린 문서의 셀·본문 라이브 입력
pip install -e ".[live]"
```

설치하지 않은 선택 기능은 성공한 것처럼 동작하지 않고 `available:false`와 필요한 의존성을 반환합니다. `describe_capabilities()`로 현재 PC에서 가능한 기능을 먼저 확인할 수 있습니다.

## 주요 MCP 워크플로우

### 1. HWPX 양식 채우기

기본 fast path:
- `inspect_editable_regions(path, compact=True)` — 파일 모드 structural target을 한 번에 파악
- `complete_addressed_template(path, edits, out_path, verify=True)` — 값을 모두 모은 뒤 새 HWPX 파일을 한 번에 생성
- `validate_hwpx(path)` / `verify_fill(path, expected)` — 결과 무결성과 반영 여부 확인
- 필요하면 `analyze_form(path)`, `analyze_formfit(path, values)` — 라벨 기반 필드와 넘침 가능성 추가 점검

수동 addressed session:
- `preview_addressed_edits(path, edits)` — 변경 엔트리/개수 audit 먼저 확인
- `apply_addressed_edits(session_id, out_path)` — 검토한 session만 새 파일로 반영
- `find_text_occurrences()`는 읽기용 위치 탐색이며, repeated text는 반드시 explicit scope로 다시 확정합니다.

기존 라벨 기반 fill:
- `fill_form(path, values, out_path, ...)` — named field/placeholder 중심의 새 HWPX 파일 생성
### 2. 읽기·검색·감사

- `extract_text`, `find_text`
- `get_document_outline`, `get_table_map`, `find_cell_by_label`
- `list_styles`, `scan_pii`

### 3. 파일 편집·생성

자체 바이트 보존 엔진:
- `search_and_replace`, `batch_replace`, `mail_merge`
- `preview_search_and_replace`, `preview_batch_replace`, `apply_edit_session`, `restore_edit_session`
- `preview_addressed_edits`, `apply_addressed_edits`, `complete_addressed_template`
  - preview는 변경 엔트리/개수 audit를 먼저 보여 줍니다.
  - apply는 단일 session 기준으로 journal/snapshot을 남깁니다.
  - `complete_addressed_template`는 값을 모두 모은 뒤 whole-template completion을 한 번에 끝내는 file fast path입니다.
  - one-shot `search_and_replace`는 2회 이상 일치 시 기본적으로 fail-closed이며, 전체 치환은 `scope="all"`을 명시해야 합니다.
  - rich formatting/image/undo를 가장하지 않고 **텍스트 치환 경로만** 다룹니다.

`python-hwpx` 위임 기능:
- HTML/Markdown 변환
- 문단·표·이미지 추가
- 표 병합·병합 해제·셀 음영
- 글자 강조
- 용지·여백·단·쪽번호·머리말·꼬리말
- 표 문서·공문 스켈레톤·블록 문서·`DocumentSpec v1`·Markdown 기반 HWPX 생성

위임 기능의 정확한 도구명은 `describe_capabilities()` 또는 서버의 도구 목록에서 확인할 수 있습니다.


### 4. 열린 한글 문서에 라이브 입력

Windows + 한컴오피스 한글이 필요합니다. 이 경로는 **같은 한글 창을 직접 수정하는 live mode**이고, 위 file fast path와 다릅니다.

**경로를 알고 있을 때**

```text
open_in_hwp(path)
→ preview_small_live_label_cells(path, values)
→ apply_small_live_label_cells(path, values)
```

누름틀이 있는 문서는 `apply_to_open_hwp(path, values)`로 exact-path 대상에 입력할 수 있습니다.

**사용자가 경로를 말하지 않고 “지금 열린 문서 채워줘”라고 할 때**

```text
resolve_current_hwp_document()
→ preview_current_hwp_document(values, candidate_id?)
→ apply_to_current_hwp_document(preview_token)
```

**풀폼(전체 양식)을 열린 창에서 이어서 끝내고 싶을 때 — `complete_and_load` 하이브리드**

현재문서 흐름은 `values` 대신 구조 주소 `edits` 배열을 받는 `complete_and_load` 라우트를 지원합니다.

```text
resolve_current_hwp_document()
→ preview_current_hwp_document(edits=[...addressed edits...], output_path?)
→ apply_to_current_hwp_document(preview_token)
```

- 검증된 완성본을 **새 파일**로 만들고(경로는 항상 응답에 반환), 그 파일을 한글에 **새 문서 탭으로 자동으로 엽니다**.
- 원본 문서는 저장·닫기·재열기 없이 그대로 남습니다(0-touch, 적용 전후 SHA 검증). 새 탭이 앞으로 오며 활성 뷰가 전환됩니다.
- 자동 열기가 실패해도 완성 파일은 남고, `completed_open_failed`와 수동 열기 안내를 돌려줍니다.
- 원본 창이 automation-visible이 아니면 완성본이 별도 창/새 인스턴스에 열릴 수 있습니다.
- `values`와 `edits`를 함께 보내면 fail-closed(`route_conflict`)입니다.

**열린 창 셀을 직접 고치는 in-place 편집 — `live_addressed` 라우트 (2026-07-15 데스크톱 QA 게이트 통과로 승격)**

`preview_current_hwp_document(edits=[...], mode="live_addressed")` → `apply_to_current_hwp_document(preview_token)`이 파일 산출 없이 열린 창의 셀을 직접 바꿉니다.

- **바이트보존이 아니며**, 서버는 창을 저장하지 않습니다(디스크 파일은 사용자가 저장하기 전까지 불변 — 캡처에서 SHA 동일 확인).
- 각 edit에 `expected_text`가 **필수**이며, 파일 기준 사전 대조 + 교체 직전 창 안 실제 텍스트 재대조로 이중 확인합니다. 불일치 셀은 건드리지 않고 skip(`expected_text_mismatch`)됩니다.
- 부분 실패 시 `applied[]`/`skipped[]`/`remaining[]`과 구조화 복구 지시(Ctrl-Z 횟수 또는 원본 재열기)를 반환하고, 적용 셀은 별도 COM 연결로 fresh read-back 재검증합니다.
- **단일/최상위 표 문서만** 지원 — 중첩 표 감지 시 `nested_tables_unsupported`로 fail-closed되며 `complete_and_load` 하이브리드를 안내합니다. 본문 문단(bN)·다문단 셀도 fail-closed입니다.
- preview token은 원본 파일 SHA에 결속되고(변경 시 `stale_preview`), COM 변이 전에 소비되는 단일 사용 토큰입니다.

이 흐름은 다음 규칙을 지킵니다.

- v1은 **저장된 `.hwpx` 현재 문서만** 지원합니다.
- 여러 문서가 있으면 임의로 고르지 않고 후보 선택을 요청합니다.
- `resolve_current_hwp_document()` 후보에는 `picker_title`/`picker_subtitle`/`picker_badges`/`picker_label`이 들어 있어 사람이 보고 고를 수 있습니다.
- preview에서 받은 일회용 token 없이는 쓰지 않습니다.
- apply 직전에 COM 객체·문서 슬롯·전체 경로를 다시 확인합니다.
- preview token은 **해당 stdio 서버 인스턴스 범위**이며, 문서가 바뀌거나 닫혔거나 token이 재사용되면 쓰지 않고 구조화된 오류를 반환합니다.
- 사용자가 연 문서를 자동 저장·닫기·재열기하지 않습니다.
- 파일 모드 addressed completion이 목적이면 live apply로 섞지 말고 `inspect_editable_regions(...)` → `complete_addressed_template(...)` 또는 `preview_addressed_edits(...)` → `apply_addressed_edits(...)`를 사용한 뒤, **검증된 출력 파일을 나중에 여는 방식**으로 분리합니다.


### 라이브 기능의 정직한 검증 상태

확인된 것:

- ROT 전체 열거와 normalized `FullName` exact match로 대상 문서를 찾는 코드
- 다중 문서·같은 파일명·stale token·active race 등에 대한 fake-COM 자동 테스트
- current-document 후보의 human-readable picker metadata(`picker_*`) 추가
- Windows Shell `Start-Process`로 연 기존 `.hwpx`에 `open_if_needed=false`로 값 2건 입력 후 별도 연결 read-back 성공
- Windows regression artifact template/validator(`docs/evidence/windows-live-regression-template.json`, `scripts/windows_live_regression_harness.py`)
- **`complete_and_load` 컴포넌트 실기기 캡처 통과(2026-07-14)**: 실제 한글로 작성된 지도안 템플릿에서 검증 완성 → **새 탭으로 열기**(`open_as_new_tab`, `XHwpDocuments.Add`) → 원본 탭 잔존 + 원본 SHA 불변 + fresh read-back 2/2 (`docs/evidence/complete-and-load-desktop-capture-components.json`)
- 실기기 발견 반영: 일반 `hwp.Open`은 활성 탭을 내비게이션(탭 추가 아님)하므로 완성본 열기는 탭 추가 후 열기로 구현; 합성 zip 픽스처는 실제 한글이 열지 못하므로 데스크톱 캡처는 실제 저작 템플릿 사용
- **다중 인스턴스 resolver 실기기 재캡처 통과(2026-07-15)**: 빈 탭/다중 문서 데스크톱에서 `selection_required`(후보 4) → 명시적 `candidate_id`로 `preview_ready` → `completed_and_loaded` 6/6 체크 (`docs/evidence/complete-and-load-desktop-capture-automation.json`) — 이전 `current_document_unsaved` 전면 차단 결함 해소
- **`live_addressed` 실기기 캡처 통과(2026-07-15, 8/8 체크)**: 게이트 기본 차단 → 토큰 발급 → 사용자 수정 주입 셀만 `expected_text_mismatch`로 무손상 skip + 나머지 17셀 in-place 적용 + fresh read-back 검증 + 토큰 단일 사용 + 디스크 파일 SHA 불변 (`docs/evidence/live-addressed-desktop-capture.json`). 이 캡처가 잡은 실결함(`get_selected_text` 후 선택 해제로 Delete 무효 → append 오염)은 재선택 로직으로 수정 후 재검증

- **Shell-open ROT 가시성 메커니즘 확정(2026-07-15, D18)**: Explorer 더블클릭 문서의 automation 가시성은 "열기 시점에 automation-visible 인스턴스가 존재하는가"로 결정됩니다 — 클린 데스크톱이면 영구 비가시(새 미등록 인스턴스), 인스턴스가 먼저 있으면 탭으로 합류해 즉시 가시(`docs/evidence/shell-rot-spike-probe.json`). NATIVEOM/DDE 승격 채널은 실측 기각. 실무 지침: 라이브로 다룰 문서는 `open_in_hwp`로 열거나, automation 인스턴스를 먼저 만든 뒤 여세요.

아직 남은 것:

- 복잡한 중첩 표에서의 라이브 셀 매핑 확대 검증(현행: 중첩 표 문서는 `live_addressed`에서 fail-closed)
- 일부 본문 라이브 안전장치의 추가 실기기 실패 주입 검증
- worker timeout 격리는 현재 `open_in_hwp(timeout_seconds=...)` 경로에만 연결돼 있습니다. 다른 live apply 경로는 아직 동일한 timeout 계약을 약속하지 않습니다.

따라서 라이브 기능은 파일 모드보다 보수적으로 사용해야 합니다. 원자료와 완료 조건은 [`PENDING_DESKTOP_LIVE_QA.md`](PENDING_DESKTOP_LIVE_QA.md), 절차는 [`docs/live-qa-runbook.md`](docs/live-qa-runbook.md)에서 확인할 수 있습니다.


## 개인정보와 로컬 실행 경계

- Hangeul-mcp 서버는 OpenAI·Anthropic·Gemini API를 직접 호출하지 않습니다.
- 문서는 도구가 실행되는 로컬 PC에서 처리됩니다.
- 다만 MCP 클라이언트가 어떤 내용을 AI 모델에 보내는지는 **해당 클라이언트의 설정과 정책**에 따릅니다.
- `scan_pii`와 `mask_pii`는 보조 안전장치이며 개인정보 처리 책임을 대신하지 않습니다.

## 개발 상태와 품질

- 패키지 버전: `0.4.0` (Pre-Alpha)
- 런타임 MCP 도구: **59 tools**

- 최신 로컬 검증: **529 passed, 1 skipped** (+ 로컬 프로파일 한정 사전 환경 실패 6건 — 릴리스 전 8건에서 2건 치유, 회귀 0)
- Architect 최신 브랜치 리뷰: current branch evidence 참조
- Critic 최신 브랜치 리뷰: current branch evidence 참조
- 마일스톤·유저 스토리: **70개 — 69 pass** + 라이브/스파이크 pending


### 배포 채널과 release 증거 원칙

- `stable` 채널은 최종 semver release만 대상으로 합니다.
- `beta` 채널은 `a`/`b`/`rc` prerelease까지 포함합니다.
- GitHub release automation은 **trusted publishing draft**입니다. workflow 성공만으로 PyPI 게시 성공을 주장하지 않습니다.
- 실제 release를 공지할 때는 release notes와 함께 최소한 SHA256 checksum 또는 provenance 위치를 같이 제공해야 합니다.
`skipped`에는 Windows·한글·Playwright·python-hwpx처럼 현재 환경에 없는 선택 의존성 테스트가 포함될 수 있습니다. 최신 자동 검증 산출물은 [`docs/evidence/`](docs/evidence/)에 있습니다.

여기서 `66 pass`는 PRD 장부의 인수조건 boolean 수치이며 “사용자 기능 66개가 모두 완성됐다”는 뜻이 아닙니다. `desktop-live-pending`, `optional-gated`, `spike-pending` 항목도 별도로 존재하므로 실제 지원 범위는 위 상태표와 [`docs/prd.json`](docs/prd.json)을 함께 봐야 합니다.

### 아직 하지 않는 것

- 서버 자체 LLM 또는 유료 AI API 제공
- `.hwp`의 검증된 비COM 헤드리스 읽기
- 임의 표의 행·열 추가/삭제, table compute, TOC 자동화
- 열린 문서의 글꼴·스타일을 라이브 COM으로 자유 편집
- `DocumentSpec v1`에서 템플릿 전용 이미지 배치·정렬 힌트·숨은 본문 합성
- 모든 HWPX 양식에 대한 무검토 자동 채우기 보장

로드맵은 [`docs/ROADMAP.md`](docs/ROADMAP.md), 상태 원본은 [`docs/prd.json`](docs/prd.json), 설계 결정은 [`docs/DECISIONS.md`](docs/DECISIONS.md)에서 관리합니다.

## Python에서 직접 사용

```python
from hangeul_core.understand import understand
from hangeul_core.inline import detect_inline
from hangeul_core.fill import fill

fields = understand("강사카드.hwpx").fields + detect_inline("강사카드.hwpx")
for field in fields:
    print(field.field_id, field.label, field.kind)

result = fill(
    "강사카드.hwpx",
    {"성명": "홍길동", "학력": "○○대학교"},
    "강사카드_완성.hwpx",
)
print(result.filled, result.skipped)
```

## 프로젝트 구조

```text
Hangeul-mcp/
├─ hangeul_core/             # HWPX 분석·채우기·검증 코어
│  └─ hwp/                   # Windows 한글 COM·ROT·현재 문서 안전장치
├─ hangeul_mcp/              # FastMCP 도구 등록과 라이브 orchestration
├─ tests/                    # 단위·통합·fake-COM 테스트와 PII 없는 fixtures
├─ docs/                     # 설계, 상태, QA, 클라이언트 설정
├─ scripts/e2e_evidence.py   # 파일 모드 E2E 증거 생성
├─ scripts/windows_live_regression_harness.py  # Windows live artifact template/validator
└─ .github/workflows/ci.yml  # CI

```

FastMCP stdio 서버에는 현재 59개의 도구가 등록됩니다 `(59 tools)`.

## 관련 문서

- [BYO-AI 사용 흐름](docs/byo-ai-harness.md)
- [Agent Skill: 검토 → 반영](skills/SKILL.md)
- [기능 구현·검증 절차](docs/feature-implementation-workflow.md)
- [수동 테스트 시나리오](docs/test-scenarios.md)
- [연구 및 오픈소스 전략](docs/research-strategy.md)

## 라이선스

MIT — [LICENSE](LICENSE)

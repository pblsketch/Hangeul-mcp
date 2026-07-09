# HANDOFF — Hangeul-mcp 현재 상태 SSOT

> 새 세션/에이전트는 **이 파일 하나**로 현재 상태를 파악한다. 여기 수치는 커밋 시점 실측값이며,
> 툴/스토리 카운트는 `tests/test_maintainability.py`의 드리프트 가드가 README와 함께 강제한다.
> 다음 작업 계획: [`.omo/plans/hangeul-mcp-stabilization-ralplan.md`](.omo/plans/hangeul-mcp-stabilization-ralplan.md)

## 검증된 기준선 (실측)

- 테스트: `./.venv/Scripts/python.exe -m pytest -q` → **195 passed, 1 skipped (196 collected)**
  - 유일한 skip = `tests/test_com.py` 라이브 COM 테스트(`HANGEUL_MCP_LIVE=1` 데스크톱 전용)
- 린트: `./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests` → clean
- 런타임 MCP 툴: **35** (등록은 정적 — optional extra 유무와 무관하게 등록되고, 미설치 시 호출 결과가 `available:false`)
- PRD: `docs/prd.json` **61 stories** (US-000~US-060), pass 카운트 정의 = `passes==true` (BC3)
- 개발 환경: venv `./.venv` (Windows), CI는 ubuntu py3.11–3.13 코어 레인

## 상태 매트릭스 (SSOT — 기계판독 원본은 docs/prd.json의 status 필드)

| 상태 | 의미 | 해당 영역 |
|---|---|---|
| `complete` | 코드 + 테스트 + 관측 산출물 모두 존재 | v1 헤드리스 코어(인식·바이트보존 채우기·읽기·검증·PII·formfit), 텍스트치환(OWN), mail_merge, capability manifest |
| `optional-gated` | 코드·테스트 완료, optional extra 필요(미설치 시 `available:false`) | 위임 편집/생성/내보내기(python-hwpx `delegate`), `render_preview`(playwright `render`) |
| `desktop-live-pending` | 코드 완료, **실기기(Windows+한글) 증거 대기** | `apply_to_open_hwp`(US-010) · `apply_cells_to_open_hwp`(US-029) · COM 브릿지(US-009). D7: 중첩표 인덱스 매핑은 best-effort |
| `spike-pending` | 구현 전 리서치/ADR 필요 | `.hwp` 비COM 읽기(US-042/054/055) · 표 행/열 추가삭제·TOC(US-060, python-hwpx 미노출) |
| `planned` | 안정화 패스에서 승인됐으나 미착수 | US-047~US-060 중 미완료분 |

## 불변식 (위반 금지)

1. **바이트보존**: OWN fill은 raw-XML splice. 재직렬화 금지(ElementTree write는 선언 훼손 — 읽기 전용에만). 바꾼 필드 외 엔트리 payload 무변경. 기존 바이트보존 테스트 약화 금지.
2. **두뇌·손 분리**: 서버는 LLM/API를 절대 호출하지 않음(D10). 문안·값 생성은 클라이언트 몫. 예외는 D6 레이아웃 chrome뿐.
3. **own vs delegate (D1)**: 차별점(인식·채우기·inline-blank·병합셀 2D·review→apply)은 OWN. commodity breadth는 python-hwpx 위임 + `validate_hwpx` 게이트(바이트동일이 아니라 게이트 통과가 기준). **위임 불가 API를 OWN raw-XML로 재발명 금지.**
4. **optional dep는 구조화 폴백**: 미설치 `available:false`, 버전 미달은 원인이 드러나는 구조화 메시지.
5. **증거 없이 완료 선언 금지**: live/render/`.hwp`는 실행 증거 또는 명시적 pending 라벨로만 종결.
6. 실 PII 파일 커밋 금지. fixture는 PII 없는 합성 양식만.

## 공통 게이트 (스토리 완료 조건)

```powershell
Set-Location E:/github/Hangeul-mcp
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests
./.venv/Scripts/python.exe -m json.tool docs/prd.json > $null
git diff --check
```

- 툴을 추가/제거하면 **같은 커밋**에서 README `(NN tools)` 수치 갱신(가드가 강제).
- 스토리 pass를 뒤집으면 **같은 커밋**에서 README `NN개 — MM pass` 갱신(가드가 강제).
- 테스트 수 문구(`NNN collected`)는 soft — `pytest -q --collect-only` 결과로 커밋 시 재동기화.

## 먼저 읽을 것

- [`.omo/plans/hangeul-mcp-stabilization-ralplan.md`](.omo/plans/hangeul-mcp-stabilization-ralplan.md) — 현재 진행 중인 안정화 패스(US-047~US-060)와 binding conditions(BC1~BC3).
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — 확정 ADR(D1 own/delegate, D6 chrome 예외, D7 live 매핑 best-effort, D9 렌더/헤드리스 게이트, D10 BYO-AI, D11 파일/live 분리, …).
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phase별 완료/후속 정의.
- [`docs/qa-codex-v0.1.0.md`](docs/qa-codex-v0.1.0.md) · [`docs/qa-codex-phaseA-D.md`](docs/qa-codex-phaseA-D.md) — 독립 QA 이력(전부 수정·명문화 완료).
- [`docs/architecture.md`](docs/architecture.md) — 계층/모듈.

## 커밋 규약

- 스토리별 커밋, conventional prefix(`feat:`/`fix:`/`docs:` …). 푸시는 사용자 요청 시.
- 커밋 메시지 끝: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` (세션 모델 기준).

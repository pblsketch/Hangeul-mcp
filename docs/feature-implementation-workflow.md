# Feature implementation workflow

Hangeul-mcp의 새 기능은 한 번에 크게 붙이지 않고, 작은 단계와 검증 가능한 품질 게이트로 진행한다.
이 문서는 `cc-feature-implementer` 스킬의 핵심 원칙을 이 저장소에 맞게 줄인 유지보수 규칙이다.

## 기본 원칙

1. 기능은 1~4시간 안에 검증 가능한 phase로 쪼갠다.
2. 각 phase는 테스트로 시작한다.
3. 테스트가 실패하는 것을 먼저 확인한 뒤, 최소 구현으로 통과시킨다.
4. 리팩터링은 테스트가 계속 통과하는 상태에서만 한다.
5. 검증 명령이 실패하면 다음 phase로 넘어가지 않는다.

## 관리/설치 문서 변경 slice

관리 surface(`hangeul-mcp-manage`, client setup, `doctor --json`, update/rollback)는 코드와 같은 phase discipline으로 문서화한다.

- **RED**: 먼저 `tests/test_docs_manage_install.py`에 ADR/워크플로우/보안 문구를 고정하는 실패 테스트를 추가한다.
- **GREEN**: `docs/DECISIONS.md`, `docs/research-strategy.md`, `docs/SECURITY.md`를 최소 수정으로 맞춘다.
- **REFACTOR**: wording만 정리하고, stdio 계약이나 extras 관계를 과장하지 않는다.
- 문서는 `hangeul-mcp` stdio entrypoint 보존, `hangeul-mcp-manage` 분리, stable launcher, absolute `sys.executable -m hangeul_mcp.server` fallback, `not_published`/구조화 오류, backup 민감성을 함께 설명해야 한다.
- 보안/업데이트 경계 변경은 같은 커밋에서 `SECURITY.md`와 테스트를 같이 갱신한다.

## Phase 작성 형식

새 기능을 시작할 때는 `docs/plans/PLAN_<feature-name>.md`에 다음 항목을 남긴다.

- 목표: 이 phase가 끝나면 사용자가 무엇을 할 수 있는가
- RED: 먼저 추가할 실패 테스트
- GREEN: 테스트를 통과시키기 위한 최소 구현
- REFACTOR: 통과 상태를 유지하며 정리할 구조
- 품질 게이트: 아래 검증 명령과 수동 확인 항목
- 되돌리기: 문제가 생기면 어떤 파일을 되돌릴 것인가

## Hangeul-mcp 품질 게이트

모든 기능 phase가 끝날 때 다음 명령을 통과해야 한다.

```powershell
& .venv/Scripts/python.exe -m pytest -q
& .venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests
& .venv/Scripts/python.exe -m json.tool docs/prd.json > $null
git diff --check
```

MCP 도구를 추가하거나 서버 등록 구조를 바꾼 경우에는 추가로 도구 노출을 확인한다.

```powershell
$env:PYTHONIOENCODING='utf-8'
& .venv/Scripts/python.exe -c "from hangeul_mcp import server; print(len(server.mcp._tool_manager._tools)); print(sorted(server.mcp._tool_manager._tools))"
```

## 유지보수 가드

다음 규칙은 코드가 다시 커져서 고치기 어려워지는 일을 막기 위한 최소 기준이다.

- `hangeul_mcp/server.py`는 등록 facade로 유지한다.
- `hangeul_core/delegate.py`는 re-export facade로 유지한다.
- 새 기능 모듈은 가능하면 순수 LOC 250줄 이하를 유지한다.
- `.hwp` live 경로와 `.hwpx` file 경로를 섞지 않는다.
- optional dependency가 없는 환경에서는 예외 대신 `available:false` 형태로 응답한다.
- 서버 내부에 OpenAI, Anthropic, Gemini 같은 LLM API SDK를 기본 의존성으로 추가하지 않는다.

이 규칙은 `tests/test_maintainability.py`에서 일부 자동 검증한다.

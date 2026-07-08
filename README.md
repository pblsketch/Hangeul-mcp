# Hangeul-mcp

> 한글(HWP/HWPX) **양식을 인식**하고, AI가 생성한 값을 **원본 서식을 보존한 채** 채워 넣는 **MCP 서버**.
> Claude Desktop · Codex · Antigravity 2.0 등 임의의 MCP 클라이언트에서 동작.

[![CI](https://github.com/pblsketch/Hangeul-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/pblsketch/Hangeul-mcp/actions/workflows/ci.yml)

**상태: v0.1.0** — v1 헤드리스(인식 · 채우기 · MCP 서버) **완성**, v2 COM 라이브 반영은 **코드 완성 + 데스크톱 실검증 대기**. 테스트 55 passed · 독립 codex QA 통과([`docs/qa-codex-v0.1.0.md`](docs/qa-codex-v0.1.0.md)).

---

## 무엇인가

한글 양식 문서(신청서·강사카드·공문 등)를 파싱해 **어디가 빈칸이고, 그 라벨이 무엇이며, 어떤 서식인지**를 구조화하고,
AI가 만든 값을 **서식·쪽수를 훼손하지 않고** 정확히 채워 넣는다.

- **두뇌와 손의 분리** — 값 *생성*은 클라이언트 LLM(Claude/Codex/Gemini)의 몫. 이 서버는 **인식·채우기·반영**이라는 기계적 도구만 제공한다.
- **바이트 보존 채우기** — 바꾼 필드 외에는 (엔트리 payload 기준) 1바이트도 건드리지 않는다. mimetype STORED·XML 선언까지 보존.
- **클라이언트 무관** — 표준 MCP(stdio) + tools-only로 여러 클라이언트에서 공통 동작.

## 차별점

기존 한글 파서/필러가 못 하는 세 가지 (모두 실제 강사카드 양식에서 동작 검증):

1. **inline-blank 채우기** — "∘ ___ 을 졸업하시고", "은행명: ___ 계좌번호: ___" 같은 **문장/셀 중간 빈칸**. 서로 다른 문단에 흩어진 빈칸도 각각 정확히 채움.
2. **병합셀 2D 이해** — 라벨 아래/병합(colSpan·rowSpan)된 값 셀을 occupancy grid로 정확히 매핑(인접 라벨이 아니라 진짜 값 셀).
3. **검토 → COM 원샷 반영** — 검토한 값 묶음을 `put_field_text`로 **열려 있는 한글 창**에 한 번에 반영(v2).

## MCP 툴

**v1 (헤드리스, 크로스플랫폼)**
- `detect_format(path)` — hwpx/hwp/unknown 감지
- `analyze_form(path)` — 양식 인식 → 필드(field_id·label·kind·서식) 목록
- `fill_form(path, values, out_path, …)` — 서식 보존 채우기 → 새 .hwpx
- `extract_text(path)` — 텍스트 추출

**v2 (COM 라이브, Windows + 한글 필요)**
- `hwp_status()` — COM 브릿지 가용 여부(부작용 없음, 한글 안 띄움)
- `apply_to_open_hwp(values)` — 열린 한글 문서에 원샷 반영(누름틀). 누름틀 없으면 `needs_field_registration` 반환

> 값 *생성*은 서버가 하지 않는다 — 클라이언트 LLM이 초안을 만들고, 서버는 인식·채우기·반영만 한다.
> 검토→반영 워크플로우 가이드: [`skills/SKILL.md`](skills/SKILL.md).

## 빠른 시작

```bash
pip install git+https://github.com/pblsketch/Hangeul-mcp   # 콘솔명령: hangeul-mcp

# 로컬 개발
git clone https://github.com/pblsketch/Hangeul-mcp && cd Hangeul-mcp
pip install -e ".[dev]"
pytest -q                     # 55 passed, 1 skipped(라이브 COM)
```

파이썬 코어 직접 사용:

```python
from hangeul_core.understand import understand
from hangeul_core.inline import detect_inline
from hangeul_core.fill import fill

# 양식 인식
for f in understand("강사카드.hwpx").fields + detect_inline("강사카드.hwpx"):
    print(f.field_id, f.label, f.kind)

# 서식 보존 채우기 (field_id 또는 label을 키로)
res = fill("강사카드.hwpx", {"성명": "홍길동", "학력": "○○대학교"}, "채움.hwpx")
print(res.filled, res.skipped)
```

## 클라이언트 지원

표준 stdio MCP 서버(**tools-only**)라 모든 MCP 클라이언트에서 동일하게 동작합니다.
실행 명령: `hangeul-mcp` 또는 `python -m hangeul_mcp.server`.
클라이언트별 등록 스니펫: [`docs/clients/`](docs/clients/README.md)
— [Claude Desktop](docs/clients/claude-desktop.md) · [Codex](docs/clients/codex.md) · [Antigravity 2.0](docs/clients/antigravity.md).

실제 stdio 클라이언트가 서버를 기동해 툴을 나열·호출하는 통합 테스트로 검증됨(`tests/test_client_stdio.py`).
COM(v2) 기능은 로컬 Windows + 한글 설치 환경에서만 활성화되고, 그 외에는 헤드리스로 폴백.

### v2 COM 라이브 실검증 (데스크톱에서)

헤드리스 세션에서는 한글 창을 띄우지 않도록 실제 COM Dispatch가 게이트되어 있습니다.
Windows + 한글에서 누름틀 있는 문서를 열고:

```bash
pip install -e ".[com]"                       # pywin32
set HANGEUL_MCP_LIVE=1
python -m pytest tests/test_com.py -q          # 라이브 연결 테스트
```

## 로드맵 / 상태

- **v1 (헤드리스)** ✅ 완료 — analyze/understand/inline/fill + MCP 서버 + `.hwp` 자동변환.
- **v2 (COM 라이브)** 🟡 코드 완료, 데스크톱 실검증 대기 — `apply_to_open_hwp`로 열린 한글에 원샷 반영.

마일스톤·유저 스토리(13개, 전부 pass): [`docs/prd.json`](docs/prd.json) · 설계 결정: [`docs/DECISIONS.md`](docs/DECISIONS.md) · 아키텍처: [`docs/architecture.md`](docs/architecture.md).

## 리포 구조

```
Hangeul-mcp/
├─ hangeul_core/            # 순수 파이썬 엔진 (MCP 무관, 재사용 가능)
│  ├─ owpml/package.py      #   바이트 보존 HWPX 컨테이너
│  ├─ analyze.py            #   구조 분석 (셀 주소/span/글머리표/자간)
│  ├─ understand.py         #   2D 라벨-값 매핑 (병합셀 occupancy)
│  ├─ inline.py             #   inline-blank 탐지 (마커/콜론)
│  ├─ fill.py               #   서식 보존 채우기 (set/append/inline, 멀티섹션)
│  ├─ extract.py            #   텍스트 추출
│  ├─ convert.py            #   .hwp → .hwpx (한글 COM)
│  ├─ schema.py             #   FieldSchema 데이터 모델
│  └─ hwp/com.py            #   (v2) COM 브릿지 (put_field_text)
├─ hangeul_mcp/server.py    # FastMCP stdio 서버 (6 tools)
├─ skills/SKILL.md          # 검토→반영 Agent Skill
├─ tests/                   # 55 tests + fixtures (PII 없는 빈 양식)
├─ docs/                    # PLAN · DECISIONS · architecture · clients/ · qa-codex · research
└─ .github/workflows/ci.yml # CI (ubuntu, py3.11–3.13)
```

## 관련 오픈소스

생태계 조사 및 개발 전략: [`docs/research-strategy.md`](docs/research-strategy.md)
(python-hwpx, kordoc, claw-hwp, hwp-mcp, pyhwpx 등).

## 라이선스

MIT — [`LICENSE`](LICENSE)

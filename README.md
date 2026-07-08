# Hangeul-mcp

> 한글(HWP/HWPX) **양식을 인식**하고, AI가 생성한 값을 **원본 서식을 보존한 채** 채워 넣는 **MCP 서버**.
> Claude Desktop · Codex · Antigravity 2.0 등 임의의 MCP 클라이언트에서 동작.

**상태: 🟡 계획 단계 (Planning)** — 스펙/PRD 확정, 빌드 착수 전. 자세한 계획은 [`docs/PLAN.md`](docs/PLAN.md).

---

## 무엇인가

한글 양식 문서(신청서·강사카드·공문 등)를 파싱해 **어디가 빈칸이고, 그 라벨이 무엇이며, 어떤 서식인지**를 구조화하고,
AI가 만든 값을 **서식·쪽수를 훼손하지 않고** 정확히 채워 넣는다.

- **두뇌와 손의 분리** — 값 *생성*은 클라이언트 LLM(Claude/Codex/Gemini)의 몫. 이 서버는 **인식·채우기·반영**이라는 기계적 도구만 제공한다.
- **바이트 보존 채우기** — 바꾼 필드 외에는 1바이트도 건드리지 않는다.
- **클라이언트 무관** — 표준 MCP(stdio) + tools-only로 여러 클라이언트에서 공통 동작.

## 차별점

기존 한글 파서/필러가 못 하는 세 가지:

1. **inline-blank 채우기** — "∘ ___ 을 졸업하시고", "은행명: ___ 계좌번호: ___" 같은 **문장/셀 중간 빈칸**.
2. **병합셀 2D 이해** — 라벨 아래/병합(colSpan·rowSpan)된 값 셀을 셀 주소로 정확히 매핑.
3. **검토 → COM 원샷 반영** — 검토한 값 묶음을 **열려 있는 한글 창**에 한 번에 반영(v2).

## 로드맵

- **v1 (헤드리스)** — 파일 in → 채워진 파일 out. `analyze_form` / `fill_form`.
- **v2 (COM 라이브)** — pyhwpx `put_field_text`로 열린 한글 창에 원샷 반영. Windows + 한글 필요.

마일스톤 M0~M4와 유저 스토리는 [`docs/prd.json`](docs/prd.json) 참고.

## MCP 툴 (계획)

- `detect_format(path)`
- `analyze_form(path) -> FieldSchema` — 양식 인식
- `fill_form(path, values, out_path)` — 서식 보존 채우기 (v1)
- `extract_text(path)`
- `hwp_status()` / `apply_to_open_hwp(values)` — COM 라이브 반영 (v2)

## 클라이언트 지원 (계획)

표준 stdio MCP 서버. `docs/clients/`(예정)에 클라이언트별 등록 스니펫 제공:
Claude Desktop · Codex · Antigravity 2.0. COM(v2) 기능은 로컬 Windows + 한글 설치 환경에서만 활성화되고, 그 외에는 헤드리스로 폴백.

## 리포 구조

```
Hangeul-mcp/
├─ docs/
│  ├─ PLAN.md              # 개발 계획 / 스펙 (SSOT)
│  ├─ prd.json             # 유저 스토리 (M0~M4)
│  ├─ progress.txt         # 진행 로그
│  └─ research-strategy.md # 오픈소스 지형도 + 전략 리서치
├─ prototype/              # 동작하는 프로토타입 (더미 데이터, 참고용)
├─ tests/fixtures/         # 샘플 양식 (PII 없는 빈 양식)
├─ hangeul_core/           # (예정) 순수 파이썬 엔진
└─ hangeul_mcp/            # (예정) MCP 서버 (FastMCP)
```

## 관련 오픈소스

계획의 근거가 된 생태계 조사는 [`docs/research-strategy.md`](docs/research-strategy.md) 참고.
(python-hwpx, kordoc, claw-hwp, hwp-mcp, pyhwpx 등)

## 라이선스

MIT — [`LICENSE`](LICENSE)

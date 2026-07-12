# Hangeul-mcp — 개발 계획 / 스펙 (v0, 계획 단계)

> 한글(HWP/HWPX) 양식을 인식하고, AI가 생성한 값을 **원본 서식을 보존한 채** 채워 넣는 **MCP 서버**.
> Claude Desktop뿐 아니라 **Codex, Antigravity 2.0** 등 임의의 MCP 클라이언트에서 동작.
> 최종 목표: **COM 라이브 반영** — 검토한 값을 **정확한 문서 경로로 식별한** 열린 한글 문서에 원샷으로 밀어넣기(unsafe generic reconnect 금지).
>
> 상태: **계획/스펙 문서(코드베이스는 이미 존재하며, 현재 승인된 라이브 정책은 Batch A exact-path attach-first)**  ·  작성 2026-07-08

> 감사용 구분: **Batch A(승인된 보수 범위)** = 헤드리스 워크플로우 + `connected:false` idle pre-attach 안내 + `open_in_hwp(path)`/`preview_cells_to_open_hwp(path, values)` 중심의 exact-path attach-first 정책. **Batch B(조건부 승격)** = 손으로 연 창까지 포함한 exact-path attach의 literal write-safe Windows 실기기 증거. Batch B는 추가 live-QA 캡처 전까지 pending이며, 이 계획 문서도 그 이상을 주장하지 않는다.

---

## 1. 목표 / 비목표

### 목표
- Korean HWP/HWPX 양식 문서를 파싱해 **필드(라벨·빈칸·타입·위치)를 구조화**한다.
- AI(=클라이언트 LLM)가 생성한 값을 받아 **서식·쪽수를 훼손하지 않고** 채운다.
- **MCP 표준(stdio)** 으로 노출해 Claude Desktop / Codex / Antigravity 2.0 등에서 공통 사용.
- v1: **헤드리스**(파일 in → 채워진 파일 out). v2: **COM 라이브 반영**(exact-path attach-first로 식별한 열린 한글 문서).

### 비목표 (v1 범위 밖)
- 텍스트 "생성" 자체는 서버가 하지 않는다 → **값 생성은 클라이언트 LLM의 몫**. 서버는 인식·채우기·반영이라는 *기계적 도구*만 제공.
- HWP 5.x 바이너리 **쓰기**는 하지 않는다(읽기/변환만). 채우기는 HWPX로만.
- 암호화(DRM) HWPX 처리 제외.
- 복잡 도형/수식 신규 생성 제외(기존 보존은 함).

---

## 2. 핵심 설계 원칙

1. **두뇌와 손의 분리** — 값 생성 = 클라이언트 LLM(Claude/Codex/Gemini). 서버 = 인식·채우기·반영 도구. 서버가 텍스트를 지어내지 않는다.
2. **바이트 보존 채우기** — 바꾼 필드 외에는 **1바이트도 변경 없음**. XML 재직렬화가 아니라 부분 치환(byte-splice) + mimetype STORED 순서 보존 + XML 선언(`standalone="yes"`) 보존. (프로토타입에서 ElementTree가 선언을 날린 사고를 정책으로 못박음.)
3. **서식정합 전처리** — 값을 넣기 전에 그 필드의 서식에 맞춰 정규화:
   - 줄바꿈(`\n`) → 실제 문단/lineBreak 구조로 (raw 개행 금지)
   - 자동 글머리표(BULLET) 칸이면 값에 `-`/`∘` 중복 금지
   - 자간(spacing) 정상화 옵션
4. **클라이언트 무관** — 순수 MCP **툴**만 사용(리소스/프롬프트 등 비필수 기능 의존 배제). 툴은 `params in → JSON out`의 순수 함수.
5. **정직한 부분 성공** — 못 채운 필드(데이터 없음/미지원 구조)는 조용히 건너뛰지 말고 `skipped` + 사유로 리포트.

---

## 3. 클라이언트 무관 전략 (Codex / Antigravity 2.0 대응)

- **전송(transport)**: `stdio` 기반 로컬 MCP 서버. 세 클라이언트 모두 stdio MCP를 표준 지원.
- **SDK**: 공식 **MCP Python SDK(FastMCP)** 사용 → 툴 스키마 자동 노출, 클라이언트 독립.
- **기능 최소주의**: MCP `tools`만 사용(널리 지원됨). `resources`/`prompts`는 선택적 부가.
- **설정 배포**: `docs/clients/`에 클라이언트별 등록 스니펫 제공
  - Claude Desktop: `claude_desktop_config.json`
  - Codex: MCP 서버 설정 항목
  - Antigravity 2.0: MCP 서버 설정 항목
- **COM(v2)의 로컬 제약 명시**: COM은 **Windows + 한글 설치 + 로컬 실행** 필요. 원격/호스팅 실행에서는 COM 툴이 비활성화되고 헤드리스로 우아하게 폴백. OS/한글 미탐지 시 명확한 에러 반환(크래시 금지).

---

## 4. 아키텍처 (계층)

```
Hangeul-mcp/
├─ hangeul_core/          # 순수 파이썬 엔진 (MCP 의존 없음, 재사용 가능)
│  ├─ owpml/              # HWPX(zip+xml) 컨테이너 I/O
│  │   ├─ package.py      #   unpack/repack (mimetype STORED first, 선언 보존)
│  │   └─ bytepatch.py    #   바이트 보존 부분 치환
│  ├─ analyze.py          # 구조 분석: 표/셀(rowAddr,colAddr,span), paraPr(bullet), charPr(spacing)
│  ├─ understand.py       # 양식 이해: 라벨↔값 2D 매핑(병합셀), 필드타입 추론
│  ├─ inline.py           # inline-blank 탐지/삽입 (문장중간·셀중간 빈칸)
│  ├─ fill.py             # 서식정합 채우기 (set/append/inline, 줄바꿈 문단화, 글머리표 dedup, 자간)
│  ├─ schema.py           # FieldSchema 데이터모델
│  └─ hwp/                # (v2) HWP5 읽기/변환, COM 브릿지
│      └─ com.py          #   pyhwpx: attach → get_field_list → put_field_text
├─ hangeul_mcp/           # MCP 서버 (FastMCP)
│  └─ server.py           #   툴 등록 + stdio 엔트리포인트
├─ skills/                # (선택) 얇은 Agent Skill — 검토→반영 워크플로우 프롬프트
├─ tests/
│  ├─ fixtures/           # 강사카드 샘플들 (빈 양식 + 채워진 참조)
│  ├─ test_analyze.py     # 골든 분석
│  ├─ test_fill.py        # 라운드트립 바이트보존 + 값 검증
│  └─ test_inline.py
├─ docs/
│  ├─ architecture.md
│  └─ clients/            # Claude Desktop / Codex / Antigravity 설정
├─ pyproject.toml         # 패키징 (uv/pip), 엔트리포인트 hangeul-mcp
├─ LICENSE                # MIT
└─ README.md
```

**기술 결정(권장):** 컨테이너 I/O·바이트 패치는 성숙한 **python-hwpx**를 저수준 substrate로 채택 검토하고, 그 위에 우리 고유의 **양식 이해 + inline-blank + 서식정합 전처리** 레이어를 얹는다(바퀴 재발명 방지). 단, python-hwpx 채택 여부는 US-002에서 스파이크로 검증 후 확정. 프로토타입의 자체 엔진은 폴백/레퍼런스로 보존.

---

## 5. 데이터 모델 — FieldSchema (analyze_form 출력)

```jsonc
{
  "doc": { "format": "hwpx", "pages_estimate": 1, "tables": 6 },
  "fields": [
    {
      "id": "t2.r2.c3",              // table.row.col 주소
      "label": "성명",
      "kind": "empty_cell",          // empty_cell | inline_blank | bullet_item | checkbox | narrative
      "value": null,                  // 현재 값(있으면)
      "loc": { "table": 2, "row": 2, "col": 3, "colSpan": 1, "rowSpan": 1 },
      "style": { "paraBullet": false, "charSpacing": 0 },
      "constraints": { "type": "name", "max_len_hint": 20, "one_line": true },
      "context": "라벨 '성명' 아래 값 셀"
    },
    {
      "id": "t2.r9.c1",
      "label": "학력",
      "kind": "inline_blank",        // "∘ ___ 을 졸업하시고"
      "template": "∘ {} 을 졸업하시고",
      "insert_after": "∘",
      "loc": { "table": 2, "row": 9, "col": 1 },
      "style": { "paraBullet": false }
    }
  ]
}
```

**필드 kind (양식 인식의 핵심 분류)**
- `empty_cell` — 빈 셀 통째 입력 (라벨 오른쪽/아래, 병합 고려)
- `inline_blank` — 문장·셀 중간 빈칸 ("∘ ___ 을 졸업하시고", "은행명: ___ 계좌번호: ___") ← **차별점**
- `bullet_item` — 자동 글머리표 문단 (값에 기호 중복 금지)
- `checkbox` — □예/□아니요, ∘존재(…) 선택
- `narrative` — 문법 정합 필요 서술형

---

## 6. MCP 툴 API (인터페이스 스펙)

### v1 (헤드리스)
- `detect_format(path) -> {format, encrypted, ok}`
- `analyze_form(path) -> FieldSchema`  ← 양식 인식 (§5)
- `fill_form(path, values: dict|list, out_path, options) -> {filled:[], skipped:[{field,reason}], out_path}`
  - `values`: `{field_id 또는 label: value}` 매핑
  - `options`: `{normalize_spacing, respect_bullets, linebreak_to_paragraph}` (기본 모두 on)
  - 보장: 바꾼 필드 외 바이트 불변, mimetype/선언 보존
- `extract_text(path, include_tables) -> markdown`  (보조)

### v2 (COM 라이브 — Windows+한글 전용)
- `hwp_status() -> {available, connected, instances:[...], attach_boundary, first_call_hint, version}`  (미지원 환경이면 available:false)
- `open_in_hwp(path) -> {ok, opened, attached_existing, active_document, cold_start, elapsed_seconds}`
- `preview_cells_to_open_hwp(path, values) -> {count, targets:[...], attach_metadata}`  (문서를 쓰지 않고 exact-path resolver 결과를 먼저 보여 줌)
- `apply_to_open_hwp(path, values)` / `apply_to_open_hwp(values) -> {applied:[], skipped:[], opened?, attached_existing?}`
  - 안전한 Batch A named-field 흐름은 `open_in_hwp(path)` 또는 `preview_cells_to_open_hwp(path, values)`로 exact-path attach를 먼저 확인한 뒤, **이미 제어 중인 active 문서에** `apply_to_open_hwp(values)`를 호출하는 것이다
  - path 인자는 exact-path 단독 쓰기 경로가 아니라 guidance/보수적 refusal 용도다
  - 내부 쓰기 단계는 서식정합 전처리 후 active 문서의 `get_field_list` 매칭 → `put_field_text(dict)` 원샷
  - 누름틀/셀필드 없는 양식이면 `needs_field_registration` 반환(안내)
- `apply_cells_to_open_hwp(path, values, open_if_needed)` — preview의 attach metadata로 same-doc가 확인된 경우에만 셀 쓰기
- `register_fields(path, mapping)` (선택) — 빈칸을 이름있는 누름틀로 1회 등록해 이후 반영을 견고하게
- `live_reload(path)` (승인된 follow-up, 미구현 가능) — exact-path 문서 재확인/재attach를 단일 helper로 캡슐화

**검토→반영 워크플로우** (클라이언트 프롬프트/Skill이 오케스트레이션)
1. `analyze_form` → 필드 스키마
2. 클라이언트 LLM이 필드별 값 생성(초안) → **사용자 검토**
3. 승인 시 v1 `fill_form`(파일) 또는 v2 `open_in_hwp(path)`/`preview_cells_to_open_hwp(path, values)`로 exact-path를 확인한 뒤 legacy active-document `apply_to_open_hwp(values)`

---

## 7. 로드맵 (마일스톤)

- **M0 스캐폴드** — 리포 뼈대, 패키징, 라이선스, CI, 픽스처 이관
- **M1 코어 엔진(v1 기반)** — owpml I/O, analyze, understand, inline, fill (프로토타입 이관+테스트화)
- **M2 MCP 서버(v1 출시)** — FastMCP stdio, v1 툴 4종, 클라이언트 무관 설정 문서
- **M3 COM 라이브(v2)** — pyhwpx 브릿지, exact-path resolver, `open_in_hwp` 진입점 + active-document `apply_to_open_hwp(values)` 가이드, 환경 가드/폴백
- **M4 폴리시** — 검토→반영 Skill, 골든테스트 확대, .hwp 변환 정책, 배포

각 마일스톤은 §8 PRD의 유저 스토리로 분해(prd.json).

---

## 8. 테스트 전략

- **픽스처**: `강사카드(양식).hwpx`(빈 양식), `강사카드(채움예시).hwpx`(채워진 참조), 이번에 채운 결과들.
- **골든 분석 테스트**: analyze_form 출력이 기대 필드 집합과 일치.
- **라운드트립 바이트보존 테스트**: fill 후 (a) 바꾼 필드 값 존재, (b) **바꾸지 않은 영역 바이트 동일**, (c) mimetype STORED 첫 엔트리, (d) XML 선언 보존, (e) well-formed.
- **inline-blank 테스트**: "∘ ___ 을 졸업하시고" 삽입이 문법·위치 정확.
- **글머리표 dedup 테스트**: BULLET 칸에 값 넣어도 `- -`/`∘ ∘` 이중 없음.
- **COM 테스트(v2)**: 한글 설치 환경에서만 실행(없으면 skip), put_field_text 왕복.

---

## 9. 리스크 & 대응

- **양식 인식 롱테일**(자유 레이아웃·이미지 양식·병합 변형) → 실패 로깅 + 점진 개선, `skipped` 정직 리포트.
- **inline-blank 정확도** → run 단위 삽입은 취약. 픽스처 기반 골든테스트로 고정, 실패 시 사용자에게 위치 확인.
- **COM 취약성**(한글 버전차·커서·보안팝업) → v2 격리, 자동 실패 시 v1 폴백, 보안 DLL 등록 문서화.
- **라이선스** → MIT 배포. `pyhwp`(AGPL) 미사용. `python-hwpx`/`pyhwpx` 라이선스 US-002/US-009에서 확인 후 확정.
- **클라이언트 편차**(Codex/Antigravity의 MCP 기능 지원 범위) → tools-only로 최소 의존, 각 클라이언트 스모크 테스트.

---

## 10. 계획 단계에서만 열려 있던 질문 (현재는 역사적 맥락)

이 섹션은 **초기 계획 승인 당시의 의사결정 포인트 기록**이다. 현재 코드베이스 전체가 이 질문들 때문에 대기 중인 상태는 아니며, 실제 shipped 동작과 현재 정책은 README/HANDOFF/`docs/DECISIONS.md`가 기준이다.

1. 리포 **위치** 및 GitHub 공개/비공개 여부 → 이미 결정되어 현재 canonical repo와 배포 문서에 반영됨.
2. **python-hwpx 채택** vs 자체 엔진 유지 → 현재는 OWN 코어 + delegate substrate 병행 전략으로 정착했고, 자세한 경계는 ADR/README에 반영됨.
3. v1 **필드 매칭 키** 우선순위 → 현재 구현/문서는 `field_id` 또는 `label` 입력을 모두 허용하는 방향으로 정리됨.
4. `.hwp`(바이너리) 입력 범위 → 현재는 headless reader adapter gate 및 COM/변환 경계를 명시하는 정책으로 정리됨.
5. 패키지/명령 이름 및 배포 여부 → `hangeul-mcp` 실행명과 현재 배포/설치 경로가 README에 반영됨.

> 따라서 위 항목들은 **원래 계획 단계의 승인 질문 아카이브**이며, 현재 작업 판단은 최신 상태 문서와 실제 코드/검증 산출물을 따른다.

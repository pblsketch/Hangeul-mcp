# Hangeul-mcp

> 한글(HWP/HWPX) **양식을 인식**하고, AI가 생성한 값을 **원본 서식을 보존한 채** 채워 넣는 **MCP 서버**.
> Claude Desktop · Codex · Antigravity 2.0 등 임의의 MCP 클라이언트에서 동작.

[![CI](https://github.com/pblsketch/Hangeul-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/pblsketch/Hangeul-mcp/actions/workflows/ci.yml)

**상태: v0.1.0 + Phase A~D 핵심** — v1 헤드리스(인식 · 채우기 · MCP 서버) **완성**, Phase A 양식 인식·채우기 심화 5종, Phase B 신뢰성·검증·읽기 자체코어 4종, Phase C 텍스트치환(OWN)·구조편집·이미지(python-hwpx 위임), Phase D 문서생성(위임)·mail_merge(OWN) **완성**, 실사용 피드백 반영(form-fit 데드밴드·체크박스 라벨·용량 힌트·PII 경고), **누름틀 없이 열린 문서 셀 라이브 채우기**(`apply_cells_to_open_hwp`, 클라이언트 실검증 대기). 테스트 159 passed(python-hwpx `delegate` extra 포함; 미설치 시 위임/라이브 테스트는 skip) · 독립 codex QA 통과([`docs/qa-codex-v0.1.0.md`](docs/qa-codex-v0.1.0.md)).

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
- `analyze_form(path)` — 양식 인식 → 필드 목록. kind: `empty_cell` · `inline_blank` · `placeholder`(`{학교명}`) · `markpen`(형광펜 예시값) · `checkbox`(☑/□, `options` 포함) · `form_field`(누름틀)
- `fill_form(path, values, out_path, normalize_spacing, checkbox_exclusive, auto_fit, mask_pii, dry_run, backup)` — 서식 보존 채우기 → 새 .hwpx. 위 모든 kind 처리. `auto_fit`은 셀 넘침 추정 시 해당 run 글꼴만 축소(하한 보장), `mask_pii`는 값의 PII 마스킹, `dry_run`은 미기록 미리보기, `backup`은 덮어쓰기 전 `.bak`
- `analyze_formfit(path, values)` — 셀 넘침(쪽수 드리프트) 추정 경고. 렌더러 없는 휴리스틱(추정치)
- `extract_text(path)` — 텍스트 추출
- `find_text(path, query)` — 텍스트 검색(문서 전역 count + 셀 주소·스니펫)
- `get_document_outline(path)` — 구조 개요(섹션·표·셀·kind별 필드 집계)
- `get_table_map(path)` — 표/셀 구조 맵(field_id·행·열·span·텍스트·빈칸)
- `find_cell_by_label(path, label)` — 라벨 셀 + 매핑된 값 셀 field_id 조회
- `verify_fill(path, expected)` — 채운 값 실제 반영 검증(present/missing)
- `list_styles(path)` — 헤더 스타일 목록(charPr 글꼴 크기/자간, paraPr 글머리표)
- `scan_pii(path)` — 문서 텍스트의 PII 감사(주민번호·전화·카드·계좌·이메일)
- `validate_hwpx(path)` — 무결성 검증(모든 XML well-formed·mimetype·XML 선언, python-hwpx 설치 시 XSD)
- `search_and_replace(path, find, replace, out_path)` — 일반 텍스트 치환 → 새 .hwpx. 바이트보존(우리 splice 엔진, `<hp:t>` 텍스트만·태그 무변경·셀 경계 넘김 방지)
- `batch_replace(path, replacements, out_path)` — 다중 find→replace 일괄(긴 매치 우선, 재치환 없음)
- `mail_merge(template_path, records, out_dir, mask_pii)` — 대량 생성. 레코드마다 **바이트보존 채우기**로 번호 매긴 .hwpx 산출(모든 kind 재사용, 문안은 클라이언트)

**위임(DELEGATE, python-hwpx substrate — optional `delegate` extra)**
> commodity breadth(편집·생성·리치 내보내기)는 재발명 대신 python-hwpx에 위임하고 우리 툴로 노출. 위임 편집은 재직렬화라 바이트동일이 아니라 **`validate_hwpx` 게이트 통과**를 무결성 기준으로 삼는다. 미설치 시 `available:false` 반환.
- `hwpx_to_html(path)` / `hwpx_to_markdown(path)` — HTML/Markdown 렌더(미리보기, read-only)
- `add_paragraph(path, text, out_path)` / `add_table(path, rows, cols, out_path)` — 구조 편집 → validate 게이트
- `add_image(path, image_path, out_path, width_mm, height_mm)` — 이미지/도장/서명 삽입 → validate 게이트
- `emphasize_text(path, find, out_path, bold, italic, underline, color, size)` — find 포함 run에 리치 서식(전체 run 단위) → validate 게이트
- `create_hwpx_table(rows, out_path)` — 2D 데이터로 채운 표 새 HWPX(레게드 행 패딩)
- `create_official_document(fields, out_path, doc_type)` — 공문/보도자료/기안문 스켈레톤 조립
- `create_hwpx_from_markdown(markdown, out_path)` — markdown/text → 새 HWPX(문안은 클라이언트, 서버는 조립만)

**v2 (COM 라이브, Windows + 한글 필요)**
- `hwp_status()` — COM 브릿지 가용 여부(부작용 없음, 한글 안 띄움)
- `apply_to_open_hwp(values)` — 열린 한글 문서에 원샷 반영(누름틀). 누름틀 없으면 `needs_field_registration` 반환
- `apply_cells_to_open_hwp(path, values)` — **누름틀 없이** 열린 셀 양식을 라이브로 채움(pyhwpx, optional `live` extra). 창을 닫지 않음

> 값 *생성*은 서버가 하지 않는다 — 클라이언트 LLM이 초안을 만들고, 서버는 인식·채우기·반영만 한다.
> 검토→반영 워크플로우 가이드: [`skills/SKILL.md`](skills/SKILL.md).

## 빠른 시작

```bash
pip install git+https://github.com/pblsketch/Hangeul-mcp   # 콘솔명령: hangeul-mcp

# 로컬 개발
git clone https://github.com/pblsketch/Hangeul-mcp && cd Hangeul-mcp
pip install -e ".[dev]"
pytest -q                     # 105+ passed(코어) · +위임 테스트는 delegate extra 설치 시
# 편집·생성·리치 내보내기(위임) 사용:
pip install -e ".[delegate]"  # python-hwpx (optional; 미설치 시 해당 툴은 available:false)
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
- **Phase A (P0) 양식 인식·채우기 심화** ✅ 완료 — 형광펜(markpen) placeholder · 체크박스(☑/□) · `{placeholder}` 전역치환 · 누름틀 헤드리스 fill · form-fit/쪽수 드리프트 가드.
- **Phase B (P1) 신뢰성·검증·읽기** 🟢 자체코어 완료 — PII 마스킹 게이트 · dry-run/백업 · 읽기 확장(find_text/outline/styles) · `validate_hwpx`. (위임/외부의존 항목 render_preview·`.hwp` 헤드리스 읽기는 도구 확보 후 진행.)
- **v2 (COM 라이브)** 🟡 코드 완료, 데스크톱 실검증 대기 — `apply_to_open_hwp`로 열린 한글에 원샷 반영.
- 다음: Phase B 잔여(render_preview·`.hwp` 읽기), Phase C/D(편집·생성, python-hwpx 위임) — [`docs/ROADMAP.md`](docs/ROADMAP.md).

마일스톤·유저 스토리(38개 — 37 pass + 1 라이브 실검증 대기): [`docs/prd.json`](docs/prd.json) · 설계 결정: [`docs/DECISIONS.md`](docs/DECISIONS.md) · 아키텍처: [`docs/architecture.md`](docs/architecture.md).

## 리포 구조

```
Hangeul-mcp/
├─ hangeul_core/            # 순수 파이썬 엔진 (MCP 무관, 재사용 가능)
│  ├─ owpml/package.py      #   바이트 보존 HWPX 컨테이너
│  ├─ analyze.py            #   구조 분석 (셀 주소/span/글머리표/자간/셀 크기)
│  ├─ understand.py         #   2D 라벨-값 매핑 (병합셀 occupancy)
│  ├─ inline.py             #   inline-blank 탐지 (마커/콜론)
│  ├─ locate.py             #   섹션 전역 {placeholder} 탐지·splice (run 분할 대응)
│  ├─ markpen.py            #   형광펜 예시값 탐지·서식보존 교체
│  ├─ checkbox.py           #   체크박스(☑/□) 탐지·선택 토글
│  ├─ formfield.py          #   누름틀 헤드리스 탐지·채우기 (COM 이름 스키마 공유)
│  ├─ formfit.py            #   셀 넘침 추정 + 선택적 auto-fit(글꼴 축소)
│  ├─ pii.py                #   PII 탐지·마스킹 게이트 (주민번호/전화/카드/계좌/이메일)
│  ├─ read.py               #   읽기 확장 (find_text/outline/styles, read-only)
│  ├─ validate.py           #   무결성 검증 (well-formed/mimetype/선언, 선택적 XSD)
│  ├─ edit.py               #   일반 텍스트 치환 (search/batch replace, 바이트보존)
│  ├─ delegate.py           #   python-hwpx 위임 (편집·생성·이미지·리치 내보내기, optional)
│  ├─ mailmerge.py          #   mail_merge (대량 생성, 우리 fill 엔진 + 레코드 반복)
│  ├─ fill.py               #   서식 보존 채우기 (set/append/inline/placeholder/markpen/checkbox/누름틀, mask_pii/dry_run/backup, 멀티섹션)
│  ├─ extract.py            #   텍스트 추출
│  ├─ convert.py            #   .hwp → .hwpx (한글 COM)
│  ├─ schema.py             #   FieldSchema 데이터 모델
│  └─ hwp/com.py            #   (v2) COM 브릿지 (put_field_text)
├─ hangeul_mcp/server.py    # FastMCP stdio 서버 (28 tools: 19 OWN + 9 위임)
├─ skills/SKILL.md          # 검토→반영 Agent Skill
├─ tests/                   # 159 tests + fixtures (PII 없는 빈 양식)
├─ docs/                    # PLAN · DECISIONS · architecture · clients/ · qa-codex · research
└─ .github/workflows/ci.yml # CI (ubuntu, py3.11–3.13)
```

## 관련 오픈소스

생태계 조사 및 개발 전략: [`docs/research-strategy.md`](docs/research-strategy.md)
(python-hwpx, kordoc, claw-hwp, hwp-mcp, pyhwpx 등).

## 라이선스

MIT — [`LICENSE`](LICENSE)

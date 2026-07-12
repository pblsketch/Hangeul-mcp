# 한글(HWP/HWPX) 양식 자동 채우기 AI 개발 전략

> 목표: **사용자가 열어둔 한글 문서의 양식(서식·표·빈칸)을 인식하고, 그 형식에 맞는 텍스트를 AI가 생성해 채워 넣는** 프로그램 / Claude Desktop Skill 개발
> 작성일: 2026-07-08

---

## 0. 3줄 결론

1. **이 분야는 이미 성숙한 오픈소스 생태계가 있다.** 바닥부터 만들 필요 없이 `python-hwpx` 또는 `kordoc`를 코어로 쓰고, 그 위에 "양식 인식 + AI 텍스트 생성" 레이어만 얹으면 된다.
2. **가장 어려운 문제(서식 보존 채우기)는 이미 풀려 있다.** kordoc의 `fill_form(hwpx-preserve)`, python-hwpx의 `fill_by_path()` + byte-preserving patch가 원본 서식을 1바이트도 안 건드리고 값만 치환한다.
3. **핵심 갈림길은 "실시간 vs 파일 기반"이다.** "문서를 열어둔 채 실시간"은 Windows COM 자동화(hwp-mcp 방식)만 가능하고, "파일 첨부→채워진 파일 반환"은 크로스플랫폼 headless로 가능하다. **후자로 시작해서 전자로 확장**하는 것을 권장한다.

---

## 1. 기술 지형: 반드시 먼저 이해할 3가지 축

### 1-1. 파일 포맷 두 갈래 (이게 모든 걸 가른다)

- **HWPX (권장 타깃)** — ZIP + XML 컨테이너, OWPML 국제표준. 한컴 오피스 없이 순수 코드로 읽기·쓰기·서식제어 전부 가능. 크로스플랫폼(Win/Mac/Linux). **좋은 오픈소스의 90%가 여기에 몰려 있다.**
- **HWP 5.x (레거시 바이너리)** — OLE2/CFB 바이너리. 읽기는 가능하나 **쓰기가 극히 어렵다.** DRM/암호화 이슈까지. → 전략: HWP는 "HWPX로 변환 후 처리" 또는 "COM으로 한컴에게 시키기".

> **실무 규칙: 신규 개발은 HWPX-first로 간다.** 사용자가 `.hwp`를 주면 (a) 한컴에서 HWPX로 저장 유도, 또는 (b) `hwp-rs`/`pyhwp`/`kordoc`로 변환 후 처리.

### 1-2. 문서를 다루는 3가지 방법론

- **A. Headless XML 조작** (한컴 오피스 불필요) — HWPX의 ZIP을 풀어 XML을 직접 편집/치환. `python-hwpx`, `kordoc`, `claw-hwp`, 로컬 `hwpxskill`이 이 방식. **크로스플랫폼, 서버 배포 가능, 안정적.**
- **B. COM 자동화** (Windows + 한컴 오피스 설치 필수) — 실행 중인 `한글.exe`를 win32com/pyhwpx로 원격 조종. **"열어둔 문서를 실시간으로" 채우는 유일한 방법.** 대신 환경 종속·취약성·커서 위치 버그·보안 DLL 우회 필요.
- **C. AI 에이전트 레이어** (A 또는 B 위에 얹음) — MCP 서버 또는 Claude Skill로 LLM이 문서 도구를 호출. 사용자가 만들려는 게 바로 이 레이어.

### 1-3. 우리가 실제로 "개발"하는 부분

오픈소스가 이미 해주는 것(파싱·서식보존 치환)과 **우리가 새로 만들 것**을 구분하는 게 핵심:

- ✅ 이미 있음: 문서 파싱, 표/셀 추출, 서식 보존 치환, 검증
- 🔨 **우리가 만들 것 1 — 양식 인식(Form Understanding)**: 어디가 빈칸인지, 그 빈칸의 "라벨"(성명/주소/사유…)이 뭔지, 옆 셀인지 아래 셀인지, colspan 병합 여부, 허용 길이/형식은 무엇인지 자동 파악
- 🔨 **우리가 만들 것 2 — 맥락 기반 텍스트 생성**: 각 필드의 라벨·주변 문맥·문서 종류(기안문/계획서/신청서)에 맞는 톤과 내용을, **페이지 수가 안 늘어나게** 길이까지 제어해서 생성
- 🔨 **우리가 만들 것 3 — UX/오케스트레이션**: 사용자 입력 최소화, 승인 게이트, 미리보기, 되돌리기

---

## 2. 오픈소스 & 레퍼런스 지형도 (검증 완료)

### 2-1. ⭐ 핵심 코어 라이브러리 (여기서 하나 골라 기반으로)

- **python-hwpx** — https://github.com/airmang/python-hwpx
  순수 파이썬 HWPX 자동화(읽기/편집/생성/검증). **`fill_by_path("성명 > right")` 같은 계층 경로 기반 셀 채우기 + byte-preserving surgical patch로 서식 100% 보존.** 메일머지·서명란 프리셋·XSD 검증·ZIP폭탄/XXE 방어까지. HWPX 3계층 스택(코어+MCP서버+공식스킬)의 코어. **→ 파이썬 진영 1순위 추천.**

- **kordoc** — https://github.com/chrisryugj/kordoc
  TypeScript. HWP3/5·HWPX·HWPML·PDF·XLS·DOCX → Markdown 통합 파서 + **`fill_form` (hwpx-preserve 모드) + `patch_document` + 신구대조(diff) + MCP 서버 11개 툴.** 도장(인) 자동 배치, 수식/차트 생성, 관제문서(공문) 프리셋까지. 지자체 공무원이 실제 공공문서 수천 건으로 검증. **→ Node/TS 진영 1순위, 그리고 지금 이 환경에 MCP 도구로 이미 연결돼 있음.**

- **hwp-rs** — https://github.com/hahnlee/hwp-rs
  Rust 기반 HWP 파서. 성능·정확도 필요 시. `rhwp`(WASM)의 기반이기도 함.

- **pyhwp** — https://github.com/mete0r/pyhwp
  HWP 5.0 바이너리 파서(읽기 전용 중심, AGPL-3.0). 레거시 `.hwp` 텍스트 추출·구조 분석용. 쓰기는 부적합.

### 2-2. 🤖 AI 에이전트 / MCP / Skill (우리가 만들려는 것의 직접 선행 사례)

- **claw-hwp** — https://github.com/DoHyun468/claw-hwp
  **Claude Agent Skill.** rhwp WASM 기반, 한컴 오피스 없이 로컬에서 .hwp/.hwpx 읽기·생성·편집. 브라우저 미리보기 내장, 서식 보존, 도장 배치, 민감정보 로컬 보관(채팅에 노출 안 함). MIT. **→ Claude Desktop Skill을 노린다면 구조·UX의 최고 참고 대상.**

- **hwpx-skill (airmang)** — https://github.com/airmang/hwpx-skill
  python-hwpx 기반 실무 스킬. 문단/표 처리 + Zip-level 전역 치환 + 네임스페이스 정리 자동화.

- **hwpx-skill (jkf87)** — https://github.com/jkf87/hwpx-skill
  AI 에이전트용 HWPX 생성 스킬. 마크다운/텍스트/URL → 한글 문서 자동 생성. 기안문·보도자료·계획서 생성기 + **양식 채우기** + 머리말/꼬리말 + 표 편집.

- **hwpx-mcp-server** — https://github.com/airmang/hwpx-mcp-server
  python-hwpx 기반 MCP 서버. Claude Desktop에 붙여 문서 생성·편집·탐색.

- **hwp-mcp (jkf87)** — https://github.com/jkf87/hwp-mcp
  **COM 자동화 방식 MCP.** Windows + 한컴 오피스 설치 필요. `한글.exe`를 직접 조종해 **열린 문서에 커서 이동·텍스트 삽입·표 채우기.** 보안 프롬프트 우회 DLL 포함. **→ "실시간 열어둔 문서" UX를 원하면 이 방식이 유일한 선행 사례.**

- **hwpilot (devxoul)** — https://github.com/devxoul/hwpilot
  TypeScript/Bun, 바이너리 직접 조작. CLI가 JSON 출력 → 에이전트 소비. Claude Skill·OpenCode 플러그인·SkillPad GUI 지원. HWP5→HWPX 변환. MIT, 활발.

- **로컬 설치됨: `hwpxskill`** (`~/.claude/skills/hwpxskill/`)
  이미 이 PC에 있음. **XML-first 워크플로우**로 (1) 첨부 HWPX 분석 → (2) header/section XML 추출 → (3) 구조 99% 복원 + 텍스트만 치환 → (4) 빌드·검증 → (5) **page_guard로 쪽수 드리프트 차단.** `analyze_template.py`가 폰트·borderFill·charPr·paraPr·표구조까지 청사진 추출. **→ 양식 인식 로직의 즉시 참고/재사용 자산.**

### 2-3. 🔄 변환 / 보조

- **pypandoc-hwpx** — https://github.com/msjang/pypandoc-hwpx : md/html/docx → hwpx (Pandoc 기반)
- **openhwp** — https://github.com/openhwp/openhwp : HWP 라이브러리+뷰어+에디터 올인원 프로젝트
- **rhwp** — https://github.com/edwardkim/rhwp : Rust+WASM HWP 뷰어/에디터 (claw-hwp의 엔진)
- **volexity/hwp-extract** : HWP 추출 (보안/포렌식 맥락)

### 2-4. 💼 상용 레퍼런스 (UX·시장 벤치마크)

- **inline AI** (inline-ai.com) — "파일 위에서 작동하는 로컬 AI 에이전트." 100% 로컬 처리·제로 데이터 보관·**모든 액션 사용자 승인.** 데스크톱 앱 형태. (HWP 명시는 약하나, "열린 문서에 바로 써주는" UX의 벤치마크)
- **폴라리스오피스 AI DataInsight** — HWP/PDF/DOCX → 구조화 데이터, 공공 AI 전환용 파서. (엔터프라이즈 파싱 벤치마크)

---

## 3. 사용자 비전에 대한 핵심 통찰

> "한글 문서를 **열어두면** 그 양식에 맞게 텍스트를 **생성하고 채우는**"

이 한 문장에 서로 다른 난이도의 3요소가 섞여 있다. 분리해서 봐야 한다:

- **(가) "열어두면" = 실시간성** → 가장 비싼 요구. Headless(파일 기반)로는 "열린 창"을 못 만짐. 진짜 실시간은 Windows COM(hwp-mcp) 뿐. **MVP에서는 "파일을 주면 채워서 돌려준다"로 완화 권장.** 체감 UX는 "드래그&드롭 → 채워진 파일" 이면 충분히 만족스럽다.
- **(나) "양식에 맞게" = 양식 인식** → 우리의 진짜 엔지니어링. 빈칸 탐지 + 라벨-값 페어링(옆/아래/병합셀) + 필드 타입/길이 추론. kordoc `parse_form` / hwpxskill `analyze_template.py`가 출발점.
- **(다) "생성하고 채우는" = AI + 서식보존 치환** → 생성은 LLM(우리가 프롬프트 설계), 치환은 오픈소스가 이미 해결(hwpx-preserve / byte-patch).

**결론적 통찰:** 시장에 **"양식을 이해해서 AI가 문맥 맞는 내용을 채우는"** 완성형은 아직 빈틈이 있다. 대부분은 (a) 파싱/치환 인프라거나 (b) 사용자가 값을 다 불러줘야 하는 mail-merge다. **차별점은 "필드 라벨만 보고 AI가 알아서 적절한 내용·길이로 채우는 지능"에 있다.** 여기에 집중하라.

---

## 4. 단계별 개발 전략

### Phase 0 — 프로토타입 (지금 당장, 1~2일)

**목표:** "HWPX 첨부 → 양식 인식 → AI 값 생성 → 서식보존 채우기 → 반환" 파이프라인을 코드 없이 검증.

- 이 환경엔 이미 **kordoc MCP 도구**(`parse_form`, `fill_form`, `parse_document`)와 로컬 **hwpxskill**이 있다.
- 실행: 샘플 신청서/기안문 HWPX 하나로 → `parse_form`으로 필드 추출 → Claude가 필드별 값 생성 → `fill_form(hwpx-preserve)`로 채움 → 결과 확인.
- **이 단계에서 "양식 인식이 실제로 얼마나 정확한지"를 측정**하는 게 핵심. 여기서 나온 실패 케이스가 Phase 1의 스펙이 된다.

### Phase 1 — MVP: HWPX 양식채우기 Claude Skill (1~2주)

**아키텍처:** `python-hwpx`(코어) + 커스텀 "Form Understanding" 레이어 + Claude Skill 래퍼

1. **코어 채택**: `python-hwpx` (파이썬 생태계·byte-preserving patch·MCP 스택 완비). Node 선호 시 `kordoc`.
2. **양식 인식 모듈 (우리가 개발)**:
   - 빈칸/플레이스홀더 탐지: 빈 셀, `(    )`, 밑줄, `{{필드명}}` 패턴
   - 라벨-값 매핑: 표에서 라벨 셀 → 값 셀(오른쪽/아래), colspan 병합 처리 (kordoc·hwpxskill 로직 참고)
   - 필드 메타 추론: 타입(이름/날짜/금액/서술형), 최대 길이(셀 폭·페이지 여유 기반)
   - 출력: `[{label, type, cell_path, max_len, context}]` JSON 스키마
3. **생성 프롬프트 설계 (우리가 개발)**:
   - 문서 종류 자동 분류(기안문/계획서/신청서/보고서)
   - 필드별 개별 생성 + **전역 일관성**(같은 문서 안에서 이름·날짜·톤 통일)
   - **길이 제어**: hwpxskill의 `page_guard` 철학 이식 — 생성 후 쪽수 드리프트 검사, 넘치면 요약 재생성
4. **서식보존 채우기**: `fill_by_path()` / `fill_form(hwpx-preserve)` 그대로 사용
5. **Skill 패키징**: `claw-hwp` / 로컬 `hwpxskill`의 SKILL.md 구조를 템플릿으로. 첨부 → 분석 → 채움 → 검증 → 반환.

**MVP 성공 기준:** 실제 공공/업무 양식 10종에서 (a) 필드 인식률 90%+, (b) 서식·쪽수 100% 보존, (c) 사용자 입력은 "무슨 내용인지" 힌트 한두 줄만.

### Phase 2 — 실시간 "열어둔 문서" 모드 (선택, Windows 전용)

**목표:** 진짜 "열어둔 채" 채우기.

- **경로 A (COM):** `hwp-mcp` 방식 채택. win32com/pyhwpx로 실행 중 한컴 조종. 열린 문서에 커서 이동·삽입. → Windows+한컴 필수, 취약성 감수.
- **경로 B (한컴 독스 자동화 캡처):** claw-hwp의 `hancomdocs-capture`처럼 실제 렌더 검증.
- **경로 C (에디터 애드인/사이드카):** 파일을 워처(`kordoc watch ./폴더`)로 감시 → 저장 시 자동 반영. "실시간 느낌"을 headless로 근사.

> 권장: **경로 C로 "실시간 체감"을 먼저 확보**하고, 진짜 COM은 수요가 확인되면.

### Phase 3 — 확장

- `.hwp` 레거시 지원 (hwp-rs/pyhwp로 읽어 HWPX 변환 후 처리)
- 양식 라이브러리/학습 (자주 쓰는 양식 프리셋 축적)
- 신구대조·감사 로그 (kordoc `compare_documents`)
- 민감정보 로컬 처리·승인 게이트 (inline AI / claw-hwp UX 벤치마크)

---

## 5. 의사결정 매트릭스 (요약)

- **파이썬 선호 + 서버/CI 배포** → 코어 `python-hwpx`
- **Node/TS 선호 + 다포맷(PDF·DOCX 포함) + MCP 즉시** → 코어 `kordoc`
- **Claude Desktop Skill 형태가 최종 목표** → `claw-hwp` 또는 로컬 `hwpxskill` 구조를 뼈대로, 위 코어를 엔진으로
- **진짜 실시간 열린-문서 제어 필수** → `hwp-mcp` (COM) 병행, Windows 종속 수용
- **레거시 .hwp 다수** → `hwp-rs`/`pyhwp` 변환 파이프라인 추가

---

## 6. 리스크 & 주의사항

- **HWP 바이너리 쓰기 금지 원칙**: 쓰기는 HWPX로만. `.hwp`는 읽기/변환만.
- **쪽수 드리프트**: 양식 채우기의 최대 함정. 생성 길이 제어 + `page_guard` 필수 게이트화.
- **COM 취약성**: 한컴 버전 업데이트마다 깨질 수 있음. 자동화 테스트 필수, 실시간 모드는 optional 유지.
- **라이선스**: `pyhwp`는 AGPL-3.0(전염성 강함) → 상용 배포 시 주의. `python-hwpx`·`kordoc`·`claw-hwp`·`hwpilot`은 관대한 라이선스(MIT 등) 확인 후 채택.
- **민감정보**: 공공/업무 양식엔 개인정보 다수. 로컬 처리 + 채팅 비노출(claw-hwp 방식) 설계.
- **양식 인식의 롱테일**: 표가 아닌 자유 레이아웃, 밑줄 빈칸, 이미지화된 양식 등 예외가 많음 → 실패 케이스 로깅·점진 개선 루프 필수.

## 6-1. 쉬운 설치·업데이트 관리면의 설계 메모

- **entrypoint 분리**: MCP 클라이언트가 쓰는 `hangeul-mcp`는 stdio 전용으로 남기고, 설치/설정/진단/업데이트는 `hangeul-mcp-manage setup`, `hangeul-mcp-manage doctor --json`, `hangeul-mcp-manage update --check` 같은 별도 관리 CLI로 분리하는 편이 안전하다. stdout 오염 없이 MCP 초기화 계약을 지키기 쉽다.
- **managed vs unmanaged**: managed install은 stable launcher가 user-data state(`current.json`, `versions/`)를 읽어 현재 runtime을 실행하고, unmanaged install은 클라이언트 설정에 절대 경로 `sys.executable -m hangeul_mcp.server`를 직접 기록하는 방식이 맞다. 현재 managed launcher의 기본 표면은 절대 경로 Python + `-m hangeul_mcp.launcher`이며, bare `hangeul-mcp`는 installer shim이 있을 때만 convenience 경로다.
- **업데이트 메타데이터**: 최신 버전 확인은 PyPI JSON API를 1차 source로 삼되, 아직 PyPI publication이 검증되지 않았으므로 404/미게시 상태를 성공처럼 포장하지 않는다. 이 경우 `not_published` 또는 구조화된 네트워크 오류가 정직한 응답이다.
- **정책 집행**: `notify|daily|off`는 단순 저장으로 끝나면 안 된다. `daily`는 launcher 기동 시 24h TTL을 보고 background `update`를 bounded next-run 방식으로 스케줄하고, `off`는 자동 실행을 금지하며, `notify`는 명시적 `update`/`update --check`만 허용해야 한다.
- **source allowlist**: updater는 임의 index URL이나 임의 package name을 사용자 설정에서 받아 실행하지 않고, allowlisted package source와 고정된 배포 식별자만 사용해야 한다.
- **stable/beta 채널 의미**: `stable`은 최종 semver release만, `beta`는 `a`/`b`/`rc` prerelease까지 포함한다. 채널 설명과 release workflow 문구가 이 의미를 벗어나면 안 된다.
- **release artifact 정직성**: trusted publishing workflow는 draft여도 release notes, SHA256 checksum 또는 provenance 위치를 같이 문서화해야 한다. workflow green만으로 PyPI 수락 증거라고 말하면 안 된다.
- **extras 설명 원칙**: 현재 pyproject 기준 optional extras는 `com`, `delegate`, `render`, `live`, `hwp-headless`, `dev`다. 특히 `com`은 Windows COM bridge용 `pywin32`, `live`는 pyhwpx 기반 live workflow용 extra다. 둘은 관련은 있지만 같은 extra가 아니며, 문서도 그 관계를 과장하면 안 된다.
- **rollback/backup 경계**: rollback은 versioned runtime 전환 범위 안에서만 현실적이다. client config backup에는 잠재 secret이 들어갈 수 있으므로 내용 로그 금지와 최소 보존 원칙이 필요하다.

---

## 7. 다음 액션 (권장 즉시 실행)

1. **샘플 양식 3~5개 확보** (기안문·신청서·계획서 등 실제 쓰는 HWPX)
2. **Phase 0 프로토타입**: 지금 이 환경의 kordoc 도구 + hwpxskill로 end-to-end 1회 돌려보기 → 인식률/보존율 실측
3. 실측 결과로 **"양식 인식 모듈" 스펙 확정** → Phase 1 착수
4. 코어 라이브러리 최종 선택(python-hwpx vs kordoc)은 팀 언어 선호로 결정

---

### 참고 링크 모음

- python-hwpx: https://github.com/airmang/python-hwpx
- kordoc: https://github.com/chrisryugj/kordoc
- claw-hwp: https://github.com/DoHyun468/claw-hwp
- hwpx-skill(airmang): https://github.com/airmang/hwpx-skill
- hwpx-skill(jkf87): https://github.com/jkf87/hwpx-skill
- hwpx-mcp-server: https://github.com/airmang/hwpx-mcp-server
- hwp-mcp(COM): https://github.com/jkf87/hwp-mcp
- hwpilot: https://github.com/devxoul/hwpilot
- hwp-rs: https://github.com/hahnlee/hwp-rs
- pyhwp: https://github.com/mete0r/pyhwp
- pypandoc-hwpx: https://github.com/msjang/pypandoc-hwpx
- openhwp: https://github.com/openhwp/openhwp
- rhwp: https://github.com/edwardkim/rhwp

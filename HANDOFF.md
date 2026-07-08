# 핸드오프 프롬프트 — Hangeul-mcp 다음 개발

> 새 세션에 이 파일 내용을 그대로 붙여넣고 시작. **/ralplan 으로 계획 → /ralph 로 구현**.

---

## 프롬프트 (복사해서 새 세션에 붙여넣기)

너는 **Hangeul-mcp** (한글 HWP/HWPX 양식 인식 + 서식보존 채우기 MCP 서버, Python)의 다음 개발을 이어받는다.

**리포**: `E:/github/Hangeul-mcp` (GitHub `pblsketch/Hangeul-mcp`, public, v0.1.0).
**개발 환경**: venv `E:/github/Hangeul-mcp/.venv` (Python 3.14, Windows).
- 테스트: `./.venv/Scripts/python.exe -m pytest -q` (현재 56 passed, 1 skipped)
- 린트: `./.venv/Scripts/python.exe -m pyflakes hangeul_core hangeul_mcp tests`
- COM(pywin32) 설치됨. 라이브 COM 테스트는 `HANGEUL_MCP_LIVE=1`에서만.

**먼저 읽을 것 (SSOT)**:
- `docs/ROADMAP.md` — 우선순위(P0/P1/P2)와 작업 정의. **이게 작업 목록**.
- `docs/gap-analysis.md` — 선행사례 대비 미지원 목록.
- `docs/DECISIONS.md` — 확정 결정(바이트보존·field_id·python-hwpx substrate 등).
- `docs/architecture.md` — 계층/모듈.
- `docs/qa-codex-v0.1.0.md` — codex QA 이력 + 남은 리팩터 제안.

**현재 상태(완료)**: 라벨:값 fill · inline-blank(마커/콜론) · 병합셀 2D occupancy · 멀티섹션 · 바이트보존 채우기 · 자간정규화 · MCP 서버 6툴(detect_format/analyze_form/fill_form/extract_text/hwp_status/apply_to_open_hwp) · 클라이언트무관 · `.hwp→hwpx` COM 변환(데스크톱) · markpen 텍스트 독해 수정.

**이번 작업 목표(전 범위)**: `docs/ROADMAP.md`의 **Phase A~D 전부**. 단 순서·방식 준수:
- **Phase A(P0, OWN, 먼저)**: ①형광펜 placeholder kind ②체크박스(☑/□) ③`{placeholder}` 전역치환 ④누름틀 헤드리스 fill ⑤form-fit/쪽수가드
- **Phase B(P1, OWN+DELEGATE)**: XSD 검증·dry-run/백업/repair·render_preview·PII 마스킹 게이트·`.hwp` 헤드리스 읽기·읽기확장(outline/find/html)
- **Phase C(P2, DELEGATE)**: 일반 편집(search/replace·문단·표·서식·이미지·머리꼬리말·TOC) — **python-hwpx를 얇게 감싸 Hangeul-mcp 툴로 노출**(재발명 금지), 편집 후 XSD/바이트무결성 게이트
- **Phase D(P3, DELEGATE+레시피)**: 문서 생성(builder·md→hwpx·기안문/보도자료/계획서/시험지·mail_merge)

핵심 방식 = **own vs delegate**: 차별점(인식·채우기)은 직접, commodity breadth(편집·생성)는 python-hwpx 위임 + 우리 툴로 노출. A·B 먼저, C·D는 위임 어댑터라 병렬 가능.

**반드시 지킬 불변식**:
- **바이트보존**: 바꾼 필드 외 (엔트리 payload 기준) 무변경. XML 재직렬화 금지 — raw-XML byte splice + mimetype STORED·XML 선언 보존. (ElementTree write는 선언 날림 — 읽기 전용에만 ET 사용.)
- **두뇌·손 분리**: 값 *생성*은 클라이언트 LLM. 서버는 인식·채우기·반영만. 텍스트 생성 툴 만들지 말 것.
- **차별점 사수**: inline-blank·병합셀 2D·review→apply. breadth(편집/생성)는 python-hwpx substrate 위임 검토, 재발명 금지(DECISIONS D1).
- **kind 인식 실양식 함정**(중요): `analyze`는 `<hp:t>` 안 inline 마크업(markpen 등) 텍스트를 itertext로 읽는다 — 새 kind 추가 시 유지. 자동 글머리표 중복 금지, 줄바꿈은 실제 문단화(raw \n/\r 금지). 자세한 함정: 커밋 이력·`docs/qa-codex-v0.1.0.md`.
- 각 스토리는 **골든/회귀 테스트** 동반. `tests/fixtures/sample_form.hwpx`(PII 없는 빈 강사카드) 사용. 실 PII 파일 커밋 금지(.gitignore).
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. 커밋/푸시는 요청 시. 스토리별 커밋.

**진행 방식**:
1. **/ralplan** 으로 P0 스토리들을 PRD로 분해(수용 기준 구체화). `docs/prd.json` 갱신 또는 신규 PRD.
2. **/ralph** 로 스토리별 구현 → 테스트 → 커밋. 리뷰어는 `--critic=codex` 권장(codex CLI 사용 가능: `codex exec`). 각 스토리 완료 시 pyflakes clean + 전체 pytest green 확인.
3. 완료 후 README/ROADMAP 상태 갱신, 푸시.

**참고**: 선행사례 `airmang/hwpx-mcp-server`(60+툴), `python-hwpx`가 편집/생성/검증 breadth를 이미 포괄 — 참고·위임 대상이지 재구현 대상 아님. 우리는 양식 인식·채우기 깊이로 승부.

---

## 빠른 시작(새 세션 첫 명령 예시)

전 범위는 Phase A→B→C→D. ralph는 증분 구현이므로 **Phase A부터** 계획·구현하고 순차 진행:
```
/ralplan  Hangeul-mcp 다음 개발 계획. 전 범위는 docs/ROADMAP.md Phase A~D(편집·생성 포함, C·D는 python-hwpx 위임).
이번엔 Phase A(P0) 5개(형광펜 placeholder·체크박스·{placeholder}전역치환·누름틀 헤드리스 fill·form-fit 가드)를
스토리로 분해하고 수용기준 확정. 불변식(바이트보존·두뇌손분리·own vs delegate)은 HANDOFF.md 참조.
```
계획 승인 후:
```
/ralph  위 계획대로 구현. 스토리별 테스트+커밋, 리뷰어 codex, 바이트보존·두뇌손분리 불변식 준수.
```
Phase A 완료 후 같은 방식으로 B → C → D 진행.

# 설계 결정 기록 (ADR-lite)

> 빌드 착수 전 확정된 결정. PLAN.md 10절 "열린 질문"의 최종 답.
> 확정일: 2026-07-08

## D1. 채우기 substrate — 자체 엔진 코어 + python-hwpx 검증 병용
- **결정**: 코어는 **자체 바이트 보존 XML 엔진**(run 단위 완전 제어). `python-hwpx`는 **XSD 스키마 검증 + 보안(ZIP-bomb/XXE) 하드닝** 레이어로만 병용.
- **이유(최대 품질)**: inline-blank(문장 중간 빈칸)·병합셀 삽입은 고수준 API가 노출하지 못하는 run/문단 단위 정밀 제어가 필요 → 제어권은 우리가 갖는다. 동시에 컨테이너 안전성·스키마 적합성은 성숙한 라이브러리로 검증한다.
- **검증 게이트**: US-002 스파이크에서 python-hwpx 검증 연동을 확인. 연동이 품질을 저해하면 자체 검증으로 대체.

## D2. 필드 매칭 키 — field_id 권위 + label 별칭
- **결정**: `field_id`(예: `t2.r2.c3`, 표·행·열 주소)를 **권위 키**로. `label`("성명")은 사람이 쓰기 쉬운 **별칭**으로 field_id에 해석.
- **이유(최대 품질)**: 병합셀·중복 라벨·라벨-아래-값 레이아웃에서 라벨 기반 매칭은 모호. 주소 기반이 무오류. label은 UX 편의로 유지하되 충돌 시 field_id 우선.

## D3. .hwp 입력 — v1 자동 HWPX 변환 지원
- **결정**: v1에서 `.hwp`(바이너리) 입력 시 자동으로 HWPX로 변환 후 처리.
- **변환 백엔드(우선순위, US에서 확정)**:
  1. 로컬 **한글(COM)** "다른 이름으로 저장 → HWPX" — 정확도 최고, Windows+한글 필요.
  2. 크로스플랫폼 대안: **LibreOffice + H2Orestart(HWP import)** 또는 hwp5 변환 파이프라인.
- **정책**: 변환 백엔드 미가용 환경에서는 명확한 에러 + 안내(수동 HWPX 저장). HWPX 입력은 항상 크로스플랫폼.

## D4. 패키지 이름 / 배포
- **결정**: 실행명 `hangeul-mcp` 확정. **PyPI 배포는 v1에서 보류**(GitHub 설치: `pip install git+https://...`). 안정화 후 v1.0에서 PyPI 등록 검토.

## D5. Git 원격
- **결정**: GitHub 원격 생성 + 푸시. 초기값 **private**(작업 중 프로젝트, PII 없음 확인 완료지만 안전 기본값). 공개는 언제든 전환 가능.

## D6. 문서 생성 레시피의 "레이아웃 골격"은 두뇌·손 분리의 명시적 예외 (codex QA High-4)
- **결정**: `create_official_document`/`create_hwpx_from_markdown` 같은 **문서 생성 레시피**는 고정 구조 라벨("보도자료", "제목", "1. 목적", "붙임" 등)을 **레이아웃 골격(layout chrome)**으로 삽입한다. 이는 "서버는 문안을 생성하지 않는다"는 두뇌·손 분리 원칙의 **의도된, 옵트인 예외**다.
- **경계**: 실제 **내용 값**(제목/본문/수신자 등)은 전부 클라이언트가 `fields`로 제공한다. 서버가 생성하는 것은 **템플릿의 고정 구조 문자열**뿐이며, 값이 아니다. 인식·채우기(OWN) 경로는 이 예외와 무관하게 문안을 생성하지 않는다.
- **불변식**: 레시피는 `fields`에 없는 **본문/문안**을 절대 생성하지 않는다. 골격 라벨만 추가한다. 새 레시피 추가 시 이 규칙을 준수한다.

## D7. 라이브 셀 채우기의 표 인덱스 매핑은 단일/최상위 표 기준 (codex QA Med-1)
- **결정**: `apply_cells_to_open`은 우리 `analyze`의 전역 표 인덱스와 pyhwpx `get_into_nth_table`의 컨트롤 순서가 일치한다고 가정한다. 이 가정은 **단일 표 또는 최상위 표만 있는 양식**(강사카드 등)에서 성립한다.
- **한계**: 중첩 표(nested table)나 병합셀이 섞인 문서에서는 표 순서/셀 주소가 어긋날 수 있다. 이는 **실기기(Claude Desktop) 라이브 검증**으로만 확정 가능하며, 그전까지 라이브 셀 채우기는 **best-effort**로 표기한다.
- **후속**: 실검증에서 매핑 오차가 확인되면 (a) 최상위 표 서수와 중첩 표 서수를 분리 저장, (b) pyhwpx가 노출하는 컨트롤 식별자로 선택, (c) 병합셀에서 `clear=True` 비활성화를 검토한다.

## D8. `create_document_from_blocks`는 D6의 완전제어 탈출구
- **결정**: `create_document_from_blocks`는 heading/paragraph/list/table/image/page_break 블록을 **클라이언트가 전부 제공**하는 구조 조립 도구다. 서버는 레시피 chrome이나 숨은 본문을 추가하지 않는다.
- **이유**: D6의 공식문서 레시피는 의도된 layout chrome 예외지만, 사용자가 고정 라벨까지 완전히 통제해야 하는 경우가 있다. blocks API는 그 경우의 기본 경로다.
- **경계**: markdown→HWPX도 내부적으로 blocks로 변환한다. full CommonMark가 아니라 문서화된 subset만 지원한다.

## D9. 렌더와 `.hwp` 헤드리스 읽기는 선택 의존성 게이트
- **결정**: `render_preview`는 Playwright/브라우저가 있을 때만 PNG를 생성하고, 없으면 `available:false`를 반환한다. 렌더는 HTML을 `file://`로 열지 않고 로컬 HTTP 경로로 screenshot한다.
- **결정**: `extract_hwp_text`는 COM 변환을 headless 읽기로 포장하지 않는다. 현재는 headless reader 후보 모듈을 점검하는 adapter gate이며, 실제 `.hwp` 추출 완료 판정은 비COM substrate와 PII 없는 `.hwp` fixture 검증 이후로 제한한다.

## D10. Hangeul-mcp는 BYO-AI 로컬 문서 하네스다
- **결정**: 서버는 LLM/API를 호출하지 않는다. 사용자가 이미 구독하는 AI 클라이언트가 문안과 값을 생성하고, Hangeul-mcp는 로컬 HWP/HWPX 문서 작업만 수행한다.
- **이유**: 별도 API 과금은 공무원·교사·공공기관 사용자의 도입 장벽이다. MCP 서버는 모델이 아니라 문서 능력 확장팩이어야 한다.
- **경계**: Hangeul-mcp가 외부 API를 호출하지 않는다는 뜻이지, 사용자의 AI 클라이언트가 문서 내용을 모델에 보내지 않는다는 보장은 아니다. 민감 문서는 `scan_pii`와 클라이언트 설정으로 통제한다.

## D11. 파일 모드와 live 모드는 분리한다
- **결정**: HWPX 파일 모드는 core/headless 경로로 유지하고, 열린 한글 문서 제어는 Windows + 한컴 + optional dependency가 필요한 live adapter로 분리한다.
- **이유**: 공공기관 타깃에서는 Windows + 한컴이 현실 전제지만, 그 의존성이 HWPX 파일 처리의 안정성과 크로스플랫폼성을 깨면 안 된다.
- **게이트**: live status/preview 도구는 side-effect-free여야 하며, 실제 apply는 사용자가 의도적으로 호출한 경우에만 열린 한글 창을 조작한다.

## D12. `.hwp` 비COM 읽기 substrate — 스파이크 결론: keep-gate (US-054)
- **결정**: `extract_hwp_text`는 adapter gate(`available:false`)를 **유지**한다. 현재 시점에 채택 가능한 비COM `.hwp` reader substrate가 없다.
- **후보 비교 (2026-07-10 실측, PyPI 메타데이터 + pip dry-run)**:

| 후보 | PyPI | 라이선스 | 설치성 | API 형태 | 판정 |
|---|---|---|---|---|---|
| `pyhwp` | ✅ v0.1b15 | **AGPLv3+** | dry-run 해석 OK (py3.14 런타임 호환은 2015년대 beta라 미보장) | `hwp5txt` CLI + hwp5 파서 모듈 | **no-go**: AGPL은 MIT 프로젝트의 위임 substrate로 부적합(optional이어도 배포·연동 리스크), 10년 무릴리스 beta |
| `rhwp` | ❌ 없음 | — | pip 불가 | — | **no-go**: pip 설치 경로 부재 |
| `kordoc` | ❌ 없음 | — | pip 불가 | MCP **서버**이지 import 라이브러리가 아님 | **no-go**: 라이브러리 아님 |
| `hwp5` | ⚠️ 존재하나 **무관 패키지** (MIT, "hard-work pattern finder") | MIT | 설치되나 .hwp와 무관 | — | **함정**: 네임스페이스 선점 — `find_spec("hwp5")`는 가짜 신호가 될 수 있음. 게이트가 항상 `available:false`라 현재 무해하나, 어댑터 채택 시 이름 검사만으로 활성화 금지 |
| `olefile` + PrvText/BodyText 직접 파싱 | ✅ v0.47 | BSD | 건강 | OLE compound 스트림 읽기(자체 어댑터 필요) | **유일한 라이선스-안전 경로**(후속 스파이크): `.hwp`는 OLE — `PrvText` 스트림(UTF-16 미리보기 텍스트) 또는 BodyText zlib 해제. 단 OWN 구현이며 PII 없는 실 `.hwp` fixture 확보가 선행 조건 |

- **fixture**: PII 없는 실 `.hwp` fixture 미확보(COM 없이 합성 `.hwp` 생성 곤란). US-055의 구현 전제조건 미충족.
- **결론**: keep-gate. `extract_hwp_text`는 계속 `available:false` + 후보 점검 결과를 반환하고, COM 변환을 headless로 위장하지 않는다(D9). 후속: olefile/PrvText 경로는 PII 없는 fixture 확보 시 별도 스토리로 재평가(OWN 텍스트 추출로 한정, 구조 파싱은 그 다음).
- **경계**: 어댑터를 채택하는 날에도 `CANDIDATES` 이름 존재 검사만으로 available을 올리지 않는다 — 실제 추출 스모크가 통과해야 활성화(hwp5 네임스페이스 함정).

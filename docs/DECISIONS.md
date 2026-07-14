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

## D13. delegate breadth는 python-hwpx 2.24 실측 표면 안에서만 (US-056, ⑤ 상류 스파이크)
- **결정**: Phase ⑤ breadth는 python-hwpx **2.24.0 실측 API 표면**이 지원하는 것만 delegate 스토리로 구현한다. 플로어는 `python-hwpx>=2.24,<3`(D1 소프트 의존 유지, `<3`은 major 격리용 — minor의 표면 변화는 런타임 feature-detect가 흡수).
- **실측 표면 (2026-07-10, hwpx 2.24.0 직접 검증)**:
  - **지원** — `HwpxDocument`: `set_header_text` / `set_footer_text` / `remove_header` / `remove_footer` / `set_header_content`·`set_footer_content`·`set_header_footer` / `set_page_size` / `set_page_margins` / `set_page_number` / `set_page_setup` / `set_columns` / `add_control`·`add_bookmark`·`add_hyperlink`. `HwpxOxmlTable`: `merge_cells` / `split_merged_cell(row, col)` / `get_cell_map` / `set_cell_shading` / `set_cell_text` / `set_column_widths`.
  - **미지원** — 표 **행/열 추가·삭제**(`add_row`/`remove_row`/`add_column`/`remove_column` 부재, `HwpxOxmlTableRow`는 `cells`만) · **임의 셀 분할**(`split_merged_cell`은 병합 해제 전용) · **TOC**(`toc`/`generate_toc` 부재).
- **계약 테스트**: `tests/test_delegate_api_surface.py` — 지원 메서드 **존재는 hard assert**(위임 툴의 실계약), 미지원 메서드 **부재는 soft tripwire**(BC1: 상류가 추가하는 날 suite를 red로 만들지 않고 "US-060 재검토" 경고만 발생 — 상류 개선은 호재이지 실패가 아니다).
- **버전 게이트**: 위임 함수는 `getattr` feature-detect로 메서드 부재 시 `AttributeError` 대신 `requires python-hwpx>=2.24` 구조화 메시지를 반환한다(2.20 설치 환경에서 원인 은폐 방지).
- **귀결**: 머리말/꼬리말(US-057)·페이지 설정(US-058)·병합셀 분할(US-059)은 delegate로 제공. 행/열 추가삭제·TOC는 D14(US-060) 재분류를 따른다.

## D14. 표 행/열 추가·삭제와 TOC는 이번 패스 미제공 — spike-pending OWN 리서치 (US-060)
- **결정**: 표 **행/열 추가·삭제**와 **TOC 생성**은 delegate로 제공 불가(D13 실측: python-hwpx 2.24에 API 부재)이며, 이번 안정화 패스에서는 **미제공**한다. 두 기능 모두 어떤 스토리에도 "동작 반영" acceptance를 커밋하지 않는다.
- **OWN 구현 타당성 판정**:
  - **행/열 추가·삭제 — implement-later(조건부)**: raw-XML `<hp:tr>`/`<hp:tc>` splice는 기술적으로 우리 엔진 역량 안에 있으나, 표 구조 변형은 grid 정합(cellAddr 재번호·span 재계산·borderFill 참조)의 파손 위험이 셀 내용 치환과 차원이 다르다. 착수 조건: (a) 전용 그리드-정합 검증 스위트 선행, (b) `validate_hwpx`+실제 한글 열람 스모크, (c) 기존 바이트보존 테스트 무손상. 조건 미충족 시 keep-out이 정직한 결론.
  - **TOC — keep-out(페이지번호 정확 TOC) / implement-later(제목 목록 변형)**: 페이지번호 있는 TOC는 렌더러 없이 정확할 수 없어(형식만 갖춘 오답 생성 위험) keep-out. `add_control`/`add_bookmark` 기반 "제목 목록(페이지번호 없음)" 변형만이 정직한 후보이며, 그것도 OWN 리서치 스토리로만 착수한다.
- **불변식 제약(명시)**: 어느 경로든 바이트보존 테스트 약화 금지, D1(재발명 금지) 위반 금지. 제약과 충돌하면 미제공이 결론이다.
- **재검토 트리거**: `tests/test_delegate_api_surface.py`의 soft tripwire가 상류 API 추가를 경고하면 이 ADR을 재평가한다(BC1 — CI를 red로 만들지 않는다).

## D15. 관리 CLI는 stdio 서버와 분리하고, managed install은 stable launcher + versioned runtime으로 운영한다
- **결정**: 기존 `hangeul-mcp` entrypoint는 MCP stdio 서버 기동 전용으로 유지하고, 설치/설정/진단/업데이트/롤백은 별도 콘솔 entrypoint `hangeul-mcp-manage`로 분리한다.
- **이유**: stdio MCP 서버는 시작 직후 stdout을 프로토콜로 사용한다. 관리 명령의 사람용 출력·JSON 진단·업데이트 안내를 같은 entrypoint에 섞으면 클라이언트 초기화와 stdout 순도를 깨기 쉽다. 별도 CLI가 서버 계약을 가장 안전하게 보존한다.
- **managed install substrate**: 클라이언트 설정은 패키지 실행 파일 자체가 아니라 **stable launcher**를 가리킨다. launcher는 user-data의 `current.json`을 읽어 `versions/<version>/` 아래의 **versioned runtime**을 다음 실행부터 dispatch하고, managed state가 없으면 base environment의 `sys.executable -m hangeul_mcp.server`로 안전 폴백한다.
- **업데이트/롤백 경계**: updater는 새 버전을 별도 runtime 디렉터리에 설치·검증한 뒤 `current.json`만 원자적으로 전환한다. 런타임 in-place mutation은 금지한다. rollback은 최소 1개 previous runtime 복구를 목표로 하지만, 손상되었거나 이미 정리된 이전 runtime까지 무제한 복구를 보장하지는 않는다.
- **정직성**: 업데이트 확인은 PyPI JSON 메타데이터를 우선 사용하되, 패키지가 아직 게시되지 않았거나 PyPI 응답이 불능이면 `not_published` 또는 구조화된 오류를 그대로 노출한다. 아직 verifiable publication이 없는데 성공을 추정하지 않는다.
- **클라이언트 설정 원칙**: managed install이 아니면 각 클라이언트는 절대 경로 `sys.executable -m hangeul_mcp.server`를 사용한다. managed install일 때만 stable launcher를 사용해 런타임 전환을 캡슐화한다.
- **extras 문서화 경계**: Windows live 문서는 `com`(pywin32)과 `live`(pyhwpx + numpy/pandas/pyperclip/pillow)가 **별도 optional extra**임을 기준으로 쓴다. `live`가 `com`을 자동 포함한다고 과장하지 않는다.
## D16. `DocumentSpec v1`는 conservative tagged union만 제공한다
- **결정**: `create_document_from_spec` v1은 `blocks_template`(`school.*`)와 `recipe_template`(`official.*`)의 **명시적 tagged union**만 허용한다. 학교 템플릿은 `sections`가 유일한 본문 권위 데이터이며, 공문 템플릿은 기존 recipe chrome만 재사용한다. 현재 shipped contract는 더 보수적으로 `meeting_overview`에 **제목 뒤 최소 1개 paragraph**를 요구하고, `letter_header`/`report_header`/`application_header`는 **단일 heading(title) 블록만** 허용한다.
- **거부 규칙**: mixed-family shape, 템플릿 전용 asset/image payload, alignment/centering hint, `header_footer.columns` 같은 경로 혼합, 중복 `section_id`, 닫히지 않은 nested payload shape는 preview 단계에서 즉시 거절한다.
- **레이아웃 경계**: page setup / header / footer / page number / columns는 최대 1개의 후속 delegate layout batch로만 적용한다. `columns`는 `page_setup.columns`에만 존재하며, base create 단계가 숨은 본문이나 위치를 합성하지 않는다.
- **정직성**: v1은 템플릿 전용 이미지 배치, centered heading, 임의 정렬, 숨은 문안 합성, 미문서 `defaults` shape를 약속하지 않는다. 그런 기능은 별도 substrate·테스트·ADR 없이는 추가하지 않는다.

## D17. OWN text edits and current-document picker stay conservative
- **결정**: OWN 텍스트 치환 경로는 `preview_search_and_replace` / `preview_batch_replace` → `apply_edit_session` → `restore_edit_session`의 **immutable preview + single-session apply + journal/snapshot restore** 제어면으로만 확장한다. 이 세션 계약은 `search_and_replace` / `batch_replace`의 텍스트 치환 경로에만 적용되며, 리치 서식·이미지·live undo를 암묵적으로 포함하지 않는다.
- **이유**: 바이트보존 불변식과 evidence-first 운영을 유지하려면, 우리가 실제로 증명한 OWN 텍스트 치환과 아직 증명하지 못한 delegate/live 편집을 같은 "undo/edit plan" 약속으로 섞으면 안 된다.
- **현재 문서 picker 경계**: `resolve_current_hwp_document()` 후보에는 `picker_title` / `picker_subtitle` / `picker_badges` / `picker_label` 같은 additive metadata만 노출한다. 선택 권위는 계속 `candidate_id`이고, saved `.hwpx`/exact-path/fail-closed 라우팅은 바뀌지 않는다.
- **Windows evidence artifact 경계**: `scripts/windows_live_regression_harness.py`와 `docs/evidence/windows-live-regression-template.json`은 데스크톱 캡처를 정리하는 scaffold일 뿐이다. 이 scaffold 자체가 Windows literal write-safe 증거를 대신하지 않으며, `PENDING_DESKTOP_LIVE_QA.md`의 pending gate를 자동 해제하지 않는다.

## D18. Shell-open 창의 ROT 가시성은 "열기 순서"가 결정한다 — 감지-only 허용, 승격 채널 기각 (Track D 스파이크)
- **실측 메커니즘** (`docs/evidence/shell-rot-spike-probe.json`, 2026-07-15): Explorer/Shell 더블클릭 문서의 automation 가시성은 조건부가 아니라 **열기 시점에 automation-visible 인스턴스가 존재하는지**로 결정된다.
  - **클린 데스크톱**(automation 인스턴스 없음): Shell이 ROT에 등록되지 않는 새 인스턴스를 만들고 120초 내 영구 비가시 (`complete-and-load-desktop-capture-shell.json` 2026-07-14, literal 더블클릭 프로브 2026-07-13).
  - **automation 인스턴스 선존재**: Shell 문서가 그 인스턴스의 **탭으로 합류해 ~1초 내 ROT 가시** — PENDING 문서에 기록된 "Claude Desktop 장기 세션에서는 직접 연 문서가 인식됐다"는 사용자 관측과 클린 캡처 실패의 모순을 해소한다.
- **승격 채널 기각**: `AccessibleObjectFromWindow(OBJID_NATIVEOM)`은 ROT-가시 상태의 창에서도 전부 `E_FAIL`(0x80004005, 포인터 null) — NATIVEOM은 한글의 automation 채널이 아니다. DDE 서비스(`Hwp`/`HwpFrame`/`Hancom`/`HwpApp` × `System`)는 전부 연결 실패 — DDE 승격 경로 없음.
- **감지-only 허용**: Win32 `EnumWindows` 제목 파싱으로 Shell 창의 존재·문서 basename 감지는 실측 가능(정확 창 식별 성공). 이는 **진단/안내 신호로만** 쓸 수 있다(`attach_ladder.window_detected` 류). **쓰기 경로는 `live_attach.py`의 exact-path 사다리(`same_doc` + `_has_active_exact_path`) 미만으로 절대 완화하지 않는다** — 창이 보인다는 것과 그 창에 안전하게 쓸 수 있다는 것은 다른 명제다.
- **결정**: 옵션 (a)+(c) 채택. 코드 변경 없이 현행 유지 + 안내를 메커니즘 기반으로 교정: 손으로 연 문서를 라이브로 다루려면 **automation 인스턴스를 먼저 존재하게 하라**(아무 `open_in_hwp` 호출이면 충분; 이후 Shell로 여는 문서는 자동으로 가시) 또는 `complete_and_load` 하이브리드를 사용하라. generic reconnect의 과거 오판(빈 인스턴스에 `connected:true`)은 다중 인스턴스 resolver(US-067)의 후보 열거 + exact-path 검증으로 이미 구조적으로 방지된다.

## D19. 원본 교체+리로드(P0-B2)의 유일한 허용 조건 — consent + dirty 거부 + 백업 (Track B, 라우트 미출하)
- **위험의 본질**: 리로드는 디스크를 읽으므로 창 안의 **미저장 타이핑을 조용히 폐기**한다. README "자동 저장·닫기·재열기 금지" 불변식의 예외는 아래 4조건이 **모두** 충족된 코드 경로에서만 허용된다.
- **예외 문안(명시적)**: 원본 교체+리로드는 (1) 호출자가 **명시적 consent 파라미터**(기본 거부)를 켰고, (2) apply 직전 COM dirty-프로브가 `{"state":"probed","dirty":false}`를 반환했으며(그 외 모든 상태 — `document_not_attached`/`probe_error`/`connect_failed`/`dirty:true`/unknown — 는 **무조건 거부**), (3) 교체 직전 원본 SHA-256을 기록하고 **백업 파일을 먼저 생성**했고, (4) 응답에 백업 경로+SHA를 반환하는 경우에만 수행할 수 있다.
- **전제 충족 현황 (2026-07-15)**: 전제 1(본 ADR+README 동시 문안) 충족. 전제 2(dirty-프로브) 충족 — `hangeul_core/hwp/dirty_probe.py`(`XHwpDocument.Modified` exact-path 판독, 동일 경로 다중 슬롯은 any-dirty 승리, 실패 전부 fail-closed)를 fake-COM 6종 + 실기기 캡처 4/4(`docs/evidence/dirty-probe-desktop-capture.json`: 클린 창 `dirty:false` → 미저장 타이핑 후 `dirty:true`, 미부착 문서 fail-closed, 디스크 무변경)로 이중 검증. **전제 3(consent 파라미터)·4(백업 의무)는 라우트 구현에 결속되는 조건으로, 라우트와 함께가 아니면 존재할 수 없다.**
- **결정**: replace+reload 라우트는 **이 패스에서 출하하지 않는다**(pending blocker). 휴면 스캐폴딩 `hangeul_core/hwp/live_reload.py`(`reload_if_unreached`, 프로덕션 호출자 0)는 유지하며, 장래 구현은 본 ADR의 4조건 + 실기기 QA 캡처 없이는 어떤 형태로도 연결 금지. dirty-프로브는 resolve/preview의 PURE(COM-free) 계약을 깨지 않도록 **apply 직전 단계 전용**이다(모듈 docstring에 계약 명시).

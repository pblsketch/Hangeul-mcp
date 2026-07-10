# PENDING: 데스크톱 라이브 QA (US-029 / US-053)

> **상태의 진실**: 라이브 셀 채우기(`apply_cells_to_open_hwp`)와 누름틀 원샷 반영(`apply_to_open_hwp`)은
> **코드·순수부 테스트 완료, 실기기(열린 한글 창) 증거 미확보**다. 이 문서가 존재하는 동안
> `docs/prd.json`의 US-029는 complete로 승격하지 않는다.

## 이번 안정화 패스에서 관측한 것 (2026-07-10, 헤드리스 세션 — side-effect-free 경로만)

```json
hwp_status()                       -> {"available": true, "connected": false}
preview_cells_to_open_hwp(fixture) -> {"available": true, "live_available": false, "count": 2, "skipped": []}
targets                            -> 성명 → t2.r2.c3, 직위 → t2.r2.c2
```

- `available:true` = Windows + pywin32 존재(COM *가능* 환경). `connected:false` = 어떤 한글 창에도 접속하지 않았음(부작용 없음 확인).
- `live_available:false` = pyhwpx(extra `live`) 미설치 — 이 세션에서는 apply가 구조화 폴백으로만 동작.
- pure 타깃 해석은 COM 없이 정확히 동작(위 targets). 라이브 apply만 미검증으로 남는다.

## 미확보 증거 (이 문서를 닫는 조건)

[`docs/live-qa-runbook.md`](docs/live-qa-runbook.md) 절차로 다음을 캡처하면 이 문서를 삭제하고
US-029/US-053 상태를 갱신한다:

1. 한글 창에 fixture 사본을 연 상태의 `hwp_status()` — `connected:true`, 버전, 문서 수
2. `apply_cells_to_open_hwp` 의 `applied[]`/`skipped[]`/count (preview target 수와 대조)
3. COM 에러 텍스트(있다면)
4. 채워진 창의 스크린샷 또는 저장본(PII 없는 fixture 사본만)

필요 환경: Windows + 한컴오피스 설치 + `pip install -e ".[live]"` + 대화형 세션(Claude Desktop 등).
pytest 라이브 레인: `$env:HANGEUL_MCP_LIVE=1; python -m pytest tests/test_com.py tests/test_live_resolve.py -q`

## D7 경계 재확인 (best-effort)

`apply_cells_to_open`은 analyze의 전역 표 인덱스 == pyhwpx `get_into_nth_table` 컨트롤 순서를
가정한다. **단일/최상위 표 양식에서만 성립 확인**되었으며 중첩 표·복잡 병합 문서에서는 어긋날 수
있다. 실기기 검증 전까지 라이브 셀 채우기는 best-effort로 표기하고, apply 전 preview 확인을
필수 절차로 유지한다.

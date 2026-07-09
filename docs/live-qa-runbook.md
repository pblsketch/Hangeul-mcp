# Live 데스크톱 QA Runbook (US-052/US-053)

열린 한글 창에 셀 값을 라이브로 채우는 v2 경로의 실기기 검증 절차.
**전제**: Windows + 한글(한컴오피스) 설치 + `pip install -e ".[live]"`(pyhwpx).
헤드리스/CI에서는 이 절차를 실행하지 않는다 — `hwp_status`/`preview_cells_to_open_hwp`만 side-effect-free로 동작한다.

## Fixture / 값 매핑 (PII 없음)

- 파일: `tests/fixtures/sample_form.hwpx` (빈 강사카드, PII 없음)
- 라이브 셀 값 매핑(검증된 해석: 성명 → t2.r2.c3, 직위 → t2.r2.c2):

```json
{"성명": "홍길동", "직위": "교사"}
```

> 참고: `학력`(append)·`은행명`(inline-blank)은 **셀 주소 기반 live 경로의 대상이 아니다**
> (파일모드 `fill_form` 전용). live 셀 채우기는 label:value **empty_cell** 필드만 해석한다.

## 절차 (열린 한글 창 필요)

1. 한글에서 `tests/fixtures/sample_form.hwpx` **사본**을 연다(원본 fixture 오염 금지).
2. `hwp_status()` — 부작용 없음(한글을 띄우지 않음). `available`/`connected` 기록.
3. `preview_cells_to_open_hwp(path, values)` — COM 미호출. `targets`(table/row/col)와 `count` 기록.
4. `apply_cells_to_open_hwp(path, values)` — 열린 창의 셀에 삽입. `applied`/`skipped`/`count` 기록.
   창은 닫히지 않는다. 저장 전이면 한글에서 Ctrl+Z로 복구 가능.
5. pytest 라이브 레인:

```powershell
$env:HANGEUL_MCP_LIVE=1
./.venv/Scripts/python.exe -m pytest tests/test_com.py tests/test_live_resolve.py -q
```

## 캡처할 증거 (US-053 종결 조건)

- `hwp_status` 출력(버전·열린 문서 수)
- preview target 수 vs applied 수
- `applied[]`/`skipped[]` 전체와 COM 에러 텍스트(있다면)
- 결과 스크린샷 또는 저장본(**PII 없는 fixture 사본만**)

증거를 확보하면 `docs/prd.json`의 US-029/US-053 상태를 갱신한다.
확보 전에는 `PENDING_DESKTOP_LIVE_QA.md`가 상태의 진실이다.

## 주의 (D7 — best-effort 경계)

`apply_cells_to_open`은 우리 `analyze`의 전역 표 인덱스와 pyhwpx `get_into_nth_table`
컨트롤 순서가 일치한다고 가정한다. **단일/최상위 표 양식**(강사카드 등)에서 성립하며,
중첩 표·복잡한 병합 문서에서는 어긋날 수 있다. apply 전에 반드시 preview로 target을
확인하고, 의심스러우면 `clear=False`로 실행한다.

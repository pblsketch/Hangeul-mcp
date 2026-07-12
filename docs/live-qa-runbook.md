# Live 데스크톱 QA Runbook (US-052/US-053)

정확한 문서 경로로 식별한 열린 한글 창에 셀 값을 라이브로 채우는 v2 경로의 실기기 검증 절차.
**전제**: Windows + 한글(한컴오피스) 설치 + `pip install -e ".[live]"`(pyhwpx).
헤드리스/CI에서는 이 절차를 실행하지 않는다 — `hwp_status`/`preview_cells_to_open_hwp`만 side-effect-free로 동작한다. **증거 분리**: raw probe/json은 exact-path resolver-path 존재만 증명하고, 실제 라이브 쓰기 안전성은 별도 캡처가 필요하다.

## Fixture / 값 매핑 (PII 없음)

- 파일: `tests/fixtures/sample_form.hwpx` (빈 강사카드, PII 없음)
- 라이브 셀 값 매핑(검증된 해석: 성명 → t2.r2.c3, 직위 → t2.r2.c2):

```json
{"성명": "홍길동", "직위": "교사"}
```

> 기본 attach/write-safe 게이트는 `성명`·`직위`처럼 결과가 단순한 `empty_cell` 값으로 먼저 검증한다.
> 인라인/본문 live 쓰기는 별도 시나리오로 확장하되, exact-path attach 증명 자체는 여기의 단순 셀 케이스로 판정한다.

## 절차 (열린 한글 창 필요, exact-path attach-first)

1. `tests/fixtures/sample_form.hwpx` **사본**을 준비한다(원본 fixture 오염 금지). 손으로 먼저 열었더라도 계속 가능하지만, 이후 판정은 창 존재 여부가 아니라 **정규화한 경로 exact match** 기준으로만 한다.
2. `hwp_status()` — 부작용 없음(한글을 띄우지 않음). `available`/`connected`뿐 아니라 `instances`/`attach_boundary`/`first_call_hint`를 함께 기록.
3. `preview_cells_to_open_hwp(path, values)` — 문서를 쓰지 않는다. `targets`(table/row/col)·`count`와 함께 attach metadata(어떤 resolver path로 exact-path를 잡았는지)를 기록한다.
4. `apply_cells_to_open_hwp(path, values)` — preview에서 exact-path가 확인된 같은 문서에만 삽입한다. `applied`/`skipped`/`count`와 `active_document`/열림 상태(`opened` 또는 `attached_existing`)를 함께 기록한다.
   창은 닫히지 않는다. 저장 전이면 한글에서 Ctrl+Z로 복구 가능.
5. pytest 라이브 레인:

```powershell
$env:HANGEUL_MCP_LIVE=1
./.venv/Scripts/python.exe -m pytest tests/test_com.py tests/test_live_resolve.py -q
```

## 캡처할 증거 (US-053 종결 조건)

- `hwp_status` 출력(`instances`/`attach_boundary` 포함)
- preview의 attach metadata + target 수 vs applied 수
- `applied[]`/`skipped[]` 전체와 COM 에러 텍스트(있다면)
- 결과 스크린샷 또는 저장본(**PII 없는 fixture 사본만**)

raw probe/json과 literal write evidence를 함께 확보하면 `docs/prd.json`의 US-029/US-053 상태를 갱신한다.
확보 전에는 `PENDING_DESKTOP_LIVE_QA.md`가 earlier failed context와 pending QA gate의 상태 진실이다.

## 주의 (D7 — best-effort 경계)

`apply_cells_to_open`의 안전 attach 기준은 **ROT 열거 → 모든 `XHwpDocuments` → 정규화한 `FullName` exact match**뿐이다. 그 다음 셀 쓰기는 우리 `analyze`의 전역 표 인덱스와 pyhwpx `get_into_nth_table` 컨트롤 순서가 일치한다고 가정한다. **단일/최상위 표 양식**(강사카드 등)에서 성립하며, 중첩 표·복잡한 병합 문서에서는 어긋날 수 있다. apply 전에 반드시 preview의 attach metadata와 target을 확인하고, 의심스러우면 `clear=False`로 실행한다.

# Literal Explorer double-click current-document QA — 2026-07-13

## 결론

**이 독립 프로브에서는 FAIL-CLOSED / 쓰기 미실행.** 사용자가 탐색기에서 직접 연 `windows-live-qa-sample.hwpx` 창은 실제로 확인됐지만, 별도 Python 프로세스가 관측한 COM ROT에는 automation 객체가 없었다. 따라서 그 프로세스의 current-document resolver는 후보를 얻지 못했고 preview/apply/read-back으로 진행하지 않았다. 사용자는 Claude Desktop의 장기 실행 MCP 서버에서는 직접 연 문서 인식이 성공했다고 보고했으므로, 이 결과를 일반적 attach 불가능의 증거로 확대하지 않는다.

이 결과는 “한글 창이 없다”는 뜻이 아니다. **창은 있지만 automation-visible COM 객체가 없다**는 뜻이다.

## 실험 대상

- 대상: `E:\github\Hangeul-mcp\build\evidence\windows-live-qa-sample.hwpx`
- PII: 없음 (`tests/fixtures/sample_form.hwpx` 사본)
- 기대 값(실제로 쓰지 않음): `{"성명":"홍길동","직위":"교사"}`
- 한글: Office 2024 / HOffice130
- 프로세스:
  - `Hwp.exe` PID 60568
  - `HwpApi.exe` PID 43280

## 관측

### 1. 창 존재 증명

Win32 창 열거에서 다음 최상위 창을 확인했다.

```text
HWND: 44632988
PID: 60568
class: HwndWrapper[hwp.exe;;de807646-ede0-4ff3-ad7e-71c0c6d29a5a]
title: windows-live-qa-sample.hwpx [E:\github\Hangeul-mcp\build\evidence\] - 한글
```

### 2. ROT 전체 열거

```json
[]
```

즉, `pythoncom.GetRunningObjectTable().EnumRunning()` 결과가 비어 있었다.

### 3. Hangeul-mcp status

```json
{
  "available": true,
  "connected": false,
  "instances": []
}
```

### 4. current-document resolve

```json
{
  "state": "no_open_documents",
  "selection_basis": "none",
  "candidates": [],
  "available": true,
  "ok": true
}
```

대상 경로와 일치하는 후보 수: `0`

### 5. OBJID_NATIVEOM 우회

Hwp/HwpApi 소유 최상위·자식 창 28개에 다음 호출을 수행했다.

```text
AccessibleObjectFromWindow(hwnd, OBJID_NATIVEOM, IID_IDispatch)
OBJID_NATIVEOM = 0xFFFFFFF0
```

모든 창에서:

```text
HRESULT = 0x80004005 (E_FAIL)
pointer = 0x0
IDispatch 성공 = 0건
```

주요 문서 뷰 자식 `HwpMainEditWnd`도 동일하게 실패했다.

## 안전 판정

- exact target proof: 실패
- preview token: 발급 안 됨
- apply: **호출 안 함**
- 파일 저장: **호출 안 함**
- fresh COM read-back: 선행 attach 실패로 실행 불가
- 원본/QA 사본 변경: 없음

현재 구현은 잘못된 문서나 새 브로커에 임의로 붙지 않고 `no_open_documents`로 중단했다. fail-closed 동작은 확인됐다.

## 제품 의미

이 결과만으로 literal Explorer double-click 세션을 현재의 ROT 기반 resolver가 항상 선택·편집할 수 있다고 주장할 수도, 항상 불가능하다고 주장할 수도 없다. Claude Desktop 성공과 독립 프로브 실패가 갈리는 조건을 재현해야 한다. 현재 가장 결정적인 안전 우회는 다음이다.

1. `open_in_hwp(path)`로 automation-visible 세션을 먼저 연다.
2. exact-path preview/apply를 사용한다.
3. 사용자가 손으로 연 창 흐름은 Claude Desktop의 실제 MCP 서버 프로세스 안에서 선행 COM 호출 여부와 ROT 상태를 함께 캡처해 조건부 지원 범위를 확정한다.

## 원자료

- `build/evidence/hwp-status-after-doubleclick.json`
- `build/evidence/windows-live-current-document-raw.json`
- `build/evidence/rot-all-after-doubleclick.json`
- `build/evidence/objid-nativeom-after-doubleclick.json`
- `build/evidence/run_current_document_qa.py`
- `build/evidence/dump_rot_all.py`
- `build/evidence/probe_objid_nativeom.py`

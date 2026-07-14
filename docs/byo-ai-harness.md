# BYO-AI local harness

Hangeul-mcp의 목표는 자체 AI 과금 앱이 아니라 **사용자가 이미 구독하는 AI가 한글 문서를 다룰 수 있게 해 주는 로컬 MCP 하네스**다.

## 원칙

- Hangeul-mcp 서버는 LLM/API를 호출하지 않는다.
- 값과 문안 생성은 Claude, ChatGPT, Codex 등 사용자의 MCP 클라이언트가 맡는다.
- Hangeul-mcp는 로컬 PC에서 HWP/HWPX 문서 분석, 편집, 채우기, 검증, 미리보기를 수행한다.
- 파일 기반 HWPX 모드와 열린 한글 문서 live 모드는 분리한다.
- live 모드는 Windows + 한컴오피스 + optional dependency가 있을 때만 활성화된다.

## 먼저 호출할 도구

AI 클라이언트는 작업 전에 다음 도구를 먼저 호출하는 것이 좋다.

```text
describe_capabilities()
```

이 도구는 현재 PC에서 가능한 기능을 알려준다.

- `file_hwpx`: HWPX 분석, 채우기, 검증
- `delegate_hwpx`: python-hwpx 기반 일반 편집/생성
- `render`: PNG 미리보기
- `live_hwp`: 열린 한글 문서 제어
- `hwp_headless`: 비COM `.hwp` 읽기 adapter gate

## 파일 양식 채우기 흐름

### 기본 addressed fast path

```text
detect_format(path)
scan_pii(path)
inspect_editable_regions(path, compact=true)
→ AI가 채울 모든 값과 addressed edits를 한 번에 생성
complete_addressed_template(path, edits, out_path, verify=true)
verify_fill(out_path, expected)
render_preview(out_path, preview_png)   # optional
```

이 흐름은 **파일 기반 HWPX 모드**다. 열린 한글 창을 건드리지 않고, 검증된 새 출력 파일을 만든 뒤 필요하면 그 결과를 연다.

### 수동 addressed review→apply

```text
inspect_editable_regions(path, compact=true)
preview_addressed_edits(path, edits)
apply_addressed_edits(session_id, out_path)
verify_fill(out_path, expected)
```

반복 텍스트나 구조 주소를 사람이 먼저 audit해야 할 때 쓰는 경로다. whole-template completion을 셀마다 여러 번 호출하는 대신, values/edits를 한 번에 모아 session 또는 one-shot으로 마무리한다.

### 기존 라벨 기반 fill 흐름

```text
detect_format(path)
scan_pii(path)
analyze_form(path)
analyze_formfit(path, values)
fill_form(path, values, out_path, dry_run=true)
fill_form(path, values, out_path, backup=true)
verify_fill(out_path, expected)
render_preview(out_path, preview_png)
```

이 흐름도 HWPX 파일을 직접 다루는 file mode다. 한글 프로그램이 열려 있을 필요는 없다.

## 새 문서 생성 흐름

```text
create_document_from_blocks(blocks, out_path)
validate_hwpx(out_path)
render_preview(out_path, preview_png)
```

본문과 표 내용은 AI 클라이언트가 만든다. Hangeul-mcp는 구조 조립과 검증만 담당한다.

## 열린 한글 문서 live 흐름

```text
hwp_status()
open_in_hwp(path)
apply_to_open_hwp(path, values)          # named field exact-path live apply
preview_small_live_label_cells(path, values)
apply_small_live_label_cells(path, values)    # cell/inline/body exact-path live apply
```

이 경로는 **same-window live editing**이다. 파일 모드 fast path처럼 새 `out_path`를 만드는 것이 아니라, 이미 열린 한글 창을 직접 수정한다.

`preview_small_live_label_cells`는 COM을 호출하지 않는다. 열린 한글 창을 건드리지 않고, 어떤 표/행/열에 값이 들어갈지만 미리 보여준다.

## 현재 문서(pathless) live 흐름 — saved `.hwpx` only

```text
resolve_current_hwp_document()
preview_current_hwp_document(values, candidate_id=None, mode="auto")
apply_to_current_hwp_document(preview_token)
```

현재 문서 pathless UX는 **저장된 `.hwpx` current document만** 지원한다. saved `.hwp` current document는 `preview_requires_hwpx`로 fail-closed 하고, apply는 preview에서 발급한 token만 받는다.

파일 템플릿 completion이 목적이면 live 모드에서 일부만 쓰고 file 모드로 되돌아가기보다, 처음부터 `inspect_editable_regions` → `complete_addressed_template` 또는 `preview_addressed_edits` → `apply_addressed_edits`로 분리하는 것이 안전하다.

## 개인정보 경계

Hangeul-mcp는 자체적으로 외부 AI API를 호출하지 않는다. 다만 사용자의 AI 클라이언트가 문서 내용을 모델에 보낼지는 해당 클라이언트의 설정과 사용 방식에 달려 있다. 민감한 문서는 먼저 `scan_pii`를 호출해 확인한다.

## 파일모드 e2e 증거팩 (재생성)

파일 모드 전체 체인(캐퍼빌리티 → 인식 → PII → dry-run → 채우기 → 검증 → validate → 렌더)의
관측 증거는 커밋하지 않고 로컬에서 재생성한다:

```bash
python scripts/e2e_evidence.py     # 산출물: build/evidence/ (gitignored)
```

- 필수 게이트(analyze/fill/verify/validate, dry-run 무기록, 바이트보존) 실패 시 exit 1.
- `render_preview`는 render extra 미설치 환경에서 `available:false`가 **관측 결과로 기록**될 뿐
  실패로 치지 않는다(렌더 pass로 위장 금지). PNG가 생성되면 시그니처·치수를 함께 기록한다.

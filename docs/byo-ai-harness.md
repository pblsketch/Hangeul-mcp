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

이 흐름은 HWPX 파일을 직접 수정한다. 한글 프로그램이 열려 있을 필요는 없다.

## 새 문서 생성 흐름

```text
create_document_from_blocks(blocks, out_path)
validate_hwpx(out_path)
render_preview(out_path, preview_png)
```

본문과 표 내용은 AI 클라이언트가 만든다. Hangeul-mcp는 구조 조립과 검증만 담당한다.

## 열린 한글 문서 live 셀 채우기 흐름

```text
hwp_status()
preview_cells_to_open_hwp(path, values)
apply_cells_to_open_hwp(path, values)
```

`preview_cells_to_open_hwp`는 COM을 호출하지 않는다. 열린 한글 창을 건드리지 않고, 어떤 표/행/열에 값이 들어갈지만 미리 보여준다.

실제 적용은 사용자가 target을 확인한 뒤 `apply_cells_to_open_hwp`로 수행한다.

## 개인정보 경계

Hangeul-mcp는 자체적으로 외부 AI API를 호출하지 않는다. 다만 사용자의 AI 클라이언트가 문서 내용을 모델에 보낼지는 해당 클라이언트의 설정과 사용 방식에 달려 있다. 민감한 문서는 먼저 `scan_pii`를 호출해 확인한다.

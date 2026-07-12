---
name: hangeul-form-fill
description: "한글(HWPX) 양식을 인식해 AI가 값을 생성·검토 후 서식 보존 채우기(헤드리스) 또는 열린 한글 창에 COM 원샷 반영. .hwpx 양식 채우기, 강사카드/신청서/공문 폼필 요청 시 사용."
---

# Hangeul form fill — review → apply

Hangeul-mcp 도구로 한글 양식을 **인식 → 초안 생성 → 사용자 검토 → 반영**하는 워크플로우.
값 생성은 이 스킬(LLM)의 몫이고, 도구는 인식·채우기·반영만 한다.

## 워크플로우

1. **인식** — `analyze_form(path)` 호출. 반환된 `fields[]`의 각 항목을 본다:
   - `field_id` (권위 키), `label` (별칭), `kind`, `insert_after`, `template`, `para_bullet`.
2. **초안 생성 (kind별 규칙 준수)** — 필드마다 값을 생성하되:
   - `empty_cell` — 값 그대로.
   - `inline_blank` + `insert_after`가 마커(∘/•)면 값에 마커를 **다시 넣지 말 것**.
   - `inline_blank` + `template`이 있으면 (예: `"∘ {} 을 졸업하시고"`) 그 문장에 **문법이 맞도록** 값을 생성.
   - `checkbox` — 선택지 중 하나를 표시(예: □→■/☑).
   - `para_bullet=true`인 셀은 자동 글머리표가 붙으므로 값 앞에 `-`/`∘`를 넣지 말 것.
   - 여러 줄이 필요하면 값에 `\n`을 넣으면 됨(도구가 실제 문단으로 변환).
3. **검토** — 생성한 `{field_id 또는 label: value}` 초안을 사용자에게 **표로 보여주고 승인/수정**을 받는다.
4. **반영** — 승인되면:
   - **헤드리스(권장 기본)**: `fill_form(path, values, out_path)` → 채워진 새 .hwpx 반환. 크로스플랫폼, 안정적.
   - **COM 라이브**: `hwp_status()`의 `connected:false`는 **정상 idle pre-attach 상태**다(아직 어떤 한글 창에도 붙지 않았다는 뜻이지 장애가 아님). 클라이언트는 **exact-path attach-first**로 시작해야 한다: `open_in_hwp(path)` 뒤 `apply_to_open_hwp(path, values)` / `apply_cells_to_open_hwp(path, values)`를 쓰거나, 저장된 `.hwpx` 현재 문서라면 `resolve_current_hwp_document()` → `preview_current_hwp_document(values)` → `apply_to_current_hwp_document(preview_token)`를 사용한다. path 없는 `apply_to_open_hwp(values)`는 이미 제어 중인 active 문서에만 쓰는 legacy 경로다. saved `.hwp` current document는 `preview_requires_hwpx`다. `needs_field_registration=true`면 문서에 누름틀(이름있는 필드)이 없다는 뜻 → 셀 경로를 안내.


## 원칙

- **개인정보**: 주민번호·계좌 등 고정 개인정보는 사용자 프로필로 두고, 강의별 변동 필드만 AI가 생성한다. 민감값은 채팅에 불필요하게 노출하지 않는다.
- **서식 보존**: `fill_form`은 바꾼 필드 외 바이트를 보존한다. 임의로 구조를 바꾸지 않는다.
- **정직한 부분성공**: 반환의 `skipped[]`(사유 포함)를 사용자에게 그대로 전달한다.
- **`.hwp` 입력**: v1은 COM 가용 시 자동 HWPX 변환(Windows+한글). 불가하면 사용자에게 HWPX로 저장하도록 안내.

## 예시 흐름

```
analyze_form("강사카드.hwpx")
 → fields: [{label:"성명",kind:empty_cell,...}, {label:"학력",kind:inline_blank,template:"∘ {} 을 졸업하시고"}, ...]
LLM 초안: {"성명":"홍길동", "학력":"○○대학교 국어교육과", ...}
사용자 검토/승인
fill_form("강사카드.hwpx", 초안, "강사카드_채움.hwpx")   # 또는 open_in_hwp("강사카드.hwpx") 후 apply_to_open_hwp("강사카드.hwpx", 초안)
```

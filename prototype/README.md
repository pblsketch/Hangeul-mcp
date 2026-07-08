# prototype/

Hangeul-mcp 코어 엔진을 만들기 전에 **개념 검증(PoC)** 으로 작성한 동작 스크립트들.
실제 한글 강사카드 양식으로 "양식 인식 → 서식 보존 채우기" 파이프라인이 성립함을 확인했다.
`hangeul_core/`는 이 스크립트들의 로직을 모듈화·테스트화한 것이 된다.

> ⚠️ **개인정보 주의:** 원래 PoC는 실제 개인정보로 테스트했으나, 이 저장소의 스크립트는
> 모두 **더미 데이터**로 치환되어 있다. 실제 데이터가 담긴 결과 파일은 커밋하지 않는다(.gitignore).

## 파일

- `fill_template.py` — 빈 HWPX 양식을 파싱해 셀 주소(rowAddr/colAddr+span)를 매핑하고,
  빈 셀(set)과 `∘` 서술 셀(append)에 값을 채운 뒤 **바이트 보존 재패킹**(mimetype STORED, XML 선언 보존).
- `fix_formatting.py` — 채운 결과의 서식 문제를 교정: **raw 개행 → 문단 분리**, **자동 글머리표 중복 제거**,
  **자간 정규화**(spacing 0 전용 charPr 클론).

## PoC로 검증된 핵심 교훈 (엔진 설계에 반영)

1. 여러 줄 값은 반드시 실제 문단/lineBreak으로. `<hp:t>` 안 raw `\n`은 한글에서 글자 겹침을 유발.
2. `heading type="BULLET"` 칸은 한글이 글머리표를 자동으로 붙이므로 값에 `-`/`∘`를 중복해선 안 됨.
3. XML 재직렬화(ElementTree)는 선언 `standalone="yes"`를 날림 → **바이트 보존 패치**가 필수.
4. 실제 양식은 병합셀 2D 레이아웃 + 문장 중간 빈칸(inline-blank)이 흔함 → 이게 핵심 난이도이자 차별점.

이 교훈들은 `docs/prd.json`의 US-002~US-006 수용 기준(acceptance criteria)으로 고정되어 있다.

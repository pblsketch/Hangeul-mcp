# 형성평가 생성·편집 실기기 테스트

이 문서는 Windows PC의 실제 한글 프로그램에서 `preview_assessment`와
`apply_assessment`를 검증하기 위한 인수 테스트 시나리오다. 테스트 중에는 원본
양식을 직접 수정하지 않고, 출력 전용 디렉터리에 새 번들을 생성한다.

## 1. 사전 준비

1. 한글 프로그램이 설치되어 있고 Hangeul MCP 클라이언트 연결이 정상인지 확인한다.
2. PowerShell에서 출력 전용 디렉터리를 만들고 사용자 환경 변수에 등록한다.

   ```powershell
   $root = Join-Path $env:USERPROFILE "Documents\HangeulMcpAssessmentQA"
   New-Item -ItemType Directory -Force -Path $root | Out-Null
   [Environment]::SetEnvironmentVariable(
     "HANGEUL_MCP_ASSESSMENT_OUTPUT_ROOTS",
     $root,
     "User"
   )
   ```

3. MCP 클라이언트를 완전히 종료한 뒤 다시 실행한다. 출력 경로 허용 목록은 서버가
   시작될 때 한 번 읽으므로 재시작이 필요하다.
4. 테스트 양식은 저장소의 `tests/hwpx template/12_형성평가 양식.hwpx`, 입력값은
   `docs/formative-assessment-sample-spec.json`을 사용한다.
5. 실행 전 출력 디렉터리에 기존 `assessment-*` 폴더가 없는지 기록한다.

## 2. 시나리오

### QA-01 미리보기는 파일을 쓰지 않는다

1. `preview_assessment(template_path, spec)`을 호출한다.
2. 응답의 `ok`가 `true`, `state`가 `preview_ready`인지 확인한다.
3. `session_id`와 `possession_token`을 테스트 기록에만 보관한다.
4. `student`, `teacher`, `answer_key` 각각의 문항별 `before`/`after`를 검토한다.
5. 출력 디렉터리가 실행 전과 동일한지 확인한다.

통과 기준: 세 변형의 계획이 보이고, 출력 파일은 0개다.

### QA-02 승인한 경로에 세 변형을 원자적으로 게시한다

1. QA-01에서 받은 값으로
   `apply_assessment(session_id, possession_token, output_dir)`을 호출한다.
2. `output_dir`에는 사전 준비에서 등록한 경로와 정확히 같은 문자열을 사용한다.
3. 응답의 `ok`가 `true`, `state`가 `applied`, `variant_count`가 `3`인지 확인한다.
4. 생성된 `assessment-<session_id>` 폴더에 아래 네 파일만 있는지 확인한다.

   - `student.hwpx`
   - `teacher.hwpx`
   - `answer-key.hwpx`
   - `manifest.json`

통과 기준: 임시 폴더나 journal/snapshot 파일 없이 위 네 파일만 존재한다.

### QA-03 실제 한글 프로그램에서 결과를 육안 검수한다

세 HWPX를 각각 한글 프로그램으로 열고 다음 항목을 확인한다.

| 검수 항목 | 학생용 | 교사용 | 정답지 |
|---|---|---|---|
| 제목·과목·학년·단원·총점 | 표시 | 표시 | 표시 |
| 세 문항과 배점 | 표시 | 표시 | 표시 |
| 정답·해설·채점 기준 | 노출 없음 | 피드백 중심 | 정답·해설·루브릭 표시 |
| 사용하지 않는 예시 문항 | 삭제 | 삭제 | 삭제 |
| 표, 문단, 페이지 경계 | 깨짐 없음 | 깨짐 없음 | 깨짐 없음 |

통과 기준: 학생용에 정답·해설·오개념·교사용 피드백이 보이지 않고, 세 파일 모두
한글에서 오류 없이 열리며 인쇄 미리보기에서 내용이 잘리지 않는다.

### QA-04 같은 승인을 재실행해도 중복 게시하지 않는다

1. QA-02와 같은 `session_id`, `possession_token`, `output_dir`로 다시 호출한다.
2. 응답의 `state`가 `already_applied`인지 확인한다.
3. 새 번들이 생기지 않고 기존 네 파일의 수정 시각과 SHA-256이 유지되는지 확인한다.

통과 기준: 파일을 다시 쓰지 않고 기존 게시 결과를 반환한다.

### QA-05 등록하지 않은 경로는 쓰기 전에 거부한다

1. 새 미리보기 세션을 만든다.
2. 허용 목록에 없는 빈 디렉터리를 `output_dir`로 지정해 apply를 호출한다.
3. `ok`가 `false`, `error_code`가 `unregistered_output_root`인지 확인한다.

통과 기준: 거부된 디렉터리와 등록된 디렉터리 모두 새 파일이 0개다.

### QA-06 미리보기 뒤 원본이 바뀌면 게시하지 않는다

1. 테스트 양식을 복사한 임시 양식으로 미리보기를 만든다.
2. 임시 양식의 내용을 한 글자 수정하고 저장한다.
3. 기존 세션으로 apply를 호출한다.
4. `ok`가 `false`, `error_code`가 `stale_source`인지 확인한다.

통과 기준: 출력 번들이 생성되지 않는다. 원본 저장소 fixture에는 이 시나리오를
직접 수행하지 않는다.

## 3. 테스트 증거 기록

각 시나리오마다 아래 항목을 남긴다. 토큰, 전체 로컬 경로, 학생 개인정보는 캡처나
공유 로그에 포함하지 않는다.

| 항목 | 기록값 |
|---|---|
| 테스트 일시 | |
| Hangeul MCP 버전 | |
| 한글 프로그램 버전 | |
| 시나리오 ID | |
| 실제 응답 상태·오류 코드 | |
| 생성 파일 수 | |
| 육안 검수 결과 | |
| 스크린샷 파일명 | |
| 최종 판정 | PASS / FAIL |

전체 통과 조건은 QA-01부터 QA-06까지 모두 PASS이고, 학생용 정보 누출 0건,
한글 열기 오류 0건, 허용 경로 밖 쓰기 0건이다.

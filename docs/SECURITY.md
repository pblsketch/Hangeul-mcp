# SECURITY

## 업데이트/설치 trust boundary

- MCP stdio 서버(`hangeul-mcp`)와 관리 CLI(`hangeul-mcp-manage`)는 trust boundary가 다르다.
- `hangeul-mcp`는 stdout을 MCP 프로토콜에만 사용해야 하므로, 설치 안내·업데이트 로그·사람용 메시지는 관리 CLI나 stderr/file only 경로로 보낸다.
- managed install에서는 client config가 package entrypoint가 아니라 stable launcher를 가리킨다. launcher는 user-data state의 `current.json`과 `versions/`만 읽어 다음 실행 runtime을 고른다.
- unmanaged install에서는 launcher 추상화를 가장하지 않고 절대 경로 `sys.executable -m hangeul_mcp.server`를 직접 기록한다.

## Updater source policy

- updater는 PyPI JSON metadata를 primary source로 본다.
- package name, index, download source는 allowlisted 값만 사용한다. 사용자 설정이나 원격 응답이 임의 package/index/url 실행으로 이어지면 안 된다.
- 원격 manifest나 web 응답 본문을 코드/명령으로 실행하지 않는다.
- install/update 호출은 pinned package/version 인수로만 수행하고 shell interpolation을 허용하지 않는다.

## Honest publication/error handling

- 현재 이 저장소는 PyPI publication이 아직 검증되지 않았다. 따라서 `update --check`는 package가 없으면 `not_published`를 반환해야 한다.
- PyPI unavailable, timeout, TLS failure, invalid JSON, 5xx 같은 경우도 성공으로 추정하지 않고 구조화된 오류 상태로 반환한다.
- doctor JSON은 업데이트 확인 실패가 전체 진단을 망치지 않게 분리된 필드로 보고해야 한다.

## Rollback and launcher limits

- rollback은 stable launcher가 가리키는 versioned runtime을 이전 값으로 되돌리는 범위에서만 지원한다.
- 최소 1개 previous runtime 복구는 목표로 하지만, 손상된 runtime 디렉터리·수동 삭제·부분 설치 실패까지 무제한 복구를 보장하지는 않는다.
- updater는 새 runtime을 별도 위치에 설치하고 self-test가 끝난 뒤 `current.json`만 원자적으로 전환해야 한다. 실행 중 runtime in-place mutation은 금지한다.

## Backup sensitivity

- client config backup에는 access token, file path, organization-specific server entries 같은 민감 정보가 들어갈 수 있다.
- backup 파일의 내용은 로그/doctor 출력에 그대로 싣지 않는다.
- backup은 최소 권한(best effort)으로 만들고, 경로만 보고한다.
- backup이 있다는 사실은 복원 수단이지 비밀정보 비식별화를 의미하지 않는다.

## Optional extras guidance

- 문서는 pyproject의 실제 extras만 기준으로 설명한다: `dev`, `com`, `delegate`, `render`, `live`, `hwp-headless`.
- `com`은 Windows COM bridge용 extra이고, `live`는 pyhwpx 기반 live workflow extra다. 둘의 사용 맥락은 겹칠 수 있지만 같은 extra는 아니다.
- extras 관계를 과장하거나, 아직 검증되지 않은 자동 설치/자동 활성화를 약속하지 않는다.

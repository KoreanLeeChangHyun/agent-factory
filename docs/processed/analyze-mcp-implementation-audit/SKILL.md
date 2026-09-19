---
name: mcp-implementation-audit
description: 작업공간 및 MCP 연결 구현 감사을 확인할 때 사용합니다.
document-type: processed
category: analyze
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/mcp-implementation-audit.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 작업공간 및 MCP 연결 구현 감사

- 검토일: 2026-09-05. 독립 검증 역할에서 현재 구현과 실행 근거를 검토했다. 요구사항 번호는 사용자에게 정리한 1–13 항목을 기준으로 한다. 구현 완료와 실제 클라이언트 실행 완료를 구분하며, 다른 문서·계획·보고 기능 변경은 감사 범위에서 제외한다.

<a id="요구사항별-판정"></a>

## 1. 요구사항별 판정

| 번호 | 요구사항 | 구현 및 테스트 근거 | 판정과 범위 |
| --- | --- | --- | --- |
| 1 | 작업공간 생성 | `app/router/account.py`, `app/modules/auth/repository.py`, `app/modules/workspace/schemas.py`, `static/js/workspace.js`; `tests/test_personal_workspaces.py`, `tests/browser/workspace-start.cjs` | 구현 확인. 개인 소유 공간 생성, 이름 검증, CSRF, 반복 생성, 생성 후 선택, 오류 처리. 생성 중 조직 전환의 늦은 응답도 차단한다. 동시 최초 생성의 실제 DB 근거는 `tests/test_personal_workspaces_integration.py` 및 기존 검증 기록이다. |
| 2 | 작업공간 및 화면 복원 | `static/js/workspace.js`의 `selectionStorageKey`, `rememberWorkspaceView`, 목록 대조와 전환 버전 검사; `workspace-start.cjs`, `mcp-onboarding.cjs` | 구현·브라우저 확인. 사용자/조직별 sessionStorage에서 새로고침 복원, 서버 목록에 없는 공간 제외, 시작 복귀 및 account 딥링크 처리. 브라우저 종료 후 영구 복원을 보장하는 저장 방식은 아니다. |
| 3 | 작업 표시줄 아이콘 통합 | `template/workspace/index.html`, `workspace.js`의 `activityPreferenceKey`, 순서/표시 설정; `tests/test_workspace_ui.py`, `workspace-start.cjs` | 구현·브라우저 확인. 단일 작업 표시줄 DOM, 미선택 목록 아이콘, 작업공간별 순서·표시 복원, 전체 숨김 이후 설정 복구. 현재 사용자가 승인한 활동 구성을 유지한다. |
| 4 | VS Code 참고 UI | `static/css/workspace.css`, 셸 템플릿; `workspace-start.cjs` | 구현·브라우저 확인. 헤더, 목록과 시작 화면, 선택 후 활동 화면. 5px 간격·1px 경계·7px 모서리 계산값, 리사이저 키보드 조작, 좁은 화면 가로 넘침 방지 검증. |
| 5 | 용어 및 공통 UI 컨벤션 | `.codex/skills/rule-ui/references/workspace-ui.md`, CSS `--ui-*`, 템플릿 및 MCP 안내; `mcp-onboarding.cjs` | 이번 셸·연결 화면 적용 확인. ‘작업공간’ 용어, 상속 글꼴, 본문/코드 크기, 간격·목록 들여쓰기·스크롤 규칙을 명문화했다. MCP 안내의 불필요한 editor-header 탭이 없음을 검증한다. 기존 모든 기능 화면의 전면 개편은 적용 범위가 아니다. |
| 6 | MCP 확인 전 기능 잠금 | `static/js/mcp-connection.js`의 `display`, `refresh`; `mcp-onboarding.cjs` | 구현·브라우저 확인. pending/reauth_required/상태 조회 오류에서 활동 버튼 disabled 및 sidebar inert. 목록·공간 선택·연결 설정은 가능. 유효한 본인 verified 연결이 있으면 해제된다. 이 UI 잠금과 별개로 서버는 실제 권한을 검증한다. |
| 7 | 공통 MCP 연결 | `app/mcp/scoped.py`, `auth.py`, `server.py`, `app/main.py`, `app/router/mcp_connections.py`, `app/modules/mcp_connection/`; `tests/test_mcp_server.py`, `tests/test_mcp_connections_integration.py` | 구현 확인. 작업공간 scoped Streamable HTTP, 발급/상태/폐기 API, 성공한 MCP 사용으로 확인 상태 기록. 기존 공통 `/mcp/`에서도 토큰의 공간·권한·활성 상태 제한을 적용한다. |
| 8 | 클라이언트 선택 | `static/js/mcp-clients.js`, `mcp-connection.js`; `mcp-onboarding.cjs` | 구현·브라우저 확인. 클라이언트/실행 환경 선택 시 서버 URL은 유지하고 설정·안내를 교체한다. 선택 자체로 verified가 되지 않는다. 전환 시 토큰 표시를 비운다. |
| 9 | 설정 및 설치 안내 생성 | `mcp-clients.js`의 catalog/build; `tests/browser/mcp-clients.cjs` | 13개 클라이언트·18개 환경 계약 PASS. JSON/TOML/YAML, 경로, transport, 인증 참조, 지원되는 설치 URI·등록 명령 생성. VS Code 입력 ID는 발급별 고유하며 기존 이름의 연결도 새로고침 시 복원한다. 계약 테스트는 실제 앱 호환성의 대체 근거가 아니다. |
| 10 | 13개 클라이언트 지원 | `mcp-clients.js`, `.codex/skills/info-platform/references/mcp-clients.md` | 설정 생성은 13개 제공. 실제 실행 완료는 클라이언트와 환경별로 다르며 아래 미검증 목록이 남는다. ‘13개 모두 실제 연결 검증 완료’는 충족하지 않았다. |
| 11 | 복사 및 인증 처리 | `mcp-connection.js`, `mcp-clients.js`, `ConnectionService`; `mcp-onboarding.cjs`, 통합 테스트 | 구현 확인. URL/설정/명령/토큰 복사, 클립보드 실패 시 선택 복사 안내. 서버는 토큰 digest만 저장하고 발급 시 한 번 반환한다. 생성 설정·URI·명령에는 원문 토큰을 넣지 않으며 브라우저 저장소 비저장을 검증한다. 환경변수 이름은 공간·클라이언트·환경별로 분리한다. |
| 12 | 사용자별 연결 및 로컬 프로젝트 절차 | `ConnectionService.status/revoke`, 연결 목록 UI, `mcp-clients.js` 안내, `.codex/skills/rule-platform/references/mcp-connections.md`; 통합 테스트 | 구현 확인. 현재 사용자 소유 연결만 표시·폐기하며 클라이언트명·관찰된 이름·최근 요청·만료/폐기 상태를 표시한다. 타 사용자 조회/폐기 격리 테스트가 있다. 프로젝트 설정에 scoped URL을 배치하거나 전역 설정 범위를 안내한다. 로컬 절대경로 자동 수집·스킬 동기화는 후속 범위다. |
| 13 | 실행 검증 및 버전 제한 기록 | `.codex/skills/info-platform/references/mcp-clients.md`, `.codex/skills/rule-platform/references/mcp-connections.md`, 이 감사 문서, browser 및 Python 테스트 | 실제 연결·도구 조회·도구 호출·재발급의 확인 수준을 각각 기록했다. DB 테스트는 공간·사용자 격리, 폐기·만료, 권한 회수와 비활성 공간 우회를 검증한다. 실제 실행 미검증 환경을 성공으로 합산하지 않는다. |

<a id="실제-실행-범위와-미충족-항목"></a>

## 2. 실제 실행 범위와 미충족 항목

- 상세 버전·임시 산출물 위치는 [클라이언트 검증 기록](../../skills/info-platform/SKILL.md#mcp-clients)을 따른다. VS Code, Continue IDE, Cline IDE, Zed, Codex CLI app-server, Claude Code CLI, OpenCode V1 CLI와 V2 serve에서 실제 클라이언트 연결 및 폐기 후 재발급 연결을 확인했다. Codex app-server에서는 실제 도구 호출까지 성공했다. Gemini는 CLI handshake와 배포 core의 도구 조회·호출을 구분하며, Cline CLI는 배포 core의 실제 loader/manager 조회·호출 검증이다. 두 core 검증을 CLI 대화형 UI 완료로 표시하지 않는다. 모델 요청은 보내지 않았다.

- 다음 항목은 실제 연결 완료로 판정할 수 없다.

- Cursor 3.19.7 및 Kiro 1.0.437: 실제 IDE 실행 후 로그인 화면이 연결 단계 진행을 막았다.
- Antigravity CLI 1.1.27: 공식 바이너리의 전역 설정 인식까지만 확인했다. OAuth/Cloud 프로젝트
  인증 없이 실제 연결은 미검증이다. CLI 목록에서 프로젝트 `.agents/mcp_config.json`만으로는
- 항목이 나오지 않아 해당 프로젝트 설정의 대화형 로드도 미검증이다. IDE 역시 미검증이다.
- Windsurf: 현재 공식 설치 안내의 Devin Desktop 이동·계정 요구를 기록했다. 실제 연결 미검증이다.
- Codex IDE 및 Claude Code IDE: CLI 성공을 IDE 확장 실행 성공으로 확대하지 않는다.

- `verified`는 유효한 토큰으로 성공 요청이 있었음을 뜻한다. 현재 프로세스의 온라인 여부나 모든 모델/도구 기능의 성공을 뜻하지 않는다. 연결 이름과 User-Agent는 표시용이며 인증 근거가 아니다.

- 감사 후 Main 추가 검증: JetBrains PyCharm 2026.2.1 + AI Assistant 262.9437.276에서 모델 계정 로그인 없이 생성 HTTP JSON을 프로젝트 수준으로 적용했다. 실제 UI의 녹색 연결과 도구 목록, 서버 `verified`를 확인했다. 폐기 후 `reauth_required`, 새 토큰을 동일 편집 화면에 적용한 뒤 `verified`로 재연결되었다. 근거는 `/tmp/af-jetbrains-check/{verified,revoked,renewed-status}.json`과 `status-menu.png`이다.

<a id="이번-독립-재실행"></a>

## 3. 이번 독립 재실행

- `node tests/browser/mcp-clients.cjs`: PASS — 13개 클라이언트, 18개 환경 계약.
- `NODE_PATH=/tmp/af-pw/node_modules PLAYWRIGHT_BROWSERS_PATH=/tmp/af-playwright node tests/browser/workspace-start.cjs`: PASS.
- 같은 환경의 `node tests/browser/mcp-onboarding.cjs`: PASS. 구형 VS Code 연결명 입력 ID 복원 테스트 포함.
- `.venv/bin/pytest -q tests/test_workspace_ui.py tests/test_personal_workspaces.py tests/test_mcp_server.py tests/test_mcp_connections_integration.py`:
  일반 focused 11개 PASS. 첫 통합 시도는 이전 임시 PostgreSQL 포트 32769의 연결 거부로
- 준비 단계에서 종료되었다. 현재 격리 DB 포트 32770의 비관리자 `mcp_runner`로 `tests/test_mcp_connections_integration.py`만 다시 실행해 **1 passed (2.19s)**를 확인했다. 최종 결과는 일반 11개 및 실제 PostgreSQL 통합 1개 PASS다.

- 실행 환경의 토큰·세션·설정 원문은 이 문서에 포함하지 않는다. 이번 감사에서는 제품 코드를 수정하지 않았다.

- Main 정리: 실제 클라이언트 검증에 사용한 폐기 가능한 테스트 사용자의 남은 연결 토큰을 모두 폐기하고 격리 IDE 및 테스트 API/DB를 종료했다. 성공 시점의 결과 파일은 유지하며, 해당 `verified` 기록은 현재 가동 중인 테스트 연결을 뜻하지 않는다.

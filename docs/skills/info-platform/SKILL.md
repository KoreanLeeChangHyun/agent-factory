---
name: info-platform
description: Consult maintained Agent Factory platform information, terminology, supported
  MCP client observations, and reporting guidance. Use for factual orientation; use
  design-platform for intended architecture and rule-platform for mandatory behavior.
metadata:
  specification-id: info-platform
  language: ko
  document-type: specification
  category: info
  domain: null
  name: platform
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/info-platform/SKILL.md
    - docs/skills/info-platform/references/agent-reporting.md
    - docs/skills/info-platform/references/mcp-clients.md
    - docs/skills/info-platform/references/platform-map.md
    - docs/specification/info-platform/index.html
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: info-platform
      description: Consult maintained Agent Factory platform information, terminology,
        supported MCP client observations, and reporting guidance. Use for factual
        orientation; use design-platform for intended architecture and rule-platform
        for mandatory behavior.
      metadata:
        specification-id: info-platform
        specification-version: '1'
        projection: ai
        language: en
        counterpart: ../docs/specification/info-platform/index.html
        semantic-revision: '1'
        sync-base-revision: '1'
        modified-at: '2026-09-14T03:40:00+09:00'
---


# 플랫폼 정보

## 1. 적용 범위와 정보 소유권

- 유지관리 사실과 관찰을 조회하는 문서입니다. 제품 동작 변경 권한을 부여하지 않습니다.
- [명세 소유자 지도](#platform-map), [MCP 클라이언트](#mcp-clients), [외부 에이전트 보고](#agent-reporting)를 이 본문에서 확인합니다.

<a id="agent-reporting"></a>

## 2. agent-reporting

- Agent Factory는 MCP 연결과 클라우드 관제 화면을 제공합니다. AI 모델을 호스팅하거나 실행하지 않습니다. 실제 작업은 사용자가 연결한 도구에서 수행합니다.

<a id="관제-원칙"></a>

## 3. 관제 원칙

- Agent Factory는 AI 하네스나 실행 런타임이 아니라 사람이 AI의 행동을 이해하고 관제하기 위한 가시화 계층입니다. 연결된 에이전트가 가진 모델, 기억, 스킬, 도구, 위임 구조와 실행 능력을 공통 규격에 맞춘다는 이유로 축소하거나 대체하지 않습니다. 서로 다른 에이전트의 고유 기능을 유지하면서 관측 가능한 보고와 증거를 연결합니다.

- 관제 화면은 가능한 범위에서 요청과 작업 목표, 계획 요약, 에이전트 및 하위 에이전트의 관계, 도구 호출, 외부 시스템에 준 영향, 문서와 산출물의 변경, 상태 전이, 비용, 오류, 검증과 최종 결과를 사람이 따라가기 쉬운 시간 순서와 계층으로 보여줍니다. 계획 요약은 에이전트가 공개적으로 보고한 근거이며 비공개 내부 추론을 수집하거나 노출한다는 뜻이 아닙니다. 중지, 재시도, 승인 같은 사람의 개입은 명시적인 관제 기능으로 제공할 수 있지만 에이전트 자체 능력의 상한으로 작동해서는 안 됩니다.

- Agent Factory는 수신하지 않은 행동을 추정하거나 만들어내지 않습니다. 에이전트의 자기 보고는 실제 AI 프로세스 또는 외부 효과의 독립적인 증명이 아니며, 도구 영수증, 산출물, 검증 결과처럼 대응하는 증거가 있을 때만 그 증거 범위에서 확인된 행동으로 표시합니다. 따라서 관제 화면은 보고된 사실, 관측된 증거와 추정 또는 오래된 상태를 서로 구분해야 합니다.

- 워크스페이스 관리자 권한으로 MCP 연결을 만들고, 도구에 `agent-factory://reporting/guide` 리소스를 읽도록 안내하세요. 새 관리자 연결에는 `agent:report` 범위가 포함됩니다. 기존 토큰에 권한이 자동 추가되지는 않습니다. 에이전트에게 구성 등록, 작업 등록, 시작·진행·입력 필요·종료와 결과를 보고하도록 지시하면 에이전트 Activity에서 확인할 수 있습니다.

- 기본 사이드바는 전체 보기와 에이전트 계층, 역할, 현재 작업 요약을 보여줍니다. 전체 화면에서는 대기, 진행 중·입력 필요, 최근 완료·실패·취소 작업을 확인합니다. 에이전트를 선택하면 책임·워크스페이스 범위·보고 소유자와 작업 이력이 나타납니다. 작업을 선택하면 보고된 진행률, 시작·종료 시간, 결과와 보고 이력을 확인할 수 있습니다. 연결된 일정 버튼은 실제 일정 항목을 열고, 문서 결과는 해당 문서를 엽니다. 관련 MCP 보고 로그 버튼은 표시된 보고와 함께 저장된 호출 기록만 보여줍니다. 다른 운영 로그를 포괄하는 콘솔은 아닙니다.

- 구성과 이력은 PostgreSQL에 보존되며 접속이 끊겨도 사라지지 않습니다. 새 연결에서도 같은 사용자와 에이전트·작업 ID로 이어서 보고합니다. 다른 사용자는 관리 권한이 있어도 해당 에이전트로 가장하여 보고할 수 없습니다. 상하위 관계는 보고 권한을 위임하지 않습니다. 등록한 사용자 단위의 신원이며 실제 AI 프로세스를 증명하는 기능은 아닙니다.

- 화면은 15초마다 갱신합니다. 최초 등록만 있으면 ‘보고 없음’, 진행 중 5분간 보고가 없으면 ‘보고 오래됨’을 표시합니다. 연결이 조용하다고 완료로 바꾸지 않으며 진행률을 추정하지 않습니다. 시작·종료는 서버가 보고를 받은 시각입니다. 완료 시에도 마지막으로 보고한 진행률을 유지합니다. 통신 오류에는 마지막 수신 자료임을 표시합니다.

- 동일 요청을 같은 키로 다시 보내면 원래 응답만 반환하고 이력을 중복 추가하지 않습니다. 다른 내용에 같은 키를 사용하거나 오래된 수정 번호로 보고하면 충돌을 반환합니다. 완료·실패·취소된 작업은 변경하지 않습니다. 결과는 종료 보고에 함께 담으세요. 다시 시도하려면 새 보고 작업을 만들고 같은 일정 항목을 연결할 수 있습니다. 일정의 상태·기간·담당자·완료 조건은 보고로 변경하지 않습니다. 이력이 연결된 일정 항목의 삭제는 차단됩니다.

- 작업 배정, 일정 연결, 상위 작업은 등록 후 고정됩니다. 잘못 등록한 작업은 취소한 후 새 ID로 등록합니다. 에이전트 구성의 이름·역할·책임·상위 관계는 수정 번호와 함께 갱신할 수 있습니다. 문서는 현재 존재하는 같은 워크스페이스 문서만 연결할 수 있습니다. 외부 HTTP(S) 결과 링크는 보고자가 제공한 참조이며 서버가 내용을 확인하지 않습니다.

- 화면에는 최대 1,000개 구성과 최근 1,000개 작업을 표시하며 초과 시 안내합니다. 작업 UUID로 직접 읽는 MCP/API는 유지됩니다. 이력은 50개씩 이전 보고를 불러옵니다. AI용 상세 계약과 JSON 예시는 [외부 에이전트 보고 안내](../rule-platform/assets/external-agent-reporting.md)에 있습니다.

<a id="mcp-clients"></a>

## 4. mcp-clients

- 공통 서버 URL은 작업공간에 바인딩된다. 브라우저 UI에서 클라이언트를 미리 선택하지 않고, 하나의 ZIP에 지원하는 모든 클라이언트·환경의 설정을 제공한다. 설정 파일을 다운로드하거나 적용한 것만으로 연결 확인 상태가 되지 않는다.

- 구현: `static/js/mcp-clients.js`의 catalog와 build 함수. UI: `static/js/mcp-connection.js`. 토큰 발급 시 클라이언트와 무관한 작업공간 연결 이름을 기록한다. 사용자 입력 이름은 요구하지 않으며 실제 요청의 clientInfo 또는 User-Agent는 별도의 관찰된 클라이언트 이름으로 기록한다. 이것을 인증 근거로 사용하지 않는다.

<a id="지원-범위와-공식-근거"></a>

## 5. 지원 범위와 공식 근거

- 2026-09-05 확인. 설정 생성 지원과 실제 클라이언트 실행 검증은 구분한다.

| 클라이언트 | 제공 환경 | 형식 / 인증 | 공식 근거 |
| --- | --- | --- | --- |
| VS Code · Copilot | IDE | servers/http + secret inputs | https://code.visualstudio.com/docs/agent-customization/mcp-servers |
| Cursor | IDE | mcpServers/url/headers + env 참조, 설치 링크 | https://prod.cursor.com/docs/mcp |
| Windsurf · Cascade | IDE | mcpServers/serverUrl/headers + env 참조 | https://docs.windsurf.com/windsurf/cascade/mcp |
| JetBrains · AI Assistant | IDE | HTTP 추가 화면, mcpServers/url/headers | https://www.jetbrains.com/help/ai-assistant/mcp.html |
| Zed | IDE | context_servers/url/headers | https://zed.dev/docs/ai/mcp |
| Kiro | IDE | mcpServers/url/headers, 승인한 env 참조 | https://kiro.dev/docs/mcp/configuration/ |
| Antigravity | IDE, CLI | mcpServers/serverUrl/headers | https://www.antigravity.google/docs/mcp |
| Cline | IDE 확장, CLI | mcpServers/type=streamableHttp/url/headers | https://github.com/cline/cline/blob/main/docs/mcp/mcp-overview.mdx |
| Continue | IDE 확장 | YAML, streamable-http/requestOptions.headers | https://docs.continue.dev/reference |
| Codex | IDE 확장, CLI | TOML, bearer_token_env_var | https://developers.openai.com/codex/mcp/ |
| Claude Code | IDE 확장, CLI | mcpServers/type=http/url/headers, env 참조 | https://code.claude.com/docs/en/mcp |
| Gemini CLI | CLI | mcpServers/httpUrl/headers | https://geminicli.com/docs/tools/mcp-server/ |
| OpenCode | V1, V2 | V1 mcp, V2 mcp.servers, type=remote | https://opencode.ai/v2/docs/mcp-servers |

<a id="버전-차이와-제한"></a>

## 6. 버전 차이와 제한

- VS Code의 inputs는 Copilot의 VS Code MCP 클라이언트용이며 Agent Host에는 그대로
  전달되지 않는다. 안내 화면에서 이 범위를 명시한다.
- Cursor 원격 MCP는 envFile을 지원하지 않는다. 환경변수는 Cursor 프로세스에 전달한다.
- Windsurf 공식 다운로드와 문서는 Devin Desktop으로 이동했다. 설정 이전 호환성은
  실제 검증 결과에 기록한다. 지원 대상 이름은 Windsurf/Cascade로 유지한다.
- Cline CLI 3.0.61의 `@cline/shared/dist/storage/index.js`에 있는
  `resolveMcpSettingsPath()`는 `~/.cline/data/settings/cline_mcp_settings.json`을 반환한다.
- `CLINE_MCP_SETTINGS_PATH`로 재지정할 수 있다. 과거 `~/.cline/mcp.json` 안내를 사용하지 않는다.
- JetBrains의 HTTP headers 예제는 공식 담당자의 TeamCity MCP 안내에도 있다:
  https://youtrack.jetbrains.com/projects/TW/issues/TW-92756/Support-of-MCP-protocol-to-enable-3rd-party-integrations
- Kiro IDE는 `.kiro/settings/mcp.json`을 사용한다. CLI의 다른 위치와 혼동하지 않는다.
- Antigravity의 현재 공식 문서는 전역 설정을 `~/.gemini/config/mcp_config.json`,
  프로젝트 설정을 `.agents/mcp_config.json`으로 안내한다. 이전 배포본은 IDE의
- Manage MCP Servers → View raw config에서 실제 경로를 확인한다.
- OpenCode V1과 V2의 서로 다른 루트 구조를 사용 환경 선택으로 구분한다.
  기본 선택은 V1이며 V2는 `opencode2`로 실행하는 베타 버전임을 표시한다.

<a id="인증과-재발급"></a>

## 7. 인증과 재발급

- 생성되는 설정·설치 URI·등록 명령에는 발급된 토큰 원문을 넣지 않는다. 지원 클라이언트에서는 환경변수 참조 또는 비밀번호 prompt를 제공한다. 환경변수 이름은 작업공간·클라이언트·실행 환경별로 구분하므로 서로 다른 연결 토큰을 같은 셸에서 사용할 수 있다. 재발급해도 같은 클라이언트의 변수 이름은 유지한다. 직접 헤더 입력을 안내하는 클라이언트에는 PASTE_TOKEN_HERE placeholder를 제공하고, 개인 설정에서만 교체하며 비밀 값이 있는 파일을 커밋하지 않도록 안내한다. 설치 링크는 공식 방식이 확인된 VS Code와 Cursor에서만 표시한다. 등록 명령은 POSIX 셸용으로 표기하고 값에 shell quoting을 적용한다.

- 하나의 개인 토큰은 해당 사용자가 선택한 하나 이상의 클라이언트에 사용할 수 있다. 재발급은 새 토큰으로 사용 중인 각 클라이언트의 입력·환경변수·헤더를 갱신하고 다시 연결한다. 토큰은 발급자 본인의 비밀이며 다른 팀원에게 공유하지 않는다.

<a id="검증"></a>

## 8. 검증

- `node tests/connections/browser/mcp-clients.cjs`: 13개 클라이언트, 18개 환경의 설정 계약,
  JSON 파싱, transport 키, 인증 참조, 설치 링크, 등록 명령.
- `tests/connections/browser/mcp-onboarding.cjs`: 13개 선택 및 환경 전환, URL 불변,
  미연결 기능 잠금, 토큰 비저장, 연결 상태 전환, 새로고침, 폐기, 오류, 모바일.

<a id="실제-실행-검증-2026-09-05"></a>

### 8.1. 실제 실행 검증 (2026-09-05)

- 기존 사용자 계정·설정·프로젝트와 분리한 `/tmp` 환경에서 실행했다. 모델 요청은 보내지 않았으며 각 클라이언트에 별도 연결 토큰을 발급했다. 실제 CLI 또는 app-server 검증과 배포본에 포함된 core 라이브러리 검증은 아래처럼 구분한다.

| 클라이언트 / 버전 | 실제 실행한 경로 | 도구 검증 | 서버 확인 |
| --- | --- | --- | --- |
| VS Code 1.136.1 | 공식 격리 Workbench의 MCP 서버 시작·비밀번호 입력 UI | 8개 도구 발견 | `verified`, `Visual Studio Code/1.136.1` |
| JetBrains PyCharm 2026.2.1 / AI Assistant 262.9437.276 | 공식 IDE와 호환 Marketplace 플러그인을 격리 설정·프로젝트에서 실행. HTTP 추가 화면에 생성 JSON 적용 | 녹색 연결 상태와 Available tools UI 확인. 개별 도구 호출은 하지 않음 | `verified`, `ktor-client` |
| Continue IDE 확장 2.1.0 / VS Code 1.136.1 | 공식 linux-x64 VSIX를 격리 extension host에서 실제 활성화. `CONTINUE_GLOBAL_DIR`와 프로젝트를 `/tmp`로 분리 | 생성된 `.continue/mcpServers/agent-factory.yaml` 자동 로드 및 MCP 성공 요청 확인. 개별 도구 호출은 하지 않음 | `verified`. 관찰된 User-Agent는 `node` |
| Cline IDE 확장 4.1.17 / VS Code 1.136.1 | 공식 VSIX를 격리 extension host에서 활성화하고 MCP Servers UI 확인. 초기 공급자 설정은 로컬 LM Studio 선택만 하고 모델 요청은 보내지 않음 | 생성된 HTTP 설정 자동 로드·성공 MCP 요청 확인. 개별 도구 호출은 하지 않음 | `verified`. `CLINE_DIR`·`CLINE_DATA_DIR` 및 VS Code globalStorage를 모두 임시 경로로 분리 |
| Zed 1.18.1+stable.352 | 공식 실제 IDE, 격리 `--user-data-dir`와 프로젝트에서 사용자 settings 로드 | 생성 `context_servers`/headers로 MCP 연결 확인. 개별 도구 호출은 하지 않음 | `verified`. 모델 로그인·호출 없음 |
| Codex CLI 0.153.4 | 실제 `codex app-server` stdio, `mcpServerStatus/list` 및 `mcpServer/tool/call` | 8개 도구 조회·`workspace_list` 성공. ephemeral thread 생성만 하고 모델 턴은 시작하지 않음 | `verified`, `codex-mcp-client/0.153.4` |
| Claude Code 2.1.220 | 실제 native CLI `mcp list`, 격리 `CLAUDE_CONFIG_DIR` | 연결 검사 성공. 별도 도구 호출은 하지 않음 | `verified`, `claude-code/2.1.220 (sdk-cli)` |
| OpenCode 1.18.29 / V1 | 실제 CLI `mcp list`, 격리 XDG 설정과 프로젝트 | 연결 검사 성공. 별도 도구 호출은 하지 않음 | `verified`, `opencode/1.18.29` |
| OpenCode V2 0.0.0-beta-19151 | 공식 배포 native `opencode2 serve`, 격리 XDG 설정·프로젝트. 실제 서버의 plugin 초기화와 MCP 상태 API 조회 | 생성 설정 로드 후 `connected`. 개별 도구 호출은 하지 않음 | `verified`, `opencode/beta/0.0.0-beta-19151/cli` |
| Gemini CLI 0.58.0 | 실제 CLI `mcp list` 및 동일 배포본 core의 `connectToMcpServer` | CLI는 handshake까지만 확인. core에서 8개 도구 조회·`workspace_list` 성공 | core 호출 후 `verified`. 관찰된 User-Agent는 `node` |
| Cline CLI 3.0.61 / core 0.0.82 | CLI에 포함된 실제 `@cline/core` 설정 loader·MCP manager. CLI UI 실행 검증과는 구분 | 생성 설정 로드·8개 도구 조회·`workspace_list` 성공 | `verified`. 관찰된 User-Agent는 `node` |

- Codex·Claude·OpenCode·Gemini·Cline의 기존 연결 5개를 폐기한 뒤 모두 `reauth_required`임을 확인했다. 새 토큰 발급, 격리 설정 또는 환경변수 갱신, 재연결 후 5개 새 연결 모두 `verified`가 되었다. Codex 및 Gemini/Cline core의 `workspace_list` 재호출도 성공했다. VS Code는 별도 검증에서 동일 서버 이름을 유지하고 새 input ID로 설정을 갱신해 새 비밀번호 입력창과 재연결 성공을 확인했다.

- Gemini의 신뢰하지 않은 프로젝트에서는 실제 CLI가 MCP를 `Disabled`로 표시했다. 임시 프로젝트를 신뢰한 실행에서는 연결되었다. UI 안내에 프로젝트 신뢰 조건을 포함한다.

- 토큰을 제외한 실행 근거는 `/tmp/af-client-inventory/server-status.json`, `revoked-status.json` 및 각 클라이언트 하위 결과 파일에 있다. VS Code 근거는 `/tmp/af-vscode-isolated/client-verified.json`, `renewed-verified.json`과 스크린샷에 있다. 이 임시 경로들은 해당 검증 환경의 산출물이며 영구 배포 파일은 아니다. 다른 IDE 환경의 완료를 설정 생성 테스트만으로 선언하지 않는다.

- OpenCode V2는 `mcp list`가 초기 MCP 연결 전에 빈 목록을 반환한 경우가 있었다. 실제 `serve` 프로세스에서 `/api/plugin/await-activation` 이후 `/api/mcp` 상태를 확인해 `connected`와 서버 `verified`를 입증했다. 기존 토큰 폐기 후 `reauth_required`를 확인하고 새 토큰 환경변수로 서버를 다시 시작해 재연결했다. 실행 근거는 `/tmp/af-opencode2-check/{verified,revoked,renewed-verified}.json`과 `api-mcp.json`이다. CLI 목록만으로 연결 실패 또는 성공을 단정하지 않는다.

- Antigravity CLI 1.1.27은 공식 manifest의 SHA-512를 검증한 바이너리를 격리 컨테이너에서 실행했다. `mcp add`가 쓰는 전역 경로는 `~/.gemini/config/mcp_config.json` 이며 생성한 `serverUrl`/headers 설정을 해당 위치에서 `mcp list`가 인식했다. 이 버전의 `mcp list`는 프로젝트 `.agents/mcp_config.json`만 있을 때 빈 목록을 표시했다. 대화형 실행은 Google OAuth 또는 Google Cloud 프로젝트 로그인을 요구해 실제 연결 검증을 진행하지 못했다. 목록의 `enabled`는 성공 연결 근거가 아니다. 프로젝트 설정의 대화형 로드도 미검증으로 남긴다.

- Continue IDE 실행 근거: `/tmp/af-continue-check/verified.json`, `loaded.png`, `settings.png`. 공식 Marketplace의 플랫폼별 linux-x64 패키지를 사용했으며 모델 제공자 로그인 없이 MCP 연결을 확인했다. Cline IDE 확장 4.1.17 검증은 위 별도 행에 기록한다.

- Continue IDE도 기존 토큰 폐기 후 `reauth_required`, 새 토큰으로 YAML 헤더 갱신 및 실제 IDE 재연결 후 `verified`를 확인했다. 근거는 `/tmp/af-continue-check/revoked.json`, `renewed-verified.json`이다.

- Cline IDE도 별도 토큰으로 연결한 뒤 폐기·재발급·실제 IDE 재연결을 확인했다. 확장 4.1.17의 현재 모드는 `CLINE_DATA_DIR/settings/cline_mcp_settings.json`을 읽었다. 초기 legacy globalStorage 경로만 갱신했을 때는 이전 토큰으로 실패했고, 실제 설정 경로를 갱신한 뒤 재연결되었다. 사용자에게 고정 경로를 추정시키지 않고 확장의 설정 열기 UI를 안내한다. 근거는 `/tmp/af-cline-ide/verified.json`, `revoked.json`, `renewed-verified.json`, `mcp-panel.png`, `renewed-connected.png`이다.

- Zed 실제 IDE에서도 토큰 폐기 후 `reauth_required`, 사용자 settings에 새 토큰 교체, IDE 자동 재연결 후 `verified`를 확인했다. root 검증 근거는 `/tmp/af-gui-check/zed-status.json`, `zed-revoked.json`, `zed-renewed.json`, `zed-connected.png`이다.

<a id="실제-ide의-외부-계정-제한"></a>

### 8.2. 실제 IDE의 외부 계정 제한

- JetBrains는 AI 모델 계정 로그인 없이도 MCP 설정·연결이 가능했다. Project 수준의 설정은 `.ai/mcp/mcp.json`에 저장되었다. 기존 토큰 폐기 후 `reauth_required`, 편집 화면에서 새 토큰으로 JSON 교체·Apply 후 다시 `verified`를 확인했다. 근거: `/tmp/af-jetbrains-check/verified.json`, `revoked.json`, `renewed-status.json`, `status-menu.png`. IDE와 플러그인 로드 버전은 격리 `log/idea.log`에 기록되어 있다.

- Cursor 3.19.7: 공식 IDE 실행은 성공했으나 로그인 overlay가 MCP enable을 막아
  연결 상태는 `pending`이다. 계정 제한을 우회하지 않았으며 실제 연결 완료로 표시하지 않는다.
- Kiro 1.0.437: 공식 IDE 실행은 성공했으나 Sign in만 제공되는 초기 로그인 화면에서
  막혔다. MCP 연결·토큰 실행 검증은 하지 않았다. root의 화면 근거는
- `/tmp/af-gui-check/kiro-current.png`이다.
- Windsurf의 현재 공식 설치 안내는 Devin Desktop으로 이동했으며 Devin 계정
  로그인을 요구한다. 로그인된 테스트 환경이 없어 실제 연결은 미검증이다.
- 이는 공식 설치 조건에 근거한 제한이며, IDE를 실행해 확인한 결과와는 구분한다. 근거: https://docs.devin.ai/desktop/getting-started#onboarding

<a id="platform-map"></a>

## 9. platform-map

- Select only the categories and references touched by the task, then read every selected reference completely.

<a id="information"></a>

## 10. Information

| Concern | Owner |
| --- | --- |
| Supported MCP clients and observed compatibility | [MCP clients](#mcp-clients) |
| Human-facing Agent reporting concepts | [Agent reporting](#agent-reporting) |

<a id="design"></a>

## 11. Design

| Concern | Owner |
| --- | --- |
| Shared cloud composition | [cloud platform](../design-platform/SKILL.md#cloud-platform) |
| Cloud Documents and editor | [cloud documents](../design-platform/SKILL.md#cloud-documents), [document editor](../design-platform/SKILL.md#document-editor) |
| Provider collection and cloud reporting | [cloud integrations](../design-platform/assets/cloud-integrations.md), [cloud reporting](../design-platform/assets/cloud-reporting.md) |
| Organization management and appearance | [organization management](../design-platform/SKILL.md#organization-management), [ThemeProfile](../design-platform/SKILL.md#theme-profiles) |
| Planning import and declarative Workbench | [planning import](../design-platform/SKILL.md#planning-import), [Workbench runtime](../../../docs/processed/process-declarative-workbench-history/SKILL.md) |

<a id="rules"></a>

## 12. Rules

| Concern | Owner |
| --- | --- |
| Identity, authorization, and administration | [authentication](../rule-platform/SKILL.md#authentication), [authorization](../rule-platform/SKILL.md#authorization), [admin](../rule-platform/SKILL.md#admin) |
| Database, security, observability, and operations | [database](../rule-platform/SKILL.md#database), [security](../rule-platform/SKILL.md#security), [observability](../rule-platform/SKILL.md#observability), [operations](../rule-platform/SKILL.md#operations) |
| Workspaces, Documents, search, and migration | [workspaces](../rule-platform/SKILL.md#workspaces), [documents](../rule-platform/SKILL.md#documents), [search](../rule-platform/SKILL.md#search), [migration](../rule-platform/SKILL.md#migration) |
| Agents, workers, and external reporting | [agents](../rule-platform/SKILL.md#agents), [workers](../rule-platform/SKILL.md#workers), [external reporting](../rule-platform/assets/external-agent-reporting.md) |
| Integrations and MCP | [integrations](../rule-platform/SKILL.md#integrations), [MCP](../rule-platform/SKILL.md#mcp), [MCP connections](../rule-platform/SKILL.md#mcp-connections) |

- Apply `$rule-project` for repository placement and verification. Apply `$rule-ui` for Human-facing interface work. Dated material under `docs/processed/` is evidence, not a replacement for these Specifications.

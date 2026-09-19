---
document-type: processed
category: process
domain: null
name: extension-agents-backend-connection-history
language: ko
provenance:
  source-paths:
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/blocks/index.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/metadata.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/context-and-scope.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/decisions-and-open-items.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/evidence-and-findings.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/request-and-goal.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/requirements-and-constraints.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/stakeholders-and-approval.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/work-unit-basis.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/table-of-contents.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/title.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/blocks/evidence/worktree-inspect.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/blocks/index.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/blocks/integration/main-no-ff.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/blocks/logs/agents-backend-verification.log
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/metadata.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/acceptance-and-verification.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/ai-review.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/basis.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/execution-context.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/execution.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/human-review.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/plan.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/report.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/work-definition.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/table-of-contents.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/title.json
  migration-request: run-20260918T153502344625Z-53d84a1e
  authority: 백업 당시 기록입니다. 현재 명세를 대체하거나 새 실행 권한을 부여하지 않습니다.
  renamed-from: docs/processed/process-extension-backup-agents-backend-connection
  classification-request: run-20260918T154226499325Z-8d8d4959
---

# Agents 백엔드 연결 이력

## 1. 기록의 범위

- 같은 주제의 백업 요청·명세·작업 기록과 첨부를 모았습니다. 과거 상태·승인·검사 결과는 해당 시점의 기록이며 현재 검증 결과가 아닙니다.
- 현행 기준은 [현재 프로젝트 명세](../../skills/)에서 확인합니다. 원문·식별자·코드·출처는 원래 언어와 바이트를 보존합니다.
- 첨부는 보존용 원문입니다. 이 문서는 원문을 탐색하기 위한 가공 기록이며, 백업의 오래된 규칙을 활성화하지 않습니다.

## 2. 원본과 이관 위치

| 이전 경로 | 보존 자료 | SHA-256 |
| --- | --- | --- |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/blocks/index.json` | [index.json](assets/intakes/agent-factory-agents-backend-connection/blocks/index.json) | `3ea63b508ced82dd19cdad9fcfc716030e510d405d86b1e516195cb40352a164` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/metadata.json` | [metadata.json](assets/intakes/agent-factory-agents-backend-connection/data/metadata.json) | `62866c6881f6bcbd2ed9a76a9bccaaf6674d24274383b7ff983537da74b73dae` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/context-and-scope.json` | [context-and-scope.json](assets/intakes/agent-factory-agents-backend-connection/data/sections/context-and-scope.json) | `c035b7485e7a1a624327e45673c7ceba83b165673df9b1c166247cf7d2dd929e` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/decisions-and-open-items.json` | [decisions-and-open-items.json](assets/intakes/agent-factory-agents-backend-connection/data/sections/decisions-and-open-items.json) | `10b8be7137d4f90a1ab31685dcdec028d6c090223e20ea5043ffc7317c6249b7` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/evidence-and-findings.json` | [evidence-and-findings.json](assets/intakes/agent-factory-agents-backend-connection/data/sections/evidence-and-findings.json) | `50c9c610eb1ff17dcab7d3a7ffdfa20429eb33946ee652ab90fed7b40da26244` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/request-and-goal.json` | [request-and-goal.json](assets/intakes/agent-factory-agents-backend-connection/data/sections/request-and-goal.json) | `c77a4fe60447a8df08deccdba0747cedb6c22bf965e192e9a7e35288d109e707` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/requirements-and-constraints.json` | [requirements-and-constraints.json](assets/intakes/agent-factory-agents-backend-connection/data/sections/requirements-and-constraints.json) | `319cbb632385754fd174c0ebb8e9b4d7f3ec9723faba5d0bf29a37cf578bb1b3` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/stakeholders-and-approval.json` | [stakeholders-and-approval.json](assets/intakes/agent-factory-agents-backend-connection/data/sections/stakeholders-and-approval.json) | `d1d284ffc8068654afd5f0509054cf31cbb57ad5d46e3ad9011ea61044666891` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/sections/work-unit-basis.json` | [work-unit-basis.json](assets/intakes/agent-factory-agents-backend-connection/data/sections/work-unit-basis.json) | `5b3d2bec79a89625bd5103acc3713083423c36a1eb316c7edb3d4f5921d401b6` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/table-of-contents.json` | [table-of-contents.json](assets/intakes/agent-factory-agents-backend-connection/data/table-of-contents.json) | `8204ed130b52293da77573770409e9e7d5b818c57d66e01f2afe6a2403602a54` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-backend-connection/data/title.json` | [title.json](assets/intakes/agent-factory-agents-backend-connection/data/title.json) | `dfe1b42070d45d55465991bae4fd7703181df1854554422ee1dd38cf85c14417` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/blocks/evidence/worktree-inspect.json` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-agents-backend-connection/blocks/evidence/worktree-inspect.json) | `094ead70fe72ba44bfff4eddd4b2825a710c3bcfaf2a4f171381637010d3ba48` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/blocks/index.json` | [index.json](assets/work-units/agent-factory-agents-backend-connection/blocks/index.json) | `745832c773d55bad5ff065dd3f2159f2c27b65c81cb8d19798acfb6091118549` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/blocks/integration/main-no-ff.json` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-agents-backend-connection/blocks/integration/main-no-ff.json) | `8f475ca4a181be2f901399ff6ac69e3f01494c87498aae6cb16c92d77c39e99a` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/blocks/logs/agents-backend-verification.log` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-agents-backend-connection/blocks/logs/agents-backend-verification.log) | `89c24ef7e654ae27fe177aadf0ebcfa82d8dcdef2b8e7518ed3bfd71d4c90f08` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/metadata.json` | [metadata.json](assets/work-units/agent-factory-agents-backend-connection/data/metadata.json) | `fddc04b5980b642b90e028f5dd33b284286f64d8fdfc8cc2fde9a5cf92c5c132` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/acceptance-and-verification.json` | [acceptance-and-verification.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/acceptance-and-verification.json) | `c11689cb4720a889d33dbf2c18d79400997510629a6d158abbfc7f4aa91ce46f` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/ai-review.json` | [ai-review.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/ai-review.json) | `870d08f90cad6530346539c17db320344b5961217aeadc885fa7251081465772` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/basis.json` | [basis.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/basis.json) | `97d1fa155fc3d03ab3c922f45e453aa4a691667c33a0ec4650ab6a5f9c99047a` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/execution-context.json` | [execution-context.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/execution-context.json) | `0605fd8dd66e9223e9254b06b0f00bb858f51419e12cfa8816e98a5c71f9e2d9` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/execution.json` | [execution.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/execution.json) | `2346d54dd372aa59453112f5fedd5ccce2cb8d8151816091cdccb69304d88d11` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/human-review.json` | [human-review.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/human-review.json) | `c797e05a90a0ab67b1ad3861b387b1adce6270f3836bd91aff22277052f20afc` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/plan.json` | [plan.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/plan.json) | `66bdaa32db91d2dbf684abcf133f17f48f6a9e36add50c99815938356509531f` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/report.json` | [report.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/report.json) | `6da16000453ee807a7ece8254cab065bf2f238be3c2f5e200905611690e69d2a` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/sections/work-definition.json` | [work-definition.json](assets/work-units/agent-factory-agents-backend-connection/data/sections/work-definition.json) | `febcacbfbffb67733856cffcaad1028c9ea6dec7dfc6f80966c7bf5e288d2710` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/table-of-contents.json` | [table-of-contents.json](assets/work-units/agent-factory-agents-backend-connection/data/table-of-contents.json) | `5bc218cc42cda129bafb7e92f81dfdb57b415f59666cca9ef674e617a15174b5` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-backend-connection/data/title.json` | [title.json](assets/work-units/agent-factory-agents-backend-connection/data/title.json) | `d4ecbb2195ed23d75bd1e2b5d405824d9fd1360e598d5bf724e779a2bd1278b1` |

## 3. 본문 기록

### 3.1. context-and-scope

- Context and Scope
- agents Extension Host의 Codex process adapter와 Webview 메시지 허용 목록
- Main Agent 세션의 메시지 전송 control, 사용자 및 assistant 메시지 surface와 세션별 상태
- codex exec --json 신규 실행과 명시적 session id resume
- JSONL 이벤트 parsing, 점진적 렌더링, 완료와 오류 정규화
- 실행 취소, View 재연결과 실행 또는 세션 상태 복원
- linux-x64 Codex CLI payload를 포함하는 플랫폼별 VSIX build
- Codex 인증 부재 및 실행 실패 안내
- 단위, adapter 통합, Extension Host E2E, package contents와 Human 검토
- ../web 코드, Python 백엔드, 서버 또는 API의 복사·실행·변경
- workspace Extension 변경
- Workflow 모드 실행 연결
- 이미지 첨부, model, reasoning 또는 service tier UI
- Windows, macOS와 arm64 VSIX
- Codex CLI 자동 업데이트 또는 첫 실행 네트워크 다운로드
- Codex 인증 생성이나 비밀 저장

### 3.2. decisions-and-open-items

- Decisions and Open Items
- Agents 백엔드 연결을 실제 운영 기능 개발의 우선 범위로 선택한다.
- Human이 선택지 C를 명시적으로 선택했다.
- accepted
- Agents 백엔드 연결의 첫 운영 범위와 세션·스트리밍 깊이 결정 완료
- Web 백엔드 Chat Job과 SSE로 스트리밍, 취소, 재연결 및 세션 복원을 구현한다.
- Human의 후속 Web/VS Code 제품 분리 및 Codex exec JSONL 결정으로 Web 전송 방식은 폐기됐으며 기능 깊이만 DECISION-007로 승계된다.
- superseded
- 백엔드 프로세스 시작 책임과 주소 구성 방식 결정 완료
- 확장 설치 시 ../web 백엔드도 함께 설치하고 확장이 관리한다.
- Human의 후속 설명으로 Web과 VS Code 확장이 별도 제품임이 확인되어 이 해석은 폐기됐다.
- VS Code 확장 전용 백엔드는 ../web과 분리된 독립 설치·실행 경계를 가지며 확장 설치로 함께 제공 가능해야 한다.
- Human이 Web과 VS Code 확장은 다른 제품이라고 명시했다.
- 독립 VS Code 확장 백엔드의 실행 런타임과 Codex 연결 방식 결정 완료
- 플랫폼별 VSIX에 Codex CLI를 포함하고 Extension Host가 codex exec --json 및 resume를 직접 실행한다.
- Human이 선택지 A를 명시적으로 선택했다.
- 첫 Work Unit 플랫폼 범위는 linux-x64로 결정 완료
- 첫 Work Unit은 linux-x64 VSIX와 플랫폼 확장 가능한 패키징 구조를 제공한다.
- resolved
- Windows, macOS와 arm64 플랫폼 패키지는 후속 Intake 및 Work Unit에서 결정한다.
- Workflow 실행 연결과 이미지 첨부 및 model control은 후속 범위다.
- 독립 VS Code 확장은 Codex exec JSONL로 스트리밍, 취소, 재연결과 명시적 세션 복원을 제공한다.
- Human이 기능 깊이 A와 독립 Codex 실행 방식 A를 차례로 선택했다.

### 3.3. evidence-and-findings

- Evidence and Findings
- 어떤 운영 기능을 먼저 구현할까요?
- 기존 Intake의 실행 순서는 Artifact View를 Kanban의 선행 의존성으로 기록했지만, Human이 Agents 백엔드 연결 우선을 선택했다.
- C
- Agents Chat은 현재 Webview 상태에 로컬 세션과 draft만 저장하며 send control, postMessage 및 backend transport가 없다.
- Agent Factory 백엔드는 기본 http://127.0.0.1:7777에서 /chat/jobs 생성, GET SSE 재개 스트림, 취소, agent-session 상태 API를 제공한다.
- 기존 웹 클라이언트는 chat job 생성 후 sequence 기반 SSE 스트림을 읽어 완료까지 복구 가능한 구조를 사용한다.
- 백엔드 CORS 허용 origin은 웹 프런트엔드 주소로 제한되어 있다.
- VS Code Webview가 백엔드에 직접 접속하기보다 Extension Host가 HTTP와 스트림을 소유하고 검증된 postMessage 계약으로 UI와 통신하는 경계가 현재 CSP와 책임 분리에 부합한다.
- Human은 연결 우선순위만 선택했으며 비스트리밍 최소 연결, job 스트리밍, 세션 복원 중 구현 깊이는 아직 결정하지 않았다.
- 백엔드 주소의 구성 방식과 백엔드 프로세스 시작 책임은 아직 결정되지 않았다.
- VS Code Webview API
- Webview는 acquireVsCodeApi().postMessage로 Extension Host에 메시지를 보내고 Extension Host는 onDidReceiveMessage로 이를 처리한다.
- VS Code API 객체는 전역에 노출하지 않아야 한다.
- 이 문서는 Agent Factory 백엔드의 job 및 SSE payload 계약을 정의하지 않는다.
- VS Code Remote Extensions
- 로컬 서비스와 상호작용하는 Webview도 HTML에서 localhost에 직접 접속하는 대신 Extension Host의 메시지 전달 경계를 사용할 수 있다.
- 이 패턴은 Remote Development와 Codespaces에서 Webview와 Extension Host 위치 차이를 다룬다.
- 현재 Work Unit이 VS Code Web까지 지원해야 하는지는 아직 Human이 결정하지 않았다.
- VS Code Contribution Points Configuration
- Extension은 contributes.configuration으로 사용자 설정을 제공하고 workspace.getConfiguration으로 읽을 수 있다.
- machine 또는 machine-overridable scope는 머신별 백엔드 주소와 같이 동기화하면 안 되는 설정에 사용할 수 있다.
- 백엔드 주소 설정의 정확한 키와 기본값은 프로젝트 결정이다.
- 첫 백엔드 연결의 구현 깊이를 어디까지 포함할까요?
- 기존 백엔드의 비동기 job과 sequence 기반 SSE 재개 계약을 직접 사용해 임시 호환 계층 없이 운영 복구를 지원한다.
- A
- 백엔드 프로세스와 주소를 누가 관리할까요?
- 통신과 프로세스 실행 책임을 분리하면 설치와 재시작 위험이 낮다.
- codex exec는 비대화형 실행, JSONL 이벤트 출력과 명시적 session id resume를 지원한다.
- codex app-server는 stdio JSONL을 제공하지만 공식 수동에서 experimental로 분류된다.
- @openai/codex npm 패키지는 플랫폼별 optional dependency 바이너리를 사용하며 현재 설치본 전체 크기는 약 347MB다.
- 독립 VS Code 확장은 ../web API를 복제하기보다 안정된 codex exec JSONL과 resume를 Extension Host에서 직접 어댑트할 수 있다.
- Codex 인증은 VSIX 설치만으로 자동 생성되지 않으며 사용자의 ChatGPT 로그인 또는 지원되는 credential이 필요하다.
- 다중 플랫폼 바이너리를 한 VSIX에 모두 넣으면 크기가 커지므로 플랫폼별 패키징 결정이 필요하다.
- VS Code Publishing Extensions - Platform-specific extensions
- VS Code는 Windows, Linux와 macOS의 아키텍처별 VSIX 패키지를 지원한다.
- 플랫폼별 패키지는 native dependency와 정확한 바이너리만 포함하도록 제어할 수 있다.
- Codex 인증과 Agent Factory 세션 모델은 VS Code 패키징 문서가 정의하지 않는다.
- OpenAI Codex Manual - Developer commands and authentication
- codex exec는 stable 비대화형 명령이며 stdout 또는 JSONL 이벤트와 session resume를 지원한다.
- codex app-server는 experimental이며 로컬 개발·디버깅용으로 변경될 수 있다.
- Codex 로컬 실행은 사용자 로그인, API key 또는 지원되는 access token 인증이 필요하다.
- 공식 수동은 이 사용자 정의 VS Code 확장의 UI와 상태 모델을 정의하지 않는다.
- 독립 VS Code 확장의 실행 백엔드를 어떤 방식으로 제공할까요?
- Web과 VS Code 확장을 분리하고 설치 시 실행 파일을 함께 제공하면서 안정된 Codex exec JSONL 경계를 재사용한다.
- 첫 Work Unit에서 어떤 플랫폼용 자동 설치 패키지를 제공할까요?
- 현재 환경에서 설치와 E2E를 실제 검증하면서 플랫폼별 패키징 구조는 후속 확장이 가능하도록 분리한다.

### 3.4. request-and-goal

- Request and Goal
- linux-x64 VSIX에 호환 Codex CLI 실행 파일이 포함된다.
- Extension Host가 Codex 프로세스와 JSONL parsing을 소유하고 Webview는 검증된 메시지 계약만 사용한다.
- Main Agent 세션의 전송, 응답 스트리밍, 취소, 재연결과 명시적 세션 복원이 검증된다.
- 기존 Explorer, Main 및 Workflow 탭, 세션별 DOM과 draft 상태가 보존된다.
- Web 애플리케이션과 workspace Extension은 변경되거나 런타임 의존성으로 사용되지 않는다.

### 3.5. requirements-and-constraints

- Requirements and Constraints
- agents는 Web 제품과 독립된 Extension Host Codex adapter를 제공한다.
- linux-x64 VSIX는 빌드 시 검증된 Codex CLI payload를 포함하며 설치 후 첫 메시지 실행에 별도 다운로드를 요구하지 않는다.
- Extension Host는 신규 메시지에 codex exec --json을, 연결된 provider session의 후속 메시지에 codex exec resume <session-id> --json을 사용한다.
- Webview와 Extension Host는 허용된 submit, cancel, reconnect 요청 및 state, event, error 응답만 교환한다.
- 각 실제 agent session은 자기 DOM, 메시지, composer, loading과 status surface를 소유한다.
- JSONL sequence와 session id를 사용해 점진적 응답, 취소와 View 재연결 복원을 제공한다.
- 인증 부재, 실행 파일 오류, JSONL 오류와 non-zero exit를 세션별 복구 가능한 오류로 표시한다.
- Webview는 child process, filesystem, 인증 저장소 또는 Codex 실행 파일에 직접 접근하지 않는다.
- Webview 입력과 Extension Host 메시지는 구조, session id, request id와 상태 전이를 검증한다.
- 가짜 fallback session id, pseudo-scope 또는 전역 활성 세션을 만들지 않는다.
- 기존 Explorer, Activity Bar, Main과 Workflow 탭, 키보드 및 접근성 동작을 보존한다.
- ../web과 workspace 파일을 변경하지 않는다.
- Codex 인증 데이터와 prompt 또는 response의 불필요한 원문을 로그에 기록하지 않는다.
- linux-x64 대상 VSIX 설치물에서 포함된 Codex CLI 경로가 resolve되고 별도 다운로드 없이 실행된다.
- Main Agent 세션에서 빈 메시지는 거부되고 유효 메시지는 정확히 한 번 Extension Host로 전달된다.
- 신규 실행과 resume 실행의 JSONL 이벤트가 해당 실제 session id의 DOM에만 렌더링된다.
- 취소는 소유한 Codex child process만 종료하고 다른 세션 실행에 영향을 주지 않는다.
- Webview 재생성 후 실행 또는 완료 상태와 provider session id를 복원한다.
- 인증 부재, malformed JSONL과 process failure가 비밀을 노출하지 않는 세션별 오류로 표시된다.
- 기존 agents npm run check와 핵심 Extension Host E2E 및 linux-x64 VSIX package 검사에 통과한다.

### 3.6. stakeholders-and-approval

- Stakeholders and Approval
- ready Intake 체크포인트 커밋 승인
- ready Work Unit 체크포인트 커밋 승인
- Codex 자동 실행 권한과 실제 Extension Development Host 동작 검토
- 실행 결과 승인 또는 재작업 결정
- main 병합, worktree cleanup, VSIX 설치·배포와 다른 플랫폼 확대 결정

### 3.7. work-unit-basis

- Work Unit Basis
- aligned
- Agents backend 제외 요구사항을 독립 Codex 실행 요구사항으로 대체
- linux-x64 플랫폼별 VSIX와 포함 Codex CLI 설치 경계 추가
- Extension Host message, process, JSONL, cancellation과 session restore 요구사항 추가
- Extension Host Codex process adapter와 Webview message contract
- Main Agent 세션 메시지 전송, JSONL streaming, cancellation, reconnect와 provider session resume
- 세션별 DOM, 메시지, composer, loading, status와 error 상태
- linux-x64 Codex CLI payload resolve 및 platform VSIX packaging
- TDD 단위, fake Codex adapter 통합, Extension Host E2E와 package contents 검증
- ../web 및 workspace 변경
- Workflow 실행 연결
- 이미지 첨부와 model control
- Windows, macOS 및 arm64 패키지
- Codex 인증 생성과 CLI 자동 업데이트
- agents/package.json 및 package lock과 VSIX build configuration
- agents/src Extension Host Codex adapter와 Chat message boundary
- agents/src Chat session message UI
- agents/test unit, integration 및 Extension Host coverage
- linux-x64 installable VSIX와 verification evidence
- VSIX에 포함된 Codex CLI가 별도 다운로드와 ../web 없이 실행된다.
- 신규 및 resume 메시지가 세션별 JSONL stream으로 렌더링된다.
- cancel, reconnect, session restore와 오류 경계가 검증된다.
- 기존 Explorer, Chat navigation, CSP, keyboard와 accessibility 검증이 유지된다.
- TDD red-green-refactor 기록
- npm run check
- fake Codex executable adapter integration tests
- VS Code 1.129.x Extension Host E2E
- vsce package --target linux-x64 및 VSIX contents 검사
- Human 설치, 로그인 상태, streaming, cancel와 reconnect 검토
- HUMAN-REQUEST-001
- HUMAN-CLARIFICATION-001
- INTERNAL-EVIDENCE-001
- INTERNAL-EVIDENCE-002
- WEB-EVIDENCE-001
- WEB-EVIDENCE-002
- WEB-EVIDENCE-004
- WEB-EVIDENCE-005
- DECISION-001
- DECISION-004
- DECISION-005
- DECISION-006
- DECISION-007
- agent-factory-agents-left-region-port

### 3.8. acceptance-and-verification

- Acceptance and Verification
- linux-x64 대상 VSIX 설치물에서 포함된 Codex CLI 경로가 resolve되고 별도 다운로드와 ../web 없이 실행된다.
- Main Agent 세션에서 빈 메시지는 거부되고 유효 메시지는 정확히 한 번 Extension Host로 전달된다.
- 신규 실행과 resume 실행의 JSONL 이벤트가 해당 실제 session id의 DOM에만 렌더링된다.
- 취소는 소유한 Codex child process만 종료하고 다른 세션 실행에 영향을 주지 않는다.
- Webview 재생성 후 실행 또는 완료 상태와 provider session id를 복원한다.
- 인증 부재, malformed JSONL과 process failure가 비밀을 노출하지 않는 세션별 오류로 표시된다.
- 기존 Explorer, Activity Bar, Main 및 Workflow 탭, CSP, keyboard와 accessibility 동작이 유지된다.
- 구현 전에 executable resolver, argv, JSONL parser, cancellation, Webview message와 session ownership의 실패 테스트를 작성한다.
- agent-factory-agents 전용 source, tests, package manifest, lock과 packaging configuration만 구현 범위로 변경한다.
- npm run check, fake Codex integration, 핵심 Extension Host E2E와 linux-x64 VSIX contents 및 bundled executable smoke 검증이 통과한다.
- AI checklist와 AI Review를 완료하고 차단 결함을 해소한다.
- 변경 파일, 명령, 검증 결과와 남은 위험을 등록된 evidence 및 Report에 기록한다.
- 한국어 Human checklist와 linux-x64 VSIX 설치, Codex 인증, streaming, cancel, reconnect 및 session restore 검토 방법을 준비한다.
- platform과 extensionUri 기반 bundled Codex executable resolver 및 unsupported platform 거부를 검증한다.
- 신규 codex exec --json과 codex exec resume <session-id> --json argv가 shell 없이 정확한 인자 배열로 실행됨을 검증한다.
- JSONL partial chunk, malformed line, provider session id, assistant delta, completion과 non-zero exit를 검증한다.
- 각 request와 session이 자기 child process, abort, DOM, loading, status와 error state만 소유함을 검증한다.
- Webview message allowlist가 unknown command, missing id와 invalid state transition을 거부함을 검증한다.
- View 재연결 시 Extension Host snapshot과 vscode state가 실제 session id로 복원됨을 검증한다.
- VS Code 1.129.x Extension Host에서 container, Explorer, Chat send와 fake stream workflow를 검증한다.
- vsce package --target linux-x64 결과가 required source, Codex launcher와 linux-x64 binary만 포함하고 ../web 및 test fixture를 제외함을 검증한다.
- 자동 검증, 패키지 검증과 범위 점검 통과
- pass
- blocks/logs/agents-backend-verification.log

### 3.9. ai-review

- AI Review
- ready Intake와 Work Unit 범위 및 Human 결정 준수
- TDD 순서와 Specification 추적성
- Web과 VS Code 확장 제품 및 런타임 분리
- Extension Host process ownership과 Webview message allowlist
- 실제 session id 기반 Session -> DOM -> State 소유권
- shell 없는 argv 실행, bundled binary path와 child process cancellation 안전성
- JSONL parsing, resume, reconnect, 오류 및 인증 비밀 비노출
- 기존 Explorer, tabs, keyboard, accessibility, CSP와 SVG 경계 보존
- linux-x64 VSIX reproducibility, contents 및 bundled executable 검증
- 단위, integration 및 E2E 검증 통과와 범위 밖 파일 미변경
- AI checklist 전체 점검 통과. Web 또는 workspace 제품 변경, shell 실행, session 간 child·DOM·state 공유, 비밀 stderr 노출, 비 SVG 아이콘과 테스트 fixture 패키징을 발견하지 못했다. 차단 결함 없음.
- pass
- 실제 패키지 경로는 설치된 @openai/codex-linux-x64 vendor/x86_64-unknown-linux-musl/bin/codex와 일치
- Webview command는 chat.ready, chat.submit, chat.cancel만 허용
- Codex stderr는 사용자 오류에 포함하지 않으며 process spawn은 shell:false
- SVG source 검사에서 glyph, pseudo-element, raster icon 없음
- VSIX는 linux-x64 payload와 production source만 포함

### 3.10. basis

- Basis
- 검증된 agent-factory-agents-backend-connection Intake의 WORK-UNIT-BASIS-001

### 3.11. execution-context

- Execution Context
- codex-goal-019f9d6b-06db-74a1-8adf-905d76ff2f16-attempt-1
- work
- ai-review
- report
- running

### 3.12. execution

- Execution
- Web과 독립된 Extension Host Codex backend, 세션별 JSONL 진행·응답·취소·복원 경계와 linux-x64 bundled CLI VSIX 구현 완료
- complete
- 구현 커밋 1576ead30208454c83741cd9dfb645132626ecab
- agents/src/codexAdapter.js: bundled resolver, shell 없는 argv, JSONL parser와 child ownership
- agents/src/chatBackend.js 및 chatView.js: allowlist, session snapshot, send, progress, cancel, reconnect와 resume
- agents/package.json 및 package-lock.json: @openai/codex 0.145.0-linux-x64 pin
- agents/dist/agent-factory-agents-linux-x64.vsix: 최종 설치 패키지

### 3.13. human-review

- Human Review
- agents/dist/agent-factory-agents-linux-x64.vsix를 linux-x64 VS Code에 설치하고 Agent Factory Activity Bar의 Explorer와 Agents View가 열리는지 확인
- 별도 Web 서버와 첫 실행 다운로드 없이 bundled Codex 0.145.0 실행 경계가 준비되는지 확인
- 기존 Codex 로그인 상태에서 Main Agent 세션 메시지를 보내 JSONL 진행 상태와 최종 assistant 응답을 확인
- 같은 세션의 다음 메시지가 provider session id를 사용해 resume되고 다른 실제 session DOM과 섞이지 않는지 확인
- 실행 중 취소가 해당 세션만 중단하고 다른 세션과 Explorer에 영향을 주지 않는지 확인
- View를 닫고 다시 열어 session, messages, 실행 또는 완료 상태와 draft가 복원되는지 확인
- 로그인 부재 또는 실행 실패에서 인증 비밀 없는 오류와 복구 안내가 표시되는지 확인
- Workflow 실행, 이미지 첨부, model control, ../web과 workspace 변경이 없는지 확인
- VSIX 129.69 MB와 LICENSE 경고 및 linux-x64 전용 범위를 수용할지 확인
- 검증 증거와 남은 위험을 확인하고 승인 또는 재작업을 결정한 뒤 main 병합, cleanup, push와 배포는 별도로 결정
- Report와 자동 검증 증거를 확인한 뒤 agents/dist/agent-factory-agents-linux-x64.vsix를 linux-x64 VS Code에 설치한다. 기존 Codex 로그인 상태와 인증이 없는 상태에서 Main Agent 신규 세션 전송, JSONL 진행 표시, 최종 응답, cancel, View reconnect와 provider session resume를 직접 검사한다. 결과 승인 또는 구체적인 재작업을 결정하며 main 병합, worktree cleanup, push, 배포와 후속 플랫폼 확대는 별도로 결정한다.
- Human 검토 대기
- approved

### 3.14. plan

- Plan
- 1. 현재 agents manifest, Chat DOM 소유권, local state와 Extension Host registration을 검사하고 변경 경계를 고정한다.
- 2. Codex executable resolver, new 및 resume argv, JSONL parser, cancellation, process error와 session-state contract의 실패 단위 테스트를 먼저 작성한다.
- 3. Webview submit, cancel, reconnect message allowlist와 세션별 message rendering 및 state restore의 실패 테스트를 먼저 작성한다.
- 4. 최소 Extension Host adapter와 Chat UI 변경으로 단위 및 integration 테스트를 통과시킨다.
- 5. @openai/codex linux-x64 payload를 정확히 pin하고 VSIX package scripts와 .vscodeignore 경계를 구현한다.
- 6. npm run check, fake Codex adapter integration, VS Code Extension Host E2E 및 linux-x64 VSIX contents와 포함 실행 파일 smoke test를 수행한다.
- 7. 보안, 세션 DOM ownership, child process lifecycle, 범위 밖 변경과 package reproducibility를 AI Review한다.
- 8. 검증 증거, Report, 한국어 Human checklist와 설치·인증·streaming·cancel·reconnect 검토 방법을 준비한다.

### 3.15. report

- Report
- 독립 VS Code Agents Extension에 bundled Codex 실행 backend를 구현했다. Main Agent 세션은 신규 exec와 provider session resume, JSONL 진행 및 응답, 세션별 취소, View snapshot 복원과 비밀 없는 오류를 제공한다. linux-x64 VSIX는 별도 Web 서버나 런타임 다운로드 없이 Codex 0.145.0을 포함한다.
- blocks/logs/agents-backend-verification.log
- blocks/evidence/worktree-inspect.json
- 실제 사용자 인증을 소비하는 live Codex turn은 자동 검증에서 실행하지 않았으므로 Human 설치 검토가 필요하다.
- 첫 패키지는 linux-x64 전용이며 Windows, macOS와 arm64는 후속 범위다.
- vsce는 프로젝트 LICENSE 파일 부재 경고를 출력했지만 패키징과 로컬 설치물 생성은 성공했다.
- 최종 VSIX 크기는 129.69 MB이므로 배포 채널의 크기 정책은 배포 승인 전에 별도 확인해야 한다.
- integrated

### 3.16. work-definition

- Work Definition
- agent-factory-agents에 Web과 독립된 Codex 실행 backend를 구현하고 포함 Codex CLI가 있는 linux-x64 VSIX를 제공한다.
- Extension Host Codex process adapter와 Webview message contract
- Main Agent 세션 메시지 전송, JSONL streaming, cancellation, reconnect와 provider session resume
- 세션별 DOM, 메시지, composer, loading, status와 error 상태
- linux-x64 Codex CLI payload resolve 및 platform VSIX packaging
- TDD 단위, fake Codex adapter 통합, Extension Host E2E와 package contents 검증
- ../web 및 workspace 변경
- Workflow 실행 연결
- 이미지 첨부와 model, reasoning 또는 service tier control
- Windows, macOS 및 arm64 패키지
- Codex 인증 생성과 CLI 자동 업데이트 또는 첫 실행 다운로드
- agents/package.json, package-lock.json과 linux-x64 VSIX build configuration
- agents/src Extension Host Codex adapter와 검증된 Chat message boundary
- agents/src Main Agent 세션 message, loading, status와 error UI
- agents/test unit, fake executable integration 및 Extension Host E2E coverage
- linux-x64 installable VSIX와 package contents 및 실행 verification evidence

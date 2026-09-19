---
document-type: processed
category: process
domain: null
name: extension-workspace-history
language: ko
provenance:
  source-paths:
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/blocks/index.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/metadata.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/context-and-scope.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/decisions-and-open-items.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/evidence-and-findings.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/request-and-goal.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/requirements-and-constraints.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/stakeholders-and-approval.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/work-unit-basis.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/table-of-contents.json
  - extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/title.json
  migration-request: run-20260918T153502344625Z-53d84a1e
  authority: 백업 당시 기록입니다. 현재 명세를 대체하거나 새 실행 권한을 부여하지 않습니다.
  renamed-from: docs/processed/process-extension-backup-workspace
  classification-request: run-20260918T154226499325Z-8d8d4959
---

# Workspace 확장 요청 이력

## 1. 기록의 범위

- 같은 주제의 백업 요청·명세·작업 기록과 첨부를 모았습니다. 과거 상태·승인·검사 결과는 해당 시점의 기록이며 현재 검증 결과가 아닙니다.
- 현행 기준은 [현재 프로젝트 명세](../../skills/)에서 확인합니다. 원문·식별자·코드·출처는 원래 언어와 바이트를 보존합니다.
- 첨부는 보존용 원문입니다. 이 문서는 원문을 탐색하기 위한 가공 기록이며, 백업의 오래된 규칙을 활성화하지 않습니다.

## 2. 원본과 이관 위치

| 이전 경로 | 보존 자료 | SHA-256 |
| --- | --- | --- |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/blocks/index.json` | [index.json](assets/intakes/agent-factory-workspace/blocks/index.json) | `3ea63b508ced82dd19cdad9fcfc716030e510d405d86b1e516195cb40352a164` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/metadata.json` | [metadata.json](assets/intakes/agent-factory-workspace/data/metadata.json) | `2beeb09e9dae497b269c1d4cafd78a2847af832bac09e6d9adea11a4aa4452cb` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/context-and-scope.json` | [context-and-scope.json](assets/intakes/agent-factory-workspace/data/sections/context-and-scope.json) | `e97a2e9a554bcfa252623b0414df5ceb4f4214c6c7593f2635a64da445f35063` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/decisions-and-open-items.json` | [decisions-and-open-items.json](assets/intakes/agent-factory-workspace/data/sections/decisions-and-open-items.json) | `08dd3a99851ba568f184bf4db5d74ca9128435095e387476fe8e1039528d43eb` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/evidence-and-findings.json` | [evidence-and-findings.json](assets/intakes/agent-factory-workspace/data/sections/evidence-and-findings.json) | `9a7dda79294b51b1fa6728ad38b03a6f7ef2a8fab9ff6b9192e7022d4ea2a161` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/request-and-goal.json` | [request-and-goal.json](assets/intakes/agent-factory-workspace/data/sections/request-and-goal.json) | `810a1ff98a832ee464d43f46d4b25424d0c49fc37b4b4dd555a604b7c3f89c10` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/requirements-and-constraints.json` | [requirements-and-constraints.json](assets/intakes/agent-factory-workspace/data/sections/requirements-and-constraints.json) | `0e8653baa16fff8cbca7ac2a523861348cabc1a02bdbacd8f22bd07f7916e565` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/stakeholders-and-approval.json` | [stakeholders-and-approval.json](assets/intakes/agent-factory-workspace/data/sections/stakeholders-and-approval.json) | `6a94f2ba0366a6306e905b30255439086fc929a97e6f4aed857e6f2722fcc9da` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/sections/work-unit-basis.json` | [work-unit-basis.json](assets/intakes/agent-factory-workspace/data/sections/work-unit-basis.json) | `774972f066a3f742164bb51536ab526dd99ae9ddbe9e93c68aabbc9388fcafce` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/table-of-contents.json` | [table-of-contents.json](assets/intakes/agent-factory-workspace/data/table-of-contents.json) | `8204ed130b52293da77573770409e9e7d5b818c57d66e01f2afe6a2403602a54` |
| `extension/.backup/.agent-factory/intakes/agent-factory-workspace/data/title.json` | [title.json](assets/intakes/agent-factory-workspace/data/title.json) | `ad63882dc54abb0cd5641c9916b881395f3228ec19c9ef629d58c63d92d77b37` |

## 3. 본문 기록

### 3.1. context-and-scope

- Context and Scope
- VS Code 에디터 영역 Webview 탭
- 탭-선택 헤더-바디 레이아웃
- Dashboard, Design, Kanban, Context, View 탭 껍데기
- 초기 Kanban 및 View 기능
- 현재 단계의 /web 변경
- 현재 단계의 Dashboard, Design, Context 기능 구현

### 3.2. decisions-and-open-items

- Decisions and Open Items
- 산출물 탐색·열람과 Work Unit 실행·상태 관리를 모두 제공한다.
- accepted
- 웹 오른쪽 영역의 구조를 따르되 초기에는 필요한 기능만 구현한다.
- Dashboard, Design, Kanban, Context, View 탭 껍데기를 모두 제공하고 초기 기능은 Kanban과 View만 구현한다.
- VS Code 에디터 영역의 Webview 탭으로 제공한다.
- 확장을 독립적으로 먼저 구현하고 web은 나중에 변경한다.
- Agent Factory 프로젝트 루트는 /home/deus/workspace/agent-factory/vscode-extension이다.
- resolved
- Kanban에서 Work Unit 생성·편집·실행·상태 변경·병합·PR 기능을 모두 제공한다.
- View에서 모든 Agent Factory 산출물을 탐색·열람하고 Work Unit의 실행 로그·체크리스트·승인·재작업·병합·PR 조작을 제공한다.
- 확장 호스트가 로컬 프로젝트의 .agent-factory 조회와 Git 작업 경계를 소유하고 canonical 변경은 Agent Factory 관리자 명령으로 수행하며 Webview는 메시지로만 요청한다.
- 초기 릴리스는 단위 테스트, Agent Factory 관리자 및 Git 통합 테스트, 핵심 VS Code E2E, 접근성·테마·보안 경계 점검과 Human 검토를 통과해야 한다.
- 초기 manifest는 내부 개발용으로 publisher agent-factory와 engines.vscode ^1.129.0을 사용한다.
- /home/deus/workspace/agent-factory/vscode-extension을 독립 Git 저장소로 초기화하고 loop을 기준 브랜치로 사용한다.
- decision-007-kanban-scope
- decision-008-view-scope
- approval-boundary-human-review
- decision-010-verification-scope
- decision-009-data-connection
- main은 사용하지 않고 loop을 작업·체크포인트 기준 브랜치로 사용한다.
- vscode-extension 저장소는 main을 기준 브랜치로 사용하고 확장 구현을 우선한다.
- decision-012-git-execution-context
- decision-013-loop-only

### 3.3. evidence-and-findings

- Evidence and Findings
- vscode-extension/workspace 디렉터리는 존재하지만 파일이 없다.
- web 오른쪽 영역은 Dashboard, Design, Kanban, Context, View 탭과 선택 헤더 및 패널 바디를 가진다.
- 현재 Kanban은 Work Unit 보드를 제공하고 Work Unit 선택은 View 전환 이벤트로 연결된다.
- 상위 agent-factory 디렉터리는 단일 Git 저장소가 아니다.
- 현재 web 구현은 이후 변경 예정이므로 확장 구현 계약으로 고정하지 않는다.
- Webviews - Visual Studio Code Extension UX Guidelines
- 사용자 정의 기능이 VS Code 기본 API를 넘어설 때 Webview를 사용할 수 있다.
- Webview는 테마 적용, 접근성, 적절한 활성화 범위를 따라야 한다.
- Webview API - Visual Studio Code Extension Guide
- Webview와 확장 호스트는 메시지 전달로 통신할 수 있다.
- Webview 상태는 getState와 setState 사용이 권장되며 retainContextWhenHidden보다 오버헤드가 낮다.
- Extension Manifest - Visual Studio Code Extension API
- 모든 VS Code 확장은 루트 package.json manifest를 요구한다.
- name, version, publisher, engines.vscode가 필수다.
- agent-factory-workspace 확장의 핵심 목적은 무엇인가요?
- 읽기 중심으로 시작하면 범위와 위험이 작고 이후 실행 기능 확장이 가능하다.
- C 이긴 해요. web 기준으로 오른쪽 영역임.
- VS Code 확장의 탭 구성을 웹 오른쪽 영역과 어느 수준으로 맞출까요?
- 웹의 오른쪽 영역 기준이라는 요구와 기존 탭 선택 테스트를 직접 보존할 수 있다.
- B
- 초기 릴리스에 어떤 탭을 포함할까요?
- 설계 문서부터 Work Unit 실행·검토까지 연결하면서 Context를 후속 범위로 둘 수 있다.
- 탭 껍데기는 모두 가져오되 기능 구현은 A로 한다.
- 워크스페이스 UI를 VS Code의 어디에 열까요?
- 가로형 탭과 Kanban 레이아웃을 옮길 충분한 공간을 제공한다.
- A
- 이후 웹을 변경할 때 확장과의 관계를 어떻게 정할까요?
- 현재 확장 개발을 진행하면서 VS Code Webview의 보안·상태·테마 요구사항을 독립적으로 적용할 수 있다.
- Agent Factory 프로젝트 루트를 어디로 정할까요?
- 요청한 위치 아래에 canonical Intake를 두면서 단일 진실 공급원을 유지한다.
- Agent Factory 패키지가 여기고 프로젝트 루트는 A가 맞음.
- 초기 Kanban에서 허용할 동작 범위를 어디까지로 정할까요?
- 기록된 실행·상태 관리 목표를 충족하면서 되돌리기 어려운 병합과 PR 작업을 초기 범위에서 분리할 수 있다.
- C
- View 탭의 역할을 어떻게 정할까요?
- 기록된 산출물 탐색·열람 목표와 전체 Work Unit 관리 범위를 함께 충족하며 상세 조작을 View에 집중해 중복 구현을 줄일 수 있다.
- VS Code 확장이 Agent Factory 데이터 및 Git 작업과 연결되는 방식을 어떻게 정할까요?
- 확장을 먼저 독립 구현한다는 기존 결정과 일치하고 Webview에 파일·명령 권한을 주지 않으면서 canonical 변경을 관리자 도구에 집중할 수 있다.
- 초기 릴리스의 성공 기준과 검증 범위를 어디까지로 정할까요?
- 파일 변경과 Git 작업이 포함되어 확장 호스트, Webview 메시지, 관리자 명령 및 Git 경계의 핵심 통합을 자동 검증할 필요가 있다.
- 현재 설치된 VS Code 버전은 1.129.1, commit 8a7abeba6e03ea3af87bfbce9a1b7e48fed567b8, x64이다.
- 검색한 인접 package.json에서 재사용할 VS Code extension publisher 또는 engines.vscode 근거를 찾지 못했다.
- 설치된 단일 VS Code 버전은 더 낮은 버전과의 호환성을 증명하지 않는다.
- 초기 manifest 배포 기준을 어떻게 정할까요?
- 현재 확인된 실행 환경 1.129.1을 정확히 지원하고 Marketplace 계정 또는 검증되지 않은 하위 버전 호환성을 전제하지 않는다.
- loop 브랜치를 어느 저장소의 기준 브랜치로 사용할까요?
- 확정된 프로젝트 루트와 canonical Intake 위치를 보존하면서 Work Unit별 브랜치와 연결 작업공간 규칙을 일관되게 적용할 수 있다.
- loop 브랜치를 사용하고 저장소 위치는 A로 선택
- 체크포인트와 loop의 역할을 어떻게 정할까요?
- 현재 lifecycle 도구 계약을 유지하면서 loop을 통합 대상으로 사용할 수 있다.
- main은 푸시 시 Git Actions에 의해 배포될 수 있으므로 사용하지 않고 loop을 작업 디렉터리 및 기준 브랜치로 사용해야 한다.
- 현재 프로젝트의 기준 브랜치를 어떻게 확정할까요?
- 현재 Agent Factory lifecycle을 추가 도구 변경 없이 진행한다.
- 일단 main으로 진행하고 확장 구현을 우선한다.

### 3.4. request-and-goal

- Request and Goal
- VS Code 1.129.x에서 에디터 영역 Webview 탭이 열리고 Dashboard, Design, Kanban, Context, View 탭 껍데기와 선택 헤더 및 바디가 제공된다.
- Kanban과 View가 확정된 산출물 탐색·열람 및 Work Unit 전체 관리 범위를 제공한다.
- 확장 호스트, Webview 메시지, Agent Factory 관리자 명령 및 Git 경계가 확정된 검증 범위를 통과한다.

### 3.5. requirements-and-constraints

- Requirements and Constraints
- decision-007-kanban-scope
- decision-008-view-scope
- decision-009-data-connection
- decision-011-manifest-profile
- approval-boundary-human-review
- requirement-layout
- requirement-tab-shells
- decision-004-vscode-surface
- requirement-kanban-full-management
- requirement-view-full-management
- decision-003-initial-tab-functionality
- constraint-data-connection-boundary
- decision-010-verification-scope

### 3.6. stakeholders-and-approval

- Stakeholders and Approval
- 요구사항 및 범위 승인
- Work Unit 승인
- 실행 결과 검토
- 병합 및 PR 승격 결정

### 3.7. work-unit-basis

- Work Unit Basis
- gap-accepted-for-work-unit
- project-core@1.0.0
- requirements-specification@1.0.0
- .agent-factory/specifications/project-core
- .agent-factory/specifications/agent-factory-workspace-requirements
- project-core@1.0.0 및 requirements-specification@1.0.0 패키지 작성
- workspace/package.json manifest와 확장 진입점 구현
- VS Code 에디터 영역 Webview 탭 구현
- Dashboard, Design, Kanban, Context, View 탭 shell과 선택 헤더 및 바디 구현
- VS Code 테마·접근성·Webview 보안 기본 경계 적용
- 단위 테스트와 핵심 VS Code E2E shell 검증
- Agent Factory 산출물 조회 구현
- Work Unit 변경·실행·병합·PR 구현
- web 저장소 변경
- Dashboard, Design, Context 기능 구현
- workspace/package.json
- workspace/src
- workspace/test
- 두 Specification 패키지가 owning manager의 전체 검증을 통과한다.
- publisher agent-factory와 engines.vscode ^1.129.0 manifest가 존재한다.
- 확장 명령으로 에디터 영역 Webview가 열리고 5개 탭 shell, 선택 헤더, 바디가 표시된다.
- Dashboard, Design, Context는 기능 없는 shell로 유지된다.
- shell 단위 테스트와 핵심 VS Code E2E가 통과한다.
- Human 검토 체크리스트와 검토 방법이 준비된다.
- Specification manager validate --full
- npm test
- VS Code extension E2E shell test
- 접근성·테마·Webview 보안 경계 점검
- human-request-extension
- desired-outcome-integrated-workspace
- internal-evidence-target-and-web
- web-evidence-vscode-webview-ux
- web-evidence-vscode-webview-api
- web-evidence-vscode-extension-manifest
- decision-001-product-purpose
- decision-002-tab-structure
- decision-003-initial-tab-functionality
- decision-004-vscode-surface
- decision-005-web-relationship
- decision-006-project-root
- decision-010-verification-scope
- decision-011-manifest-profile
- decision-014-main-final
- 확장 호스트의 프로젝트 루트 및 .agent-factory 산출물 탐색
- canonical Intake, Specification, Work Unit 및 Deliverable 읽기 모델
- Webview 메시지 요청·응답 계약
- View의 목록, 선택, 상세 열람, 오류 및 빈 상태
- Kanban 선택에서 View 전환 연결
- 단위·통합·핵심 E2E 및 보안 경계 검증
- canonical JSON 직접 변경
- Work Unit 실행·상태 변경·병합·PR 조작
- workspace/src extension-host artifact reader and message boundary
- workspace/src View UI
- workspace/test artifact fixtures and tests
- View가 지원 산출물을 탐색하고 선택한 canonical 내용을 표시한다.
- Webview는 파일시스템에 직접 접근하지 않고 확장 호스트 메시지만 사용한다.
- 잘못되거나 누락된 산출물은 사용자에게 오류 또는 빈 상태로 표시되며 임의 fallback 데이터를 만들지 않는다.
- 단위·통합·핵심 VS Code E2E가 통과한다.
- artifact fixture integration tests
- VS Code extension E2E View workflow
- Webview filesystem isolation check
- agent-factory-workspace-extension-shell
- decision-008-view-scope
- decision-009-data-connection
- Work Unit Kanban 상태 보드와 선택 흐름
- Agent Factory 관리자 명령 기반 생성·편집·실행·재개·상태 변경
- View의 실행 로그, AI·Human 체크리스트와 승인·재작업 조작
- Human 승인 기반 병합 및 PR 조작
- 확장 호스트의 명령 허용 목록, 인자 검증, 취소, 오류 및 진행 상태
- 단위·관리자/Git 통합·핵심 VS Code E2E·보안 검증
- Human 승인 없는 병합·PR·승격
- workspace/src Kanban UI and Work Unit command boundary
- workspace/src View execution and review controls
- workspace/test manager and Git integration fixtures
- Kanban이 Work Unit 상태를 표시하고 확정된 전체 관리 동작을 제공한다.
- 모든 canonical 변경은 Agent Factory 관리자 명령을 통과한다.
- 병합 및 PR 동작은 Human 결정을 요구하고 승인되지 않은 변경을 수행하지 않는다.
- 단위·관리자/Git 통합·핵심 VS Code E2E·접근성·테마·보안 검증이 통과한다.
- Agent Factory manager integration tests
- Git integration tests
- VS Code extension E2E Kanban and review workflow
- Human approval boundary negative tests
- agent-factory-workspace-artifact-view
- decision-007-kanban-scope

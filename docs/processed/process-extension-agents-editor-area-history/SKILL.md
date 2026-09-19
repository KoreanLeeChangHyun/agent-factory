---
document-type: processed
category: process
domain: null
name: extension-agents-editor-area-history
language: ko
provenance:
  source-paths:
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/blocks/index.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/metadata.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/context-and-scope.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/decisions-and-open-items.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/evidence-and-findings.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/request-and-goal.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/requirements-and-constraints.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/stakeholders-and-approval.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/work-unit-basis.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/table-of-contents.json
  - extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/title.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/blocks/evidence/agents-editor-area-verification.txt
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/blocks/evidence/integration-main-no-ff.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/blocks/evidence/worktree-inspect-before-review.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/blocks/index.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/metadata.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/acceptance-and-verification.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/ai-review.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/basis.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/execution-context.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/execution.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/human-review.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/plan.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/report.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/work-definition.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/table-of-contents.json
  - extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/title.json
  migration-request: run-20260918T153502344625Z-53d84a1e
  authority: 백업 당시 기록입니다. 현재 명세를 대체하거나 새 실행 권한을 부여하지 않습니다.
  renamed-from: docs/processed/process-extension-backup-agents-editor-area
  classification-request: run-20260918T154226499325Z-8d8d4959
---

# Agents 편집 영역 전환 이력

## 1. 기록의 범위

- 같은 주제의 백업 요청·명세·작업 기록과 첨부를 모았습니다. 과거 상태·승인·검사 결과는 해당 시점의 기록이며 현재 검증 결과가 아닙니다.
- 현행 기준은 [현재 프로젝트 명세](../../skills/)에서 확인합니다. 원문·식별자·코드·출처는 원래 언어와 바이트를 보존합니다.
- 첨부는 보존용 원문입니다. 이 문서는 원문을 탐색하기 위한 가공 기록이며, 백업의 오래된 규칙을 활성화하지 않습니다.

## 2. 원본과 이관 위치

| 이전 경로 | 보존 자료 | SHA-256 |
| --- | --- | --- |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/blocks/index.json` | [index.json](assets/intakes/agent-factory-agents-editor-area/blocks/index.json) | `3ea63b508ced82dd19cdad9fcfc716030e510d405d86b1e516195cb40352a164` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/metadata.json` | [metadata.json](assets/intakes/agent-factory-agents-editor-area/data/metadata.json) | `2751e3ca011592f026d03fb9ab1423b8a90c1efcc7f7ff6ec65fdb3e8f183436` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/context-and-scope.json` | [context-and-scope.json](assets/intakes/agent-factory-agents-editor-area/data/sections/context-and-scope.json) | `3546bc541d63820b6547e0ed4cb43e26332d8257c3d928a301ef4a1f40d26467` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/decisions-and-open-items.json` | [decisions-and-open-items.json](assets/intakes/agent-factory-agents-editor-area/data/sections/decisions-and-open-items.json) | `01382cc7acb7a707dc2621e275c3957bd2771309f305d2b7b9777a86fe838412` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/evidence-and-findings.json` | [evidence-and-findings.json](assets/intakes/agent-factory-agents-editor-area/data/sections/evidence-and-findings.json) | `df5fb61997f518dd0274dee0007640f4a0b4fa611b563a7a36267f86b1122d58` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/request-and-goal.json` | [request-and-goal.json](assets/intakes/agent-factory-agents-editor-area/data/sections/request-and-goal.json) | `9bd2212c8c75927a39781da9746ad2cc023d22832df1049c6e7c89216486cff1` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/requirements-and-constraints.json` | [requirements-and-constraints.json](assets/intakes/agent-factory-agents-editor-area/data/sections/requirements-and-constraints.json) | `6083ac840c816f466080778d5f84eaf377a8a63b968849746754792703d84dfe` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/stakeholders-and-approval.json` | [stakeholders-and-approval.json](assets/intakes/agent-factory-agents-editor-area/data/sections/stakeholders-and-approval.json) | `90d8d936f7c8af549a2c6714262ba0944b92c91268b6be662b4309624694fa62` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/sections/work-unit-basis.json` | [work-unit-basis.json](assets/intakes/agent-factory-agents-editor-area/data/sections/work-unit-basis.json) | `5dee962e207554adb5bd32f7b6f40d52e3b61681b181bb5ecda756af375e2545` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/table-of-contents.json` | [table-of-contents.json](assets/intakes/agent-factory-agents-editor-area/data/table-of-contents.json) | `8204ed130b52293da77573770409e9e7d5b818c57d66e01f2afe6a2403602a54` |
| `extension/.backup/.agent-factory/intakes/agent-factory-agents-editor-area/data/title.json` | [title.json](assets/intakes/agent-factory-agents-editor-area/data/title.json) | `9c2e88722a07ce2953eeb463e5b81ebbab36899c4078436dba48066d7576fa6c` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/blocks/evidence/agents-editor-area-verification.txt` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-agents-editor-area/blocks/evidence/agents-editor-area-verification.txt) | `ba0defb25923925e49a21e564553bfbef59f563ad2faf1bba70accc4b7510c1e` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/blocks/evidence/integration-main-no-ff.json` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-agents-editor-area/blocks/evidence/integration-main-no-ff.json) | `0658803bbb1a8dff4612f00cf14f7b353cc3d491762d1676af0669053579a08f` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/blocks/evidence/worktree-inspect-before-review.json` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-agents-editor-area/blocks/evidence/worktree-inspect-before-review.json) | `878aeca9b2ac1cb17fa9711588de3d940f0ca80456d9937f2589cf4633050f0a` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/blocks/index.json` | [index.json](assets/work-units/agent-factory-agents-editor-area/blocks/index.json) | `d6980d65520e790d4bfc4cae4d403bde8241825b4b5d9dd465036522d0e43acb` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/metadata.json` | [metadata.json](assets/work-units/agent-factory-agents-editor-area/data/metadata.json) | `d45144761cf19eca0a8a559bea42a6f0b188c19421f9223f915d855fd905d4ad` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/acceptance-and-verification.json` | [acceptance-and-verification.json](assets/work-units/agent-factory-agents-editor-area/data/sections/acceptance-and-verification.json) | `c5233a2f16222f048d14db1cf4837b4722037e2dffca73a4c2d14548dfbf9e81` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/ai-review.json` | [ai-review.json](assets/work-units/agent-factory-agents-editor-area/data/sections/ai-review.json) | `1e2dfd6ac62e82093f1f8a3b30bc0ed23e4d4799774e7fe40f20d705a5cbdbac` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/basis.json` | [basis.json](assets/work-units/agent-factory-agents-editor-area/data/sections/basis.json) | `6aca98027d64ef30c994a7666bb8d6a7799bc47b18c236a20b93235063a6e519` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/execution-context.json` | [execution-context.json](assets/work-units/agent-factory-agents-editor-area/data/sections/execution-context.json) | `fb6fb0d79c452091854eea8919c5dde0e2dc0445d3f5666ca44d2ff3750520a1` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/execution.json` | [execution.json](assets/work-units/agent-factory-agents-editor-area/data/sections/execution.json) | `e0258d04fa66861f2dd43adc65dd8eaee80e215033ff7ff41f89ab12b0468ab2` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/human-review.json` | [human-review.json](assets/work-units/agent-factory-agents-editor-area/data/sections/human-review.json) | `ccb98706e6f3c094148631a06fe29fa744dbd04b21258a184caf0251e8e2c0c4` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/plan.json` | [plan.json](assets/work-units/agent-factory-agents-editor-area/data/sections/plan.json) | `1d2134c9ae88b8298084b7907ac2dbd1c7007a9fe129053eee195f292bd479a9` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/report.json` | [report.json](assets/work-units/agent-factory-agents-editor-area/data/sections/report.json) | `c3897043d88fd9e137cbe3b60489a2e524047846e1e17a45189dd3f97db8b768` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/sections/work-definition.json` | [work-definition.json](assets/work-units/agent-factory-agents-editor-area/data/sections/work-definition.json) | `708988abd8ef67d961360b6560d56fba28ee6fd2274320cd4beaade1ff370f9d` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/table-of-contents.json` | [table-of-contents.json](assets/work-units/agent-factory-agents-editor-area/data/table-of-contents.json) | `5bc218cc42cda129bafb7e92f81dfdb57b415f59666cca9ef674e617a15174b5` |
| `extension/.backup/.agent-factory/work-units/agent-factory-agents-editor-area/data/title.json` | [title.json](assets/work-units/agent-factory-agents-editor-area/data/title.json) | `9c2e88722a07ce2953eeb463e5b81ebbab36899c4078436dba48066d7576fa6c` |

## 3. 본문 기록

### 3.1. context-and-scope

- Context and Scope
- 현재 Agents manifest는 Activity Bar container 아래 file Explorer Tree View와 Agents Webview View를 등록한다.
- 현재 Agents extension은 registerWebviewViewProvider로 Chat을 Primary Sidebar에 소유한다.
- Workspace extension은 command와 createWebviewPanel을 사용해 editor area의 singleton panel을 연다.
- 공식 VS Code API는 createWebviewPanel을 editor UI로, Webview View를 Sidebar 또는 Panel UI로 구분한다.
- 공식 viewsWelcome contribution은 empty native View에 command links를 제공한다.
- agents/package.json의 activation, commands, views와 viewsWelcome contribution 전환
- agents/src/extension.js의 Agents singleton Webview Panel 및 command lifecycle
- Agent Factory empty launcher View provider와 Agents 및 Workspace command links
- file Explorer runtime registration과 sidebar Chat provider 제거
- 관련 manifest, panel lifecycle, backend ownership, E2E 및 VSIX 테스트
- linux-x64 VSIX 패키징과 내부 설치 검증
- workspace 확장의 Webview UI 또는 Kanban 기능 변경
- Web 애플리케이션 변경
- Agents 채팅 내부 visual hierarchy와 backend message contract 변경
- Windows, macOS와 arm64 패키지
- Human 승인 없는 integration, cleanup, push와 PR promotion

### 3.2. decisions-and-open-items

- Decisions and Open Items
- 이전 선택 C는 후속 Human 피드백과 선택지 B에 의해 대체되었다.
- Human은 선택지 B를 승인했다. 하나의 Agent Factory launcher view에서 Agents와 Workspace singleton editor panel command를 제공하고 file Explorer와 sidebar Chat은 제거한다.
- 실제 설치본에서 launcher 버튼과 editor panel opening을 Human이 검토해야 한다.
- Windows, macOS와 arm64 패키지는 후속 결정이다.
- integration, cleanup, 내부 재배포, push와 PR promotion은 별도 Human 결정이다.
- panel lifecycle 전환 중 controller postMessage binding이 disposed Webview를 참조할 수 있으므로 dispose 및 reopen 회귀 테스트가 필요하다.
- 동일 version 강제 재설치 후 현재 Extension Host에는 이전 코드가 남을 수 있어 Human Reload Window가 필요하다.
- Workspace 확장이 설치되지 않았거나 command가 없으면 launcher의 Workspace action이 실패할 수 있으므로 오류 경계를 검증해야 한다.

### 3.3. evidence-and-findings

- Evidence and Findings
- Agents는 viewsContainers.activitybar 아래 Explorer Tree View와 Agents Webview View를 함께 기여하고 registerWebviewViewProvider로 채팅을 Primary Sidebar에 소유한다.
- Workspace는 agentFactoryWorkspace.open command가 createWebviewPanel을 ViewColumn.Active에 생성해 editor area의 단일 panel을 열고 기존 panel은 reveal한다.
- Agents E2E는 sidebar container와 agentFactoryAgents.chat.focus command를 직접 열도록 고정돼 있어 전환 시 manifest, activation, extension lifecycle과 E2E 계약을 함께 변경해야 한다.
- Agents chat을 editor area로 이동하려면 기존 Webview View registration을 Webview Panel command 및 panel lifecycle로 교체해야 한다.
- Explorer를 Sidebar에 유지할지와 Agents editor opener를 어디에 노출할지는 Human 결정이 필요하다.
- VS Code Webview API
- createWebviewPanel로 만든 Webview Panel은 VS Code에서 별도 editor로 표시된다.
- Webview View는 Sidebar 또는 Panel 영역의 view로 렌더링된다.
- Webview Panel은 reveal을 통해 기존 editor tab을 전면으로 가져올 수 있다.
- 프로젝트 고유 command id와 Explorer 유지 여부는 공식 API 문서가 결정하지 않는다.
- VS Code UX Guidelines: Views
- View Container는 Activity Bar 또는 Panel에서 Views를 소유한다.
- 공식 UX 지침은 Activity Bar Item을 editor Webview를 여는 용도로 사용하지 말라고 명시한다.
- View toolbar의 command action은 지원되는 발견 가능성 경계다.
- toolbar action 사용 여부와 위치는 프로젝트 UX 결정이다.
- Explorer를 유지하면서 Agents editor panel을 여는 진입점을 어디에 둘지 결정
- Explorer는 기존 native 책임을 유지하고, Explorer title action과 Command Palette가 동일한 singleton editor command를 호출하면 공식 VS Code UX 경계를 지키면서 발견 가능성과 유지보수성을 함께 확보한다.
- C
- A: Explorer Sidebar는 유지하고 title action 및 Command Palette에서 singleton Agents editor panel을 연다.
- B: Explorer Sidebar는 유지하고 Command Palette에서만 Agents editor panel을 연다.
- C: Activity Bar와 Explorer까지 제거하고 Agents editor command만 유지한다.
- 기존 선택 C를 유지할지, Agents와 Workspace를 여는 launcher surface로 변경할지 결정
- Human의 최신 피드백을 직접 반영하면서 file Explorer와 sidebar Chat은 제거하고, 하나의 launcher view가 두 editor panel command만 제공하면 중앙 작업 영역 소유권과 두 확장의 진입점을 분리할 수 있다.
- B
- A: 기존 C 유지 — Activity Bar와 Explorer를 제거하고 Agents와 Workspace를 각 Command Palette에서 연다.
- B: 선택 변경 — 하나의 Agent Factory launcher view에서 Agents와 Workspace editor panel을 연다. file Explorer와 sidebar Chat은 제거한다.
- C: 중앙 Home editor panel에서 Agents와 Workspace를 선택해 연다. Activity Bar와 Explorer는 제거한다.
- VS Code Contribution Points: viewsWelcome
- viewsWelcome은 empty Tree View에 native welcome content를 제공한다.
- 독립된 command link는 button으로 표시할 수 있고 지정 command를 실행한다.
- Welcome View를 사용하면 file tree item을 command button으로 오용하거나 별도 launcher Webview를 만들 필요가 없다.
- empty TreeDataProvider registration과 exact command ids는 구현 및 테스트에서 검증해야 한다.

### 3.4. request-and-goal

- Request and Goal
- Agent Factory Activity Bar container에는 하나의 native launcher View만 표시된다.
- launcher View는 Agents와 Workspace를 여는 command links를 제공한다.
- Agents command는 editor area에 singleton panel을 열고 재호출 시 같은 panel을 reveal한다.
- Workspace command는 기존 Workspace editor panel을 연다.
- file Explorer와 sidebar Agents Chat View는 표시되지 않는다.
- 기존 Agents session, draft, submit, cancel, reconnect, CSP와 Codex adapter 동작을 보존한다.
- 단위, 통합, Extension Host E2E, linux-x64 VSIX 검증이 통과한다.

### 3.5. requirements-and-constraints

- Requirements and Constraints
- Agent Factory Activity Bar container에는 하나의 native launcher View만 제공해야 한다.
- launcher View는 Agents와 Workspace를 여는 두 command links를 제공해야 한다.
- Agents open command는 editor area에 singleton Agents Webview panel을 열고 재호출 시 reveal해야 한다.
- Workspace command link는 설치된 Workspace 확장의 기존 open command를 실행해야 한다.
- file Explorer Tree View와 sidebar Agents Chat Webview View를 제거해야 한다.
- Agents panel은 기존 Main 및 Workflow, 세션별 DOM, draft, submit, cancel, reconnect와 Codex process ownership을 보존해야 한다.
- launcher는 별도 custom Webview를 추가하지 않고 empty native View와 viewsWelcome command links를 사용한다.
- Workspace 소스와 Web 애플리케이션 소스는 변경하지 않는다.
- 현재 chat.ready, chat.submit, chat.cancel message allowlist와 Codex adapter 계약을 변경하지 않는다.
- 기존 Agent Factory Activity Bar SVG icon은 유지한다.
- agents package 밖의 다른 Work Unit 미커밋 파일을 변경하거나 staging하지 않는다.
- manifest에는 하나의 Activity Bar container, 하나의 launcher View, Agents open command와 viewsWelcome command links가 존재한다.
- manifest에는 기존 file Explorer View와 sidebar Agents Chat Webview View가 존재하지 않는다.
- Agents open command는 createWebviewPanel을 editor area에 생성하고 재호출 시 동일 panel을 reveal한다.
- panel dispose 시 Webview binding, controller와 runner가 정리되고 다음 open에서 정상 재생성된다.
- Workspace command link는 agentFactoryWorkspace.open을 실행한다.
- 기존 chat render, submit, cancel, reconnect, draft, CSP, session ownership과 Codex adapter 테스트가 통과한다.
- npm run check, npm run test:e2e, package:linux-x64와 verify:vsix가 통과한다.

### 3.6. stakeholders-and-approval

- Stakeholders and Approval
- 내부 배포된 Linux x64 VS Code Agent Factory 확장을 사용하는 Human
- Agents와 Workspace 확장 유지보수 및 검증 담당자
- launcher surface와 editor area ownership
- Human review 승인
- integration, cleanup, 내부 재배포, push와 PR promotion
- Human은 최종 선택 B로 하나의 Agent Factory launcher View에서 Agents와 Workspace editor panel을 열도록 결정했다.
- 앞선 Activity Bar 및 Explorer 전체 제거 선택 C는 후속 선택 B에 의해 대체됐다.
- Intake checkpoint, Work Unit checkpoint, integration, cleanup, 재배포, push와 PR promotion은 각각 별도 승인이다.

### 3.7. work-unit-basis

- Work Unit Basis
- Project Core와 Agent Factory Workspace requirements Specification을 Agent Factory launcher View 및 Agents와 Workspace singleton editor panel 기준으로 정렬했고 full validation이 통과했다.
- aligned
- agents manifest를 하나의 launcher View, viewsWelcome과 Agents 및 Workspace open commands로 전환
- Agents Chat을 singleton Webview Panel과 command lifecycle로 전환
- empty launcher provider 추가 및 file Explorer provider와 obsolete Explorer source 및 tests 제거
- panel bind, reveal, dispose, reopen과 기존 backend session ownership 검증
- 단위, 통합, Extension Host E2E, linux-x64 package와 VSIX contents 검증
- AI Review와 한국어 Human checklist 준비
- Agents 및 Workspace command links를 제공하는 native launcher View
- editor area의 singleton Agents Chat panel
- file Explorer와 sidebar Chat View가 제거된 manifest 및 runtime
- 기존 chat/backend/session 동작을 보존하는 passing evidence
- 설치 가능한 linux-x64 VSIX
- Workspace 확장 UI 및 Kanban 구현 변경
- Web 애플리케이션 변경
- Agents 채팅 내부 visual hierarchy와 backend message contract 변경
- 다른 플랫폼 패키지
- Human 승인 없는 integration, cleanup, 재배포, push와 PR promotion
- INTERNAL-EVIDENCE-001
- WEB-EVIDENCE-001
- WEB-EVIDENCE-002
- WEB-EVIDENCE-003
- INTERVIEW-OPEN-SURFACE-001
- INTERVIEW-LAUNCHER-SURFACE-002
- SPECIFICATION-IMPACT-001

### 3.8. acceptance-and-verification

- Acceptance and Verification
- manifest는 하나의 Agent Factory Activity Bar container와 하나의 native launcher View를 제공한다.
- launcher viewsWelcome은 Agents와 Workspace command links를 제공한다.
- manifest와 runtime에는 기존 file Explorer와 sidebar Agents Chat View가 없다.
- Agents open command는 ViewColumn.Active에 singleton Webview Panel을 생성하고 재호출 시 같은 panel을 reveal한다.
- panel dispose 후 Webview binding, controller와 runner가 정리되고 다음 open에서 정상 재생성된다.
- Workspace link는 기존 agentFactoryWorkspace.open command를 실행한다.
- 현재 chat.ready, chat.submit, chat.cancel, reconnect, draft, CSP, SVG와 session ownership이 유지된다.
- TDD로 manifest와 panel lifecycle 실패 테스트를 먼저 기록하고 구현 후 통과시킨다.
- obsolete file Explorer source 및 tests의 삭제 범위가 Work Unit과 일치한다.
- npm run check와 npm run test:e2e를 통과한다.
- linux-x64 VSIX를 생성하고 launcher commands, panel runtime과 Codex payload contents를 검증한다.
- 실행 evidence, AI checklist, AI review result, report와 한국어 Human review 방법을 canonical Work Unit에 기록한다.
- integration, cleanup, 재배포, push와 PR promotion은 Human 승인 전 수행하지 않는다.
- unit: manifest의 container, launcher View, commands와 viewsWelcome links 및 Explorer와 sidebar Chat 부재를 검증한다.
- unit: Agents panel create, reveal, dispose, reopen과 Webview binding을 검증한다.
- unit/integration: 기존 submit, cancel, reconnect, draft restore, session-owned DOM, CSP와 Codex adapter 회귀를 검증한다.
- E2E: Extension Host에서 launcher View, Agents editor panel과 Workspace open command를 검증한다.
- package: linux-x64 VSIX 생성과 archive contents를 검증한다.
- 문법, 단위, 통합, VS Code 1.129.1 E2E와 linux-x64 VSIX 검증 통과
- pass
- blocks/evidence/agents-editor-area-verification.txt

### 3.9. ai-review

- AI Review
- Work Unit scope와 exclusions를 준수했는가
- launcher가 native empty View와 viewsWelcome command links만 사용하는가
- Agents와 Workspace editor panel ownership이 확인된 command 경계와 일치하는가
- singleton create, reveal, dispose, reopen과 resource cleanup을 검증했는가
- Session -> DOM -> State와 backend message allowlist를 보존했는가
- obsolete Explorer 코드와 테스트를 범위대로 제거했는가
- 검증 evidence가 실제 명령 및 결과와 일치하는가
- AI checklist 전 항목 통과. 차단 결함 없음. 설치 후 시각 및 인증 smoke는 Human review에서 확인한다.
- pass

### 3.10. basis

- Basis
- 승인된 Agents editor area 및 Agent Factory launcher basis

### 3.11. execution-context

- Execution Context
- 019f9d6b-06db-74a1-8adf-905d76ff2f16
- PLAN-001
- PLAN-002
- PLAN-003
- PLAN-004
- PLAN-005
- running

### 3.12. execution

- Execution
- launcher와 singleton Agents editor panel 구현 및 자동 검증 완료
- complete

### 3.13. human-review

- Human Review
- Agent Factory Activity Bar를 열면 하나의 launcher View만 표시되는지 확인한다.
- launcher에서 Agents를 누르면 sidebar가 아니라 editor area의 Agents tab이 열리는지 확인한다.
- Agents를 다시 눌렀을 때 중복 tab 없이 기존 tab이 reveal되는지 확인한다.
- launcher에서 Workspace를 누르면 기존 Workspace editor panel이 열리는지 확인한다.
- file Explorer와 sidebar Agents Chat View가 제거됐는지 확인한다.
- Agents의 Main 및 Workflow, 세션 전환, draft, 전송, 취소, reconnect와 실제 인증 메시지 smoke를 확인한다.
- 검토 후 승인 또는 rework를 결정하고 integration, cleanup, 재배포, push와 PR promotion은 각각 별도로 결정한다.
- 생성된 linux-x64 VSIX를 내부 설치 환경에 설치하고 Reload Window 후 Agent Factory launcher, Agents 및 Workspace editor tab, 중복 open 방지와 기존 Chat 동작을 체크리스트 순서로 확인한 뒤 승인 또는 rework를 결정한다.
- Human 검토 대기
- approved

### 3.14. plan

- Plan
- manifest launcher contribution과 singleton Agents panel lifecycle 실패 테스트를 먼저 추가한다.
- empty launcher provider, viewsWelcome command links와 Agents open command panel lifecycle을 최소 범위로 구현한다.
- file Explorer 및 sidebar Chat contribution, registration, obsolete source와 tests를 제거하고 관련 단위 및 통합 회귀를 통과시킨다.
- Extension Host E2E에서 launcher와 Agents 및 Workspace editor command를 검증하고 linux-x64 VSIX를 패키징 및 검증한다.
- AI Review, 실행 보고서와 한국어 Human review 자료를 작성한다.

### 3.15. report

- Report
- Agent Factory launcher와 Agents 및 Workspace editor panel 경계를 구현했다. Agents는 singleton이며 기존 Chat backend와 session 상태를 보존한다. Explorer와 sidebar Chat runtime은 제거됐다.
- blocks/evidence/agents-editor-area-verification.txt
- blocks/evidence/worktree-inspect-before-review.json
- integrated

### 3.16. work-definition

- Work Definition
- Agent Factory launcher View에서 Agents와 Workspace를 editor area에 열고 file Explorer와 sidebar Chat View를 제거하면서 Agents runtime 계약을 보존한다.
- agents/package.json을 하나의 launcher View, viewsWelcome, Agents 및 Workspace open commands로 전환
- agents/src/extension.js를 singleton Agents Webview Panel command lifecycle로 전환
- empty launcher provider 추가
- file Explorer registration과 obsolete Explorer source 및 tests 제거
- manifest, panel create/reveal/dispose/reopen, launcher links와 기존 backend ownership 테스트
- 단위, 통합, Extension Host E2E, linux-x64 VSIX package 및 contents 검증
- AI Review, 실행 보고서와 한국어 Human review 자료 준비
- Workspace 확장 UI 및 Kanban 구현 변경
- Web 애플리케이션 변경
- Agents 채팅 내부 visual hierarchy와 backend message contract 변경
- 다른 플랫폼 패키지
- Human 승인 없는 integration, cleanup, 재배포, push와 PR promotion
- 다른 Work Unit 변경
- Agents 및 Workspace command links를 제공하는 native launcher View
- editor area의 singleton Agents Chat Webview Panel
- file Explorer와 sidebar Chat View가 제거된 manifest 및 runtime
- 기존 chat, backend와 session 동작을 보존하는 passing verification evidence
- 설치 가능한 linux-x64 VSIX

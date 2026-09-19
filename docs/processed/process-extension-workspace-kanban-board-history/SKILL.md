---
document-type: processed
category: process
domain: null
name: extension-workspace-kanban-board-history
language: ko
provenance:
  source-paths:
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/blocks/evidence/kanban-board-integration.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/blocks/evidence/kanban-board-verification.txt
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/blocks/evidence/worktree-inspect-review.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/blocks/index.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/metadata.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/acceptance-and-verification.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/ai-review.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/basis.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/execution-context.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/execution.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/human-review.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/plan.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/report.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/work-definition.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/table-of-contents.json
  - extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/title.json
  migration-request: run-20260918T153502344625Z-53d84a1e
  authority: 백업 당시 기록입니다. 현재 명세를 대체하거나 새 실행 권한을 부여하지 않습니다.
  renamed-from: docs/processed/process-extension-backup-workspace-kanban-board
  classification-request: run-20260918T154226499325Z-8d8d4959
---

# Workspace 칸반 보드 구현 이력

## 1. 기록의 범위

- 같은 주제의 백업 요청·명세·작업 기록과 첨부를 모았습니다. 과거 상태·승인·검사 결과는 해당 시점의 기록이며 현재 검증 결과가 아닙니다.
- 현행 기준은 [현재 프로젝트 명세](../../skills/)에서 확인합니다. 원문·식별자·코드·출처는 원래 언어와 바이트를 보존합니다.
- 첨부는 보존용 원문입니다. 이 문서는 원문을 탐색하기 위한 가공 기록이며, 백업의 오래된 규칙을 활성화하지 않습니다.

## 2. 원본과 이관 위치

| 이전 경로 | 보존 자료 | SHA-256 |
| --- | --- | --- |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/blocks/evidence/kanban-board-integration.json` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-workspace-kanban-board/blocks/evidence/kanban-board-integration.json) | `3a399ae32d5779b9ad411cdd611a88f80193af9c540e1db0b4c2d03268b9ed04` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/blocks/evidence/kanban-board-verification.txt` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-workspace-kanban-board/blocks/evidence/kanban-board-verification.txt) | `538049c83e71cb82dde998951dec8d394b03e7fc3d96394c4aa6ec3338dc32cc` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/blocks/evidence/worktree-inspect-review.json` | [실행 증거 보관](../../../../../.agent-factory/projects/project-697734d129ab44cdaea697d6744ce0ca/agents/main-acc78514-564a-4363-b9eb-e36cf7fe73ca/runs/run-20260918T153502344625Z-53d84a1e/evidence-archive/work-units/agent-factory-workspace-kanban-board/blocks/evidence/worktree-inspect-review.json) | `5da69413e71afcbd95391d9576a59848e68700ae47dd6214aa0697f678db23cf` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/blocks/index.json` | [index.json](assets/work-units/agent-factory-workspace-kanban-board/blocks/index.json) | `31ee4fd04bd3cfe5223a55968d6157d61ece4d928edf8db5f6057f5642934124` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/metadata.json` | [metadata.json](assets/work-units/agent-factory-workspace-kanban-board/data/metadata.json) | `ed48987705efce22045fc2ee4994d5fd22de6b30588d794cc56e0b39622ebec8` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/acceptance-and-verification.json` | [acceptance-and-verification.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/acceptance-and-verification.json) | `11f05410318999de8875f2fe61dc00354d2d7e6e5e9018641f9450114407335e` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/ai-review.json` | [ai-review.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/ai-review.json) | `b1bb5e58f4f876eb7adee86b7b32106217d40f59a025803ec01d0309df25f146` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/basis.json` | [basis.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/basis.json) | `b52737fb4d3a54f4f7ebebd324bab150de7f161fd0489e7380d3b7f01d64c2fe` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/execution-context.json` | [execution-context.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/execution-context.json) | `4853067a8175311872cc4450a180f5b91bdc89822db87c7060a25cf48095eb78` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/execution.json` | [execution.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/execution.json) | `21e6a12cf04c5e61058cd42b6e666ce18abf890788a2b3cbf0eab8ee2a47593b` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/human-review.json` | [human-review.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/human-review.json) | `44745eade35aabcc6f296a769b882ace30562b2fc3f4e3cdaf5f67642a9f941c` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/plan.json` | [plan.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/plan.json) | `2d08f5d0f9662d0ff45bfc43b7a79b4198437a6b094405c7b59c4ca58855764d` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/report.json` | [report.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/report.json) | `e235ff8be7de4ac50e7f8841fe64328434902b90fffafce3a1b636f6cb945ed9` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/sections/work-definition.json` | [work-definition.json](assets/work-units/agent-factory-workspace-kanban-board/data/sections/work-definition.json) | `28d684ce9b547979a0ba41fe297b4b23ef6928c4683037a59655e80b947e5665` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/table-of-contents.json` | [table-of-contents.json](assets/work-units/agent-factory-workspace-kanban-board/data/table-of-contents.json) | `5bc218cc42cda129bafb7e92f81dfdb57b415f59666cca9ef674e617a15174b5` |
| `extension/.backup/.agent-factory/work-units/agent-factory-workspace-kanban-board/data/title.json` | [title.json](assets/work-units/agent-factory-workspace-kanban-board/data/title.json) | `2230ca2cb13c50c492cdbdb3668b2d6ad93c4933ae1a238514838ce07e4073a6` |

## 3. 본문 기록

### 3.1. acceptance-and-verification

- Acceptance and Verification
- 실제 canonical fixture가 정확한 6개 상태 칼럼에 표시된다.
- filter, count, watcher refresh, reconnect, empty와 partial error가 검증된다.
- 지원하지 않는 schema와 unsafe path는 mutation capability 없이 오류를 표시한다.
- drag와 Move 대상은 capability와 동일하게 표시되지만 이 Work Unit은 mutation을 수행하지 않는다.
- 실패 테스트를 먼저 작성하고 최소 구현으로 통과시킨다.
- workspace/src와 workspace/test 산출물을 완성한다.
- 단위·통합·VS Code E2E·접근성·테마·보안 검증을 통과시킨다.
- AI checklist와 AI Review를 완료한다.
- 변경 파일, 검증 결과와 남은 위험을 Report에 기록한다.
- 한국어 Human checklist와 검토 방법을 준비한다.
- schemaVersion 4.0.0 reader, 정렬, 카드 projection과 unsafe root 거부를 검증한다.
- snapshot/error message contract, watcher coalescing, reconnect state와 stale capability 거부를 검증한다.
- 6개 칼럼, count, filter, empty·partial-error와 drag·Move affordance의 동일 대상을 검증한다.
- 키보드, click·tap Move 대체 조작과 visible focus를 검증한다.
- VS Code 1.129.x Extension Development Host에서 보드 렌더링과 갱신을 검증한다.
- 구문, 13개 단위 테스트, 실제 canonical reader probe, VS Code 1.129.1 E2E, production audit와 diff 검증이 통과했다.
- pass
- blocks/evidence/kanban-board-verification.txt

### 3.2. ai-review

- AI Review
- Intake와 Work Unit 범위 준수
- TDD 순서 준수
- canonical reader 및 host-only 보안 경계 준수
- drag·Move 접근성 동등성 준수
- 단위·통합·E2E·테마·보안 검증 통과
- 생성·편집·실행·병합·PR 범위 미구현
- Intake와 Work Unit 범위, TDD, canonical reader와 host-only 경계, capability 동등성, 접근성, 검증 및 후속 mutation 범위 제외를 검토했으며 차단 결함을 발견하지 않았다.
- pass
- blocks/evidence/kanban-board-verification.txt

### 3.3. basis

- Basis
- 검증된 Kanban Operations Intake의 첫 번째 보드 기반 Work Unit basis

### 3.4. execution-context

- Execution Context
- codex-20260726-kanban-board-001
- specification-and-tests
- implementation-and-verification
- running

### 3.5. execution

- Execution
- canonical Work Unit v4 reader, host snapshot·watcher 경계, 6개 lifecycle Kanban 보드, filter·count·reconnect·partial error와 capability 기반 비변경 drag·Move affordance를 구현했다.
- complete
- blocks/evidence/kanban-board-verification.txt

### 3.6. human-review

- Human Review
- Human 검토 대기
- approved
- 실제 canonical Work Unit이 6개 상태 칼럼에 올바르게 표시되는지 확인
- 제목·id 필터, 칼럼 수, empty와 partial error 표시 확인
- 파일 변경 후 자동 갱신과 Webview 재연결 상태 복원 확인
- 허용 target만 drag와 Move UI에 표시되는지 확인
- click, tap, keyboard Move와 visible focus 확인
- 밝은·어두운 테마와 오류 복구 안내 확인
- 생성·편집·실행·상태 변경·병합·PR이 아직 동작하지 않는지 확인
- 검증 결과와 남은 위험을 확인하고 승인 또는 재작업 결정
- Report와 검증 근거를 확인한 뒤 Extension Development Host에서 canonical fixture 보드, 필터, 갱신, 재연결, drag 및 동등한 Move 조작을 직접 검사한다. 실행 결과 승인 또는 구체적인 재작업을 결정하며 integration과 PR 승격은 별도로 결정한다.

### 3.7. plan

- Plan
- 1. 승인된 Specification과 Intake basis를 fixture 및 실패 테스트로 고정한다.
- 2. canonical Work Unit reader, root·schema 거부와 partial-error 테스트를 먼저 작성한다.
- 3. host-Webview snapshot, capability, watcher와 reconnect 계약 테스트를 먼저 작성한다.
- 4. 6개 칼럼, 카드, count, filter, drag·Move affordance와 접근성 테스트를 먼저 작성한다.
- 5. 최소 구현 후 단위·통합·VS Code E2E·테마·보안 검증을 통과시킨다.
- 6. AI Review, Report와 한국어 Human 검토 자료를 완성한다.

### 3.8. report

- Report
- Workspace Kanban 보드 기반 구현 완료. 실제 canonical Work Unit을 6개 상태로 투영하며 filter, count, watcher, reconnect, partial error, drag와 동등한 Move preview를 제공한다. 실제 canonical mutation은 후속 Work Unit 범위다.
- blocks/evidence/kanban-board-verification.txt
- blocks/evidence/worktree-inspect-review.json
- workspace/package.json
- workspace/src/extension.js
- workspace/src/kanbanController.js
- workspace/src/kanbanReader.js
- workspace/src/webviewShell.js
- workspace/test/suite/index.js
- workspace/test/unit/kanbanController.test.js
- workspace/test/unit/kanbanReader.test.js
- workspace/test/unit/webviewShell.test.js
- pointer-level Chromium drag gesture는 Human review에서 확인한다.
- 실제 상태 변경은 후속 authoring Work Unit에서 manager semantic revalidation과 함께 구현한다.
- integrated

### 3.9. work-definition

- Work Definition
- canonical Work Unit 읽기 모델과 GitHub Projects 참고 Kanban 보드 기반을 구현한다.
- 요구사항 Specification 정합성 확인
- schemaVersion 4.0.0 Work Unit reader와 안전한 project root 경계
- 확장 호스트-Webview snapshot 및 오류 message contract
- backlog, ready, working, review, done, blocked 6개 칼럼
- 카드 정보, 항목 수, 제목·id filter, empty·partial-error 상태
- filesystem watcher와 Webview state 복원
- 카드별 transition capability와 drag·Move affordance의 비변경 기반
- 단위·통합·핵심 VS Code E2E, 접근성·테마·보안 검증
- canonical Work Unit 생성·편집·상태 변경
- Codex 실행
- Human review 승인·rework
- Git integration과 PR 생성
- 다른 workspace 탭과 agents·web 변경
- workspace/src
- workspace/test

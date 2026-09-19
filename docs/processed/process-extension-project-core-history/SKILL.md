---
document-type: processed
category: process
domain: null
name: extension-project-core-history
language: ko
provenance:
  source-paths:
  - extension/.backup/.agent-factory/specifications/project-core/blocks/index.json
  - extension/.backup/.agent-factory/specifications/project-core/data/metadata.json
  - extension/.backup/.agent-factory/specifications/project-core/data/sections/basis-and-relations.json
  - extension/.backup/.agent-factory/specifications/project-core/data/sections/decisions-and-open-items.json
  - extension/.backup/.agent-factory/specifications/project-core/data/sections/purpose-and-scope.json
  - extension/.backup/.agent-factory/specifications/project-core/data/sections/verification-and-traceability.json
  - extension/.backup/.agent-factory/specifications/project-core/data/table-of-contents.json
  - extension/.backup/.agent-factory/specifications/project-core/data/title.json
  migration-request: run-20260918T153502344625Z-53d84a1e
  authority: 백업 당시 기록입니다. 현재 명세를 대체하거나 새 실행 권한을 부여하지 않습니다.
  renamed-from: docs/processed/process-extension-backup-project-core
  classification-request: run-20260918T154226499325Z-8d8d4959
---

# Workspace 프로젝트 핵심 구조 이력

## 1. 기록의 범위

- 같은 주제의 백업 요청·명세·작업 기록과 첨부를 모았습니다. 과거 상태·승인·검사 결과는 해당 시점의 기록이며 현재 검증 결과가 아닙니다.
- 현행 기준은 [현재 프로젝트 명세](../../skills/)에서 확인합니다. 원문·식별자·코드·출처는 원래 언어와 바이트를 보존합니다.
- 첨부는 보존용 원문입니다. 이 문서는 원문을 탐색하기 위한 가공 기록이며, 백업의 오래된 규칙을 활성화하지 않습니다.

## 2. 원본과 이관 위치

| 이전 경로 | 보존 자료 | SHA-256 |
| --- | --- | --- |
| `extension/.backup/.agent-factory/specifications/project-core/blocks/index.json` | [index.json](assets/specifications/project-core/blocks/index.json) | `3ea63b508ced82dd19cdad9fcfc716030e510d405d86b1e516195cb40352a164` |
| `extension/.backup/.agent-factory/specifications/project-core/data/metadata.json` | [metadata.json](assets/specifications/project-core/data/metadata.json) | `162681bddab8cf9cd85700af1f4bb294c15ce42f6238e068925566255d347f4c` |
| `extension/.backup/.agent-factory/specifications/project-core/data/sections/basis-and-relations.json` | [basis-and-relations.json](assets/specifications/project-core/data/sections/basis-and-relations.json) | `82f99a69fab634590c29563ae4213a788e0a786aea836394bfc5e2f5a2b62812` |
| `extension/.backup/.agent-factory/specifications/project-core/data/sections/decisions-and-open-items.json` | [decisions-and-open-items.json](assets/specifications/project-core/data/sections/decisions-and-open-items.json) | `e403d6b2e11033e0bed6865b1f94e67236a869a542bb50eb2371cdcbb34b3e12` |
| `extension/.backup/.agent-factory/specifications/project-core/data/sections/purpose-and-scope.json` | [purpose-and-scope.json](assets/specifications/project-core/data/sections/purpose-and-scope.json) | `2636fb00543e0606729f8b2c3d1d7ba56c3f3a44d4c9a8ab379dc377c3c112b2` |
| `extension/.backup/.agent-factory/specifications/project-core/data/sections/verification-and-traceability.json` | [verification-and-traceability.json](assets/specifications/project-core/data/sections/verification-and-traceability.json) | `9e743e9d9606bc78612a4fb31bf5f6f8e438f53aeac9e3bebd56b8b6a074afe9` |
| `extension/.backup/.agent-factory/specifications/project-core/data/table-of-contents.json` | [table-of-contents.json](assets/specifications/project-core/data/table-of-contents.json) | `5ca65a54c447c9c8d989120e2ab84ac226c579d6ba89654fbd036a7b50a14a71` |
| `extension/.backup/.agent-factory/specifications/project-core/data/title.json` | [title.json](assets/specifications/project-core/data/title.json) | `8f193dc2f04efbcb9119c7e077cbcd249852a82b6767abc2def4fdb43e95e497` |

## 3. 본문 기록

### 3.1. basis-and-relations

- basis-and-relations
- canonical Agent Factory JSON 변경은 owning manager를 통한다.
- Webview는 파일시스템과 명령을 직접 소유하지 않고 확장 호스트 메시지 경계를 사용한다.
- 요구사항, Work Unit, 실행 결과, 병합 및 PR 승격의 최종 결정은 Human이 소유한다.
- 공식 VS Code Webview 보안·테마·접근성 지침을 따른다.
- agent-factory-workspace Intake
- Agents editor area 및 launcher surface Intake

### 3.2. decisions-and-open-items

- decisions-and-open-items
- 요구사항 및 범위 승인
- Work Unit 승인
- 실행 결과 검토
- 병합 및 PR 승격 결정
- 후속 Work Unit에서 산출물 읽기 모델과 Work Unit 조작 계약을 상세화한다.
- agents Chat의 메시지 전송, backend 연결, 원격 세션과 스트리밍 계약은 후속 Intake에서 결정한다.

### 3.3. purpose-and-scope

- purpose-and-scope
- Agent Factory 산출물 탐색·열람과 Work Unit 실행·상태 관리를 VS Code 에디터 및 네이티브 Workbench View 영역에서 제공한다.
- VS Code 에디터 Webview
- Dashboard, Design, Kanban, Context, View 탭 shell
- Kanban 및 View 초기 기능
- Agent Factory launcher View
- Agents와 Workspace singleton editor Webview panel
- 독립 확장 구현

### 3.4. verification-and-traceability

- verification-and-traceability
- Specification manager 전체 검증
- Intake 목적·범위·승인 경계 추적성 검토
- Human 검토

---
name: info-extension-architecture
description: Agent Factory 익스텐션 프로젝트에 적용합니다. 확장의 현재 소스 위치, 런타임 바인딩과 문서 소유권을 설명합니다.
  기능의 구현 위치와 연동 경계를 찾을 때 사용하며 목표 설계와 관찰을 구분합니다.
metadata:
  document-type: specification
  category: info
  domain: null
  name: extension-architecture
  language: ko
  provenance:
    prior-provenance:
      organization-authority: Human approved these three package identities and organization
        on 2026-09-16 KST; unresolved semantic changes remain unresolved.
      collected-on: '2026-09-16'
      sources:
      - historical-source-path: docs/directory-structure.md
        preserved-record: docs/processed/other-directory-structure-history/SKILL.md
      - README.md
      - src/infrastructure/agent-factory/agent-client.ts
      - src/modules/chat/session-controller.ts
      - src/common/types/business-mode.ts
      - scripts/build.mjs
      - .vscodeignore
    merged-from:
    - docs/skills/info-extension-architecture/SKILL.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: info-extension-architecture
      description: Agent Factory 익스텐션 프로젝트에 적용합니다. 확장의 현재 소스 위치, 런타임 바인딩과 문서 소유권을
        설명합니다. 기능의 구현 위치와 연동 경계를 찾을 때 사용하며 목표 설계와 관찰을 구분합니다.
      metadata:
        document-type: specification
        category: info
        domain: null
        name: extension-architecture
        language: ko
        provenance:
          organization-authority: Human approved these three package identities and
            organization on 2026-09-16 KST; unresolved semantic changes remain unresolved.
          collected-on: '2026-09-16'
          sources:
          - historical-source-path: docs/directory-structure.md
            preserved-record: docs/processed/other-directory-structure-history/SKILL.md
          - README.md
          - src/infrastructure/agent-factory/agent-client.ts
          - src/modules/chat/session-controller.ts
          - src/common/types/business-mode.ts
          - scripts/build.mjs
          - .vscodeignore
---


# 확장 구조 정보

- 적용 대상은 Agent Factory 익스텐션입니다. 플러그인 내부 구현과 MCP 개발 규칙은 이 문서가 소유하지 않습니다.

<a id="활성화와-플러그인-준비-위치"></a>

## 1. 활성화와 플러그인 준비 위치

- `src/extension.ts`가 의존성 확인·진행 알림·오류의 Retry와 성공 후 단일 bootstrap을 연결합니다. 추가 명령 등록은 없습니다.
- `src/infrastructure/agent-factory/plugin-dependency.ts`가 설치 목록, 공식 Marketplace 소스 확인과 부재 시 등록, 정확한 버전 후보 설치·재확인 및 동시 요청 공유를 소유합니다.
- Codex CLI는 `execFile` 인자 배열·호스트 홈 작업 디렉터리·`runtimeEnvironment()`로 실행합니다. 설치·등록은 30초, 목록은 15초이며 설치 후보 목록은 4 MiB, 나머지 출력은 256 KiB로 제한합니다.
- `tests/unit/plugin-dependency.test.mjs`에 준비·실패·재시도·동시 활성화 모의 사례를 둡니다. 이 기록은 테스트 실행 결과가 아닙니다.

<a id="범위와-근거"></a>

## 2. 범위와 근거

- 2026-09-16 KST에 extension 작업 트리의 문서와 소스를 읽어 정리한 구조 정보입니다. 실행·빌드·테스트 결과 또는 모든 요구사항의 충족 판정이 아닙니다.
- 이 파일은 현재 위치·관찰 사실의 원문입니다. 목표와 FR-01~FR-13은 [채팅 설계](../design-main-chat/SKILL.md), 의무는 [개발 규칙](../rule-extension-development/SKILL.md)에 있습니다.
- 기존 목표 트리의 없는 파일을 구현 결함으로 단정하지 않습니다. 실제 소스가 목표와 다르다는 이유로 목표를 변경하지 않습니다.

<a id="문서-소유권과-출처"></a>

## 3. 문서 소유권과 출처

| 당시 출처 경로(현재 파일 아님) | 현재 소유 패키지 | 보존 방식 |
| --- | --- | --- |
| `docs/requirements.md` | `design-main-chat` | FR-01~13·목적·품질·완료 조건·사전 계약을 이어받고 현재 런타임 경로를 정정합니다. 기존 본문은 역사 자료로 남습니다. [현재 Processed 기록](../../../docs/processed/process-extension-requirements-history/SKILL.md)에 전체 이전 본문을 보존합니다. |
| `docs/directory-structure.md` | 세 패키지 | 목표 트리·탭 생명주기·초기 구현 순서는 design, 실제 위치·런타임 identity는 info, 책임·의존·설정·보안·패키징·테스트 원칙은 rule이 소유합니다. [현재 Processed 기록](../../../docs/processed/process-extension-directory-structure-history/SKILL.md)에 전체 이전 본문을 보존합니다. |
| `docs/queued-input.md` | `design-main-chat` | 병합·권한·Goal·실패·연결·복구 조건을 보존합니다. 당시 Main 확인 요청은 역사 자료에 남습니다. [현재 Processed 기록](../../../docs/processed/process-extension-queued-input-history/SKILL.md)에 전체 이전 본문을 보존합니다. |
| `docs/status-bar.md` | `design-main-chat` | UX·항목별 출처·한계·설정 호환·미지원 정보를 보존합니다. Processed 출처와 당시 확인 요청을 유지합니다. [현재 Processed 기록](../../../docs/processed/process-extension-status-bar-history/SKILL.md)에 전체 이전 본문을 보존합니다. |
| `README.md` | 설치·사용·개발·배포 진입점 | 기존 설명은 유지하고 현재 명세 링크와 소유권 안내를 추가합니다. |

<a id="문서-저장-루트"></a>

## 4. 문서 저장 루트

- 문서 유형과 루트는 상위 Agent Factory 저장소의 `docs/original/`, `docs/processed/`, `docs/skills/` 세 가지입니다. 익스텐션 루트에서는 `../docs/`로 참조합니다. 역사 기록은 Processed의 상태이며 별도 루트를 만들지 않습니다.
- 현재 세 Specification은 기존 이름과 요구사항 권위를 유지합니다. 위 표의 네 과거 문서는 Processed 보존 패키지이며 활성 프로젝트 Skill로 노출하지 않습니다.
- 이번에 보존한 자료는 Original 문서가 아닙니다. 익스텐션의 현재 Original 문서는 없으며 상위 `docs/original/`은 다른 구성 요소와 공유합니다. 내용을 채우기 위한 placeholder는 두지 않습니다.
- 옛 docs 루트의 네 파일은 이전 후 제거했습니다. 아래 및 목표 트리의 과거 경로는 출처 기록으로만 남습니다.

<a id="현재-소스-위치"></a>

## 5. 현재 소스 위치

- 경로는 모두 프로젝트 루트 기준입니다.

| 경로 | 관찰한 역할 |
| --- | --- |
| `src/extension.ts`, `src/core/bootstrap.ts`, `src/core/container.ts` | 확장 진입과 초기화·의존성 조립 |
| `src/core/config/{types,defaults,resolver}.ts` | 설정 타입, 기본값, 병합 |
| `src/modules/chat/{chat-state,session-controller,task-selection}.ts` | 채팅 상태, 요청·큐·실행 추적, UI 작업 선택과 실행 경로 매핑 |
| `src/common/types/business-mode.ts` | 요청별 Normal/Interview/Planning/Design 지침 구성 |
| `src/infrastructure/agent-factory/agent-client.ts` | 런타임 위치 확인, 명령 호출, 실행 결과·이벤트·사용량 변환 |
| `src/infrastructure/agent-factory/{plugin-locator,plugin-dependency,process-environment}.ts` | 플러그인 탐색·의존성, 프로세스 환경 |
| `src/infrastructure/agent-factory/{model-catalog,cli-theme}.ts` | 모델 목록 및 CLI 테마 연동 |
| `src/infrastructure/vscode/chat-panel-manager.ts` | 패널·입력·설정·상태 전달 및 VS Code 연동 |
| `src/infrastructure/vscode/{chat-panel-serializer,chat-template-renderer,agent-sidebar}.ts` | 탭 복원, 템플릿, Agent 사이드바 |
| `src/infrastructure/vscode/image-attachment-store.ts`, `src/common/image-input.ts` | 이미지 첨부 저장·입력 처리 |
| `src/protocol/{messages,validator}.ts` | Host와 화면 사이 메시지 모델·검증 |
| `templates/chat.html`, `static/js/chat.js`, `static/css/` | 채팅 화면과 동작·스타일 |
| `src/webview/{syntax-highlighter,cli-theme-colors}.ts`, `src/webview/cli-themes.json` | 브라우저 구문 강조 및 테마 소스; 기존 명명 규칙과 충돌 |
| `scripts/build.mjs` | `src/extension.ts`를 `dist/extension.js`로, 구문 강조를 `static/vendor/syntax-highlighter.js`로 번들링하는 구성 |
| `tests/unit/`, `tests/integration/`, `tests/browser/`, `tests/fixtures/` | 조사에서 발견한 테스트·fixture 위치; 실행 결과를 뜻하지 않음 |
| `.vscodeignore` | dist/static/templates/package.json/README.md를 포함하는 allowlist 구성 |

- 기존 목표 트리의 `docs/protocol.md`, `core/lifecycle.ts`, `modules/chat/message-queue.ts`, `capability-client.ts`, `scripts/verify-vsix.mjs`는 조사한 현재 파일 목록에 없습니다.
- 현재 큐는 `session-controller.ts`, 프로토콜 모델은 `messages.ts`에 있습니다. 목표 계층의 모든 모듈이 독립 파일로 구현된 것은 아닙니다.
- 패키징 산출물 내용은 확인하지 않았습니다. allowlist에 포함되는 디렉터리 내부 파일의 실제 배포 포함 여부를 이 정보로 보증하지 않습니다.

<a id="런타임-위치와-identity"></a>

## 6. 런타임 위치와 identity

- `agent-client.ts`의 `loadLocation`은 workspace Extension Host에서 `exec.py init --project-root <project-root>`를 호출합니다. 응답의 schemaVersion 1, registered, 정규화된 projectRoot, home 및 projectId에 따른 runtimeRoot/agentsRoot를 확인하고 바인딩을 유지합니다.

```text
<runtime-home>/                 # AGENT_FACTORY_HOME 또는 해당 호스트의 ~/.agent-factory
└── projects/
    └── <project-id>/
        └── agents/
            └── <agent-id>/
                ├── session.json
                ├── dispatches/ # 기존 설계의 dispatch 기록 위치; Provider 계약 참조
                └── runs/
                    └── <run-id>/
```

- home과 projectId는 init 응답에서 얻습니다. 위 구조는 경로를 직접 생성하라는 지시가 아닙니다. `dispatches/` 등 하위 저장 schema 전체를 이번에 Provider 구현에서 조사하지 않았습니다.
- `<agent-id>`는 채팅의 durable identity, session의 Codex Session ID는 Resume identity, `<run-id>`는 요청·결과 identity입니다.
- 패널 ID, 화면 캐시, VS Code view column은 런타임 identity가 아닙니다. 확장이 상태 파일을 직접 만들어 identity를 정하지 않습니다.
- SSH/container에서는 UI 기계가 아닌 workspace Extension Host의 home을 사용합니다. 이후 명령은 바인딩한 `--runtime-home`과 `--project-id`를 전달합니다.
- 기존 `<project-root>/.agent-factory/agent/`는 과거 표기입니다. 첫 submit이 그 checkout-local 폴더를 생성한다는 과거 설명은 현재 경로 계약으로 사용하지 않습니다. init을 통한 위치 초기화·발견과 첫 메시지의 Agent 바인딩을 구분합니다.

<a id="관찰된-동작과-요구사항의-차이"></a>

## 7. 관찰된 동작과 요구사항의 차이

- 큐는 `queuedSends` 메모리 배열과 `mergePendingSends`의 병합으로 처리합니다. durable 큐 요구와의 차이는 설계 문서의 미해결 표에 있습니다.
- 작성기의 여섯 실행 액션은 `task-selection.ts`에서 런타임 route로 전달됩니다. 일반 전송과 과거 모드 복원은 direct입니다. Verification은 관리형 독립 검증이며 다른 액션과 큐에서 병합하지 않습니다. 플러그인이 standalone receipt와 실제 Plan 협업 모드를 소유합니다.
- 상태바는 `static/js/chat.js`, `core/config`, `protocol/validator.ts`, `chat-panel-manager.ts`가 함께 관여합니다. `readLatestTokenCount`는 `last_token_usage`를, `readWeeklyUsedPercent`는 주간 rate limit 값을 읽습니다. 선택한 다음 모델과 실제 실행 모델, 현재 컨텍스트와 누적 소비량을 구분합니다. 전체 항목·상한·미제공 정책은 설계의 상태바 기록을 참조하십시오.
- 이미지가 있는 `agent-client.ts`의 `inputCommand`는 versioned 입력 계약을 사용합니다. 파일·폴더의 텍스트 참조와 이미지 전달을 구분합니다. README Runtime notes의 첨부 일반화는 Features의 이미지 계약 설명과 불일치합니다.
- README에는 macOS 설정·제한이 있으며 `process-environment.ts`에는 Darwin PATH 보완이 있습니다. 이 사실만으로 macOS 지원 완료를 판정하지 않습니다.
- `readGitDiff`의 변경 표시를 FR-10의 실행 전 스냅샷·충돌 안전 복원 구현으로 간주하지 않습니다.
- `business-mode.ts`와 README Composer modes의 HTML·영어 Skill 쌍 지침은 현재 단일 원문 계약과 다릅니다. 문서 정리에서 실행 소스를 수정하지 않았으므로 여전히 발생 가능한 workflow 불일치입니다.

<a id="정보-유지-시-주의점"></a>

## 8. 정보 유지 시 주의점

- 현재 경로와 함수 관찰은 소스 변경에 따라 갱신합니다. 갱신한 사실만으로 설계 요구를 수용·폐기하지 않습니다.
- README의 플러그인 버전 요구와 설치 설명은 두 절에서 반복됩니다. 이번 변경은 링크·문서 소유권 안내 범위이며 해당 본문과 배포 절차를 재작성하지 않습니다.
- 명세 발견은 일반 Markdown Skill 진입점을 통해 원문을 읽도록 구성합니다. symlink discovery 호환성을 실행 확인하지 않았으므로 symlink에 의존하지 않습니다.

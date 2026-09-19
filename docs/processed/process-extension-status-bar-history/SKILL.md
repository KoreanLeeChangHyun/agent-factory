---
name: extension-status-bar-history
description: 상태바 이전 기록을 출처와 함께 보존하는 비권위 Processed 기록입니다. 현재 명세 적용 지침이 아닙니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance:
    historical-source-path: docs/status-bar.md
    preserved-record: docs/processed/other-status-bar-history/SKILL.md
    captured-on: '2026-09-16'
    organization-authority: Human requested only original, processed and specification
      roots and authorized migration of these four historical records.
    fidelity: 기존 본문과 앞선 정리 안내를 보존하고 안내의 상대 링크만 새 위치에 맞게 변경했습니다.
    status: historical-snapshot
  merged-from:
  - docs/processed/other-status-bar-history/SKILL.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  source-metadata:
    name: other-status-bar-history
    description: 상태바 이전 기록을 출처와 함께 보존하는 비권위 Processed 기록입니다. 현재 명세 적용 지침이 아닙니다.
    metadata:
      document-type: processed
      category: other
      domain: null
      name: status-bar-history
      language: ko
      provenance:
        historical-source-path: docs/status-bar.md
        preserved-record: docs/processed/other-status-bar-history/SKILL.md
        captured-on: '2026-09-16'
        organization-authority: Human requested only original, processed and specification
          roots and authorized migration of these four historical records.
        fidelity: 기존 본문과 앞선 정리 안내를 보존하고 안내의 상대 링크만 새 위치에 맞게 변경했습니다.
        status: historical-snapshot
  renamed-from: docs/processed/other-status-bar-history
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# 상태바 이전 기록

- 이 패키지는 앞선 명세 정리 시 남겼던 `docs/status-bar.md`의 이전 기록을 보존합니다. 옛 경로는 출처 식별자이며 현재 파일 위치가 아닙니다.
- 문서 유형은 Processed입니다. 역사 기록이라는 상태는 네 번째 문서 유형이나 저장 루트가 아닙니다. `other`는 내용을 분석·판정하지 않고 보존하는 가공 기록의 범주입니다.
- 현재 요구사항과 설계의 권위는 아래 링크된 기존 Specification에 있습니다. 이번 이전은 현재 명세를 강등하거나 요구사항을 폐기하지 않습니다.
- 아래 과거 경로·목표 트리·구현 설명·확인 요청·외부 근거는 당시 기록입니다. 새 검증 결과나 현재 실행 지시로 간주하지 마십시오.

<a id="보존된-이전-문서"></a>

## 1. 보존된 이전 문서

<!-- Historical source preserved during the approved specification organization, 2026-09-16 KST. -->
> **역사 자료 — 현재 편집 원문은 [design-main-chat](../../skills/design-main-chat/SKILL.md)입니다.**
> 아래는 정리 직전 본문을 보존한 출처 자료이며 최신 명세의 경쟁 원본이 아닙니다. 과거 런타임 경로·구현 설명·당시 확인 요청은 현재 사실이나 검증 결과로 사용하지 마십시오. 의미 변경은 링크된 명세에서 관리합니다.

<a id="채팅-상태-표시줄-사용자-설정"></a>

## 2. 채팅 상태 표시줄 사용자 설정

- 채팅 하단의 톱니바퀴 SVG 버튼(**상태 표시줄 설정**)에서 표시할 정보를 선택합니다. 선택된 항목은 목록 위쪽에 현재 표시 순서로 나타납니다. 목록에서 위·아래 방향으로, 상태 표시줄에서는 좌·우 방향으로 드래그하면 대상 항목 앞이나 뒤의 삽입 위치가 표시됩니다. 놓는 즉시 화면에 반영됩니다. 목록의 **앞으로·뒤로** 버튼 또는 상태 항목의 **Alt+왼쪽/오른쪽**으로도 이동할 수 있습니다. Escape로 설정을 닫으면 설정 버튼으로 포커스가 돌아옵니다.

- 선택 항목과 순서는 `agentFactory.mainChat.statusItems` 배열로 저장합니다. 작업 영역이 있으면 Workspace, 없으면 Global 범위를 사용합니다. 열린 채팅에는 설정 변경 이벤트를 반영하고, 복원 시에는 VS Code 설정을 웹뷰 캐시보다 우선합니다. 빈 배열은 모든 정보를 숨기며 설정 버튼은 유지됩니다. 기본값 재설정은 기존 기본 배열 `status, agents, project, branch, context, queue`를 다시 저장합니다. 기존 항목 ID는 유지하며, 중복·알 수 없는 설정 값은 정규화합니다. 잘못된 값만 있는 설정은 기본값으로 복구합니다. 웹뷰 메시지의 알 수 없는 ID와 중복은 거부합니다.

<a id="정보-목록과-근거"></a>

## 3. 정보 목록과 근거

- 아래 목록은 2026-09-14 UTC에 확장 소스와 공식 문서를 조사하여 작성한 Processed 설명입니다. 공식 API의 전체 기능 목록과 현재 확장이 실제로 전달받는 정보는 구분하였습니다. 새 계정 API·권한·인증·유료 서비스는 추가하지 않았습니다.

| ID | 표시 정보 | 실제 데이터 및 한계 |
| --- | --- | --- |
| `status` | 실행·대기·결정 필요 | 실행 및 결정 이벤트, 연결 미확인 표시 |
| `agent`, `role` | 채팅 이름·역할 | 탭 상태와 호스트 초기화, 내부 실행 ID 제외 |
| `agents`, `agentsTotal` | 작업·검증 수, 누적 호출 수 | 기존 자식 Agent 목록·요약, Main 전용; 수신 전 확인 불가 |
| `project`, `branch` | 프로젝트 이름·Git 브랜치 | 기존 workspace 이름과 브랜치 갱신 경로; 없으면 — |
| `queue` | 전송 대기 메시지 수 | 현재 채팅 큐 이벤트 |
| `runtime` | 연결 확인 상태 | 기존 연결 결과; 네트워크 지연 측정값 아님 |
| `elapsed` | 현재 실행 경과 시간 | 웹뷰가 실행을 관측한 시작 시각; 초 단위 갱신, 복원 시 저장 시각 사용, 미실행 시 — |
| `context` | Content 잔여 비율 | 기준 대비 잔여 비율만 표시; 최소 0%; 사용량 미제공 또는 기준 0/미제공 시 확인 불가 |
| `contextUsed` | Content 사용 토큰 | `last_token_usage.input_tokens`; 현재 사용 토큰 수만 표시하며 세션 누적 소비량 아님; 기준이 없어도 수신한 토큰 수는 표시 |
| `contextRemainingTokens` | Content 잔여 토큰 | 기준 − 현재 사용 토큰, 최소 0; 토큰 수만 표시; 사용량 미제공 또는 기준 0/미제공 시 확인 불가 |
| `contextUsedPercent` | Content 사용 비율 | 현재 사용 토큰 ÷ 기준 × 100; 비율만 표시; 사용량 미제공 또는 기준 0/미제공 시 확인 불가 |
| `contextWindow` | Content 기준 토큰 | `model_context_window`; 0/미제공 시 확인 불가 |
| `weekly` | Weekly 사용량 | `rate_limits`의 7일 창 `used_percent`; 최근 수신값이며 미제공 시 확인 불가 |
| `weeklyRemaining` | Weekly 잔량 | `100 − used_percent`; Weekly 사용률 미제공 시 확인 불가; 절대 토큰 수를 추정하지 않음 |
| `model`, `reasoning`, `fast` | 선택한 다음 전송 옵션 | 현재 composer 상태와 capability; 서버가 실제 실행한 모델이라는 보장 없음 |
| `task`, `execution` | 다음 작업 모드·실행 권한 | 기존 작업 모드 및 호스트 권한 값; 작업 모드는 Main 전용 |
| `goal` | 목표 상태·켜짐 여부 | 기존 Goal 관측 결과; Main 전용 |
| `goalTokens`, `goalTime`, `goalBudget` | 목표 사용 토큰·시간·예산 | `NativeGoal.tokensUsed`, `timeUsedSeconds`, `tokenBudget`; 미제공·오류 시 확인 불가 |

<a id="독립-선택과-기존-설정-호환"></a>

### 3.1. 독립 선택과 기존 설정 호환

- Content 잔여 비율·사용 토큰·잔여 토큰·사용 비율 및 Weekly 사용량·잔량을 각각 독립적으로 선택하고 정렬합니다. 비율과 토큰 수를 한 항목에 합치지 않습니다.
- 기존 `context`는 잔여 비율만, `contextUsed`는 사용 토큰 수만 표시하도록 변경합니다. 기존 ID·선택 순서·빈 배열·기본 배열은 그대로 유지하며 설정을 자동으로 확장하지 않습니다. 새 `contextRemainingTokens`와 `contextUsedPercent`는 설정 메뉴에서 선택합니다. 기존 `contextWindow`, `weekly`, `weeklyRemaining`도 유지합니다.
- 비율은 소수점 최대 한 자리로 표시합니다. Content 사용량이 기준을 초과하면 실제 사용률은 100%를 넘을 수 있으며 잔량은 0으로 제한합니다. 미제공 값은 0으로 대체하지 않습니다.
- `branch`는 실제 브랜치 이름만 표시합니다. 표시 접두어 `Branch`만 제거하며 Git 기능과 저장된 선택은 유지합니다.

- 소스 소유자는 `static/js/chat.js`의 카탈로그·렌더러, `src/core/config/`의 설정 정의, `src/protocol/validator.ts`의 메시지 검증, `chat-panel-manager.ts`의 설정 저장·상태 전달입니다. 사용량 근거는 `agent-client.ts`의 `readLatestTokenCount`/`readWeeklyUsedPercent`와 `NativeGoal`입니다. 새 항목을 추가할 때에는 카탈로그, 타입, package 설정 enum을 함께 갱신합니다.

<a id="현재-표시할-수-없는-정보"></a>

## 4. 현재 표시할 수 없는 정보

- 공식 Codex App Server는 thread 토큰 사용량 알림, 계정 rate limit 조회·알림과 reset 시각, 조건부 credit 정보, 계정 전체 사용 통계를 설명합니다. 그러나 현재 확장은 이 계정 조회 연결을 사용하지 않습니다. 따라서 비용·크레딧·단기 한도·초기화 시각·계정 전체 통계·입출력/캐시별 누적량·처리 속도를 추정하여 표시하지 않습니다. 이 항목들은 설정 UI의 미지원 안내에 포함합니다. [공식 Codex App Server 문서](https://learn.chatgpt.com/docs/app-server)

- VS Code 설정 저장 범위와 변경 이벤트는 공식 `WorkspaceConfiguration.update` 및 `workspace.onDidChangeConfiguration`을 따릅니다. [VS Code API](https://code.visualstudio.com/api/references/vscode-api#WorkspaceConfiguration)

- 웹뷰 캐시는 `getState`/`setState`로 유지하되 표시 항목은 호스트 설정을 기준으로 복원합니다. [VS Code Webview 상태 유지](https://code.visualstudio.com/api/extension-guides/webview#getstate-and-setstate)

<a id="main의-집중-확인"></a>

## 5. Main의 집중 확인

- Work는 테스트·빌드·검증을 실행하지 않았습니다. Main에서 아래 범위를 확인해 주십시오.

```sh
node --test tests/unit/status-customization.test.mjs tests/unit/runtime-adapter.test.mjs tests/unit/structure.test.mjs
npm run typecheck
npm run check:static
```

- Extension Development Host에서 24px 너비의 SVG 설정 버튼·툴팁·접근성 이름, 잔여 비율과 사용/잔여 토큰의 개별 표시, 항목 모두 숨기기, 기본값 복원, 목록과 표시줄의 양방향 DnD, 삽입 표시, Alt+방향키와 이동 버튼, Escape/포커스, 좁은 패널·고대비 테마를 확인합니다. 두 채팅 동시 변경, 설정 파일에서의 편집, Reload Window 후 빈 배열·순서 유지, 저장 실패 후 복구, 실행 중 경과 시간과 사용량 갱신도 확인합니다. 배포·재시작은 이 Work에서 수행하지 않았습니다.

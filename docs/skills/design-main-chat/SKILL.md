---
name: design-main-chat
description: Agent Factory 익스텐션 프로젝트에 적용합니다. Main 채팅의 요구사항과 탭·큐·첨부·상태바 설계를 적용합니다.
  채팅 동작 변경 시 사용하며 관찰된 구현을 요구사항 승인으로 간주하지 않습니다.
metadata:
  document-type: specification
  category: design
  domain: null
  name: main-chat
  language: ko
  provenance:
    prior-provenance:
      organization-authority: Human approved these three package identities and organization
        on 2026-09-16 KST; unresolved semantic changes remain unresolved.
      collected-on: '2026-09-16'
      sources:
      - historical-source-path: docs/requirements.md
        preserved-record: docs/processed/other-requirements-history/SKILL.md
      - historical-source-path: docs/directory-structure.md
        preserved-record: docs/processed/other-directory-structure-history/SKILL.md
      - historical-source-path: docs/queued-input.md
        preserved-record: docs/processed/other-queued-input-history/SKILL.md
      - historical-source-path: docs/status-bar.md
        preserved-record: docs/processed/other-status-bar-history/SKILL.md
      - src/modules/chat/session-controller.ts
      - src/modules/chat/task-selection.ts
    merged-from:
    - docs/skills/design-main-chat/SKILL.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: design-main-chat
      description: Agent Factory 익스텐션 프로젝트에 적용합니다. Main 채팅의 요구사항과 탭·큐·첨부·상태바 설계를 적용합니다.
        채팅 동작 변경 시 사용하며 관찰된 구현을 요구사항 승인으로 간주하지 않습니다.
      metadata:
        document-type: specification
        category: design
        domain: null
        name: main-chat
        language: ko
        provenance:
          organization-authority: Human approved these three package identities and
            organization on 2026-09-16 KST; unresolved semantic changes remain unresolved.
          collected-on: '2026-09-16'
          sources:
          - historical-source-path: docs/requirements.md
            preserved-record: docs/processed/other-requirements-history/SKILL.md
          - historical-source-path: docs/directory-structure.md
            preserved-record: docs/processed/other-directory-structure-history/SKILL.md
          - historical-source-path: docs/queued-input.md
            preserved-record: docs/processed/other-queued-input-history/SKILL.md
          - historical-source-path: docs/status-bar.md
            preserved-record: docs/processed/other-status-bar-history/SKILL.md
          - src/modules/chat/session-controller.ts
          - src/modules/chat/task-selection.ts
---


# Main 채팅 설계

- 적용 대상은 Agent Factory 익스텐션입니다. 플러그인 내부 구현과 MCP 개발 규칙은 이 문서가 소유하지 않습니다.

- 설치된 익스텐션과 플러그인의 기본 버전이 같으면 최신 릴리스가 아니어도 사용할 수 있습니다. 자동 런타임 탐색과 재탐색은 같은 기본 버전의 플러그인 manifest를 확인하며, 더 최신 캐시로 대체하지 않습니다. 명시적인 runtimeExecPath 개발 override는 유지합니다.

<a id="최초-활성화의-플러그인-준비"></a>

## 1. 최초 활성화의 플러그인 준비

- Human이 2026-09-16 KST에 승인한 자동 설치 동작입니다. 최초 활성화 시 workspace Extension Host의 Codex와 설치된 플러그인을 확인하며, 기본 버전이 일치하고 활성화되어 있으면 바로 채팅 초기화로 진행합니다.
- 플러그인이 없거나 비활성·버전 불일치이면 공식 Marketplace가 없는 경우에만 `KoreanLeeChangHyun/agent-factory-codex-plugin --ref main`을 등록합니다. 같은 이름의 다른 소스 또는 확인할 수 없는 소스는 충돌로 표시하며 덮어쓰지 않습니다.
- 카탈로그에 기본 버전이 정확히 일치하는 후보만 설치하고 설치 후 활성 상태·버전을 다시 확인합니다. 기존 호환 대체 Marketplace 지원을 유지하며 임의 최신 버전으로 대체하지 않습니다.
- Codex 부재·등록/설치 실패·버전 미제공 시 채팅 초기화를 차단하고 오류와 **Retry**를 제공합니다. Retry는 전체 의존성 확인을 다시 수행합니다. 알림을 닫은 경우 확장 호스트를 다시 로드하여 재시도합니다.
- 동시 요청은 진행 중인 준비 작업을 공유하며 성공 후 채팅 초기화는 한 번만 수행합니다. SSH/WSL/container에서는 원격 workspace Extension Host의 환경을 사용합니다.

<a id="읽는-방법과-권위"></a>

## 2. 읽는 방법과 권위

- 이 파일이 채팅 설계의 단일 편집 원문입니다. 프로젝트 Skill은 이 파일을 읽는 진입점입니다.
- Human은 세 명세의 이름과 정리를 승인하셨습니다. 기존 요구사항을 현재 구현에 맞춰 완화하거나 미구현 기능을 폐기하는 승인은 아닙니다.
- 아래 **제품 요구사항**은 기존 FR-01~FR-13과 품질·완료 조건을 보존합니다. **큐 상세 기록**과 **상태바 상세 기록**은 기존 문서의 설계·관찰을 출처와 함께 유지하며, 상충하는 부분은 **미해결 차이**를 함께 읽으십시오.
- [현재 구조 정보](../info-extension-architecture/SKILL.md), [개발 규칙](../rule-extension-development/SKILL.md)을 함께 참조하십시오.
- [기존 요구사항](../../../docs/processed/process-extension-requirements-history/SKILL.md), [기존 구조 문서](../../../docs/processed/process-extension-directory-structure-history/SKILL.md), [기존 큐 문서](../../../docs/processed/process-extension-queued-input-history/SKILL.md), [기존 상태바 문서](../../../docs/processed/process-extension-status-bar-history/SKILL.md)는 `docs/processed/`에 정리 직전 본문을 보존한 비권위 Processed 기록입니다. 명세 의미 변경은 이 패키지에서 관리합니다.

<a id="미해결-차이"></a>

## 3. 미해결 차이

| 대상 | 유지하는 요구·의도 | 소스 관찰과 남은 차이 |
| --- | --- | --- |
| FR-05 큐 | 세션 대기열, 실행 전 수정·제거, 순서대로 자동 처리, 취소 후 다음 입력 처리 | `session-controller.ts`의 `queuedSends`는 메모리 큐이며 여러 입력을 병합합니다. 호스트 재시작 시 자동 재전송하지 않고 복원하는 정책은 durable 큐 요구 충족의 증거가 아닙니다. 개별 실행과 병합의 의미, 지속성·수정·제거 요구의 충족 여부는 미해결입니다. |
| 구조 명명 | 소스 디렉터리에 `webview`를 사용하지 않는 기존 규칙 | `src/webview/`와 build 입력이 존재합니다. 구조 규칙을 자동 폐기하거나 코드 이동을 승인하지 않습니다. |
| 지원 환경 | Linux/WSL MVP와 macOS·Windows 후속 지원 목표 | README에 macOS 설정·제한이 있고 Darwin 환경 보완 코드가 있습니다. 실제 Mac 지원 완료·실행 검증 또는 기존 지원 목표 변경으로 간주하지 않습니다. |
| FR-10 스냅샷 | 실행 전 기준, 변경 run만 보존, 복원 전 안전 사본, 충돌 중단 | Git diff 수집은 스냅샷·충돌 안전 복원과 다릅니다. 대응 구현 및 완료 증거는 이번 조사에서 확인하지 못했습니다. 요구사항을 유지합니다. |
| 문서 workflow | 한국어 원문 하나와 파생 Skill 노출 | `src/common/types/business-mode.ts`는 여전히 HTML·영어 Skill 쌍과 이전 동기화 메타데이터를 지시합니다. README Composer modes에도 이전 설명이 남아 있습니다. 실행 지침의 불일치는 미수정 상태입니다. |
| 실행 액션 | 입력별 실행 경로 캡처 | 영속 선택 대신 메시지별 액션으로 변경합니다. 새 계약은 아래 실행 액션 절을 따릅니다. |
| 런타임 사전 계약 | 기존의 사전 확정 항목과 완료 조건 | 아래 사전 계약 목록은 원래 설계의 요구 목록입니다. 현재 미구현 목록 또는 이미 확정된 Provider 계약의 재승인 요청으로 해석하지 않습니다. |

<a id="런타임-경로-표기"></a>

## 4. 런타임 경로 표기

- 아래 `<runtime-home>`은 workspace Extension Host의 `AGENT_FACTORY_HOME` 또는 `~/.agent-factory`입니다.
- `exec.py init --project-root <project-root>`가 반환하는 home/projectId/agentsRoot를 사용합니다. 클라이언트가 프로젝트 ID나 checkout-local 저장 경로를 추측하지 않습니다.
- 이전 `<project-root>/.agent-factory/agent/` 표기는 역사 자료에만 보존합니다. 이는 저장 경로 정정이며 세션·실행의 소유권이나 지속성 요구를 변경하지 않습니다.

<a id="제품-요구사항"></a>

## 5. 제품 요구사항

- 다음 목적·기능·품질·완료 조건은 기존 요구사항을 이어받습니다. 항목이 있다는 사실은 구현 완료를 뜻하지 않습니다.

<a id="목적"></a>

## 6. 목적

- 여러 Codex CLI 터미널을 직접 열고 관리하는 대신, 독립된 Main Agent 세션을 VS Code 편집기 탭의 채팅 UI로 동시에 사용할 수 있는 확장 하나를 제공한다.

- 이 확장은 Agent Factory를 대체하지 않는다. 설치된 Agent Factory 플러그인의 관리형 런타임을 사용하며, 메인 에이전트에 대한 VS Code 전용 UI/UX를 제공한다.

<a id="핵심-개념"></a>

## 7. 핵심 개념

- 편집기 채팅 탭 하나는 Main Agent 하나와 Codex 세션 하나에 대응한다.
- 여러 채팅 탭을 열어 여러 Main Agent를 병렬로 사용할 수 있다.
- Main은 사용자에게 노출되는 전문 역할 선택지가 아니다. 런타임 호환을 위해
  내부적으로만 `role: main`을 사용한다.
- Codex CLI는 화면에 노출되는 TUI가 아니라 백그라운드 실행 엔진이다.
- Main Agent별 프로세스, 환경, 세션과 실행 상태는 독립된다.
- Main Agent들은 현재 프로젝트 루트와 파일을 공유한다. Git worktree나 파일
  복제로 격리하지 않는다.
- 운영 상태의 기준 저장소는
  `<runtime-home>/projects/<project-id>/agents/<agent-id>/`이다.

<a id="제품-및-책임-경계"></a>

## 8. 제품 및 책임 경계

<a id="vs-code-확장"></a>

### 8.1. VS Code 확장

- Main Agent 채팅 편집기 탭을 렌더링한다.
- 사용자 입력, 첨부, 승인, 설정, 알림과 VS Code 편집기 통합을 제공한다.
- Agent Factory Runtime의 명령과 이벤트를 UI 프로토콜로 변환한다.
- 자체 에이전트 런타임이나 별도 로그인 체계를 만들지 않는다.

<a id="익스텐션이-소비하는-플러그인-계약"></a>

### 8.2. 익스텐션이 소비하는 플러그인 계약

- 필수 의존성이다.
- `skills/agent/scripts/exec.py`가 세션, 실행, 취소, 복원과 기록의 단일 제어
  경로다.
- `submit`, `send`, `list`, `status`, `result`, `inbox`, `cancel`, `reconcile`
  계약을 사용한다.
- 세션과 실행 상태를 `<runtime-home>/projects/<project-id>/agents/`에 저장한다.

<a id="웹-workspace"></a>

### 8.3. 웹 Workspace

- Main을 포함한 전체 에이전트를 관리하는 별도 웹 제품이다.
- VS Code 확장에 Workspace, Kanban, Dashboard 또는 다중 에이전트 관리 화면을
  복제하지 않는다.
- 두 UI는 같은 Agent Factory 런타임 상태를 읽을 수 있어야 한다.

<a id="기능-요구사항"></a>

## 9. 기능 요구사항

<a id="fr-01-채팅-편집기-탭"></a>

### 9.1. FR-01. 채팅 편집기 탭

- 채팅은 사이드바나 하단 패널이 아니라 VS Code 편집기 영역에 Webview 탭으로
  열린다.
- 파일과 터미널처럼 탭 이동, 분할, 닫기와 다시 열기를 지원한다.
- Main Agent별 채팅 탭과 상태가 섞이지 않아야 한다.
- 채팅 탭을 닫아도 Agent 실행과 입력 대기열은 유지되어야 한다.
- 탭을 닫는 동작은 취소나 Archive로 해석하지 않는다.

<a id="fr-02-새-세션과-resume"></a>

### 9.2. FR-02. 새 세션과 Resume

- 별도의 `New` 버튼이나 상시 세션 관리 목록을 제공하지 않는다.
- Resume로 기존 세션을 선택하지 않은 채팅 탭은 새 Main Agent 세션으로
  시작한다.
- 첫 메시지를 제출할 때 새 Agent Factory 세션을 생성한다.
- `Resume`은 현재 프로젝트의 `<runtime-home>/projects/<project-id>/agents/`에 저장된 Main Agent
  세션만 VS Code 선택창에 표시한다.
- 선택한 Agent ID와 Codex Session ID를 명시적으로 사용한다.
- `resume --last`처럼 세션을 추측하지 않는다.
- 세션 이름 변경과 Archive/Unarchive를 지원한다.
- 영구 삭제와 이전 메시지 수정에 따른 Fork는 제공하지 않는다.

<a id="fr-03-런타임-연결"></a>

### 9.3. FR-03. 런타임 연결

- 확장은 Agent Factory 플러그인 설치 여부, `agent` Skill, `exec.py`, Python과
  Codex CLI 가용성을 진단해야 한다.
- 필수 구성요소가 없거나 호환되지 않으면 실행을 차단하고 설치 또는 수정
  안내와 다시 확인 동작을 제공한다.
- Codex CLI를 별도의 직접 제어 경로로 실행하지 않는다.
- 실행 이벤트를 실시간으로 읽고 탭이 다시 열리면 유실 없이 복원한다.
- 동일 Codex 세션에서 동시에 두 turn을 실행하지 않는다.
- Agent별 백그라운드 실행 환경은 독립하고 프로젝트 파일은 공유한다.

<a id="fr-04-응답-타임라인"></a>

### 9.4. FR-04. 응답 타임라인

- 다음 이벤트를 하나의 시간순 타임라인에 표시한다.
  - 사용자 및 Main Agent 텍스트
  - 진행 상태
  - 셸 명령과 출력
  - 파일 변경
  - 도구 호출과 결과
  - 계획 변경
  - Work 및 Verification Agent dispatch와 진행 상태
  - 승인 요청
  - 오류, 취소와 완료
- 긴 도구 출력은 요약 상태로 시작하며 사용자가 펼칠 수 있어야 한다.
- Agent Factory의 계획·작업·검증 및 런타임 관리 스크립트 호출과 Skill 문서 읽기는 전용 카드로 구분한다. 셸 래퍼·Python 옵션·복수 호출도 식별 가능한 범위에서 적용하며, 실제 실행 위치가 아닌 인용 예시는 실행으로 분류하지 않는다.
- Agent나 실행 식별자가 없는 관리 명령도 Agent Factory 호출 카드로 표시하되 식별자·상태를 추측하지 않는다. 원본 명령, 혼합 출력과 오류는 카드 안에 보존한다.
  - 근거: Human 요청 `run-20260917T183411720327Z-30c9041f` (2026-09-18 KST).
- Main Agent가 호출한 Work와 Verification Agent는 별도 채팅 탭으로 만들지 않고
  Main 타임라인의 dispatch 카드로 표시한다.
- 상태바에는 현재 실행 중인 Work 및 Verification Agent 수를 역할별로 표시하고,
  활성 Agent가 있으면 시각적으로 강조한다.
- Markdown, 코드 블록과 표를 안전하게 렌더링한다.
- 모델이 생성한 HTML을 신뢰해 직접 삽입하지 않는다.

<a id="fr-05-입력과-실행-제어"></a>

### 9.5. FR-05. 입력과 실행 제어

- Enter는 전송, Shift+Enter는 줄바꿈으로 동작한다.
- IME 조합 중 Enter는 전송하지 않는다.
- 실행 중에도 추가 메시지를 제출할 수 있다.
- 추가 메시지는 현재 실행을 암묵적으로 취소하지 않고 세션 대기열에 저장한다.
- 대기 메시지는 실행 전까지 수정하거나 제거할 수 있어야 한다.
- 현재 실행이 끝나면 다음 대기 메시지를 순서대로 자동 처리한다.
- 실행 중 `Esc`는 현재 실행만 취소한다.
- 취소가 끝나면 다음 대기 메시지를 자동 처리한다.
- 화면의 중지 버튼도 `Esc`와 같은 동작을 제공한다.

<a id="fr-06-승인"></a>

### 9.6. FR-06. 승인

- 파일 수정, 명령 실행 또는 권한 확장이 승인을 요구하면 채팅 카드로 표시한다.
- 사용자는 채팅에서 승인 또는 거절할 수 있어야 한다.
- 승인 대기 중인 실행 상태를 명확히 표시한다.
- 승인 결과와 근거를 해당 run 기록에 남긴다.
- Webview가 승인 정책을 우회하거나 직접 시스템 권한을 갖지 않는다.

<a id="fr-07-실행-설정"></a>

### 9.7. FR-07. 실행 설정

- 모델과 추론 강도는 하나의 설정창에서 Main·Work·Verification별로 지정한다. 기존 모델·추론 선택은 Main 값으로 유지하며 자식 역할의 미지정 값은 런타임 기본값을 사용한다. Plan은 Work 설정을 사용한다.
- 모델 설정창은 세 역할을 내부 스크롤 없이 표시하고, 선택 상자의 포커스는 주황색 기본 강조 대신 UI의 파란 강조색을 사용한다.
- 자식 역할 설정은 요청에 캡처하고, 서로 다른 자식 역할 설정의 대기 요청을 병합하지 않는다. 작업·검증 루프는 최초 호출과 수정·재검증에 역할별 모델·추론 강도를 전달한다.
- 근거: Human 요청 `run-20260917T184345063796Z-77646fcc` (2026-09-18 KST).

- 모델, 추론 수준, Fast 설정, Goal 제출, 샌드박스와 승인 정책을 조정할 수 있어야
  한다.
- Fast 모드는 세션 단위로 유지되는 On/Off 설정이다.
- Goal은 일회성 제출 버튼이다. 현재 작성기 텍스트를 목표로 즉시 전송하고 다음 일반 전송에는 적용하지 않는다. 이전 목표로 암묵적으로 대체하지 않는다.
- Goal 버튼을 Fast 버튼 앞에 배치한다. Fast는 유지되는 On/Off 설정이다.
- Goal 목표는 공백 제거 후 1~4,000자여야 한다. 빈 입력·이미지만 있는 입력·상한 초과 입력은 수정 안내와 함께 보존하며 제출하지 않는다.
- 워크플로우 항목(Interview·Planning·Design)을 누르면 현재 입력을 그 방식으로 즉시 한 번 제출한다. 일반 전송은 Normal이며, 중복되는 Normal 항목은 메뉴에 표시하지 않는다. 이전 선택을 저장하거나 복원하지 않는다. 대기열에는 각 제출 시의 워크플로우를 보존한다.
- Goal은 Main 및 런타임 capability가 지원하는 요청에만 적용하며 Verification에서는 제외한다. 네이티브 목표 상태는 제출 설정을 변경하지 않는다.
- 근거: Human 요청 `run-20260917T185148018204Z-48443db7` (2026-09-18 KST).
- 기존 네이티브 목표의 상태·제어는 유지하되 목표나 오류 상태가 없으면 빈 패널을 표시하지 않습니다.
- 모델과 지원 옵션은 하드코딩하지 않고 현재 Codex 런타임 capability를
  기준으로 제공한다.
- 설정 범위와 우선순위는 다음과 같다.
  1. 세션 설정
  2. 현재 프로젝트 기본값
  3. Codex 전역 기본값
- 세션 설정은 해당 Main Agent에만 적용하며 Resume 후에도 유지한다.
- 프로젝트 기본값은 VS Code 확장과 웹 Workspace가 함께 읽을 수 있는 Agent
  Factory 런타임 설정에 저장한다.
- UI는 각 값의 현재 값과 출처를 표시하고 상위 기본값으로 복원할 수 있어야 한다.

<a id="fr-08-첨부"></a>

### 9.8. FR-08. 첨부

- 클립보드 이미지 붙여넣기와 미리보기를 지원한다.
- 운영체제 파일 탐색기와 VS Code Explorer에서 파일 및 폴더 DnD를 지원한다.
- 열린 편집기 파일, 여러 파일과 여러 폴더를 첨부할 수 있어야 한다.
- 파일 및 폴더 선택 버튼을 제공한다.
- `+` 버튼은 여러 파일을 고를 수 있는 파일 선택 창을 연다. 파일·폴더 동시 선택으로 폴더 전용 창이 열리지 않도록 한다. 폴더 첨부는 DnD를 유지한다. SSH 환경에서는 VS Code의 원격 파일 선택 동작을 따른다.
- 첨부 항목은 작성기에 칩으로 표시하며 개별 제거할 수 있어야 한다.
- 전송 후 사용자 메시지에도 파일·폴더 이름을 표시하고, 이미지는 기존 미리보기를 유지한다.
- 폴더는 전체 내용을 복제하지 않고 경로 참조로 전달한다.
- 현재 프로젝트 외부의 파일과 폴더도 명시적 첨부로 사용할 수 있다.
- 프로젝트 외부 경로는 기본 읽기 전용이며 쓰기는 별도 승인을 요구한다.
- 첨부 개수, 크기, 형식과 경로를 검증하고 사용자에게 구체적인 오류를 표시한다.
- 선택 코드 또는 파일의 `Add to Chat`을 보조 기능으로 제공한다.
- DnD를 주 첨부 흐름으로 최적화한다.

<a id="fr-09-vs-code-코드-통합"></a>

### 9.9. FR-09. VS Code 코드 통합

- 응답의 프로젝트 파일 경로와 줄 번호를 클릭하면 편집기에서 연다.
- 외부 파일 링크는 허용 경로를 검증한 뒤 연다.
- 변경된 파일 목록을 표시하고 VS Code Diff 화면으로 연결한다.
- Main Agent가 만든 변경과 실행 전 상태를 비교할 수 있어야 한다.

<a id="fr-10-자동-스냅샷과-복원"></a>

### 9.10. FR-10. 자동 스냅샷과 복원

- 각 실행 직전에 임시 기준 상태를 안전하게 생성한다.
- 실행에서 파일 변경이 발생한 경우에만 기준 상태를 정식 스냅샷으로 보존한다.
- 파일 변경이 없으면 임시 기준 상태를 폐기한다.
- 특정 run의 실행 전 상태와 현재 상태를 Diff로 확인할 수 있어야 한다.
- 사용자는 특정 스냅샷으로 복원할 수 있어야 한다.
- 복원 직전에 현재 상태를 다시 복구 가능한 스냅샷으로 남긴다.
- 스냅샷 이후 사용자 변경과 충돌하면 자동 덮어쓰지 않고 복원을 중단해 충돌
  파일을 표시한다.
- `git reset --hard`처럼 작업 트리를 무조건 덮어쓰는 방식은 사용하지 않는다.
- Git 프로젝트에서는 브랜치나 HEAD를 이동하지 않는 Git 객체 또는 패치 기반
  구현을 우선한다.

<a id="fr-11-알림"></a>

### 9.11. FR-11. 알림

- 닫힌 탭의 실행이 완료, 실패하거나 승인을 기다리면 VS Code 알림을 표시한다.
- 알림을 선택하면 정확한 Main Agent 채팅 탭을 열거나 복원한다.
- 활성 탭에서 이미 확인 중인 상태를 중복 알림하지 않는다.

<a id="fr-12-상태바"></a>

### 9.12. FR-12. 상태바

- 채팅 하단에 고정 상태바를 제공한다.
- 공식 Codex 확장의 실행 위치 선택 바(`로컬에서 작업`)는 제공하지 않는다.
- 실행 위치는 현재 프로젝트의 Agent Factory 로컬 런타임으로 고정한다.
- 사용자는 상태바 항목의 표시 여부와 순서를 조정할 수 있다.
- 상태바 자체의 위·아래 위치 변경은 제공하지 않는다.
- 후보 항목에는 Agent 이름, 실행 상태, 활성 Work/Verification 수, 모델, 추론 수준,
  Fast, Goal, 프로젝트, Git
- 브랜치, 컨텍스트 사용량, 실행 시간, 대기 메시지 수와 런타임 상태가 포함된다.

<a id="fr-13-인증"></a>

### 9.13. FR-13. 인증

- 별도 로그인, API key 또는 토큰 관리 UI를 만들지 않는다.
- 기존 Codex CLI 인증 상태를 그대로 사용한다.
- 확장과 Webview는 인증 비밀을 읽거나 저장하지 않는다.
- 미로그인 상태에서는 Codex CLI 로그인이 필요하다는 안내만 제공한다.

<a id="품질-및-보안-요구사항"></a>

## 10. 품질 및 보안 요구사항

- Extension Host가 파일 시스템, 프로세스와 VS Code API를 소유한다.
- Webview는 렌더링과 입력만 담당하며 모든 메시지는 allowlist schema로 검증한다.
- Webview에는 nonce 기반 Content Security Policy를 적용한다.
- 외부 경로, 파일 링크와 DnD payload는 정규화하고 symlink 및 traversal을
  검증한다.
- 대용량 메시지, 첨부와 도구 출력에 명시적인 상한을 둔다.
- 한 Agent의 실패나 취소가 다른 Agent 세션에 영향을 주지 않아야 한다.
- 탭이 닫혀도 런타임 이벤트를 지속적으로 수집해야 한다.
- 런타임 상태 파일을 UI가 임의 수정하지 않고 공식 런타임 계약을 사용한다.
- 밝은/어두운/고대비 테마, 키보드 탐색, 스크린 리더와 reduced motion을
  지원한다.
- 핵심 상태 전이, Resume, 큐, 승인, 첨부, 설정 우선순위, 이벤트 복원과
  스냅샷 안전성을 자동화 테스트한다.

<a id="지원-범위"></a>

## 11. 지원 범위

<a id="mvp"></a>

### 11.1. MVP

- Linux
- Linux에서 실행되는 VS Code Remote WSL Extension Host

<a id="후속"></a>

### 11.2. 후속

- macOS: Darwin/launchd containment adapter가 Agent Factory Runtime에 추가된 후
- Windows 및 Git Bash: Windows Job Object containment adapter가 추가된 후

- 지원되지 않는 환경에서는 capability 진단 결과와 이유를 표시하고 Main Agent 실행을 시작하지 않는다.

<a id="제외-범위"></a>

## 12. 제외 범위

- Agent Factory 웹 Workspace의 VS Code 확장화
- Work 및 Verification Agent 관리 화면
- Kanban, Dashboard, Document 또는 Artifact 관리
- Cloud/Local 실행 위치 전환
- Codex TUI 표시 또는 터미널 탭 관리
- 별도 인증 및 계정 관리
- 세션 영구 삭제
- 이전 메시지 수정 기반 Fork
- Agent별 Git worktree 또는 프로젝트 파일 격리

<a id="mvp-완료-조건"></a>

## 13. MVP 완료 조건

- Agent Factory 플러그인이 설치된 Linux/WSL 프로젝트에서 채팅 편집기 탭을
  열 수 있다.
- 여러 Main Agent 탭이 서로 독립적으로 병렬 실행된다.
- 새 세션, 명시적 Resume, 스트리밍, 승인, 큐, `Esc` 취소와 백그라운드 알림이
  동작한다.
- 탭을 닫았다 다시 열어도 세션과 진행 상태가 복원된다.
- 이미지·파일·폴더 DnD와 프로젝트 외부 읽기 전용 첨부가 동작한다.
- 파일 링크, 변경 목록과 Diff가 VS Code 편집기에 연결된다.
- 파일 변경 run만 스냅샷을 남기고 충돌 없는 복원이 가능하다.
- 전역, 프로젝트와 세션 설정 우선순위가 일관되게 적용된다.
- 상태바 항목을 선택하고 순서를 변경할 수 있다.
- 단위, 통합, Extension Host E2E와 패키징 검증이 통과한다.

<a id="익스텐션-구현에-필요한-런타임-연동-계약"></a>

## 14. 익스텐션 구현에 필요한 런타임 연동 계약

- Main 세션의 대화 기록과 이벤트 pagination 계약
- 승인 요청과 승인 응답의 비동기 프로토콜
- 세션 입력 대기열의 durable schema와 처리 순서
- 프로젝트 기본 설정의 저장 위치와 schema
- Archive/Unarchive 및 사용자 표시 이름 명령
- 파일 변경 감지, 스냅샷과 복원 명령
- 외부 읽기 전용 경로 전달 계약
- 모델 및 실행 capability 조회 명령
- macOS와 Windows containment adapter 경계

<a id="메시지별-실행-액션"></a>

## 15. 메시지별 실행 액션

- 2026-09-18 KST Human 요청으로 영속 작업 모드와 자동 기본값을 대체합니다. 이전 정책은 Git 이력과 기존 Processed 출처에 보존합니다.
- 일반 Enter·전송은 항상 Main 직접 실행입니다. 과거 저장된 모드는 다음 입력에 적용하지 않습니다.
- 실행 액션 아이콘은 서로 구별하며, Plan은 문서·목록 아이콘으로 Work의 공구 아이콘과 구별한다.
- 작성기 메뉴의 Work, Plan, Verification, Plan·Work, Work·Verification, Plan·Work·Verification은 현재 초안·첨부를 즉시 Main으로 보내는 일회 액션입니다.
- Plan 단독은 실제 Work Plan 협업 모드에서 계획만 작성합니다. Plan·Work 계열은 동일 Work 세션에서 Plan→실행으로 전환합니다. 실패·취소·미해결 Human 결정에서는 구현을 시작하지 않습니다.
- Work는 관리형 Work를 실행합니다. Work·Verification 계열은 같은 Work·Verification 세션으로 수정·재검증합니다.
- 독립 Verification은 관리형 Verification을 실행합니다. 명시 대상, 현재 채팅의 이전 완료 작업 순서로 대상을 정하고 불명확하면 질문합니다. Main inspectionOnly 검사로 대체하거나 Work 루프 receipt를 만들지 않습니다.
- 액션은 각 큐 입력에 캡처하고 서로 다른 액션은 병합하지 않습니다. 업무 모드·Goal·첨부·권한은 기존 계약을 유지합니다.
- 런타임 capability가 없는 액션은 거부합니다. 자세한 계약은 [실행 액션 설계](../design-auto-execution-mode/SKILL.md)를 따릅니다.

<a id="목표-소스-배치"></a>

## 16. 목표 소스 배치

- 아래 트리는 기존 설계의 책임 배치 목표입니다. 현재 파일 목록이 아니며, 트리 안의 옛 docs 파일명은 당시의 경로 기록이며 현재 파일 위치가 아닙니다. 역사 본문은 `docs/processed/other-*-history/SKILL.md`에 보존합니다. 현재 명세 패키지 경로는 이 문서 상단의 링크를 기준으로 합니다. 없는 파일·폴더를 이번 정리에서 만들지 않습니다.

```text
extension/
├── .backup/                         # 레거시 보존; 빌드/패키징 제외
├── .vscode/
│   ├── launch.json                  # Extension Development Host
│   └── tasks.json
├── docs/
│   ├── requirements.md
│   ├── directory-structure.md
│   └── protocol.md
├── src/
│   ├── extension.ts                 # VS Code activate/deactivate 진입점
│   ├── core/                        # 확장 전체의 조립과 구동
│   │   ├── bootstrap.ts
│   │   ├── container.ts
│   │   ├── lifecycle.ts
│   │   └── config/
│   │       ├── types.ts
│   │       ├── defaults.ts
│   │       └── resolver.ts
│   ├── common/                      # 계층/기능에 종속되지 않는 공통 요소
│   │   ├── types/
│   │   ├── errors/
│   │   ├── events/
│   │   └── contracts/
│   ├── modules/                     # 사용자 기능 단위
│   │   ├── agent/
│   │   ├── session/
│   │   ├── run/
│   │   ├── chat/
│   │   │   ├── chat-state.ts
│   │   │   ├── session-controller.ts
│   │   │   └── message-queue.ts
│   │   ├── resume/
│   │   ├── approval/
│   │   ├── attachment/
│   │   ├── snapshot/
│   │   └── settings/
│   ├── infrastructure/              # 외부 시스템 adapter
│   │   ├── agent-factory/
│   │   │   ├── plugin-locator.ts
│   │   │   ├── capability-client.ts
│   │   │   ├── agent-client.ts
│   │   │   ├── event-reader.ts
│   │   │   └── contracts.ts
│   │   ├── vscode/
│   │   │   ├── chat-panel-manager.ts
│   │   │   ├── chat-panel-serializer.ts
│   │   │   ├── chat-template-renderer.ts
│   │   │   ├── configuration-store.ts
│   │   │   ├── resume-picker.ts
│   │   │   ├── attachments.ts
│   │   │   ├── notifications.ts
│   │   │   ├── file-links.ts
│   │   │   └── diff-view.ts
│   │   └── filesystem/
│   └── protocol/                    # Extension Host ↔ 채팅 화면 계약
│       ├── host-to-client.ts
│       ├── client-to-host.ts
│       └── validator.ts
├── templates/
│   └── chat.html                    # CSP/nonce/resource URI 주입 템플릿
├── static/
│   ├── css/
│   │   └── chat.css
│   ├── js/
│   │   └── chat.js
│   ├── images/
│   └── fonts/
├── dist/
│   └── extension.js                 # Extension Host 번들
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── scripts/
│   ├── build.mjs
│   └── verify-vsix.mjs
├── .gitignore
├── .vscodeignore
├── package.json
├── package-lock.json
└── tsconfig.json
```

- 빈 디렉터리는 실제 구현이 시작될 때 생성한다. 위 트리는 책임의 목표 위치를 나타내며, 빈 폴더를 유지하기 위한 placeholder 파일은 만들지 않는다.

<a id="편집기-탭-생명주기"></a>

## 17. 편집기 탭 생명주기

```text
채팅 열기
  ├── Resume 없음 ──> unbound chat tab ──첫 submit──> Agent ID 바인딩
  └── Resume 선택 ──> 기존 Agent ID에 즉시 바인딩

탭 닫기 ──> WebviewPanel dispose
              └── Agent Runtime 실행과 메시지 큐는 유지

알림/Resume ──> 같은 Agent ID의 기존 탭 reveal 또는 새 탭 복원
```

- 탭 하나는 Main Agent 하나이며 Agent Factory 세션 하나에 대응한다.
- 하나의 Agent ID에 활성 편집기 탭을 중복 생성하지 않는다.
- `WebviewPanelSerializer`를 등록하여 VS Code 재시작 시 화면을 복원한다.
- 복원 판단의 기준은 화면 캐시가 아니라 런타임의 durable 상태다.
- 탭이 닫혀도 Extension Host는 실행 완료·실패·승인 요청 알림을 처리한다.

<a id="초기-구현-순서"></a>

## 18. 초기 구현 순서

1. TypeScript Extension Host 셸, 템플릿과 정적 채팅 화면을 구성한다.
2. 편집기 탭 manager와 `WebviewPanelSerializer`를 구현한다.
3. Agent Factory 플러그인 탐색과 capability/version 진단을 구현한다.
4. 새 Main submit, Resume, 이벤트 복원과 탭 identity를 구현한다.
5. 타임라인, 작성기, 메시지 큐와 `Esc` 취소를 구현한다.
6. 승인 프로토콜과 세션/프로젝트/전역 설정 범위를 연결한다.
7. 이미지·파일·폴더 DnD 및 외부 읽기 전용 경로를 구현한다.
8. 파일 링크, 변경 목록과 VS Code Diff를 연결한다.
9. 런타임 스냅샷/복원 계약을 구현하고 화면을 연결한다.
10. 구성 가능한 하단 상태바와 백그라운드 알림을 완성한다.
11. Linux/WSL E2E 및 VSIX 패키징을 검증한다.

<a id="큐-상세-기록"></a>

## 19. 큐 상세 기록

- 당시 출처 경로는 `docs/queued-input.md`이며 현재 보존 위치는 [대기 메시지 이전 기록](../../../docs/processed/process-extension-queued-input-history/SKILL.md)입니다. 병합 정책과 실패·복구 조건을 보존합니다. FR-05와 충돌하는 지속성·실행 단위는 위 미해결 차이를 따릅니다. 과거 Work의 실행 여부와 당시 Main 확인 요청은 역사 문서에 보존하며 현재 검증 결과로 옮기지 않습니다.

- 실행 중 입력은 원래 순서와 개별 메시지 ID를 유지하여 보관합니다. 전송 동작은 현재 실행을 중지하거나 런타임에 추가 지시를 보내지 않습니다.
- 현재 작업이 끝나면 그때까지 받은 대기 메시지 중 연속된 동일 액션만 **하나의 요청으로 병합하여 한 번 실행**합니다. 액션이 달라지면 다음 묶음으로 분리합니다. 이미 받은 입력의 첨부 준비까지 기다린 뒤 묶음을 확정합니다.
- 병합 접수를 시작한 뒤 새로 들어온 입력은 다음 묶음에 포함합니다. 유휴 상태의 단일 입력은 기존처럼 단독으로 처리합니다.
- 진행 표시줄 오른쪽 **대기 N** 버튼은 원래 메시지 수를 표시합니다. 접수 후에는 병합된 큰 메시지 대신 원래 메시지들을 순서대로 각각 대화에 표시합니다.
- 빈 입력창의 중지 버튼과 Esc는 현재 실행만 중지합니다.

<a id="병합-내용과-설정"></a>

### 19.1. 병합 내용과 설정

| 항목 | 정책 |
| --- | --- |
| 본문 | 메시지별 번호·시작·끝 경계로 원래 순서를 보존합니다. |
| 첨부 | 각 메시지 구간에 첨부 참조를 포함하고, 파일·폴더·이미지 전체를 원래 순서대로 전달합니다. 첨부만 있는 입력도 유지합니다. |
| 액션·모델·추론·Fast | 같은 액션만 병합하며 모델·추론·Fast는 묶음의 첫 메시지에 저장된 설정을 적용합니다. 뒤의 메시지 설정으로 덮어쓰지 않습니다. |
| 명시 실행 권한 | `workspace-write` → `danger-full-access` → `bypass` 순서 중 더 제한적인 권한을 적용합니다. 앞의 두 값은 Human 승인 정책을 `required`로 유지합니다. |
| 상속 권한 | 전부 상속(`cli-default` 또는 생략)이면 기존 세션 정책을 유지합니다. 명시 권한과 섞이면 읽기 전용 가능성 등을 추정하지 않고 병합 접수를 중단합니다. |
| 실행 주체·검증 대상 | `actor`와 `verifiedWorkRunId`가 모두 일치해야 합니다. 불일치하면 원래 입력들을 복원 가능한 상태로 남깁니다. |
| Goal | Goal 제출 여부 또는 목표가 다르면 다음 묶음으로 분리하여 각 제출의 목표를 보존합니다. 같은 목표의 Goal 제출끼리만 병합합니다. |

- 권한·주체·검증 대상의 병합이 불가능하면 이유를 표시하고, 원래 메시지마다 **입력창으로 복원**을 제공합니다. 같은 권한 또는 원래 대상별로 다시 입력할 수 있습니다. 일부 메시지만 임의로 실행하지 않습니다.
- 실행 권한은 호스트 수신 시, 나머지 설정·첨부는 각 입력 시점에 보관합니다. 복원할 때도 원래 개별 설정과 첨부를 사용합니다.
- 병합 이미지도 기존 런타임의 이미지 수·크기 한도를 따릅니다. 한도를 넘으면 이미지를 버리거나 묶음을 임의 분할하지 않고 원래 입력들의 복원을 제공합니다.

<a id="종료연결실패-정책"></a>

### 19.2. 종료·연결·실패 정책

| 상황 | 처리 |
| --- | --- |
| 현재 실행 완료·실패·명시적 취소 결과 확인 | 보관된 메시지를 한 묶음으로 실행합니다. |
| 사용자 결정 필요 | 대기열을 유지합니다. 승인 버튼이나 새 답변을 먼저 단독 처리하고, 그 실행 종료 후 대기 메시지를 병합합니다. |
| 상태 조회·연결 실패 | 실행 종료를 추정하지 않습니다. 현재 실행 ID와 원래 입력·완료 대기를 보존합니다. 재연결 후 한 번만 병합 접수합니다. |
| 병합 요청 접수 확인 실패 | 자동 재전송하지 않습니다. 해당 묶음의 모든 원래 입력을 복원할 수 있습니다. 접수 여부가 불명확하면 실행 기록을 먼저 확인해야 합니다. |
| 접수 후 연결 실패 | 원래 메시지는 이미 표시된 상태로 유지하고 기존 실행에 재연결합니다. 같은 묶음을 다시 제출하지 않습니다. |
| 화면 재연결 | 호스트가 원래 메시지별 접수 알림을 재전달하며 ID로 중복 표시를 방지합니다. |
| 확장 호스트 재시작 | 화면에 저장된 입력은 보존하되 자동 재전송하지 않습니다. 메모리 큐를 잃은 항목은 입력창으로 복원할 수 있습니다. |

- 대기 입력을 추가해도 현재 실행의 시작 시간·진행 표시·하위 에이전트 목록은 초기화되지 않습니다.
- 같은 메시지 ID의 중복 수신은 다시 제출하지 않습니다. 접수 알림과 화면 목록은 패널 단위입니다.
- 프로세스 종료를 넘는 런타임 제출의 원자적 중복 제거는 제공하지 않으므로 접수 여부가 불명확한 요청은 자동 재시도하지 않습니다.

<a id="후속-소스-관찰"></a>

### 19.3. 후속 소스 관찰

- `session-controller.ts`는 inspection 요청과 구현 요청의 경계에서 묶음을 나누며 순서를 유지합니다. inspection이 다른 메시지의 구현 경로를 상속하지 않습니다.
- `mergePendingSends`는 원래 메시지별 workflow 지침을 본문 경계 안에 유지하고 병합 바깥의 workflow는 normal로 둡니다.
- 권한 표의 `required`는 Human 승인 정책입니다. `agent-client.ts`의 실행 승인 정책 `--approval-policy never`와 별개입니다. bypass만 Human 정책을 bypass로 전달합니다.
- 위 내용은 현 소스의 관찰이며 새 권한 부여 또는 원래 큐 요구사항의 변경 승인이 아닙니다.

<a id="상태바-상세-기록"></a>

## 20. 상태바 상세 기록

- 당시 출처 경로는 `docs/status-bar.md`이며 현재 보존 위치는 [상태바 이전 기록](../../../docs/processed/process-extension-status-bar-history/SKILL.md)입니다. 표시·정렬·호환 의도와 데이터 출처·한계를 보존합니다. 아래 Processed 조사 문구와 조사일은 실제 출처를 나타냅니다. 외부 API에 관한 설명을 이번에 새로 확인하거나 전체 API를 명세로 채택한 것은 아닙니다.

- 채팅 하단의 톱니바퀴 SVG 버튼(**상태 표시줄 설정**)에서 표시할 정보를 선택합니다. 선택된 항목은 목록 위쪽에 현재 표시 순서로 나타납니다. 목록에서 위·아래 방향으로, 상태 표시줄에서는 좌·우 방향으로 드래그하면 대상 항목 앞이나 뒤의 삽입 위치가 표시됩니다. 놓는 즉시 화면에 반영됩니다. 목록의 **앞으로·뒤로** 버튼 또는 상태 항목의 **Alt+왼쪽/오른쪽**으로도 이동할 수 있습니다. Escape로 설정을 닫으면 설정 버튼으로 포커스가 돌아옵니다.

- 선택 항목과 순서는 `agentFactory.mainChat.statusItems` 배열로 저장합니다. 작업 영역이 있으면 Workspace, 없으면 Global 범위를 사용합니다. 열린 채팅에는 설정 변경 이벤트를 반영하고, 복원 시에는 VS Code 설정을 웹뷰 캐시보다 우선합니다. 빈 배열은 모든 정보를 숨기며 설정 버튼은 유지됩니다. 기본값 재설정은 기존 기본 배열 `status, agents, project, branch, context, queue`를 다시 저장합니다. 기존 항목 ID는 유지하며, 중복·알 수 없는 설정 값은 정규화합니다. 잘못된 값만 있는 설정은 기본값으로 복구합니다. 웹뷰 메시지의 알 수 없는 ID와 중복은 거부합니다.

<a id="정보-목록과-근거"></a>

### 20.1. 정보 목록과 근거

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

<a id="영문-상태-문구-축약"></a>

### 20.2. 영문 상태 문구 축약

- 상태바와 설정 미리보기는 `Ctx`, `Wk`, `left`, `used`, `Verify`, `Queue`, `Calls`를 사용합니다. 예: `Ctx left 79%`, `Ctx used 54,264 tokens`, `Wk used 12.5%`, `Work 1 · Verify 2`입니다.
- 미제공 수치는 `—`로 표시하고 토큰 항목은 `tokens` 단위를 유지합니다. `Running`, `Awaiting input`, `Idle`, `Offline`과 지원 여부 `Unknown`을 구분합니다.
- 현재 컨텍스트와 누적 Goal 사용량은 각각 `Ctx used`와 `Goal used`로 구분합니다. 설정 목록의 전체 이름, 툴팁과 접근성 설명을 유지하고 프로젝트·브랜치·Agent·모델 이름은 축약하지 않습니다.
- 표시 문자열만 변경하며 항목 ID, 옵션 값, 저장 및 계산 계약은 유지합니다.

<a id="독립-선택과-기존-설정-호환"></a>

### 20.3. 독립 선택과 기존 설정 호환

- Content 잔여 비율·사용 토큰·잔여 토큰·사용 비율 및 Weekly 사용량·잔량을 각각 독립적으로 선택하고 정렬합니다. 비율과 토큰 수를 한 항목에 합치지 않습니다.
- 기존 `context`는 잔여 비율만, `contextUsed`는 사용 토큰 수만 표시하도록 변경합니다. 기존 ID·선택 순서·빈 배열·기본 배열은 그대로 유지하며 설정을 자동으로 확장하지 않습니다. 새 `contextRemainingTokens`와 `contextUsedPercent`는 설정 메뉴에서 선택합니다. 기존 `contextWindow`, `weekly`, `weeklyRemaining`도 유지합니다.
- 비율은 소수점 최대 한 자리로 표시합니다. Content 사용량이 기준을 초과하면 실제 사용률은 100%를 넘을 수 있으며 잔량은 0으로 제한합니다. 미제공 값은 0으로 대체하지 않습니다.
- `branch`는 실제 브랜치 이름만 표시합니다. 표시 접두어 `Branch`만 제거하며 Git 기능과 저장된 선택은 유지합니다.

- 소스 소유자는 `static/js/chat.js`의 카탈로그·렌더러, `src/core/config/`의 설정 정의, `src/protocol/validator.ts`의 메시지 검증, `chat-panel-manager.ts`의 설정 저장·상태 전달입니다. 사용량 근거는 `agent-client.ts`의 `readLatestTokenCount`/`readWeeklyUsedPercent`와 `NativeGoal`입니다. 새 항목을 추가할 때에는 카탈로그, 타입, package 설정 enum을 함께 갱신합니다.

<a id="현재-표시할-수-없는-정보"></a>

### 20.4. 현재 표시할 수 없는 정보

- 공식 Codex App Server는 thread 토큰 사용량 알림, 계정 rate limit 조회·알림과 reset 시각, 조건부 credit 정보, 계정 전체 사용 통계를 설명합니다. 그러나 현재 확장은 이 계정 조회 연결을 사용하지 않습니다. 따라서 비용·크레딧·단기 한도·초기화 시각·계정 전체 통계·입출력/캐시별 누적량·처리 속도를 추정하여 표시하지 않습니다. 이 항목들은 설정 UI의 미지원 안내에 포함합니다. [공식 Codex App Server 문서](https://learn.chatgpt.com/docs/app-server)

- VS Code 설정 저장 범위와 변경 이벤트는 공식 `WorkspaceConfiguration.update` 및 `workspace.onDidChangeConfiguration`을 따릅니다. [VS Code API](https://code.visualstudio.com/api/references/vscode-api#WorkspaceConfiguration)

- 웹뷰 캐시는 `getState`/`setState`로 유지하되 표시 항목은 호스트 설정을 기준으로 복원합니다. [VS Code Webview 상태 유지](https://code.visualstudio.com/api/extension-guides/webview#getstate-and-setstate)

<a id="제출-방식과-전달-지침-표시"></a>

## 21. 제출 방식과 전달 지침 표시

- Human이 승인한 메시지 렌더링 요청(2026-09-18 KST)에 따라 각 사용자 메시지에 실제 제출 시점의 워크플로우·실행 액션·Goal 여부를 보존합니다. 현재 작성기 설정이나 실행 상태에서 추측하지 않습니다.
- 일반 direct·Normal·비Goal 전송에는 추가 배지를 표시하지 않습니다. Interview·Planning·Design, Work·Plan·Verification 및 조합 액션, Goal은 해당 제출에만 표시합니다. 실행 중·완료 상태와 구분합니다.
- 관리형 제출의 시스템 준비 문맥은 실제 전송 시점에 Git 변경·추가 경로, 수집 시각과 출처를 제공합니다. 대기 요청도 전송 시점에 수집하며 파일 내용과 ignored 파일은 수집하지 않습니다. 조회 불가·비 Git·실패를 깨끗한 작업 트리로 표시하지 않습니다.
- 제출 준비에는 선택한 런타임의 Agent Skill 본문을 제공합니다. 실행 모드·런타임 상세 참조는 출처 경로만 제공하고, 해당 작업에 필요한 경우에만 읽습니다. 미첨부 참조를 이미 읽은 지침으로 표시하지 않습니다.
- 해시 기능 확인만을 위한 capability 조회와 준비 문맥의 해시 기능 필드는 사용하지 않습니다. 실행 옵션에 필요한 capability 검사는 유지합니다.
- Main과 Work는 제공된 문맥·지침을 재사용합니다. 오래된 정보, 동시 변경이나 작업의 필요에 따른 재확인은 허용하며 필수 지침·실행·권한 확인은 유지합니다.
- 작업 제출에서 요청 해시 계산·제공·일치 검사를 요구하지 않습니다. 제출자가 보낸 해시는 무시하며 그 값으로 제출을 거부하지 않습니다. 런타임의 요청 보관과 실행·결과·재시도 연결은 유지합니다. 이전 런타임이 해시 없는 제출을 거부하면 수동 계산을 추가하지 않고 호환성 제한을 알립니다.
- 시스템 준비 문맥도 기존 전달 지침 펼침 영역에 기본 접힘으로 표시합니다. 원문, 실제 작업 설명·상태·결과를 보존하며 기록 복원은 저장된 준비 문맥을 사용합니다.
- 사용자 제출 원문과 앱이 추가한 지침을 분리합니다. 실제 dispatch에서 생성한 워크플로우·요청 지침이 있으면 기본 접힘 상태의 접근 가능한 `View delivered guidance`를 제공합니다. 이는 앱 추가 지침이며 전체 Provider 프롬프트가 아닙니다.
- 대기 항목의 제출 설정, Host 수락 이벤트, 저장된 타임라인과 복원 기록에 메시지별 정보를 유지합니다. 병합 시 각 원문의 지침을 한 번만 생성하며 첨부 참조를 중복 추가하지 않습니다.
- 과거 기록에 메타데이터나 실제 지침이 없으면 현재 템플릿으로 재구성하거나 정확한 전달 내용으로 주장하지 않습니다. 저장된 값만 표시합니다. UI 기록 보존 범위를 넘는 런타임 이력을 새로 생성하지 않습니다.

<a id="작성기-아이콘의-동작-구분"></a>

## 22. 작성기 아이콘의 동작 구분

- 선택·메뉴 열기에는 펼침 화살표를 사용합니다. 워크플로우·실행 액션 메뉴를 여는 동작과 항목의 즉시 제출을 구분합니다.
- 즉시 제출하는 메뉴 항목과 Goal에는 전송 화살표를 표시합니다. Goal은 라벨을 함께 표시하고 토글 상태를 갖지 않습니다.
- Fast와 자동 스크롤은 각각 `Fast`, `Scroll` 라벨과 SVG 스위치를 표시하며 켜짐·꺼짐을 손잡이 위치와 접근성 상태로 구분합니다. 색상이나 테두리 강조만으로 상태를 전달하지 않습니다.

<a id="통합-설정과-제출-메뉴"></a>

## 23. 통합 설정과 제출 메뉴

- 모델·추론 수준·권한은 하나의 설정 패널에서 관리합니다. 모델·추론은 Agent별, 권한은 다음 메시지에 적용되는 공통 설정으로 구분합니다. 실행 중 권한 변경은 막습니다.
- 일반 전송 버튼과 Enter는 Main 직접 전송입니다. 옆의 펼침 버튼은 워크플로우·작업·Goal 그룹의 제출 메뉴를 엽니다. 항목을 누르면 현재 초안을 즉시 해당 방식으로 제출하며 선택을 다음 메시지에 유지하지 않습니다.
- 작성기에는 별도 권한·워크플로우·작업·Goal 버튼을 두지 않습니다. `Fast`, `Scroll` 스위치를 유지합니다.
- 텍스트·첨부가 모두 없으면 전송하지 않고 입력창에 필요한 내용과 간단한 입력 예시를 안내합니다. 첨부만 있는 일반 요청과 문맥상 충분한 짧은 답변을 길이 기준으로 거부하지 않습니다. Goal은 목표 텍스트가 필요합니다.
- Main은 대화·첨부까지 확인한 뒤 내용이 부족하면 부족한 항목·필요한 이유·추가 입력 예시를 구체적으로 안내합니다. 이미 제공된 내용을 다시 요구하거나 의미를 추측해 완료 처리하지 않습니다. 이 AI 판단 계약은 플러그인의 Main 프롬프트가 소유합니다.

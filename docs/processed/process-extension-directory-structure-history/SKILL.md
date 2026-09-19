---
name: extension-directory-structure-history
description: 디렉터리 설계 이전 기록을 출처와 함께 보존하는 비권위 Processed 기록입니다. 현재 명세 적용 지침이 아닙니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance:
    historical-source-path: docs/directory-structure.md
    preserved-record: docs/processed/other-directory-structure-history/SKILL.md
    captured-on: '2026-09-16'
    organization-authority: Human requested only original, processed and specification
      roots and authorized migration of these four historical records.
    fidelity: 기존 본문과 앞선 정리 안내를 보존하고 안내의 상대 링크만 새 위치에 맞게 변경했습니다.
    status: historical-snapshot
  merged-from:
  - docs/processed/other-directory-structure-history/SKILL.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  source-metadata:
    name: other-directory-structure-history
    description: 디렉터리 설계 이전 기록을 출처와 함께 보존하는 비권위 Processed 기록입니다. 현재 명세 적용 지침이 아닙니다.
    metadata:
      document-type: processed
      category: other
      domain: null
      name: directory-structure-history
      language: ko
      provenance:
        historical-source-path: docs/directory-structure.md
        preserved-record: docs/processed/other-directory-structure-history/SKILL.md
        captured-on: '2026-09-16'
        organization-authority: Human requested only original, processed and specification
          roots and authorized migration of these four historical records.
        fidelity: 기존 본문과 앞선 정리 안내를 보존하고 안내의 상대 링크만 새 위치에 맞게 변경했습니다.
        status: historical-snapshot
  renamed-from: docs/processed/other-directory-structure-history
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# 디렉터리 설계 이전 기록

- 이 패키지는 앞선 명세 정리 시 남겼던 `docs/directory-structure.md`의 이전 기록을 보존합니다. 옛 경로는 출처 식별자이며 현재 파일 위치가 아닙니다.
- 문서 유형은 Processed입니다. 역사 기록이라는 상태는 네 번째 문서 유형이나 저장 루트가 아닙니다. `other`는 내용을 분석·판정하지 않고 보존하는 가공 기록의 범주입니다.
- 현재 요구사항과 설계의 권위는 아래 링크된 기존 Specification에 있습니다. 이번 이전은 현재 명세를 강등하거나 요구사항을 폐기하지 않습니다.
- 아래 과거 경로·목표 트리·구현 설명·확인 요청·외부 근거는 당시 기록입니다. 새 검증 결과나 현재 실행 지시로 간주하지 마십시오.

<a id="보존된-이전-문서"></a>

## 1. 보존된 이전 문서

<!-- Historical source preserved during the approved specification organization, 2026-09-16 KST. -->
> **역사 자료 — 현재 편집 원문은 [design-main-chat](../../skills/design-main-chat/SKILL.md) · [info-extension-architecture](../../skills/info-extension-architecture/SKILL.md) · [rule-extension-development](../../skills/rule-extension-development/SKILL.md)입니다.**
> 아래는 정리 직전 본문을 보존한 출처 자료이며 최신 명세의 경쟁 원본이 아닙니다. 과거 런타임 경로·구현 설명·당시 확인 요청은 현재 사실이나 검증 결과로 사용하지 마십시오. 의미 변경은 링크된 명세에서 관리합니다.

<a id="main-chat-vs-code-extension-목표-디렉터리-구조"></a>

## 2. Main Chat VS Code Extension 목표 디렉터리 구조

<a id="구조-원칙"></a>

## 3. 구조 원칙

- 저장소 루트는 하나의 VS Code 확장 패키지다.
- `core`, `common`, 기능 `modules`, 외부 연동 `infrastructure`를 구분한다.
- VS Code의 Webview API는 사용하지만 소스 디렉터리 이름으로 `webview`를 사용하지
  않는다. 화면 리소스는 `templates/`와 `static/`에 둔다.
- Agent Factory 플러그인의 런타임 코드를 복사하거나 포크하지 않는다.
- `.agent-factory/`는 확장 소스가 아니라 사용 프로젝트의 런타임 데이터다.
- 웹 Workspace 코드를 이 저장소에 포함하지 않는다.
- `.backup/`과 빌드 중간 산출물은 확장 패키지에서 제외한다.

<a id="목표-구조"></a>

## 4. 목표 구조

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

<a id="책임-경계"></a>

## 5. 책임 경계

| 영역 | 책임 | 포함하지 않는 것 |
| --- | --- | --- |
| `extension.ts` | VS Code 진입점에서 `core` 구동 및 종료 | 기능 구현과 런타임 세부사항 |
| `core` | 확장 초기화, 의존성 조립, 생명주기, 설정 병합 | 채팅 기능 세부사항, VS Code adapter 구현 |
| `common` | 여러 영역에서 공유하는 기술 중립 타입·오류·이벤트·계약 | VS Code 타입, Agent Factory JSON, 잡다한 utils |
| `modules` | 채팅, 세션, 실행, Resume, 승인, 첨부, 스냅샷, 설정 기능 | 자식 프로세스 및 VS Code API 직접 호출 |
| `infrastructure/agent-factory` | 플러그인 탐색, capability 확인, `exec.py` 호출, 이벤트 읽기와 변환 | 런타임 schema 임의 확장과 상태 파일 직접 쓰기 |
| `infrastructure/vscode` | 설정 저장소, Quick Pick, 알림, 파일 열기, Diff, DnD | Agent Factory 기능 규칙 |
| `infrastructure/filesystem` | 경로 검사와 필요한 읽기 전용 파일 접근 | 세션 상태의 우회 변경 |
| `protocol` | Extension Host와 채팅 화면 사이의 검증 가능한 메시지 계약 | DOM 객체, 함수, 검증되지 않은 payload |
| `templates` | 채팅 문서 뼈대와 안전한 리소스 placeholder | 인라인 스크립트 및 인라인 스타일 |
| `static` | 채팅 화면의 CSS, 브라우저 JS, 이미지와 폰트 | Node.js API와 Extension Host 전용 코드 |

<a id="common-승격-기준"></a>

### 5.1. `common` 승격 기준

- 한 기능에서만 사용하는 코드는 해당 `modules/<feature>/`에 둔다.
- 실제로 둘 이상의 영역에서 공유하는 기술 중립 요소만 `common/`으로 옮긴다.
- `utils.ts`, `helpers.ts` 같은 무제한 수집 파일은 만들지 않는다.
- 화면에 직렬화되는 메시지 형식은 공유되더라도 `protocol/`에 둔다.

<a id="의존-관계"></a>

## 6. 의존 관계

```text
extension.ts
    │
    ▼
  core ─────────────── 조립 ──────────────┐
    │                                     │
    ├────────> modules ───────> common    │
    │              │                      │
    └────────> infrastructure ────────────┘
                       │
                       ├── Agent Factory Runtime
                       ├── VS Code API
                       └── File System

templates/static ◄──── protocol ────► modules/chat
```

- `core`는 이 프로젝트에서 의존성 없는 도메인 계층이 아니라 확장 전체를 조립하는
  구동부다.
- `common`은 `core`, `modules`, `infrastructure`, `protocol`을 import하지 않는다.
- 모듈이 요구하는 외부 기능은 계약으로 표현하고 `infrastructure` 구현체를
  `core/container.ts`에서 연결한다.
- Agent Factory 원본 이벤트를 그대로 화면에 전달하지 않고 내부 이벤트와 protocol
  메시지로 변환한다.
- 화면에서 온 메시지는 protocol 검증 후 해당 module로 전달한다.

<a id="설정-경계"></a>

## 7. 설정 경계

- 설정 우선순위는 다음과 같다.

```text
세션 override > 프로젝트 기본값 > Codex 전역값 > 확장 fallback
```

- `core/config/types.ts`: 설정 모델
- `core/config/defaults.ts`: 확장 자체 fallback
- `core/config/resolver.ts`: 범위별 설정 병합 규칙
- `modules/settings/`: 설정 조회·변경 use case와 화면 동작
- `infrastructure/vscode/configuration-store.ts`: VS Code 프로젝트 설정 읽기·쓰기
- `infrastructure/agent-factory/`: 세션 및 Codex 전역 설정 연동
- `package.json`: `contributes.configuration` 항목 선언

- 확장은 파일이나 DB를 직접 세션 저장소로 사용하지 않는다. 세션과 실행의 영속 상태는 Agent Factory가 소유하고, 확장은 Agent Runtime 스크립트만 호출한다. 향후 Agent Factory가 내부 저장 방식으로 DB를 도입해도 이 경계는 바뀌지 않는다.

<a id="런타임-데이터-구조와의-관계"></a>

## 8. 런타임 데이터 구조와의 관계

- 확장은 열린 프로젝트의 다음 구조를 대상으로 동작한다.

```text
<project-root>/.agent-factory/
└── agent/
    └── <agent-id>/
        ├── session.json
        ├── dispatches/
        └── runs/
            └── <run-id>/
```

- `<agent-id>`는 Main Agent 채팅 탭의 durable identity다.
- `session.json`의 Codex Session ID가 Resume identity다.
- `runs/<run-id>`는 사용자 요청과 실행 결과의 durable identity다.
- 편집기 탭 ID, 화면 상태와 VS Code view column은 런타임 identity가 아니다.
- `.agent-factory/agent`가 없으면 첫 submit 시 Agent Factory Runtime이 생성한다.
- 상태 변경은 반드시 Agent Factory Runtime 명령을 사용한다.
- append-only 실행 이벤트처럼 런타임이 읽기 계약을 제공한 파일만 직접 읽을 수
  있으며, 확장이 `session.json`이나 run 파일을 직접 생성·수정하지 않는다.

<a id="편집기-탭-생명주기"></a>

## 9. 편집기 탭 생명주기

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

<a id="화면-리소스와-보안"></a>

## 10. 화면 리소스와 보안

- `templates/chat.html`에는 CSP, nonce, CSS URI, JS URI와 최소 bootstrap 값만
  안전하게 주입한다.
- 스크립트와 스타일은 인라인으로 넣지 않고 `static/js`, `static/css`에서
  `asWebviewUri`로 로드한다.
- `localResourceRoots`는 필요한 `templates/` 및 `static/` 범위로 제한한다.
- 화면 JS는 `acquireVsCodeApi()`를 통해서만 Extension Host와 통신한다.
- 파일 시스템, 자식 프로세스, 인증 정보에는 화면에서 직접 접근하지 않는다.

<a id="빌드-원격-실행과-패키징"></a>

## 11. 빌드, 원격 실행과 패키징

- `package.json.main`은 `dist/extension.js`를 가리킨다.
- `extensionKind`는 workspace 우선으로 선언하여 WSL/Remote 환경의 프로젝트와
  Agent Factory Runtime 가까이에서 Extension Host가 실행되도록 한다.
- `templates/`와 실행에 필요한 `static/` 리소스는 VSIX에 포함한다.
- `.backup/`, `docs/`, 테스트, source map, 임시 첨부와 `.agent-factory/`는 VSIX에서
  제외한다.
- Agent Factory 플러그인과 Codex CLI 바이너리는 VSIX에 중복 포함하지 않는다.
- 패키징 검증은 `package.json.main`, 템플릿, 정적 리소스와 불필요 파일 제외 여부를
  확인한다.

<a id="테스트-구조"></a>

## 12. 테스트 구조

- `unit`: config 우선순위, 공통 타입, 모듈 상태 전이, protocol 검증, 경로 검증
- `integration`: 가짜 `exec.py`와 이벤트 fixture를 이용한 submit, send, Resume,
  cancel 및 복원
- `e2e`: Extension Development Host에서 편집기 탭, serializer, DnD, 승인, Diff와
  알림 검증
- `fixtures`: 비밀값 없는 최소 Agent Factory 세션과 이벤트

- 실제 사용자 `.agent-factory/agent`나 Codex 인증 정보를 테스트 fixture로 사용하지 않는다.

<a id="초기-구현-순서"></a>

## 13. 초기 구현 순서

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

# 목표 디렉터리 구조

저장소 루트를 하나의 VS Code 확장 패키지로 사용한다. Extension Host와 Webview는
실행 환경이 다르므로 소스 경계를 분리하고, 공유되는 것은 메시지 protocol과 순수
데이터 모델로 제한한다.

```text
extension/
├── .backup/
│   └── legacy-2026-08-29/
│       ├── agents/
│       └── workspace/
├── .vscode/
│   ├── launch.json
│   └── tasks.json
├── docs/
│   ├── requirements.md
│   └── directory-structure.md
├── media/
│   └── icon.svg
├── scripts/
│   ├── ensure-dist.js
│   └── verify-vsix.js
├── src/
│   ├── extension/
│   │   ├── activate.js
│   │   ├── launcher.js
│   │   └── chat-panel.js
│   ├── chat/
│   │   └── chat-controller.js
│   ├── codex/
│   │   ├── codex-adapter.js
│   │   └── status-metadata.js
│   └── webview/
│       └── chat/
│           └── view.js
├── test/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── .vscodeignore
├── package.json
├── package-lock.json
└── README.md
```

## 책임 경계

| 디렉터리 | 책임 |
| --- | --- |
| `src/extension` | 활성화, 명령 등록, Webview panel 생명주기 |
| `src/chat` | 세션 상태와 채팅 use case, 영속화, 입력 검증 |
| `src/codex` | Codex 실행 파일 탐색, 인자 구성, 프로세스 및 이벤트 변환 |
| `src/protocol` | Extension Host와 Webview 사이 메시지 계약 |
| `src/webview/chat` | 채팅 렌더링, 작성기, 세션 전환과 로컬 UI 상태 |
| `test` | 실행 환경별 검증과 패키지 회귀 방지 |

## 의존 방향

```text
webview/chat ──protocol──> extension ──> chat ──> codex
                              │
                              └──> VS Code API
```

- `chat`과 `codex`는 Webview DOM을 알지 않는다.
- `webview`는 Node.js API나 Codex 프로세스에 직접 접근하지 않는다.
- `protocol`은 양쪽에서 사용할 수 있는 순수 데이터 계약만 가진다.
- 기능 간 순환 import를 허용하지 않는다.

현재 1차 배치에서는 채팅 상태와 검증이 `chat-controller.js`에, Codex 옵션과
프로세스 실행이 `codex-adapter.js`에 함께 있다. `src/protocol`, `session-store`,
`message-validator`, `codex-runner`, `codex-options` 분리는 동작을 바꾸지 않는
후속 리팩터링으로 진행한다.

## 현재 코드의 이동 기준

| 현재 위치 | 목표 위치 |
| --- | --- |
| `agents/src/extension.js` | `src/extension/activate.js` |
| `agents/src/launcher.js` | `src/extension/launcher.js` |
| `agents/src/agentsPanel.js` | `src/extension/chat-panel.js` |
| `agents/src/chatBackend.js` | `src/chat/chat-controller.js` 외 2개 모듈로 분리 |
| `agents/src/codexAdapter.js` | `src/codex/` 하위 모듈로 분리 |
| `agents/src/chatView.js` | `src/webview/chat/view.js`; 후속 단계에서 HTML, CSS, JS 분리 |
| `agents/src/statusMetadata.js` | 책임 확인 후 `src/chat` 또는 제거 |
| `workspace/` | `.backup/legacy-2026-08-29/workspace/`에 보존 |

## 마이그레이션 순서

1. 루트 package manifest와 테스트 명령을 단일 확장 기준으로 만든다.
2. Extension Host 모듈을 이동하고 기존 동작을 유지한다.
3. 채팅 controller, validator, session store를 분리한다.
4. Codex adapter의 옵션과 프로세스 실행 책임을 분리한다.
5. 인라인 Webview를 HTML, CSS, JavaScript 파일로 분리하고 CSP resource URI를 적용한다.
6. 테스트와 패키징 경로를 갱신한다.
7. 새 VSIX 검증 후 백업 이외의 기존 패키지 중복이 없는지 확인한다.
8. 백업된 Workspace 기능의 선택적 통합 여부를 별도 결정한다.

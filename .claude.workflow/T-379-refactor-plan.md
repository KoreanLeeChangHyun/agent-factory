# T-379 Board 전면 리팩토링 플랜

> **원칙**: 파일당 1500줄 예산, 단일 책임, 유지보수 우선, Phase 0는 로직 변경 0.

## 0. 확정 제약

### Python
- **최소 버전**: 3.10+ (3.11/3.12 전용 기능 금지 — `tomllib`, `typing.Self`, generic type params 등)
- **의존성**: stdlib only
- **3rd-party**: 필요 시 vendor (프로젝트에 파일로 커밋)
- `pip install` / `requirements.txt` / `pyproject.toml` / `setup.py` 생성 금지
- `http.server.ThreadingHTTPServer` 기반 sync 아키텍처 유지 (asyncio 전환 금지)

### JavaScript
- vanilla JS, **ES modules 금지** (IIFE + `Board.*` 네임스페이스 유지)
- 빌드 도구 금지 (webpack/vite/rollup/esbuild/tsc)
- `package.json` / `node_modules` 금지
- **CDN 금지** — 외부 라이브러리는 로컬 `static/js/vendor/`, `static/css/vendor/`
- 버전은 파일명에 명시 (`marked-15.0.0.min.js`)

### 공통
- 시스템 패키지 설치 금지 (apt/brew 등)
- 기존 런타임 파일 경로 유지 (`.board.url`, `.sessions/`, `.last-session-id`)
- 기존 SSE 이벤트 이름 및 HTTP 엔드포인트는 **추가만**, 삭제 금지
- Phase 0 는 로직 변경 0 원칙

## 1. 최종 디렉터리 구조

```
.claude.workflow/board/
├── server/                          # Python 패키지
│   ├── __init__.py                  # exports
│   ├── __main__.py                  # python3 -m board.server 지원 (~30)
│   ├── _common.py                   # consts, logger, helpers (~150)
│   ├── app.py                       # main, run_server, resolve_port, is_port_in_use (~200)
│   ├── sse_client_manager.py        # FileWatcher + SSEClientManager (kanban/workflow sync) (~250)
│   ├── terminal_channel.py          # TerminalSSEChannel + _parse_last_event_id helpers (~430)
│   ├── claude_process.py            # ClaudeProcess + _validate_images (~450)
│   ├── poll_tracker.py              # PollChangeTracker (~80)
│   ├── workflow_session.py          # WorkflowSession + WorkflowSessionRegistry (~320)
│   ├── http_router.py               # BoardHTTPRequestHandler base + do_GET/POST/DELETE/OPTIONS (~350)
│   ├── board_data.py                # (기존 그대로, 1008)
│   ├── vendor/                      # (비어있음, 미래용)
│   └── handlers/
│       ├── __init__.py
│       ├── files.py                 # FilesHandlerMixin (memory/rules/prompt/claude-md write) (~120)
│       ├── generic.py               # GenericHandlerMixin (api, poll, sse) (~150)
│       ├── sync.py                  # SyncHandlerMixin (restart, workflow_sync) (~160)
│       ├── terminal.py              # TerminalHandlerMixin (~360)
│       └── workflow.py              # WorkflowHandlerMixin (~400)
│
└── static/                          # 프런트엔드 (HTTP 서빙 루트)
    ├── index.html
    ├── terminal.html
    ├── css/
    │   ├── core/
    │   │   ├── common.css
    │   │   └── dashboard.css
    │   ├── terminal/
    │   │   ├── layout-and-message.css     # ~686 (S1+S2)
    │   │   ├── tool-box.css                # ~805 (S3)
    │   │   ├── renderers.css               # ~553 (S4)
    │   │   └── workflow-panels.css         # ~1163 (S5+S6)
    │   ├── views/
    │   │   ├── kanban.css
    │   │   ├── memory.css
    │   │   ├── roadmap.css
    │   │   ├── viewer.css
    │   │   └── workflow.css
    │   ├── widgets/
    │   │   └── settings.css
    │   └── vendor/
    │       └── highlight-github-dark.min.css
    └── js/
        ├── core/
        │   ├── common.js
        │   ├── sse.js
        │   └── slash-commands.js
        ├── terminal/
        │   ├── terminal.js                 # 엔트리, renderTerminal, state (~950)
        │   ├── output-pipe.js               # append + markdown + scroll (~500)
        │   ├── tool-box.js                  # Tool Box + Workflow Tool Card 렌더링 (~490)
        │   ├── terminal-input.js            # Spinner + Image/File + sendInput (~380)
        │   ├── session-switcher.js          # _save/restore/switchSession (~170)
        │   ├── tool-renderers.js            # (기존 renderers.js 이동)
        │   └── wf-ticket-renderer.js        # (기존 이동)
        ├── workflow/
        │   ├── session.js                   # SSE 연결/재연결 (기존 이동, Phase 2에서 재작성)
        │   ├── workflow-bar.js              # 패널 FSM (기존 이동, Phase 2에서 재작성)
        │   ├── workflow-sessions.js
        │   ├── workflow.js
        │   └── step-fsm.js                  # (Phase 2 신규)
        ├── memory/
        │   ├── memory-core.js               # 공통 상태 + 탭 전환 + Memory + CLAUDE.md (~850)
        │   └── memory-rules-prompt.js       # Rules + Prompt Files sub-tabs (~760)
        ├── views/
        │   ├── dashboard.js
        │   ├── kanban.js
        │   ├── roadmap.js
        │   ├── viewer.js
        │   └── settings.js
        └── vendor/
            ├── chart-4.5.0.min.js
            ├── marked-15.0.0.min.js
            ├── highlight-11.11.1.min.js
            └── highlight-languages/
                ├── bash.min.js
                ├── python.min.js
                ├── javascript.min.js
                └── json.min.js
```

## 2. Phase 0 매핑 — `server.py` 3013줄 → 13개 .py 파일

| 원본 라인 | 내용 | → 새 위치 |
|:-:|-----|-----|
| L1~100 | imports, constants, helpers | `server/_common.py` |
| L101~133 | `resolve_port` | `server/app.py` |
| L134~241 | `FileWatcher` | `server/sse_client_manager.py` |
| L242~354 | `SSEClientManager` | `server/sse_client_manager.py` |
| L355~411 | `_parse_last_event_id*` helpers | `server/terminal_channel.py` |
| L412~783 | `TerminalSSEChannel` | `server/terminal_channel.py` |
| L784~820 | `_validate_images` | `server/claude_process.py` |
| L821~1225 | `ClaudeProcess` | `server/claude_process.py` |
| L1226~1290 | `PollChangeTracker` | `server/poll_tracker.py` |
| L1291~1319 | `WorkflowSession` | `server/workflow_session.py` |
| L1320~1603 | `WorkflowSessionRegistry` | `server/workflow_session.py` |
| L1604~1728, 2827~2864 | `BoardHTTPRequestHandler` base + `do_GET/POST/DELETE/OPTIONS` + 라우팅 + 공용 helpers | `server/http_router.py` |
| L1729~1818 | `_handle_memory_write`, `_handle_rules_write`, `_handle_prompt_write`, `_handle_claude_md_write` | `server/handlers/files.py` |
| L1819~1840 | `_handle_restart` | `server/handlers/sync.py` |
| L1841~1954 | `_handle_workflow_sync` | `server/handlers/sync.py` |
| L1955~2088 | `_handle_api`, `_handle_poll`, `_handle_sse` | `server/handlers/generic.py` |
| L2089~2438 | 8개 `_handle_terminal_*` 메서드 | `server/handlers/terminal.py` |
| L2440~2826 | 8개 `_handle_workflow_*` 메서드 | `server/handlers/workflow.py` |
| L2865~2877 | `is_port_in_use` | `server/app.py` |
| L2878~2962 | `_run_server` | `server/app.py` |
| L2963~end | `main()` | `server/__main__.py` |

### 핸들러 Mixin 조립

```python
# server/http_router.py
from http.server import SimpleHTTPRequestHandler
from .handlers.terminal import TerminalHandlerMixin
from .handlers.workflow import WorkflowHandlerMixin
from .handlers.files import FilesHandlerMixin
from .handlers.generic import GenericHandlerMixin
from .handlers.sync import SyncHandlerMixin

class BoardHTTPRequestHandler(
    TerminalHandlerMixin,
    WorkflowHandlerMixin,
    FilesHandlerMixin,
    GenericHandlerMixin,
    SyncHandlerMixin,
    SimpleHTTPRequestHandler,
):
    def do_GET(self): ...
    def do_POST(self): ...
    def do_DELETE(self): ...
    def do_OPTIONS(self): ...
    # 공용 helpers: _send_json, _send_error, _parse_query_param 등도 여기 유지
```

### 하위호환 entry

기존 `.claude.workflow/board/server.py` 를 삭제하지 않고 shim 파일로 남김:

```python
# .claude.workflow/board/server.py (shim for backward compat)
from server.app import main
import sys
sys.exit(main())
```

또는 `server.py` 를 완전 삭제하고 실행 방식을 `python3 -m board.server` 로 변경. 결정은 Phase 0 실행 시 검증하여 확정.

## 3. Phase 0 매핑 — `terminal.js` 2355줄 → 5개 .js 파일

| 원본 섹션 | 원본 라인 | → 새 위치 |
|-----|:-:|-----|
| Markdown Renderer | L27~126 | `terminal/output-pipe.js` |
| Constants / Session dispatcher / State | L128~242 | `terminal/terminal.js` (엔트리) |
| Output Div + Scroll + append* + UI Helpers | L243~359 | `terminal/output-pipe.js` |
| Tool Box Renderer | L360~660 | `terminal/tool-box.js` |
| Workflow Tool Card Renderer | L661~849 | `terminal/tool-box.js` |
| Spinner / Image / File / Input | L850~1234 | `terminal/terminal-input.js` |
| Clear Output / updateControlBar / updateStatusLine | L1235~1385 | `terminal/terminal.js` |
| Session Switcher (_saveCurrentSession, _restoreSession, switchSession) | L1386~1555 | `terminal/session-switcher.js` |
| getContainer / renderTerminal | L1556~2253 | `terminal/terminal.js` |
| cleanupTerminal / switchTab hook / Board namespace | L2254~2312 | `terminal/terminal.js` |

### Script 태그 순서

`terminal.html` `<script>` 로딩 순서 (의존 역순 금지):

```html
<script src="js/vendor/marked-15.0.0.min.js"></script>
<script src="js/vendor/highlight-11.11.1.min.js"></script>
<script src="js/vendor/highlight-languages/bash.min.js"></script>
<script src="js/vendor/highlight-languages/python.min.js"></script>
<script src="js/vendor/highlight-languages/javascript.min.js"></script>
<script src="js/vendor/highlight-languages/json.min.js"></script>
<script src="js/core/common.js"></script>
<script src="js/core/slash-commands.js"></script>
<script src="js/terminal/tool-renderers.js"></script>
<script src="js/terminal/output-pipe.js"></script>
<script src="js/terminal/tool-box.js"></script>
<script src="js/terminal/terminal-input.js"></script>
<script src="js/terminal/session-switcher.js"></script>
<script src="js/terminal/wf-ticket-renderer.js"></script>
<script src="js/workflow/workflow-bar.js"></script>
<script src="js/workflow/workflow-sessions.js"></script>
<script src="js/workflow/session.js"></script>
<script src="js/terminal/terminal.js"></script>    <!-- 엔트리, 마지막 -->
```

`index.html` 도 동일 원칙으로 재정렬.

## 4. Phase 0 매핑 — `memory.js` 1611줄 → 2개 .js 파일

| 원본 섹션 | → 새 위치 |
|-----|-----|
| 공통 상태, 탭 전환, Memory API/CRUD, CLAUDE.md | `memory/memory-core.js` (~850) |
| Rules / Prompt Files sub-tab UI + CRUD + 모달 | `memory/memory-rules-prompt.js` (~760) |

## 5. Phase 0 매핑 — `terminal.css` 3210줄 → 4개 .css 파일

| 원본 섹션 | 원본 라인 | → 새 위치 | 줄수 |
|-----|:-:|-----|:-:|
| S1 Layout + S2 Message/Output | L1~686 | `terminal/layout-and-message.css` | ~686 |
| S3 Tool Box | L687~1492 | `terminal/tool-box.css` | ~805 |
| S4 Renderers | L1493~2046 | `terminal/renderers.css` | ~553 |
| S5 Workflow Timeline + S6 Workflow Step Panels | L2047~3210 | `terminal/workflow-panels.css` | ~1163 |

## 6. Phase 0 매핑 — 나머지 파일 (순수 이동)

| 기존 | → 새 위치 |
|-----|-----|
| `js/common.js` (648) | `static/js/core/common.js` |
| `js/sse.js` (315) | `static/js/core/sse.js` |
| `js/slash-commands.js` (97) | `static/js/core/slash-commands.js` |
| `js/session.js` (978) | `static/js/workflow/session.js` |
| `js/workflow-bar.js` (1044) | `static/js/workflow/workflow-bar.js` |
| `js/workflow-sessions.js` (212) | `static/js/workflow/workflow-sessions.js` |
| `js/workflow.js` (613) | `static/js/workflow/workflow.js` |
| `js/renderers.js` (952) | `static/js/terminal/tool-renderers.js` |
| `js/wf-ticket-renderer.js` (337) | `static/js/terminal/wf-ticket-renderer.js` |
| `js/dashboard.js`, `kanban.js`, `roadmap.js`, `viewer.js`, `settings.js` | `static/js/views/*.js` |
| `css/common.css`, `dashboard.css` | `static/css/core/*.css` |
| `css/kanban.css`, `memory.css`, `roadmap.css`, `viewer.css`, `workflow.css` | `static/css/views/*.css` |
| `css/settings.css` | `static/css/widgets/settings.css` |
| `index.html`, `terminal.html` | `static/*.html` |

## 7. 정적 루트 이동 처리

서버가 `SimpleHTTPRequestHandler` 를 통해 정적 파일을 서빙합니다. `static/` 하위로 이동하면 다음 1개 변경만 필요:

```python
# server/http_router.py (또는 app.py 서버 초기화 부)
class BoardHTTPRequestHandler(..., SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        static_dir = os.path.join(
            os.getcwd(), '.claude.workflow', 'board', 'static'
        )
        super().__init__(*args, directory=static_dir, **kwargs)
```

URL 경로(`/terminal.html`, `/index.html`) 는 브라우저 측에서 변경 없음.

## 8. Vendor 라이브러리 다운로드 목록

Phase 0 에서 수동 다운로드 후 커밋:

| 파일 | 출처 | 크기 추정 |
|------|-----|:-:|
| `marked-15.0.0.min.js` | `https://cdn.jsdelivr.net/npm/marked@15.0.0/marked.min.js` | ~50KB |
| `chart-4.5.0.min.js` | `https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.min.js` | ~200KB |
| `highlight-11.11.1.min.js` (core only) | `https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/highlight.min.js` | ~30KB |
| `highlight-languages/bash.min.js` | 동일 CDN `/languages/bash.min.js` | ~3KB |
| `highlight-languages/python.min.js` | 동일 CDN `/languages/python.min.js` | ~5KB |
| `highlight-languages/javascript.min.js` | 동일 CDN `/languages/javascript.min.js` | ~5KB |
| `highlight-languages/json.min.js` | 동일 CDN `/languages/json.min.js` | ~2KB |
| `highlight-github-dark.min.css` | `https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/styles/github-dark.min.css` | ~3KB |

**총 ~300KB 정적 자산**. 프로젝트에 커밋.

## 9. Phase 0 검증 체크리스트

Phase 0 완료 조건:

| # | 검증 |
|---|-----|
| 1 | `python3 .claude.workflow/board/server.py --serve /home/deus/workspace/claude` 또는 `python3 -m board.server ...` 정상 실행 |
| 2 | 모든 기존 HTTP 엔드포인트 응답 동일 |
| 3 | 기존 `.board.url`, `.sessions/*.jsonl`, `.last-session-id` 파일 읽기/쓰기 경로 불변 |
| 4 | 브라우저에서 index.html, terminal.html 모두 정상 로드, 콘솔 에러 없음 |
| 5 | 터미널 세션 시작/kill, 워크플로우 세션 시작/kill 동작 |
| 6 | 모든 `.py` / `.js` / `.css` 파일 **1500줄 이하** |
| 7 | `git diff --stat` 상 이동된 파일만 100% 이동으로 표시 (rename detection) |
| 8 | 로직 변경은 import 경로와 mixin 상속 선언 정도만 — 동작 변경 0 |

## 10. Phase 1~3 개요 (Phase 0 이후)

### Phase 1 — 서버 SSE 이벤트 모델 확장 + lock 재설계

- `TerminalSSEChannel.add()` 에서 `_lock` 은 스냅샷만 보유, 히스토리 재생은 lock 밖에서 per-client lock 으로 직렬화
- 재생 중 broadcast 는 `_replaying` 플래그를 가진 클라이언트에 대해 per-client 버퍼에 보류 후 재생 완료 시 flush
- 새 SSE 이벤트: `event: replay_start` (재생 구간 시작), `event: replay_end` (재생 구간 종료), `event: workflow_step` (서버가 결정한 워크플로우 단계 전이 통보)
- heartbeat `time.sleep(1)` → `time.sleep(0.25)` (좀비 스레드 회수 지연 축소)

### Phase 2 — 클라이언트 replay 모드 + workflow-bar FSM 재작성

- `session.js` 에 `_isReplaying` 플래그 도입. `replay_start`~`replay_end` 구간에서는 DOM/FSM 변이 없이 `_lastEventId` 만 전진
- `workflow-bar.js` 재작성:
  - stdout `[WORKFLOW]` 토큰 parser 폐기
  - `workflow_step` SSE 이벤트만 수신하여 FSM 전이
  - 멱등 상태 머신: 같은 `step_seq` 이벤트 재수신 시 no-op
  - `_reset()` 제거
- `terminal.js` / `session-switcher.js` 에서 `_restoreSession` 시 FSM 상태도 세션 엔트리에 저장/복원

### Phase 3 — smoke test + 기존 가드 rollback

- T-378 과 동일 프롬프트로 smoke 재실행
- 기존 가드 중 redundant 코드 제거: T-371(last-event-id 세션 전역), T-377(`_reset` 재진입 가드) 등
- T-380/T-381 증상 재관찰 → 해소되었는지 확인 후 해당 티켓 Done 처리

## 11. 각 Phase 의 태스크 예상

| Phase | 태스크 수 | 소요 추정 (세션 수) |
|:-:|:-:|:-:|
| 0 | 5 (server / terminal.js / memory.js / terminal.css / 나머지 이동 + vendor) | 1~2 |
| 1 | 3~4 | 1 |
| 2 | 4~5 | 1~2 |
| 3 | 2~3 | 1 |

**총 ~14~17 태스크, 4~6 워크플로우 세션** 예상.

## 12. 진행 중 관찰할 버그 티켓

리팩토링 중 또는 이후 재관찰:

- **T-380** Board SSE 탭 전환 불안정 증상 관찰 — Phase 1 이후 재현 시도
- **T-381** Board 워크플로우 패널 오염 증상 관찰 — Phase 2 이후 재현 시도
- **T-382** Planner ↔ skill_mapper 파서 불일치 — 리팩토링과 무관, 독립 해결
- **T-378** smoke test — T-379/T-380/T-381/T-382 모두 완료 후 자동 Done 가능

## 13. 회귀 롤백 지점

- Phase 0 실패 시: `git reset --hard` 로 develop 으로 복구 (현재 커밋 `40a53b8`)
- Phase 1 실패 시: Phase 0 완료 지점 커밋으로 복구
- Phase 2 실패 시: Phase 1 완료 지점 커밋으로 복구
- 각 Phase 는 **단일 PR / 단일 커밋 단위** 로 처리하여 롤백 원자성 보장

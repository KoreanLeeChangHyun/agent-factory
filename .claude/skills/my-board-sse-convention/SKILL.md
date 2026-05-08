---
name: my-board-sse-convention
description: "TRIGGER: board 자체 SSE 코드(.claude-organic/board/static/js/core/sse.js, .claude-organic/board/server/sse_client_manager.py, broadcast 호출, WATCH_DIRS, /events·/poll 엔드포인트) 추가·수정 시 자동 호출. board 가 클라이언트로 보내는 자체 EventSource 이벤트 스트림의 발사·수신 컨벤션을 정의한다 — ① 백엔드 이벤트 종류·payload schema·트리거 시점 ② 프론트엔드 dom 갱신 규약(shell vs tbody 분리, focus·스크롤·selection 보존, prevJson 가드, addEventListener 중복 금지) ③ 운영·디버그 회귀 진단 절차(race 보정, 무한 재렌더 검출, EventSource 재연결, 캐시 버스터). Anthropic API SSE 와 분리 — 그쪽은 .claude/skills/reference-claude-api/references/streaming.md. SKIP only when no board SSE code is being touched."
license: "Apache-2.0"
---

# Board SSE 컨벤션

본 프로젝트 board 의 자체 SSE(Server-Sent Events) 사용·구현 컨벤션입니다. board 서버(`.claude-organic/board/server/`)가 클라이언트(`.claude-organic/board/static/js/core/sse.js`)로 보내는 자체 이벤트 스트림이 대상이며, Anthropic API SSE 와는 별개입니다.

## 사용 시기

- `.claude-organic/board/static/js/core/sse.js` 또는 `.claude-organic/board/server/sse_client_manager.py` 수정 시
- 새 SSE 이벤트 타입 추가 / `WATCH_DIRS` 변경 / `broadcast()` 호출 추가 시
- SSE 트리거에 반응해 dom 을 갱신하는 frontend 렌더 함수(`renderXxx`) 신설 또는 수정 시
- "검색창 포커스가 사라진다", "행이 안 보인다", "스크롤 리셋된다" 같은 SSE 회귀 진단 시
- `EventSource` / `/events` / `/poll` 관련 코드 다룰 때

## 1. 백엔드 — SSE 이벤트 송신 규약

### 1.1 이벤트 타입 SSOT

이벤트 타입은 `.claude-organic/board/server/_common.py:WATCH_DIRS` 가 단일 진실 공급원입니다. 디렉터리 → event_type 매핑 변경 시 본 표를 갱신해야 합니다.

| event | 트리거 (디렉터리·이벤트) | payload | broadcast 위치 |
| --- | --- | --- | --- |
| `kanban` | `tickets/{open,progress,review,done}/` 변경 | `{"files": [...]}` | `app.py:on_change` (FileWatcher) |
| `workflow` | `runs/`, `runs/.history/` 변경 | `{"files": [...]}` | `app.py:on_change` |
| `dashboard` | `board/data/` 변경 | `{"files": [...]}` | `app.py:on_change` |
| `roadmap` | `roadmap/` 변경 | `{"files": [...]}` | `app.py:on_change` |
| `memory` | 동적 등록된 mem_dir 변경 | `{"files": [...]}` | `app.py:on_change` (등록 시점에 결정) |
| `git_branch` | `.git/HEAD` 변경 | `{"branch": "..."}` | `app.py:on_branch_change` (GitBranchWatcher) |
| `terminal_*` (`stdout`/`result`/`system`/`permission`/`skill_listing`/`workflow_step`) | terminal_channel 별개 broadcast | NDJSON → SSE 매핑 (`terminal_channel.py:180-186`) | `terminal_sse_channel.broadcast` |
| `archived_end` (sync 채널) | curl bash 부트스트랩 종료 | `{...}` | `handlers/sync.py:286` |

### 1.2 Broadcast API

`sse_client_manager.py:254` 의 `SSEManager.broadcast(event_type, files=None, data=None)`:

- payload 우선순위: `data` > `files` > `int(time.time())`
  - 둘 다 지정하면 `data` 가 이김 (의도하지 않은 회귀 패턴 — 1.4 반례 참조)
- 실패 클라이언트(BrokenPipe 등)는 자동 제거
- per-client lock 으로 heartbeat 와의 concurrent write 방지
- terminal SSE 는 별도 채널(`terminal_channel.py`) — manager 와 분리되어 wfile 단위 직렬화 정책이 다름 (TerminalSSEChannel)

### 1.3 Polling fallback

- `/poll` 엔드포인트가 동일 changes dict 반환 (event_type → 변경 list)
- 클라이언트가 SSE 연결 실패·미지원 시 2초 간격 polling
- 백엔드는 `poll_tracker.add(event_type, files)` 로 SSE 와 polling 양쪽 일관성 유지 (`app.py:149`)
- **SSE 만 추가하고 polling 매핑 누락 = 자동 차이 회귀**

### 1.4 백엔드 반례

- `broadcast(evt, files=[...], data={...})` — files 가 silently 무시됨 (data 우선)
- 새 `WATCH_DIRS` 항목 추가 후 `pollChanges` (`sse.js:249-270`) 분기 누락
- broadcast 시 큰 payload 직렬화 실패 → 모든 클라이언트 끊김 (try/except 누락 시)
- terminal_channel 과 sse_client_manager 두 채널을 같은 wfile 에서 함께 사용 (lock 정책 충돌)

## 2. 프론트엔드 — SSE 트리거 수신 시 dom 갱신 규약

### 2.1 핵심 패턴: shell vs tbody 분리 (MUST)

탭 영역을 두 계층으로 분리합니다.

- **shell**: 검색바·테이블 헤더·정적 layout. **첫 렌더 1회만**, 이후 보존.
- **tbody/list**: 행 데이터. SSE 트리거·검색 입력·정렬 변경 시 **이 영역만** `innerHTML` 교체.

```
function renderXxx() {              // shell — 1회
  if (이미 그려져 있으면) { renderXxxBody(); return; }
  el.innerHTML = shellHtml;          // 검색바·헤더
  bind input/sort/resize handlers;   // 핸들러도 1회만
  renderXxxBody();                   // 첫 행 채우기
}

function renderXxxBody() {           // 행만
  list.innerHTML = rowsHtml;
  bindFileLinks(list);
  bindRowClicks(list);
  attachSentinel();
  updateStatus();
}
```

SSE 트리거·input·sort 모두 `renderXxxBody()` 만 호출합니다. 검색 input·스크롤 위치·focus·selection 이 살아남습니다.

### 2.2 prevJson 가드 (MUST)

변경 검출은 직렬화 비교로 수행하고 동일하면 재렌더 skip 합니다.

```
fetch(...).then(function (data) {
  const json = JSON.stringify(data);
  if (json === prevJson) return;      // 가드
  prevJson = json;
  Board.state.X = data;
  renderXxxBody();
});
```

가드 누락 시 SSE 이벤트마다 dom 폭주 → main thread blocking → 검색·스크롤 frozen.

### 2.3 focus·스크롤·selection 보존

- shell 보존이 1차 방어선 (대부분 케이스 충족)
- 부득이하게 shell 자체를 교체해야 하면:

```
const prev = el.querySelector(".my-input");
const wasFocused = !!(prev && document.activeElement === prev);
const ss = prev ? prev.selectionStart : null;
const se = prev ? prev.selectionEnd : null;
// ... innerHTML 교체 ...
if (wasFocused) {
  const next = el.querySelector(".my-input");
  if (next) {
    next.focus();
    try { next.setSelectionRange(ss, se); } catch (_) {}
  }
}
```

### 2.4 addEventListener 중복 등록 금지

- shell 1회 렌더에서만 핸들러 등록
- tbody 갱신 함수에서는 재등록 금지
- 행 단위 핸들러가 필요하면 `data-bound` 속성 가드(`bindWfFileLinks` 패턴) 또는 컨테이너에 위임

### 2.5 페이지네이션 (loadMore + IntersectionObserver)

- sentinel `<tr id="wf-sentinel">` 을 tbody 끝에 두고 IntersectionObserver 로 추가 페이지 로드
- 다음 페이지 도착 시 `appendXxxRows(items)` 로 **행만 append** (dom 통째 재구성 금지)
- observer 는 sentinel 제거 시 자동 disconnect — 추가 등록 시 옛 observer 명시 disconnect

### 2.6 fetch 사이 의존성 (race) 처리

페이지 로드 시 **두 개 이상의 fetch 가 병렬**이고 한쪽이 다른 쪽의 결과를 사용하는 경우(예: workflow 행이 ticket 매핑을 사용), 늦은 fetch 의 콜백에서 ready 가드 + tbody 재갱신을 수행합니다.

```
fetchA.then(function (a) {
  Board.state.A = a;
  renderA();
  // B 가 이미 첫 렌더된 상태면 매핑이 비어있을 수 있으므로 다시 그려준다
  if (Board.state.bInitialized && Board.render.renderBBody) {
    Board.render.renderBBody();
  }
});
```

## 3. 운영·디버그 — 회귀 진단 절차

### 3.1 무한 재렌더 검출

- DevTools Performance 탭 녹화 (10초) → SSE 이벤트마다 layout/paint 폭주 확인
- 의심 함수 첫 줄에 `console.count("renderXxx")` 임시 삽입 → 1초 내 호출 카운트 측정
- prevJson 가드 누락 / shell 통째 교체 / 무한 재연결 중 하나가 원인

### 3.2 Race 보정

- 페이지 로드 직후 비어있는 매핑(예: 모든 행 "(미연결)") 고착 → race 의심
- DevTools Network 에서 fetch 끝 시각 비교 → 늦은 fetch 의 콜백 누락 확인
- 1.4 패턴으로 늦은 fetch 콜백에 ready 가드 + tbody 재호출 추가
- `wfInitialized`·`bInitialized` 같은 플래그가 SSOT — 중간에 false 로 토글 금지

### 3.3 EventSource 재연결

- `es.onerror` 시 **반드시 `es.close()` 명시 호출** (브라우저 자동 재연결 차단)
- close 후 `startPolling()` + `scheduleSSERetry()` (30초 후 `initSSE()` 재시도)
- 새 SSE 연결 시 `currentES` 닫고 재할당 (중복 연결 방지)
- `visibilitychange` 시 SSE 연결되어 있으면 `refreshXxx()` 로 보정, 끊겨있으면 즉시 polling 재개

### 3.4 캐시 버스터

- `index.html` 의 script src 에 `?v=YYYYMMDD-tag` 추가
- 동일 세션 도중 코드 패치 시 강제 새로고침(Ctrl+Shift+R) 안내
- `index.html` 자체 캐시도 의심 — 강제 새로고침으로만 갱신

### 3.5 board 서버 재기동

- 서버 재기동/재실행은 **사용자 사전 동의 필수** (auto memory `feedback_server_restart_consent` 캐논)
- 정적 파일 서빙(html/js/css)만 변경 시 재기동 불필요 — 강제 새로고침으로 충분
- Python handler 변경 시에만 재기동 요청

## 4. 반례 (절대 하지 말 것)

- `el.innerHTML = h` 로 검색바·헤더 포함 dom 통째 재구성 → focus·스크롤·selection 폭주 reset
- prevJson 가드 누락 → SSE 이벤트마다 무한 재렌더 → 검색·스크롤 frozen
- `es.onerror` 후 `es.close()` 호출 안 함 → 브라우저 자동 재연결 무한 루프
- shell 갱신마다 `addEventListener` 등록 → 메모리 누수 + 동일 이벤트 중복 발사
- IntersectionObserver disconnect 누락 → 페이지네이션 무한 트리거
- `WATCH_DIRS` 에 이벤트 타입 추가하면서 프론트 핸들러(`es.addEventListener` + `pollChanges` 분기) 미등록
- `broadcast(evt, files=[...], data={...})` 동시 지정 → files 가 silently 무시됨
- 사용자 명시 동의 없이 자동 강제 정책·가드 도입 (auto memory `feedback_no_speculative_guards_2026-05-08` 캐논)
- 사용자 명시 동의 없이 board 서버 재기동 (auto memory `feedback_server_restart_consent` 캐논)
- 본 컨벤션 정의를 다른 룰 문서(`workflow.md`, `general.md`)에 복붙 — cross-reference 만 (단일 진실 공급원)

## 5. 학습 사례 (2026-05-09)

### renderWorkflow 폭주 + race 보정

- **증상**: Workflow 탭 모든 행 `(미연결)` + 검색 input 클릭 시 포커스 안 잡힘 + 스크롤 frozen
- **원인 1 (race)**: `fetchTickets`(~344ms, XML 379개 파싱)가 `fetchWorkflowEntries`+50개 detail(~50ms)보다 늦어, `Board.state.TICKETS=[]` 인 상태로 첫 워크플로우 렌더 → 모든 행 미연결 고착. `fetchTickets` 콜백이 `renderKanban` 만 호출하고 `renderWorkflow` 미호출이라 영구 고착.
- **원인 2 (dom 폭주)**: SSE ticket 변경 트리거(`sse.js:76`) + 검색 input 이벤트가 `renderWorkflow` 호출, `el.innerHTML = h` 로 통째 교체 → 검색 input 폐기·재생성 → focus 잃음. 입력 도중 SSE 들어오면 더 빈번하게.
- **해결**:
  1. `renderWorkflow` → shell + `renderWfTbody` 분리 (`workflow.js`)
  2. `refreshWfSortIndicators(el)` — sort 화살표만 교체 (dom 교체 없이)
  3. SSE/race/input/sort 모두 `renderWfTbody` 호출 → tbody 만 교체, shell 보존
  4. `fetchTickets` 콜백(`sse.js:315`)에 `wfInitialized` 가드 + `renderWfTbody` 호출 추가 (race 보정)
- **관련 commits**: `0a66457`(SSE 트리거 추가), `7ff9066`(cache buster + trim 가드), `95221cb`(ticketNumber 응답), `c855c40`(티켓 컬럼 룰 강화), `ad8d9bd`(신구조 fold 우선) + 본 세션 패치(shell/tbody 분리 + race 보정)

## 6. 출처 / Cross-reference

### 룰·정책 단일 진실 공급원
- `.claude/rules/workflow/general.md` — UI 컨벤션, 메인 세션 제약, 추측 금지, 메모리 정책
- `.claude/rules/workflow/workflow.md` — 워크플로우 시스템 룰
- `.claude-organic/board/server/event_filter.py:is_user_visible` — 사용자 가시성 정책 SSOT
- `.claude-organic/board/server/terminal_channel.py:_SYSTEM_TOP_LEVEL_FIELDS` — system payload 계약
- `.claude-organic/board/server/_common.py:WATCH_DIRS` — SSE 이벤트 타입 → 디렉터리 매핑

### 분리된 영역
- Anthropic API SSE: `.claude/skills/reference-claude-api/references/streaming.md` (별개)

### auto memory 단편 (배경 학습)
- `project/synthesis_workflow_infra_invocation_canon` — 워크플로우 인프라 통합 캐논
- `project/synthesis_board_terminal_ui_session_consolidated` — Board 터미널 UI 통합 가이드 (SSE 이벤트, 채팅 입력 1:1 turn 큐)
- `project/project_sdk_runtime_behavior_2026-04-29` — SDK 런타임 동작 (system init 매 turn 재발사)
- `project/project_esc_interrupt_session_preservation_2026-04-29` — ESC 인터럽트 세션 보존 + SSE `user_input_interrupted` broadcast
- `reference/reference_sdk_esc_interrupt_behavior` — SDK ESC/SIGINT 인터럽트 시 실제 동작
- `feedback/feedback_server_restart_consent` — board 서버 재기동 사용자 동의 필수
- `feedback/feedback_no_speculative_guards_2026-05-08` — 추측 기반 자동 강제 정책 도입 금지

## 7. 시스템 분류

본 스킬은 `my-*` 접두사 — **프로젝트 스킬**(`.claude/` 갱신 정책상 보존 대상)입니다. board 인프라가 본 프로젝트 자체이므로 시스템 갱신 영향을 받지 않도록 분리합니다.

# Board UI 운영 규칙

Board 터미널 (http://127.0.0.1:9927/terminal.html) = 본 시스템의 **주 인터페이스**. 본 시스템을 도입한 모든 프로젝트에 적용되는 UI 운영 규약.

> CLI 직접 사용 안 함 (2026-04-07 확정) → CLI 배너/장식 출력 불필요. Board 폰트는 CLI 보다 작게.

## 1. SSE 이벤트 계약 (MUST)

| 이벤트 | 용도 |
|--------|------|
| stdout | 실시간 출력 |
| result | 최종 결과 |
| system | 시스템 메시지 |
| permission | 권한 프롬프트 |
| user_input | 사용자 입력 히스토리 |
| replay_start / replay_end | 히스토리 재생 구간 경계 |
| workflow_step | 유일한 FSM 전이 경로 (`{step, prev_step, trigger, phase?, mode?, result?}`) |

새 이벤트 추가 시 위 계약과 정합해야 한다. `type: "attachment"` 같은 미분류 갭은 별 트랙 박제 후 처리.

## 2. 채팅 입력 1:1 turn 큐 모델 (MUST)

### 핵심 원리
- **1 메시지 = 1 turn 단순 표시** (그룹화 모델 폐기)
- **echo 시점 = send 직전** (큐 dequeue 시), push 시점 노출 X
- **자동 합치기 일체 X** — 시간 idle / Gatekeeper LLM / 휴리스틱 도입 금지
- **합치기는 사용자 명시 액션만** — ESC 인터럽트 후 추가 입력 send
- **ESC 인터럽트 = stream 종료**, conversation history + 세션 ID + DOM 보존
- **이미지 첨부도 동일 큐 모델** — 텍스트/이미지 동시 큐잉

### 큐 stack UI 사양

| 항목 | 값 |
|------|-----|
| 위치 | `.terminal-input-card` **외부**, 카드 바로 위 별도 row |
| 정렬 | `flex-end` (오른쪽) |
| max-width | **30%** (입력란 가시성 우선) |
| 텍스트 | 한 줄 ellipsis + OS tooltip (`title`) |
| 이미지 라벨 | `[이미지 N장]` |
| 컨테이너 max-height | 96px + scroll |
| 카드 색 | 테라코타 #D97757 톤 다운 (`rgba(217,119,87,0.12)` + outline 0.55) |
| × 버튼 | hover #f44747, click → `removePendingEntry` |
| 큐 비면 | 컨테이너 `hidden` |

### LLM 본질 한계
Anthropic Messages API 한 turn = `[user_msg → assistant stream]` 단방향. stream 도중 user_message 합치기 메커니즘 X. → UI 측 합치기도 안 함.

### 검증 시나리오
- (a) idle → enter A → 즉시 echo + busy → 응답 → idle
- (b) busy 중 B → B 미표시 (큐 카드만) → A 응답 끝 → B echo + send (**핵심**)
- (c) ESC → stream 중단, 세션 보존, 새로고침 후 history 복원
- (d) IME composition 가드 (한국어 변환 enter 자동 send 안 함)
- (e) hint: idle/큐0=`Shift+Enter 줄바꿈` / busy+큐≥1=`ESC 중지 · 큐 N개` / busy+큐0=`ESC 중지`
- (f) 이미지 큐잉: 카드 `텍스트 [이미지 N장]`, dequeue 시 thumbnail echo

## 3. ESC 인터럽트 UX 모델 (MUST)

사용자의 ESC 시맨틱 모델은 Claude CLI 의 그것과 다르다.

| 항목 | 사용자 모델 | 나이브 구현 (회피) |
|------|----------|------------------|
| ESC 누름 | "응답만 멈춤" | SIGINT → process_exit → STOPPED |
| 세션 | 그대로 유지, 다음 메시지 이어서 가능 | Start 버튼 누르기 전엔 못 씀 |
| 직전 메시지 | 입력창에 자동 복원되어 수정/재전송 | 응답 영역에 `[Request interrupted by user]` 노이즈만 |
| 새로고침 | 위 상태 그대로 유지 | 초기화 |

### Why
ESC 의 메타 의도 = **"이 메시지로는 응답을 못 받겠다, 다시 다듬어서 보내자"**. 따라서 **메시지 보존이 핵심**.

### How to apply (3가지 동시 고려)
1. **세션 보존**: 같은 session_id 로 자동 resume (Claude CLI 가 종료해도 클라가 즉시 spawn)
2. **입력창 복원**: 직전 send 한 텍스트를 입력창에 자동 채워 사용자가 수정/재전송 가능
3. **영속화**: 새로고침해도 위 둘이 유지 — localStorage 또는 sidecar

### 마커 정책
- "중지됨" 마커는 user 말풍선에 시각적으로 명시 (테라코타 배지)
- SDK 가 생성하는 placeholder `[Request interrupted by user]` user-role 메시지는 노이즈이므로 history 에서 필터링
- ESC 흐름 변경 시 사용자에게 "ESC 의도가 무엇인지" 다시 묻지 말 것 — 이미 합의됨

## 4. 휘발성 시스템 메시지 출력 금지 (MUST NOT)

### 금지 대상
- "Session started", "Response complete", "Connecting...", "Press Start..."
- 슬래시 명령 피드백, `[Interrupted]` 등

### 예외 (유지)
- `appendErrorMessage` (`[Error]/[오류]`) — 디버깅 필수
- `/help` 테이블 등 사용자 명시 요청 결과
- 실시간 `[Permission Request]` UI

### Why
새로고침 시 jsonl 에서 복원되지 않는 placeholder/상태 알림은 일관성을 해친다.

### 적용 룰
새 메시지 설계 시 **"새로고침 후에도 복원되는가?"** 를 기준으로 출력 여부 결정. `appendSystemMessage` 호출 보이면 제거 검토.

## 5. Board 서버 재기동·재실행 (MUST)

### 동의 필수
- Board 서버 (`python3 .claude-organic/board/server.py`) 재기동/재실행은 **반드시 사용자 사전 동의** 받은 뒤에만 수행
- 자동 재기동 스크립트 호출 금지
- execv 기반 restart 버튼도 동일하게 사용자 트리거 대상

### Why
Board 터미널이 사용자의 주 인터페이스이므로 재기동은 진행 중인 세션/SSE 연결/UI 상태를 날린다. T-379 리팩토링 중 세션 상태 손실 사고가 있었음.

### 횟수 최소화 (흡수)
서버 (Python) 코드 수정 시 모든 문제를 **한 번에 잡아서 재기동 1회로 끝낸다** (MUST).

- 서버 코드 수정 시 커밋 전에 전체 import 검증, 엔드포인트 전수 curl 테스트 등 기계적 검증을 먼저 수행
- "고쳤습니다 → 재기동해주세요" 를 반복하지 않도록 수정 사항을 모아서 한 번에 처리
- 체크리스트 항목 중 서버 관련 검증은 재기동 요청 전에 코드 레벨에서 최대한 선검증

## 6. 시각 컨벤션 (pulse + 테라코타)

### 색상 토큰

| 의미 | 값 | 사용처 |
|------|-----|--------|
| 진행 중 (테마) | `#D97757` (테라코타) | step active 배지, tool card running pulse |
| 완료 success | `#4ec9b0` (청록) | tool card 완료 ✓ SVG, step done 배지 |
| 완료 fail | `#f48771` (주홍) | tool card 완료 × SVG + border 강조 |

### 펄스 리듬
- **주기**: 1.6s (sub-agent task pulse-dot 만 1.2s 변종)
- **타이밍**: ease-in-out
- **루프**: infinite
- **변조**: opacity / background / box-shadow / border-color (둘 이상 조합 가능)

```css
@keyframes wf-*-pulse {
  0%, 100% { /* 약 / 투명 */ }
  50%      { /* 강 / 진함 */ }
}
```

### 접근성 (MUST)
모든 pulse animation 에는 `prefers-reduced-motion: reduce` 미디어 쿼리로 `animation: none` 제공 (시각 자극 회피).

### DO NOT
- **border-left 한쪽 색상 디자인 금지** (general.md UI 디자인 참조)
- **외부 아이콘 라이브러리/폰트 사용 금지** — SVG 직접 inline (general.md 참조)
- **깜빡 (blink, opacity 0↔1 급변) 형 애니메이션 금지** — pulse (breathing) 만 (시각 피로 회피)

## 7. 첨부 도메인 4종 (티켓 / 메모리 / 이미지 / 파일)

| 첨부 타입 | MIME | dragstart 출처 | chip |
|----------|------|---------------|------|
| 티켓 | `application/x-board-ticket` | kanban 카드 dragstart | command badge (IMP/RSC/REV/TKT) + title + subtitle |
| 메모리 | `application/x-board-memory` | memory file item dragstart | MEM 청록 배지 (#4ec9b0) + description + path |
| 이미지 | (browser native files) | OS 드래그 또는 attach button | 썸네일 (data:image base64) |
| 파일 (비이미지) | (browser native files) | OS 드래그 | 파일 카드 + 파일명 textarea 인라인 |

### 가드 패턴 (티켓 ↔ 메모리 일관)
- workflow 모드 비활성 (`isWorkflowMode` sendInput 가드)
- 같은 첨부 중복 방지 (name 기준)
- busy 상태에서 큐 진입 + clearAttachments 일관 처리
- parse 실패 graceful (description 빈 채로 chip name 폴백)

### 메모리 DnD 전송 형태 (path prefix block)
본문 fetch 안 함 + path 만 prefix block 인라인 → 어시스턴트가 메모리 디렉터리 절대경로와 합성하여 Read.

```
[참고 메모리]
- <description>: memory/<category>/<filename>

<user_text>
```

- backend 변경 0건 — 일반 사용자 텍스트 메시지로 전송
- attachments 사이드카 영속화 X (chip 시각 카드는 새로고침 시 사라지지만 메시지 본문 prefix block 으로 메모리 정보 보존)

## 8. SVG 아이콘 룰 (Lucide 스타일)

CLAUDE.md / general.md "터미널 외 UI 아이콘은 SVG 로 직접 생성 (MUST), 외부 아이콘 라이브러리/폰트 사용 금지" 룰의 구현 상세:

**스타일 통일**:
- `viewBox="0 0 24 24"`
- `stroke="currentColor"`
- `stroke-width="2"`
- `linecap/linejoin="round"`

CSS 의 `color` 속성이 `currentColor` 로 SVG 에 전달되어 테마 변경 시 자동 추종.

## 9. Board 디버그 로거 진단 절차

프론트엔드 회귀 (플리커, 상태 불일치) 진단 시.

```bash
# 활성화
touch .claude-organic/runs/bg/debug.enabled
: > .claude-organic/runs/bg/debug.log
# 사용자 재현 → 분석 (Read tool) → 비활성화
rm .claude-organic/runs/bg/debug.enabled
```

### 계측 추가

```js
if (Board.debugLog) Board.debugLog('tag-name', { state1, state2 });
// 스택 필요 시:
//   stack: new Error().stack.split('\n').slice(1, 5).join(' | ')
```

### 교훈 (2026-04-25 토큰바 플리커)
회귀는 추측보다 **계측 먼저**. 가설 1은 효과 없었고, 계측 후 1분 내 정확한 원인 (`_resetSessionDerivedState` + `process_exit`) 특정.

## 10. standalone vs index 페이지 모듈 격리

`terminal.html` 은 standalone 페이지로 자체 script 로드 목록을 가진다. `index.html` 의 로드 목록과 **별개**.

→ `Board.fetch.*` / `Board._memory.*` API 호출하는 신규 핸들러는 `terminal.html` 에 모듈 명시 추가 필수 (예: Memory 버튼 `memory-core.js` 누락 사례).

## 11. 책임 경계 자주 터지는 지점

| 경계 | 증상 |
|------|------|
| BE→FE 이벤트 계약 | event 이름/payload 스키마 불일치, replay/live 미구분 |
| 세션 식별자 3중 | 프런트 `_activeSessionId` vs 서버 `session_id` vs Claude CLI 내부 ID |
| Replay 타이밍 | 재연결 시 history 재전송이 live 이벤트와 겹침 |
| DOM ↔ 상태 맵 | `_sessionMap`/`_stepPanels` DOM 어긋남 |
| 수명 종료 lag | STOPPED 표시와 실제 subprocess 상태 시간차 |

## How to apply

- 터미널 UI 회귀 → session.js / workflow-bar.js / session-switcher.js / terminal_channel.py 사각 구조로 접근
- standalone 모드 누락 의심 → `terminal.html` script 목록 ↔ `index.html` 비교가 첫 진단
- 회귀 진단 → 추측보다 계측 먼저 (Board 디버그 로거 절차 9절)
- 새 메시지 출력 결정 → "새로고침 후 복원되는가?" 기준 (4절)
- 사용자 확인 필요 → AskUserQuestion 금지 (general.md 메인 세션 제약 참조), 텍스트 메뉴 패턴 사용

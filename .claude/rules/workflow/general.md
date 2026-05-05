# 일반 규칙

## 언어 및 톤
- 언어: 한국어
- 톤: 존댓말

## 브랜치 정책
- 메인 브랜치(main/master)에 직접 커밋 절대 금지 (MUST NOT)
- 모든 변경은 피처 브랜치 생성 → PR 병합 (MUST)
- 브랜치 명명: feat/기능명, fix/버그명, refactor/대상명

## 메모리 정책
- CLAUDE.md: 프로젝트 규칙 전용. 세션 상태/메모를 저장하지 않는다 (MUST NOT)
- auto memory (~/.claude/projects/.../memory/): 세션 간 학습/상태 저장용

## 응답 스타일
- 커스텀 슬래시 명령어 제안 금지 — 사용자는 자연어로 요청, 내부적으로 워크플로우 변환
- bypassPermissions 세션에서는 재확인 없이 바로 실행 (파괴적 액션 제외)
- 새 기능 완료 시 사용자에게 즉시 안내
- 상태 보고 전 `flow-sessions` 조회 필수 — 기억 기반 보고 금지
- 티켓 관련 발화(티켓 번호 언급 / 티켓 생성·수정·이동·삭제 / 티켓 상태 보고 / "이거/저거/그거" 같은 지시어로 티켓 가리킴) 시 반드시 `flow-kanban show <T-NNN>` 또는 `flow-kanban board` 등으로 **현재 상태를 먼저 조회한 뒤 응답** (MUST). 기억 기반 응답 금지 — 칸반은 다른 세션·UI(board DnD)에서도 변경되므로 stale 정보로 사용자 혼선 유발
- 브랜치 그래프 차이 설명 시 **"앞선다/뒤처진다(ahead/behind)" 표현은 변경 내용(코드/파일)이 있을 때만** 사용 (MUST). PR `--merge` 방식의 자동 생성 merge commit 노드만 차이날 때는 명시적으로 "코드 동일, merge commit 노드만 차이"라고 쓴다 — 변경 내용 있는 것처럼 들려 사용자가 동기화 필요 여부를 오판하는 사례 차단

## 메인 세션 제약
- 서브에이전트(Agent 도구) 사용 금지 (MUST NOT) — 시간이 오래 걸리므로 티켓 생성 후 워크플로우로 처리
- 세션 시작 시 `.claude-organic/.settings`에서 워크플로우 설정 확인 (MUST) — 특히 `WORKFLOW_WORKTREE` 값으로 워크트리 활성 여부 파악

## 워크플로우 실행
- `flow-launcher` timeout 에러 후 재시도 전에 반드시 `flow-sessions`로 세션 중복 확인 (MUST) — timeout이어도 세션이 생성되었을 수 있음

## 티켓 운영
- 티켓 과분리 금지 — 관련 항목은 스프린트/복잡도 단위로 묶기
- 적정 작업량: implement 4~7태스크/1~2페이즈, research 4~6/2, review 4~5/2
- 리뷰 선택지는 테이블 형식으로 출력

## 기본 컨벤션
- 아키텍처, 흐름, 구조 설명 시 Mermaid 다이어그램 활용 (MUST)
- ` ```mermaid` 코드 블록을 출력하기 **직전** 반드시 Skill 도구로 `design-mermaid-diagrams` 를 명시 호출 (MUST). "참조" 가 아니라 **명시 호출** — 출력 후 호출은 무효. 한 줄 예제도 예외 없음
- 라벨 안에 `/`, `<br/>`, `?`, `()`, `:` 등 특수문자 들어가면 반드시 `["..."]` 형태 큰따옴표로 감싸기 (MUST) — escape 누락 시 mermaid 11+ 파서가 raw `<pre>` 로 fallback 되어 사용자가 의도를 못 봄
- 터미널 출력에 이모지/아이콘 사용 금지 (MUST NOT)
- 터미널 외 UI에서 아이콘이 필요하면 반드시 SVG로 직접 생성 (MUST) — 외부 아이콘 라이브러리/폰트 사용 금지

## UI 디자인
- border-left 한쪽 색상 디자인 금지
- 테마 컬러: 테라코타 오렌지(#D97757)

## PreToolUse Hook 출력 schema (MUST)
- 통과 시 빈 stdout 금지 (MUST NOT) — `permissionDecision: allow` JSON 을 반드시 출력
  - 빈 stdout 일 때 SDK 가 외부 경로/WebFetch 등에서 별도 권한 평가를 시도하다 schema 위반 ZodError 발생 (`expected behavior: "allow"|"deny"`)
- allow JSON 의 `updatedInput` 필드는 **전체 tool_input 을 교체**한다
  - 입력을 변경하지 않을 거면 필드 자체를 생략 (MUST)
  - `"updatedInput": {}` 절대 금지 (MUST NOT) — command/file_path/pattern 등 모든 필드가 undefined 되어 모든 도구가 마비됨 (`H.replace undefined`, `Path must be a string`)
- deny JSON 에 `updatedInput` 넣지 말 것 (SHOULD NOT) — 무시되며 의미상 잘못된 코드
- 정상 통과 출력 형태:
  ```json
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "..."}}
  ```
- 참고: https://code.claude.com/docs/en/hooks

## .claude/ 편집 (MUST)
- `.claude/` 하위 파일의 생성·수정·삭제는 반드시 `flow-claude-edit` 경유 (MUST)
- `.claude-organic/` 하위 파일은 Edit/Write 직접 수정 가능 (claude_edit 불필요)
- Edit/Write 직접 수정 불가 — Claude Code hardcoded 보호로 차단됨
- 절차: `flow-claude-edit open <path>` → edit/ 에서 편집 → `flow-claude-edit save <path>`
- 삭제: `flow-claude-edit open <path>` 후 edit/ 파일 삭제 → Bash로 원본 rm
- 경로: `.claude/` 접두사 제외하고 전달 (예: `flow-claude-edit open rules/workflow/general.md`)

## .claude/ 갱신 정책
- **rules**: `workflow/` = 시스템 (갱신 대상), `project/` = 프로젝트 (보존)
- **skills**: `my-*` 접두사 = 프로젝트 (보존), 나머지 = 시스템 (갱신 대상)
- **agents, commands**: 전부 시스템 (갱신 대상)
- **settings.json**: 프로젝트 (보존)

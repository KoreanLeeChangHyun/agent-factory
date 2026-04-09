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

## 메인 세션 제약
- 서브에이전트(Agent 도구) 사용 금지 (MUST NOT) — 시간이 오래 걸리므로 티켓 생성 후 워크플로우로 처리
- 세션 시작 시 `.claude.workflow/.settings`에서 워크플로우 설정 확인 (MUST) — 특히 `WORKFLOW_WORKTREE` 값으로 워크트리 활성 여부 파악

## 워크플로우 실행
- `flow-launcher` timeout 에러 후 재시도 전에 반드시 `flow-sessions`로 세션 중복 확인 (MUST) — timeout이어도 세션이 생성되었을 수 있음

## 티켓 운영
- 티켓 과분리 금지 — 관련 항목은 스프린트/복잡도 단위로 묶기
- 적정 작업량: implement 4~7태스크/1~2페이즈, research 4~6/2, review 4~5/2
- 리뷰 선택지는 테이블 형식으로 출력

## 기본 컨벤션
- 아키텍처, 흐름, 구조 설명 시 Mermaid 다이어그램 활용 (MUST)
- 터미널 출력에 이모지/아이콘 사용 금지 (MUST NOT)
- 터미널 외 UI에서 아이콘이 필요하면 반드시 SVG로 직접 생성 (MUST) — 외부 아이콘 라이브러리/폰트 사용 금지

## UI 디자인
- border-left 한쪽 색상 디자인 금지
- 테마 컬러: 테라코타 오렌지(#D97757)

## .claude/ 편집 (MUST)
- `.claude/` 하위 파일의 생성·수정·삭제는 반드시 `flow-claude-edit` 경유 (MUST)
- `.claude.workflow/` 하위 파일은 Edit/Write 직접 수정 가능 (claude_edit 불필요)
- Edit/Write 직접 수정 불가 — Claude Code hardcoded 보호로 차단됨
- 절차: `flow-claude-edit open <path>` → edit/ 에서 편집 → `flow-claude-edit save <path>`
- 삭제: `flow-claude-edit open <path>` 후 edit/ 파일 삭제 → Bash로 원본 rm
- 경로: `.claude/` 접두사 제외하고 전달 (예: `flow-claude-edit open rules/workflow/general.md`)

## .claude/ 갱신 정책
- **rules**: `workflow/` = 시스템 (갱신 대상), `project/` = 프로젝트 (보존)
- **skills**: `my-*` 접두사 = 프로젝트 (보존), 나머지 = 시스템 (갱신 대상)
- **agents, commands**: 전부 시스템 (갱신 대상)
- **settings.json**: 프로젝트 (보존)

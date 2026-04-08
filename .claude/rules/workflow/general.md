# 일반 규칙

## 응답 스타일
- 커스텀 슬래시 명령어 제안 금지 — 사용자는 자연어로 요청, 내부적으로 워크플로우 변환
- bypassPermissions 세션에서는 재확인 없이 바로 실행 (파괴적 액션 제외)
- 새 기능 완료 시 사용자에게 즉시 안내
- 상태 보고 전 `flow-sessions` 조회 필수 — 기억 기반 보고 금지

## 메인 세션 제약
- 서브에이전트(Agent 도구) 사용 금지 (MUST NOT) — 시간이 오래 걸리므로 티켓 생성 후 워크플로우로 처리

## 티켓 운영
- 티켓 과분리 금지 — 관련 항목은 스프린트/복잡도 단위로 묶기
- 적정 작업량: implement 4~7태스크/1~2페이즈, research 4~6/2, review 4~5/2
- 리뷰 선택지는 테이블 형식으로 출력

## UI 디자인
- border-left 한쪽 색상 디자인 금지
- 테마 컬러: 테라코타 오렌지(#D97757)

## .claude/ 편집 (MUST)
- `.claude/` 하위 파일의 생성·수정·삭제는 반드시 `claude_edit.py` 경유 (MUST)
- Edit/Write 직접 수정 불가 — Claude Code hardcoded 보호로 차단됨
- 절차: `claude_edit.py open <path>` → edit/ 에서 편집 → `claude_edit.py save <path>`
- 삭제: `claude_edit.py open <path>` 후 edit/ 파일 삭제 → Bash로 원본 rm

## .claude/ 갱신 정책
- **rules**: `workflow/` = 시스템 (갱신 대상), `project/` = 프로젝트 (보존)
- **skills**: `my-*` 접두사 = 프로젝트 (보존), 나머지 = 시스템 (갱신 대상)
- **agents, commands**: 전부 시스템 (갱신 대상)
- **settings.json**: 프로젝트 (보존)

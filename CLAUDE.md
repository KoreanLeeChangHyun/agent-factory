# CLAUDE.md

## 언어 및 톤
- 언어: 한국어
- 톤: 존댓말

## 핵심 원칙

### 브랜치 정책
- 메인 브랜치(main/master)에 직접 커밋 절대 금지 (MUST NOT)
- 모든 변경은 피처 브랜치 생성 → PR 병합 (MUST)
- 브랜치 명명: feat/기능명, fix/버그명, refactor/대상명

### 메인 세션 정책
- 기본: 워크플로우 티켓 기반(/wf)으로 처리
- 직접 수정: 사용자가 명시적으로 요청한 경우에만 허용
- PreToolUse Hook 활성 시 직접 수정 차단됨 (환경 설정 따름)
- 기본 역할: 티켓 관리·상태 확인·결과 리뷰 등 조율(orchestration)

### 티켓 운영
- 자연어 요청도 워크플로우 명령으로 변환하여 처리
- 파일 직접 수정 시 Hook이 차단하므로 티켓 생성 필수
- flow-kanban 복수 항목 필드(goal, target, constraints, criteria, context)는 \n 개행 삽입 (MUST)

### 메모리 정책
- CLAUDE.md: 프로젝트 규칙 전용. 세션 상태/메모를 저장하지 않는다 (MUST NOT)
- auto memory (~/.claude/projects/.../memory/): 세션 간 학습/상태 저장용


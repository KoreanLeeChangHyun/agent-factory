# 일반 규칙

## 응답 스타일
- 커스텀 슬래시 명령어 제안 금지 — 사용자는 자연어로 요청, 내부적으로 워크플로우 변환
- bypassPermissions 세션에서는 재확인 없이 바로 실행 (파괴적 액션 제외)
- 새 기능 완료 시 사용자에게 즉시 안내
- 상태 보고 전 `flow-sessions` 조회 필수 — 기억 기반 보고 금지

## 티켓 운영
- 티켓 과분리 금지 — 관련 항목은 스프린트/복잡도 단위로 묶기
- 적정 작업량: implement 4~7태스크/1~2페이즈, research 4~6/2, review 4~5/2
- 리뷰 선택지는 테이블 형식으로 출력

## UI 디자인
- border-left 한쪽 색상 디자인 금지
- 테마 컬러: 테라코타 오렌지(#D97757)

## .claude/ 편집
- Edit/Write 직접 수정 불가 (Claude Code hardcoded 보호)
- `claude_edit.py open/save/diff` 로 간접 편집

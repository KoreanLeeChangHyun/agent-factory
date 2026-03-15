---
name: workflow-wf-submit
description: "Workflow command skill for wf -s. Submits a ticket and auto-routes to the appropriate workflow (implement/research/review) based on the <command> tag in the ticket XML."
disable-model-invocation: true
license: "Apache-2.0"
---

# Submit Command (티켓 제출)

`.kanban/T-NNN.xml` 티켓 파일의 `<command>` 태그를 읽어 해당 워크플로우를 자동 실행하는 커맨드 스킬.

상세 실행 절차는 `.claude/commands/wf.md`를 참조한다.

## 메타데이터

### 자동 라우팅 매핑

| `<command>` 값 | 실행 커맨드 |
|---------------|-----------|
| `implement` | `/wf -s #N` (implement 모드) |
| `research` | `/wf -s #N` (research 모드) |
| `review` | `/wf -s #N` (review 모드) |

### 티켓 파일 처리 규칙

- `#N` 지정 시: `.kanban/T-NNN.xml` 정확 매칭으로 티켓 파일 탐색
- `#N` 미지정 시: `.kanban/` 디렉터리의 XML 파일을 스캔하여 Open 상태 티켓을 자동 선택
- `<current>` 값이 `0` 또는 미존재 시: 에러 출력 후 종료
- `<command>` 유효 값: `implement`, `research`, `review`

### 비워크플로우 독립 명령어

이 스킬은 워크플로우 FSM과 무관하게 독립 실행된다. 사용 가능 도구: Bash, Glob, Read. Task 도구 호출 금지.

## 참조

이 스킬의 실행 절차는 대응 커맨드 파일(`.claude/commands/wf.md`)이 Single Source of Truth이다.

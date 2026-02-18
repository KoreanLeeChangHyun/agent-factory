# TaskCompleted

## 발생 시점

TaskUpdate 도구로 태스크를 완료 처리하거나 Agent Teams 팀원이 in-progress 태스크와 함께 종료 시 발생한다.

## 매처 입력 (matcher_input)

매처 없음. 항상 실행된다.

## 핸들러 타입

- command (전용)

> prompt 및 agent 타입 핸들러는 미지원.

## 차단 가능 여부

가능. exit code 2만 지원 (JSON 결정 반환 불가).

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "task_id": "task-001",
  "task_subject": "Implement user authentication",
  "task_description": "Add login and signup endpoints",
  "teammate_name": "implementer",
  "team_name": "my-project"
}
```

## 제약사항

- Agent Teams 전용 이벤트
- command 타입만 사용 가능
- exit code 2로만 차단 가능 (JSON 결정 반환 불가)

## 사용 예시

```json
{
  "hooks": {
    "TaskCompleted": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/task-completed/notify-completion.sh",
            "async": true,
            "statusMessage": "태스크 완료 알림 중..."
          }
        ]
      }
    ]
  }
}
```

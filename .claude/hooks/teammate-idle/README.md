# TeammateIdle

## 발생 시점

Agent Teams에서 팀원이 idle 전환 직전에 발생한다.

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
  "teammate_name": "researcher",
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
    "TeammateIdle": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/teammate-idle/reassign-task.sh",
            "statusMessage": "팀원 idle 처리 중..."
          }
        ]
      }
    ]
  }
}
```

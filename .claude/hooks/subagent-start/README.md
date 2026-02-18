# SubagentStart

## 발생 시점

Task 도구로 서브에이전트를 스폰할 때 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `agent_type` | `Bash`, `Explore`, `Plan`, 커스텀 에이전트 이름 |

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

불가.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "agent_id": "agent-abc123",
  "agent_type": "Explore"
}
```

## JSON 출력

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "서브에이전트에 주입할 컨텍스트"
  }
}
```

## 사용 예시

```json
{
  "hooks": {
    "SubagentStart": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/subagent-start/inject-context.sh",
            "statusMessage": "서브에이전트 컨텍스트 주입 중..."
          }
        ]
      }
    ]
  }
}
```

# SubagentStop

## 발생 시점

서브에이전트가 응답을 완료했을 때 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `agent_type` | `Bash`, `Explore`, `Plan`, 커스텀 에이전트 이름 |

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

가능. Stop과 동일한 방식으로 차단할 수 있다.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "stop_hook_active": false,
  "agent_id": "def456",
  "agent_type": "Explore",
  "agent_transcript_path": "~/.claude/projects/.../abc123/subagents/agent-def456.jsonl"
}
```

## 특수 필드

- `agent_transcript_path`: 서브에이전트 자체 트랜스크립트 경로 (메인 세션의 `transcript_path`와 별도)

## 사용 예시

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/subagent-stop/usage-tracker.sh",
            "async": true,
            "timeout": 30,
            "statusMessage": "사용량 추적"
          }
        ]
      }
    ]
  }
}
```

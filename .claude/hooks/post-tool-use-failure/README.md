# PostToolUseFailure

## 발생 시점

도구 호출이 실패한 후 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `tool_name` | `Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `Task`, `WebFetch`, `WebSearch`, `mcp__*` |

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

불가. 이미 실패가 발생한 상태.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "tool_name": "Bash",
  "tool_input": { "command": "npm test" },
  "tool_use_id": "toolu_01ABC123...",
  "error": "Command exited with non-zero status code 1",
  "is_interrupt": false
}
```

## 사용 예시

```json
{
  "hooks": {
    "PostToolUseFailure": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/post-tool-use-failure/error-logger.sh",
            "async": true,
            "statusMessage": "실패 로그 기록 중..."
          }
        ]
      }
    ]
  }
}
```

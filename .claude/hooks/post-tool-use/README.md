# PostToolUse

## 발생 시점

도구 호출이 성공한 직후 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `tool_name` | `Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `Task`, `WebFetch`, `WebSearch`, `mcp__*` |

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

불가. 이미 실행이 완료되었으나, 피드백(additionalContext)은 가능하다.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "tool_name": "Write",
  "tool_input": { "file_path": "/path/to/file.txt", "content": "..." },
  "tool_response": { "filePath": "/path/to/file.txt", "success": true },
  "tool_use_id": "toolu_01ABC123..."
}
```

## JSON 출력

```json
{
  "decision": "block",
  "reason": "이유",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "추가 컨텍스트",
    "updatedMCPToolOutput": "..."
  }
}
```

- `updatedMCPToolOutput`은 MCP 도구 전용 (출력 교체)

## 사용 예시

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/post-tool-use/lint-check.sh",
            "statusMessage": "린트 검사 중..."
          }
        ]
      }
    ]
  }
}
```

# PreToolUse

## 발생 시점

도구 파라미터 생성 후, 도구 실행 전에 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `tool_name` | `Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `Task`, `WebFetch`, `WebSearch`, `mcp__*` |

MCP 도구는 `mcp__<서버>__<도구>` 패턴으로 매칭 가능.

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

가능. `hookSpecificOutput.permissionDecision: "deny"`로 도구 실행을 차단할 수 있다.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "tool_name": "Bash",
  "tool_input": { "command": "npm test" },
  "tool_use_id": "toolu_01ABC123..."
}
```

## JSON 출력 (hookSpecificOutput 패턴)

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "이유",
    "updatedInput": { "field": "new_value" },
    "additionalContext": "컨텍스트 문자열"
  }
}
```

> 구형 top-level `decision`/`reason` 필드는 deprecated. `hookSpecificOutput` 패턴 사용 필수.

## 사용 예시

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/pre-tool-use/dangerous-command-guard.sh",
            "statusMessage": "위험 명령어 검사 중..."
          }
        ]
      }
    ]
  }
}
```

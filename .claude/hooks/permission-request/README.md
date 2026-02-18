# PermissionRequest

## 발생 시점

사용자에게 권한 대화가 표시되려는 시점에 발생한다. PreToolUse보다 나중에 발생하며, 권한 대화가 필요한 경우에만 실행된다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `tool_name` | `Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `Task`, `WebFetch`, `WebSearch`, `mcp__*` |

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

가능. `hookSpecificOutput.decision.behavior: "deny"`로 차단할 수 있다.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "tool_name": "Bash",
  "tool_input": { "command": "rm -rf node_modules" },
  "permission_suggestions": [
    { "type": "toolAlwaysAllow", "tool": "Bash" }
  ]
}
```

## JSON 출력

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow|deny",
      "updatedInput": {},
      "updatedPermissions": {},
      "message": "이유",
      "interrupt": true
    }
  }
}
```

- `updatedInput`, `updatedPermissions`: allow 시에만 사용
- `message`, `interrupt`: deny 시에만 사용. `interrupt: true`이면 Claude 중단

## PreToolUse와의 차이

- **PreToolUse**: 권한 상태와 무관하게 모든 도구 호출 전 실행
- **PermissionRequest**: 권한 대화가 표시될 때만 실행 (이미 허용된 도구는 트리거되지 않음)

## 사용 예시

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/permission-request/auto-approve.sh",
            "statusMessage": "권한 자동 승인 검사 중..."
          }
        ]
      }
    ]
  }
}
```

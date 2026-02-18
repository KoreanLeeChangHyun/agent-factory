# SessionEnd

## 발생 시점

세션이 종료될 때 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `reason` | `clear`, `logout`, `prompt_input_exit`, `bypass_permissions_disabled`, `other` |

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
  "reason": "other"
}
```

## 사용 예시

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/session-end/cleanup.sh",
            "timeout": 30,
            "async": true
          }
        ]
      }
    ]
  }
}
```

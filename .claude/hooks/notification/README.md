# Notification

## 발생 시점

Claude Code가 알림을 전송할 때 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `notification_type` | `permission_prompt`, `idle_prompt`, `auth_success`, `elicitation_dialog` |

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
  "message": "Claude needs your permission to use Bash",
  "title": "Permission needed",
  "notification_type": "permission_prompt"
}
```

## 사용 예시

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "permission_prompt|idle_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/notification/slack-notify.sh",
            "async": true,
            "statusMessage": "Slack 알림 전송 중..."
          }
        ]
      }
    ]
  }
}
```

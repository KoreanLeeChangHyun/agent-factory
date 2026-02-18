# PreCompact

## 발생 시점

컨텍스트 컴팩션 실행 직전에 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `trigger` | `manual` (/compact 명령), `auto` (자동 컴팩션) |

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
  "trigger": "manual",
  "custom_instructions": ""
}
```

- `custom_instructions`: /compact에 전달된 사용자 지시사항

## 사용 예시

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/pre-compact/save-context.sh",
            "statusMessage": "컴팩션 전 컨텍스트 저장 중..."
          }
        ]
      }
    ]
  }
}
```

# SessionStart

## 발생 시점

새 세션 시작 또는 기존 세션 재개 시 발생한다.

## 매처 입력 (matcher_input)

| 필드 | 값 |
|------|-----|
| `source` | `startup` (새 세션), `resume` (--resume/--continue/재개), `clear` (/clear 후), `compact` (컴팩션 후) |

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

불가. exit 2 시 stderr를 사용자에게만 표시.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "source": "startup",
  "model": "claude-sonnet-4-6",
  "agent_type": "custom-agent-name"
}
```

- `agent_type`은 `--agent` 옵션 사용 시에만 포함

## 특수 기능

- stdout 출력이 Claude 컨텍스트에 직접 추가됨 (다른 이벤트와 다름)
- `CLAUDE_ENV_FILE` 환경변수로 이후 Bash 명령에 지속될 환경변수 설정 가능

## 사용 예시

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "echo '프로젝트 컨텍스트 로드 완료'",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

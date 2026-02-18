# Stop

## 발생 시점

메인 Claude 에이전트 응답 완료 시 발생한다. 사용자 인터럽트로 인한 중단 시에는 발생하지 않는다.

## 매처 입력 (matcher_input)

매처 없음. 항상 실행된다.

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

가능. `decision: "block"` + `reason`으로 Claude가 계속 작업하도록 할 수 있다.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "stop_hook_active": true
}
```

> `stop_hook_active`가 `true`이면 이미 Stop Hook으로 계속 진행 중인 상태. 무한 루프 방지를 위해 이 값을 반드시 확인해야 한다.

## JSON 출력

```json
{
  "decision": "block",
  "reason": "계속 작업해야 하는 이유 (필수)"
}
```

## 사용 예시

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/stop/auto-continue.sh",
            "timeout": 30,
            "statusMessage": "계속 여부 확인"
          }
        ]
      }
    ]
  }
}
```

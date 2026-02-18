# UserPromptSubmit

## 발생 시점

사용자가 프롬프트를 제출하고 Claude가 처리하기 전에 발생한다.

## 매처 입력 (matcher_input)

매처 없음. 항상 실행된다.

## 핸들러 타입

- command
- prompt
- agent

## 차단 가능 여부

가능. `decision: "block"` + `reason`으로 프롬프트를 차단하고 컨텍스트에서 제거할 수 있다.

## stdin JSON 필드

공통 필드 외 추가:

```json
{
  "prompt": "Write a function to calculate the factorial of a number"
}
```

## 특수 기능

- stdout 출력이 Claude 컨텍스트에 직접 추가됨 (다른 이벤트와 다름)
- JSON 출력으로 `additionalContext` 제공 가능 (비공개 컨텍스트)

## 사용 예시

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/user-prompt-submit/validate-prompt.sh",
            "statusMessage": "프롬프트 검증 중..."
          }
        ]
      }
    ]
  }
}
```

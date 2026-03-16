# Tool Use Reference

공식 문서: https://platform.claude.com/docs/en/build-with-claude/tool-use/overview

## 도구 정의 스키마 (Custom Tool)

```json
{
  "type": "custom",
  "name": "get_weather",
  "description": "특정 위치의 현재 날씨를 반환합니다 (설명 강력 권장)",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "도시명, 예: San Francisco, CA"
      }
    },
    "required": ["location"]
  }
}
```

`strict: true` 추가 시 스키마 일치 보장 (Structured Outputs).

## 서버 내장 도구

| 도구명 | 용도 |
|--------|------|
| `web_search` | 웹 검색 |
| `web_fetch` | 웹 콘텐츠 가져오기 |
| `code_execution` | Python 코드 실행 |
| `bash_code_execution` | Bash 명령 실행 |
| `text_editor_code_execution` | 파일 편집 |
| `memory` | 영구 메모리 저장 |

## tool_choice 옵션

| 값 | 동작 |
|----|------|
| `{"type": "auto"}` | 모델이 도구 사용 여부 결정 (기본값) |
| `{"type": "any"}` | 반드시 도구 중 하나 선택 |
| `{"type": "tool", "name": "..."}` | 특정 도구 강제 사용 |
| `{"type": "none"}` | 도구 사용 금지 |

## Tool Use 전체 흐름

### Step 1: 사용자 요청 + 도구 정의

```json
{
  "model": "claude-opus-4-6",
  "max_tokens": 1024,
  "tools": [{ "name": "get_weather", ... }],
  "messages": [{"role": "user", "content": "샌프란시스코 날씨?"}]
}
```

### Step 2: 모델 응답 (tool_use)

```json
{
  "stop_reason": "tool_use",
  "content": [
    {"type": "text", "text": "날씨를 확인하겠습니다."},
    {
      "type": "tool_use",
      "id": "toolu_abc123",
      "name": "get_weather",
      "input": {"location": "San Francisco, CA"}
    }
  ]
}
```

### Step 3: 도구 결과 반환

```json
{
  "messages": [
    {"role": "user", "content": "샌프란시스코 날씨?"},
    {"role": "assistant", "content": [/* Step 2 content */]},
    {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "toolu_abc123",
          "content": "현재 온도: 15°C, 흐림"
        }
      ]
    }
  ]
}
```

### Step 4: 최종 응답 (stop_reason: end_turn)

```json
{"content": [{"type": "text", "text": "샌프란시스코는 현재 15°C이며 흐립니다."}]}
```

## 오류가 있는 도구 결과

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_abc123",
  "is_error": true,
  "content": "날씨 API 연결 실패"
}
```

## Extended Thinking과 Tool Use

Extended Thinking + Tool Use 사용 시 `tool_choice`는 `auto` 또는 `none`만 허용.
`any`나 특정 도구 강제(`tool`) 사용 시 에러 발생.

인터리빙 사용 시: `interleaved-thinking-2025-05-14` beta 헤더 추가.

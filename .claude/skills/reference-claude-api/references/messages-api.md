# Messages API Reference

공식 문서: https://platform.claude.com/docs/en/api/messages

## 엔드포인트

```
POST https://api.anthropic.com/v1/messages
```

## 필수 헤더

```
x-api-key: $ANTHROPIC_API_KEY
anthropic-version: 2023-06-01
content-type: application/json
```

## 요청 파라미터

### 필수

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `model` | string | 모델 ID (예: `claude-opus-4-6`) |
| `max_tokens` | number | 최대 생성 토큰 수 (모델별 상한 있음) |
| `messages` | MessageParam[] | `user`/`assistant` 교대 배열 |

### 선택

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `system` | string \| TextBlockParam[] | 시스템 프롬프트 |
| `stream` | boolean | SSE 스트리밍 활성화 |
| `temperature` | number | 무작위성 (0.0-1.0, 기본 1.0) |
| `top_p` | number | 누클리어스 샘플링 |
| `top_k` | number | Top-K 샘플링 |
| `stop_sequences` | string[] | 생성 중단 문자열 |
| `tools` | ToolUnion[] | 도구 정의 목록 |
| `tool_choice` | ToolChoice | `auto` \| `any` \| `tool` \| `none` |
| `thinking` | ThinkingConfigParam | Extended Thinking 설정 |
| `cache_control` | CacheControlEphemeral | 프롬프트 캐싱 설정 |
| `metadata` | Metadata | 외부 사용자 ID (남용 탐지용) |
| `service_tier` | `"auto"` \| `"standard_only"` | 우선순위 처리 |

## 메시지 구조

```json
{
  "role": "user",
  "content": "텍스트 문자열 또는 ContentBlockParam 배열"
}
```

### content block 타입 (입력)

| 타입 | 주요 필드 |
|------|---------|
| `text` | `text: string`, `cache_control?` |
| `image` | `source: {type: "base64", media_type, data}` 또는 `{type: "url", url}` |
| `document` | `source: Base64PDFSource \| URLPDFSource \| PlainTextSource` |
| `tool_use` | `id`, `name`, `input` |
| `tool_result` | `tool_use_id`, `content?`, `is_error?` |
| `thinking` | `thinking: string`, `signature: string` |

## 응답 구조

```json
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "content": [ContentBlock],
  "model": "claude-opus-4-6",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 25,
    "output_tokens": 1024,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  }
}
```

### stop_reason 값

| 값 | 의미 |
|----|------|
| `end_turn` | 자연 종료 |
| `stop_sequence` | 지정 중단 문자열 도달 |
| `max_tokens` | 최대 토큰 한도 도달 |
| `tool_use` | 도구 호출 |

### content block 타입 (응답)

| 타입 | 주요 필드 |
|------|---------|
| `text` | `text: string`, `citations?` |
| `tool_use` | `id`, `name`, `input: object` |
| `thinking` | `thinking: string` |
| `redacted_thinking` | `data: string` |

## 기본 예시

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello, Claude"}]
  }'
```

## 이미지 입력 예시

```json
{
  "role": "user",
  "content": [
    {
      "type": "image",
      "source": {
        "type": "base64",
        "media_type": "image/jpeg",
        "data": "<base64_string>"
      }
    },
    {"type": "text", "text": "이 이미지에 무엇이 있나요?"}
  ]
}
```

지원 이미지 형식: `image/jpeg`, `image/png`, `image/gif`, `image/webp`

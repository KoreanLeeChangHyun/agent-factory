# Streaming Reference

공식 문서: https://platform.claude.com/docs/en/api/messages-streaming

## 활성화

요청에 `"stream": true` 추가.

## SSE 이벤트 흐름

```
message_start
  content_block_start (index: 0)
    content_block_delta* (text_delta / thinking_delta / input_json_delta)
  content_block_stop (index: 0)
  [content_block_start ... content_block_stop]*
message_delta
message_stop
[ping]*  (언제든 삽입 가능)
```

## 이벤트별 구조

### message_start

```json
{"type": "message_start", "message": {"id": "msg_...", "type": "message", "role": "assistant", "content": [], "model": "claude-opus-4-6", "stop_reason": null, "usage": {"input_tokens": 25, "output_tokens": 1}}}
```

### content_block_start

```json
{"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
```

### content_block_delta

**text_delta:**
```json
{"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}
```

**input_json_delta** (tool_use):
```json
{"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "{\"location\": \"San Fra"}}
```
`content_block_stop` 이후 부분 JSON을 합쳐 파싱.

**thinking_delta** (Extended Thinking):
```json
{"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "분석 중..."}}
```

**signature_delta** (thinking 블록 종료 직전):
```json
{"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "EqQBCg..."}}
```

### message_delta

```json
{"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": null}, "usage": {"output_tokens": 128}}
```
`usage`의 토큰 수는 **누적값**.

### message_stop

```json
{"type": "message_stop"}
```

### error (스트림 중 오류)

```json
{"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}
```

## SDK 사용 예시

```python
# Python SDK
with client.messages.stream(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    # 완료 후 전체 Message 객체 필요 시:
    message = stream.get_final_message()
```

```typescript
// TypeScript SDK
await client.messages
  .stream({model: "claude-opus-4-6", max_tokens: 1024, messages: [...]})
  .on("text", (text) => process.stdout.write(text));

// 전체 Message 객체:
const message = await stream.finalMessage();
```

## 주의사항

- 스트리밍 중 200 응답 후에도 에러 이벤트 발생 가능
- `tool_use` 블록은 `content_block_stop` 이전까지 부분 JSON 누적 필요
- 장기 요청(10분+)은 반드시 스트리밍 또는 Batch API 사용

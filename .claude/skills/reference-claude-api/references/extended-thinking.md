# Extended Thinking Reference

공식 문서: https://platform.claude.com/docs/en/build-with-claude/extended-thinking

## 활성화

```json
{
  "thinking": {
    "type": "enabled",
    "budget_tokens": 10000
  }
}
```

**Claude Opus 4.6**: `type: "adaptive"` 사용 (manual 모드 deprecated).

## budget_tokens

- 모델이 내부 추론에 사용할 최대 토큰 수
- `max_tokens`보다 작아야 함 (인터리빙 제외)
- 모델이 반드시 전부 사용하지는 않음
- 최소: 1,024 tokens

## 응답 구조

```json
{
  "content": [
    {
      "type": "thinking",
      "thinking": "단계별 분석...",
      "signature": "WaUjzkypQ2mUEVM36O2TxuC06KN8..."
    },
    {
      "type": "text",
      "text": "분석 결과:"
    }
  ]
}
```

`redacted_thinking` 블록: 보안 이유로 일부 thinking 내용 숨김.

## Streaming + Extended Thinking

스트리밍 시 `thinking_delta` 이벤트로 수신:

```
content_block_start (type: "thinking")
  content_block_delta (thinking_delta) *
  content_block_delta (signature_delta)   ← thinking 블록 종료 직전
content_block_stop
```

## 인터리빙 (Interleaved Thinking)

도구 호출 사이에 thinking 블록 삽입.

| 모델 | 활성화 방법 |
|------|-----------|
| Claude Opus 4.6 | adaptive thinking 자동 활성화 |
| Claude Sonnet 4.6 | beta 헤더 `interleaved-thinking-2025-05-14` |
| 기타 Claude 4 | beta 헤더 `interleaved-thinking-2025-05-14` |

**인터리빙 없이:**
```
[thinking] → [tool_use] → (결과) → [tool_use] → [text]
```

**인터리빙 활성화:**
```
[thinking] → [tool_use] → (결과) → [thinking] → [tool_use] → (결과) → [thinking] → [text]
```

인터리빙 시 `budget_tokens`는 한 턴의 모든 thinking 블록 합산 예산이므로 `max_tokens` 초과 가능.

## Tool Use 제약

Extended Thinking + Tool Use 조합 시:
- `tool_choice: auto` 또는 `none`만 허용
- `tool_choice: any` 또는 특정 도구 강제 사용 시 400 에러

## Fine-Grained Tool Streaming

세밀한 도구 스트리밍: beta 헤더 `fine-grained-tool-streaming-2025-05-14` 추가.

---
name: reference-claude-api
description: "Reference skill for Anthropic Claude API. Use when implementing or debugging Claude API integrations: Messages API parameters, Tool Use schema and flow, Streaming SSE events, Extended Thinking, Prompt Caching, model selection, and error handling."
license: "Apache-2.0"
---

# Claude API Reference

Anthropic Claude API 공식문서 기반 레퍼런스. 구현 시 필요한 섹션만 참조하세요.

- 공식 문서: [platform.claude.com/docs](https://platform.claude.com/docs/en/api/messages)
- API 기본 URL: `https://api.anthropic.com`
- 필수 헤더: `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json`

## 모델 목록

| 모델 | API ID | 컨텍스트 | 최대 출력 | 가격(입력/출력, MTok) |
|------|--------|---------|---------|---------------------|
| Claude Opus 4.6 | `claude-opus-4-6` | 1M | 128k | $5 / $25 |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | 64k | $3 / $15 |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | 200k | 64k | $1 / $5 |
| Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | 200k/1M* | 64k | $3 / $15 |
| Claude Opus 4 | `claude-opus-4-20250514` | 200k | 32k | $15 / $75 |

*`context-1m-2025-08-07` beta 헤더로 1M 활성화

상세 섹션별 레퍼런스는 `references/` 하위 파일을 참조하세요:

- **Messages API**: `references/messages-api.md` — 엔드포인트, 파라미터, 응답 구조
- **Tool Use**: `references/tool-use.md` — 도구 정의 스키마, 호출 흐름, tool_choice
- **Streaming**: `references/streaming.md` — SSE 이벤트 타입, delta 구조
- **Extended Thinking**: `references/extended-thinking.md` — thinking 파라미터, 인터리빙
- **Prompt Caching**: `references/prompt-caching.md` — cache_control, TTL, 비용
- **Errors**: `references/errors.md` — HTTP 에러 코드, 에러 객체 구조

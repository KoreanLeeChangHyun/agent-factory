# Prompt Caching Reference

공식 문서: https://platform.claude.com/docs/en/build-with-claude/prompt-caching

## 빠른 시작 (자동 캐싱 - 권장)

요청 최상위에 `cache_control` 추가:

```python
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    cache_control={"type": "ephemeral"},
    system="시스템 프롬프트...",
    messages=[{"role": "user", "content": "질문"}],
)
```

## 명시적 캐시 브레이크포인트

특정 content block에 `cache_control` 지정:

```json
{
  "system": [
    {"type": "text", "text": "기본 지침"},
    {
      "type": "text",
      "text": "[대용량 문서]",
      "cache_control": {"type": "ephemeral"}
    }
  ]
}
```

최대 4개의 캐시 브레이크포인트 설정 가능.

## TTL (캐시 수명)

| TTL | 설정 | 비용 배수 |
|-----|------|---------|
| 5분 (기본) | `{"type": "ephemeral"}` | 캐시 쓰기: 1.25x |
| 1시간 | `{"type": "ephemeral", "ttl": "1h"}` | 캐시 쓰기: 2x |

캐시 히트 시 재사용은 무료 갱신(TTL 리셋).

## 가격 (100만 토큰 기준)

| 모델 | 기본 입력 | 5m 쓰기 | 1h 쓰기 | 캐시 히트 | 출력 |
|------|---------|--------|--------|---------|------|
| Opus 4.6 | $5 | $6.25 | $10 | $0.50 | $25 |
| Sonnet 4.6 | $3 | $3.75 | $6 | $0.30 | $15 |
| Haiku 4.5 | $1 | $1.25 | $2 | $0.10 | $5 |

캐시 히트 = 기본 입력의 0.1x.

## 최소 캐시 가능 길이

| 모델 | 최소 토큰 |
|------|---------|
| Claude Opus 4.6, 4.5 | 4,096 |
| Claude Sonnet 4.6 | 2,048 |
| Claude Sonnet 4.5, 4, 4.1 | 1,024 |
| Claude Haiku 4.5 | 4,096 |
| Claude Haiku 3.5, 3 | 2,048 |

## 사용량 추적

응답 `usage` 필드:
- `cache_creation_input_tokens`: 캐시에 쓴 토큰
- `cache_read_input_tokens`: 캐시에서 읽은 토큰
- `input_tokens`: 마지막 캐시 브레이크포인트 이후 토큰

```python
total_input = cache_read + cache_creation + input_tokens
```

## 캐시 가능 항목

캐시 가능: 도구 정의, 시스템 메시지, 텍스트/이미지/문서 메시지, tool_use/tool_result
캐시 불가: thinking 블록, citations, 빈 텍스트 블록

## 캐시 무효화 조건

도구 정의 변경, web_search/citations 활성화 변경, 이미지 추가/제거, thinking 파라미터 변경

## 모범 사례

1. 안정적인 콘텐츠(시스템 지침, 대용량 문서, 도구 정의)를 앞에 배치
2. 자주 변경되는 내용은 뒤에 배치
3. 멀티턴 대화에는 자동 캐싱 사용
4. 20개 블록 이상 프롬프트에서는 자주 편집되는 섹션 앞에 명시적 브레이크포인트 추가

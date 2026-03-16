# Errors Reference

공식 문서: https://platform.claude.com/docs/en/api/errors

## HTTP 에러 코드

| 코드 | 타입 | 원인 |
|------|------|------|
| 400 | `invalid_request_error` | 요청 형식/내용 오류 |
| 401 | `authentication_error` | API 키 문제 |
| 403 | `permission_error` | API 키 권한 부족 |
| 404 | `not_found_error` | 리소스 없음 |
| 413 | `request_too_large` | 요청 크기 초과 |
| 429 | `rate_limit_error` | 속도 제한 초과 |
| 500 | `api_error` | Anthropic 내부 오류 |
| 529 | `overloaded_error` | API 과부하 (일시적) |

## 요청 크기 제한

| 엔드포인트 | 최대 크기 |
|-----------|---------|
| Messages API | 32 MB |
| Token Counting API | 32 MB |
| Batch API | 256 MB |
| Files API | 500 MB |

## 에러 객체 구조

```json
{
  "type": "error",
  "error": {
    "type": "not_found_error",
    "message": "The requested resource could not be found."
  },
  "request_id": "req_011CSHoEeqs5C35K2UUqR7Fy"
}
```

## request_id 확인

```python
message = client.messages.create(...)
print(message._request_id)  # Python SDK
```

```typescript
const message = await client.messages.create(...);
console.log(message._request_id);  // TypeScript SDK
```

지원 문의 시 `request_id` 포함 필수.

## 주요 에러 처리 지침

- **429**: 지수 백오프로 재시도. 급격한 트래픽 증가 방지.
- **529**: 일시적 과부하. 재시도 가능.
- **500**: 드문 내부 오류. 재시도 가능.
- **스트리밍 중 에러**: 200 응답 후에도 에러 이벤트 발생 가능. SSE 에러 처리 필요.

## 특수 에러: Prefill 미지원

Claude Opus 4.6은 assistant 메시지 프리필 미지원:

```json
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "Prefilling assistant messages is not supported for this model."
  }
}
```

대안: Structured Outputs, 시스템 프롬프트 지침, `output_config.format` 사용.

## 장기 요청 주의사항

- 10분 이상 요청: 스트리밍 또는 Batch API 사용
- 비스트리밍 대용량: 네트워크 타임아웃 위험
- TCP 소켓 keep-alive 설정 권장 (직접 API 연동 시)

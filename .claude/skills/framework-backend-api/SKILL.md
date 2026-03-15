---
name: framework-backend-api
description: "General-purpose backend API design skill covering RESTful conventions, API versioning, error response standards (RFC 7807), auth/authz patterns, rate limiting, and pagination. Use when designing REST API endpoints or HTTP API structure, standardizing error responses, selecting authentication and authorization patterns, implementing rate limiting or pagination, or planning API versioning strategy for backend services."
license: "Apache-2.0"
---

# 백엔드 API 설계 스킬

범용 백엔드 API 설계 원칙 및 구현 패턴 가이드.

## RESTful 설계 원칙

### 리소스 명명 규칙

```
# 컬렉션: 복수 명사
GET    /api/v1/users           # 목록 조회
POST   /api/v1/users           # 생성

# 단일 리소스: 식별자 포함
GET    /api/v1/users/{id}      # 단건 조회
PUT    /api/v1/users/{id}      # 전체 수정
PATCH  /api/v1/users/{id}      # 부분 수정
DELETE /api/v1/users/{id}      # 삭제

# 중첩 리소스: 소유 관계 표현
GET    /api/v1/users/{id}/posts
POST   /api/v1/users/{id}/posts

# 동사형 액션 (비 CRUD): 동사를 경로 마지막에
POST   /api/v1/users/{id}/activate
POST   /api/v1/orders/{id}/cancel
```

### HTTP 메서드 & 상태 코드

| 메서드 | 성공 | 실패 |
|--------|------|------|
| GET | 200 OK | 404 Not Found |
| POST (생성) | 201 Created | 400 Bad Request |
| PUT/PATCH | 200 OK | 404, 400 |
| DELETE | 204 No Content | 404 Not Found |

## 에러 응답 표준 (RFC 7807)

```json
{
  "type": "https://api.example.com/errors/validation-error",
  "title": "Validation Error",
  "status": 400,
  "detail": "Request body contains invalid fields",
  "instance": "/api/v1/users/123",
  "errors": [
    {
      "field": "email",
      "code": "INVALID_FORMAT",
      "message": "Must be a valid email address"
    }
  ],
  "traceId": "abc-123-xyz"
}
```

### 에러 코드 체계

```
# 비즈니스 에러 코드: 도메인_동사_대상
USER_NOT_FOUND
ORDER_ALREADY_CANCELLED
PAYMENT_INSUFFICIENT_BALANCE

# HTTP 상태 코드 용도
400 Bad Request     - 유효성 검사 실패, 잘못된 요청 형식
401 Unauthorized    - 미인증 (토큰 없음/만료)
403 Forbidden       - 인가 실패 (권한 없음)
404 Not Found       - 리소스 미존재
409 Conflict        - 중복 생성, 상태 충돌
422 Unprocessable   - 형식은 올바르나 비즈니스 규칙 위반
429 Too Many Requests - 레이트 리미트 초과
500 Internal Error  - 서버 오류 (상세 정보 노출 금지)
```

## API 버전 관리

### URL 버전 관리 (권장)

```
/api/v1/users   # v1
/api/v2/users   # v2 (breaking change 시)
```

### 버전 전환 전략

1. **동시 운영**: v1 유지 + v2 도입, Deprecation 헤더 추가
2. **Sunset 헤더**: `Sunset: Sat, 01 Jan 2028 00:00:00 GMT`
3. **마이그레이션 가이드**: 구버전 응답에 `x-deprecated: true` 헤더

## 인증/인가 패턴

### JWT Bearer Token

```
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...

# 토큰 구성
Access Token:  짧은 만료 (15분~1시간), stateless
Refresh Token: 긴 만료 (7~30일), DB 저장, 회전(rotation) 적용
```

### API Key 인증 (서비스 간)

```
X-API-Key: sk-prod-xxxxxxxxxxxxxxxx

# 권장 구성
- Header 방식 (query param 사용 금지: 로그에 노출)
- 해시 저장 (평문 저장 금지)
- 범위(scope) 지정: read-only / write / admin
```

### OAuth 2.0 패턴 선택

| 시나리오 | Flow |
|---------|------|
| SPA/모바일 앱 | Authorization Code + PKCE |
| 서버 간 통신 | Client Credentials |
| 사용자 대리 동작 | On-Behalf-Of |

## 페이지네이션

### 커서 기반 (대규모 데이터 권장)

```json
GET /api/v1/posts?cursor=eyJpZCI6MTAwfQ&limit=20

{
  "data": [...],
  "pagination": {
    "cursor": "eyJpZCI6MTIwfQ",
    "hasMore": true,
    "limit": 20
  }
}
```

### 오프셋 기반 (소규모/관리자 UI)

```json
GET /api/v1/posts?page=1&perPage=20

{
  "data": [...],
  "pagination": {
    "page": 1,
    "perPage": 20,
    "total": 150,
    "totalPages": 8
  }
}
```

## 레이트 리미팅

```
# 응답 헤더로 한도 공개
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1735689600    # Unix timestamp

# 초과 시
HTTP 429 Too Many Requests
Retry-After: 60                  # 재시도 가능 시간(초)
```

### 레이트 리미트 정책 설계

| 계층 | 단위 | 권장 한도 |
|------|------|---------|
| IP 기반 | 1분 | 100 req |
| 사용자 기반 | 1시간 | 1,000 req |
| API Key 기반 | 1일 | 10,000 req |
| 엔드포인트별 | 1분 | 개별 설정 |

## API 응답 표준

### 성공 응답 구조

```json
{
  "data": { ... },        // 단건
  "meta": {               // 선택적 메타데이터
    "createdAt": "2024-01-01T00:00:00Z",
    "version": "1.0"
  }
}

{
  "data": [...],          // 목록
  "pagination": { ... }
}
```

### 공통 헤더

```
Content-Type: application/json; charset=utf-8
X-Request-ID: uuid-v4              # 요청 추적
X-Response-Time: 42ms              # 응답 시간
Cache-Control: no-store            # 민감 데이터
```

## 보안 체크리스트

- [ ] HTTPS 전용 (HTTP 301 리다이렉트)
- [ ] CORS 화이트리스트 (`*` 금지)
- [ ] 입력 유효성 검사 (서버 사이드 필수)
- [ ] SQL 인젝션 방지 (파라미터화된 쿼리)
- [ ] 응답에 스택 트레이스 미포함
- [ ] 민감 필드 응답 제외 (password, secret 등)
- [ ] Idempotency-Key 지원 (결제/중요 변경)

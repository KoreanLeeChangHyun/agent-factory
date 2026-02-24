---
name: debug-static-analysis
description: "Security deep static analysis skill. Performs OWASP Top 10 full vulnerability scan, dependency vulnerability scanning (npm audit/pip-audit/cargo-audit), secret detection, CSRF/XSS/SQL Injection defense verification, auth/authz logic pattern validation, and CSP configuration guidance. Use for security analysis: security-related code during implement/refactor, security audits, pre-production security checks. Triggers: '보안', 'security', 'OWASP', '취약점', '정적 분석', 'static analysis', 'CodeQL', 'Semgrep', '시크릿 탐지', 'secret detection', '의존성 취약점', 'dependency vulnerability'."
license: "Apache-2.0"
---

# Static Analysis - Security Deep Inspection

보안 취약점을 체계적으로 탐지하고 방어 패턴을 검증하는 정적 분석 스킬.

## Overview

코드베이스를 대상으로 다음을 수행한다:
- OWASP Top 10 전체 카테고리 검사
- 의존성 취약점 스캔
- 시크릿/자격증명 탐지
- 인증/인가 로직 검증
- CSP 및 보안 헤더 검증
- 안전하지 않은 기본값 탐지

보안 기본값 및 언어별 체크리스트는 [references/insecure-defaults.md](references/insecure-defaults.md) 참조.

> This skill performs automated static analysis scanning for OWASP Top 10. For manual code review perspective, refer to the review-security skill.

### OWASP 역할 분리 상세

| Area | review-security | static-analysis |
|------|----------------|-----------------|
| OWASP approach | Checklist-based code review evaluation | Automated pattern detection and tool-based verification |
| Injection (A03) | Review parameterized query usage in changed code | Detect string concatenation SQL, eval/exec patterns |
| Access Control (A01) | Verify authorization decorators on new endpoints | Scan for missing auth middleware, IDOR patterns |
| Crypto (A02) | Review algorithm choices and key management | Detect hardcoded keys, weak hash usage |
| Authentication (A07) | Evaluate JWT/session logic correctness | Detect missing signature verification, weak policies |
| Dependencies (A06) | Check if new deps have known issues | Run npm audit/pip-audit/cargo-audit tools |
| Secrets | Manual review of credential handling | Regex-based automated secret pattern scanning |
| Output | Security review verdict with blast radius | Tool scan results with severity mapping |

## OWASP Top 10 검사 체크리스트

### A01: Broken Access Control

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| 수평적 권한 상승 | 사용자 ID 직접 참조 없이 리소스 접근 | HIGH |
| 수직적 권한 상승 | 역할 검사 누락된 관리자 엔드포인트 | HIGH |
| CORS 미설정 | `Access-Control-Allow-Origin: *` | MEDIUM |
| 디렉터리 트래버설 | 미검증 파일 경로 입력 | HIGH |
| IDOR | URL/파라미터의 ID로 직접 객체 참조 | HIGH |

```
검사: 모든 엔드포인트에 인가 미들웨어/데코레이터 적용 여부 확인
검사: 리소스 접근 시 소유자 검증 로직 존재 여부 확인
```

### A02: Cryptographic Failures

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| 약한 해시 알고리즘 | MD5, SHA1 사용 | HIGH |
| 하드코딩 암호화 키 | 코드 내 키/IV 리터럴 | CRITICAL |
| 약한 난수 생성 | Math.random(), random.random() | MEDIUM |
| 평문 전송 | HTTP URL, 미암호화 소켓 | HIGH |
| 약한 패스워드 해시 | bcrypt/argon2 미사용 | HIGH |

### A03: Injection

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| SQL Injection | 문자열 연결 쿼리, f-string SQL | CRITICAL |
| NoSQL Injection | 미검증 객체를 쿼리 조건에 직접 전달 | HIGH |
| OS Command Injection | shell=True, exec(), eval() | CRITICAL |
| LDAP Injection | 미이스케이프 LDAP 필터 | HIGH |
| Template Injection | 사용자 입력의 직접 템플릿 렌더링 | HIGH |

```
필수: 파라미터 바인딩/준비된 쿼리 사용 확인
필수: 사용자 입력의 eval/exec 전달 금지 확인
```

### A04: Insecure Design

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| Rate Limiting 부재 | 인증/API 엔드포인트에 제한 없음 | MEDIUM |
| 입력 검증 부재 | 스키마/타입 검증 없는 API 입력 | MEDIUM |
| 에러 정보 노출 | 스택 트레이스/내부 경로 응답 포함 | MEDIUM |

### A05: Security Misconfiguration

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| 디버그 모드 | DEBUG=True, 개발 설정 프로덕션 사용 | HIGH |
| 기본 자격증명 | admin/admin, root/root, password 등 | CRITICAL |
| 불필요한 기능 활성화 | 사용하지 않는 포트/서비스/엔드포인트 | MEDIUM |
| 보안 헤더 누락 | X-Frame-Options, X-Content-Type-Options 미설정 | MEDIUM |

### A06: Vulnerable and Outdated Components

의존성 취약점 스캔 섹션 참조.

### A07: Identification and Authentication Failures

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| 약한 패스워드 정책 | 길이/복잡도 검증 없음 | MEDIUM |
| 세션 고정 | 로그인 후 세션 ID 미갱신 | HIGH |
| JWT 검증 누락 | 서명 미검증, 만료 미확인 | CRITICAL |
| 무차별 대입 미방어 | 로그인 시도 제한 없음 | HIGH |

### A08: Software and Data Integrity Failures

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| 미검증 역직렬화 | pickle.loads(), JSON.parse() 후 미검증 | HIGH |
| CI/CD 파이프라인 | 미서명 아티팩트, 미검증 의존성 | MEDIUM |
| 자동 업데이트 미검증 | 무결성 체크 없는 업데이트 | HIGH |

### A09: Security Logging and Monitoring Failures

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| 인증 이벤트 미로깅 | 로그인 실패 로깅 없음 | MEDIUM |
| 민감 데이터 로깅 | 패스워드, 토큰, PII 로그 출력 | HIGH |
| 로그 인젝션 | 미새니타이즈 사용자 입력 로그 기록 | MEDIUM |

### A10: Server-Side Request Forgery (SSRF)

| 검사 항목 | 탐지 패턴 | 심각도 |
|-----------|----------|--------|
| URL 미검증 | 사용자 입력 URL로 서버 측 요청 | HIGH |
| 내부 네트워크 접근 | 127.0.0.1, 169.254.169.254 등 접근 가능 | CRITICAL |
| DNS 리바인딩 | URL 검증 후 재요청 시 다른 IP 해석 | HIGH |

## 의존성 취약점 스캔

### 스캔 명령어

```bash
# JavaScript/TypeScript
npm audit --json 2>&1
npx audit-ci --config audit-ci.json 2>&1

# Python
pip-audit --format json 2>&1
safety check --json 2>&1

# Rust
cargo audit --json 2>&1

# Go
govulncheck ./... 2>&1

# Ruby
bundle audit check 2>&1

# Java/Kotlin
mvn dependency-check:check 2>&1
```

### 심각도 매핑

| 의존성 심각도 | 조치 |
|-------------|------|
| CRITICAL | 즉시 업데이트 필수. 차단 이슈로 보고 |
| HIGH | 가능한 빨리 업데이트. 릴리스 전 해결 필수 |
| MEDIUM | 다음 정기 업데이트에 포함 |
| LOW | 모니터링, 필요 시 업데이트 |

## 시크릿 탐지

### 탐지 패턴

```
# API 키/토큰
[A-Za-z0-9_-]{20,}  (변수명: api_key, token, secret, password, credential)

# AWS
AKIA[0-9A-Z]{16}

# GitHub
gh[pousr]_[A-Za-z0-9_]{36,}

# Slack
xox[baprs]-[0-9a-zA-Z-]+

# 일반 패턴
(?i)(password|secret|token|api.?key)\s*[=:]\s*['"][^'"]{8,}['"]
```

### 검사 절차

1. 변경된 파일에서 위 패턴 매칭
2. 환경변수 참조 여부 확인 (process.env, os.environ, env::var)
3. .gitignore에 시크릿 파일(.env, *.pem, *.key) 포함 여부 확인
4. 커밋 이력에 시크릿 노출 여부 확인 (git log -p | grep 패턴)

## CSRF 보호 검증

| 프레임워크 | 확인 사항 |
|-----------|----------|
| Express/Node | csurf 또는 동등 미들웨어 적용 |
| Django | CsrfViewMiddleware 활성화, {% csrf_token %} 사용 |
| Rails | protect_from_forgery 선언 |
| Spring | CsrfFilter 활성화 |
| Next.js | API 라우트에 CSRF 토큰 검증 |

```
필수: 상태 변경 요청(POST/PUT/DELETE)에 CSRF 토큰 검증
필수: SameSite 쿠키 속성 설정 확인 (Strict 또는 Lax)
```

## 인증/인가 로직 검증

### 인증 패턴 체크리스트

- [ ] 패스워드 해싱: bcrypt/argon2/scrypt 사용 (SHA256/MD5 금지)
- [ ] JWT: 서명 알고리즘 명시 (none 금지), 만료 시간 설정, 리프레시 토큰 분리
- [ ] 세션: httpOnly, secure, SameSite 쿠키 플래그 설정
- [ ] OAuth: state 파라미터 검증, PKCE 사용 (public 클라이언트)
- [ ] MFA: 중요 작업에 2차 인증 고려

### 인가 패턴 체크리스트

- [ ] RBAC/ABAC 일관 적용
- [ ] 최소 권한 원칙 (기본 거부, 명시적 허용)
- [ ] API 엔드포인트별 권한 매핑 문서화
- [ ] 리소스 소유자 검증 (IDOR 방지)

## CSP 설정 가이드

### 권장 CSP 헤더

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'nonce-{random}';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  font-src 'self';
  connect-src 'self' https://api.example.com;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

### 필수 보안 헤더

| 헤더 | 값 | 목적 |
|------|---|------|
| X-Content-Type-Options | nosniff | MIME 스니핑 방지 |
| X-Frame-Options | DENY 또는 SAMEORIGIN | 클릭재킹 방지 |
| Strict-Transport-Security | max-age=31536000; includeSubDomains | HTTPS 강제 |
| Referrer-Policy | strict-origin-when-cross-origin | 리퍼러 정보 제한 |
| Permissions-Policy | camera=(), microphone=(), geolocation=() | 기능 권한 제한 |

## Workflow

### 1. 대상 파일 식별

변경된 파일 목록에서 보안 관련 파일을 우선 식별:
- 인증/인가 관련 (auth, login, session, token, permission)
- API 엔드포인트 (routes, controllers, handlers)
- 데이터베이스 접근 (models, repositories, queries)
- 설정 파일 (config, env, settings)
- 외부 입력 처리 (forms, validators, parsers)

### 2. OWASP Top 10 검사 실행

위 체크리스트를 기반으로 각 카테고리별 검사 수행. 발견된 이슈를 심각도와 함께 기록.

### 3. 의존성 스캔

프로젝트 언어에 맞는 스캔 도구 실행. CRITICAL/HIGH 취약점은 차단 이슈로 보고.

### 4. 시크릿 탐지

변경 파일 및 새로 추가된 파일에서 시크릿 패턴 검사.

### 5. 보고

```yaml
security_scan:
  verdict: PASS | CONCERNS | ISSUES_FOUND
  owasp_findings:
    - category: "A03: Injection"
      severity: CRITICAL
      file: "src/api/users.ts:42"
      finding: "SQL 문자열 연결 사용"
      remediation: "파라미터 바인딩으로 변경"
  dependency_vulnerabilities:
    critical: 0
    high: 1
    medium: 3
  secrets_detected: 0
  headers_missing: ["CSP", "HSTS"]
```

## code-quality-checker와의 역할 분리

| 영역 | code-quality-checker | debug-static-analysis |
|------|---------------------|------------------------|
| 범위 | SEC- 접두사 기본 보안 (4-5개 패턴) | OWASP Top 10 전체 + 의존성 + 시크릿 |
| 깊이 | 하드코딩 자격증명, 미검증 입력, XSS | 인증/인가 로직, CSP, CSRF, SSRF 등 |
| 도구 | 수동 정적 분석 | 의존성 스캔 도구 연동 |
| 목적 | 코드 품질의 보안 측면 | 보안 전문 심층 검사 |

**상호 보완**: code-quality-checker가 기본 보안 이슈를 탐지하고, debug-static-analysis가 심층 보안 검사를 수행. 두 스킬이 동시 로드되면 code-quality-checker의 SEC- 결과를 기반으로 심층 분석을 확장한다.

## Critical Rules

1. **OWASP 전체 커버**: A01-A10 모든 카테고리 검사 수행
2. **증거 기반**: 모든 발견에 파일:라인 참조 포함
3. **심각도 정확**: CRITICAL/HIGH/MEDIUM/LOW 정확 분류
4. **수정 방안 제시**: 각 발견에 구체적 수정 가이드 제공
5. **의존성 스캔 필수**: 프로젝트에 패키지 매니저가 있으면 반드시 실행
6. **시크릿 제로 정책**: 시크릿 탐지 시 즉시 차단 이슈로 보고
7. **안전한 기본값 참조**: 언어별 기본값 체크리스트는 [references/insecure-defaults.md](references/insecure-defaults.md) 참조

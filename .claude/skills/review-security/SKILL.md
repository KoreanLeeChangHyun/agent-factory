---
name: review-security
description: "Security-specialized code review skill. Performs OWASP Top 10 checklist-based review, secret detection, dependency vulnerability checks, blast radius estimation, and escalation criteria enforcement. Use for security review: security-related code changes, auth/authz module review, external input handling review. Triggers: '보안 리뷰', 'security review', 'OWASP 리뷰', '취약점 리뷰'."
license: "Apache-2.0"
---

# Security Code Review

리뷰어 관점에서 코드 변경의 보안 위험을 체계적으로 평가하고 판정하는 스킬.

## Overview

코드 리뷰 시 보안 관점의 전문 체크리스트를 적용하여 취약점을 조기에 식별한다.

**적용 시점:**
- 인증/인가 모듈 변경 리뷰
- 외부 입력 처리 로직 변경 리뷰
- API 엔드포인트 추가/변경 리뷰
- 시크릿/자격증명 관련 코드 변경 리뷰
- 암호화/해싱 로직 변경 리뷰

**핵심 원칙:** 변경의 보안 영향(blast radius)을 먼저 평가하고, 영향 범위에 비례하는 깊이로 리뷰한다.

## debug-static-analysis와의 역할 분리

| 영역 | debug-static-analysis | review-security |
|------|------------------------|------------------------|
| 목적 | 보안 도구 실행 및 심층 검사 | 리뷰 관점 체크리스트 및 판정 |
| 사용 시점 | implement/refactor 중 코드 작성 시 | review 명령어에서 리뷰어 관점 평가 시 |
| 도구 의존 | npm audit, pip-audit, cargo-audit 등 실행 | 도구 비의존, 코드 리딩 기반 판단 |
| 산출물 | 의존성 스캔 결과, OWASP 검사 결과 | 보안 리뷰 판정(PASS/CONCERNS/ISSUES_FOUND) |
| OWASP 접근 | 코드 패턴 탐지 및 도구 기반 검증 | 리뷰 관점 체크리스트 기반 평가 |
| Blast Radius | 해당 없음 | SMALL/MEDIUM/LARGE 3단계 분류 |
| 에스컬레이션 | 심각도 매핑(CRITICAL~LOW) | 즉시 에스컬레이션 대상 판정 |

**상호 보완:** 두 스킬이 동시 로드되면 review-security가 리뷰 체크리스트 관점에서 판정하고, static-analysis가 도구 실행으로 검증한다. review-security의 체크리스트에서 의심 항목을 식별하면 static-analysis의 도구 실행 결과로 증거를 보강한다.

> This skill reviews OWASP Top 10 from a code review perspective. For automated tool-based scanning, refer to the debug-static-analysis skill.

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

## OWASP Top 10 리뷰 체크리스트

변경된 코드를 대상으로 6단계 분석 절차를 적용한다:
1. 변경 범위 식별 (diff 기반)
2. 데이터 흐름 추적 (입력 -> 처리 -> 출력)
3. 신뢰 경계 확인 (외부 입력 진입점)
4. 카테고리별 체크리스트 적용
5. 발견 사항 심각도 분류
6. 수정 방안 제시

### A01: Broken Access Control

| 검사 항목 | 심각도 |
|-----------|--------|
| 새 엔드포인트에 인가 미들웨어/데코레이터 적용 여부 | HIGH |
| 리소스 접근 시 소유자 검증 로직 존재 여부 (IDOR 방지) | HIGH |
| CORS 설정의 허용 범위가 최소 권한 원칙을 준수하는지 | MEDIUM |
| 관리자 전용 기능에 역할 기반 접근 제어 적용 여부 | HIGH |

### A02: Cryptographic Failures

| 검사 항목 | 심각도 |
|-----------|--------|
| 암호화 키/IV가 코드에 하드코딩되어 있지 않은지 | CRITICAL |
| 약한 해시 알고리즘(MD5, SHA1) 대신 적절한 알고리즘 사용 여부 | HIGH |
| 민감 데이터 전송 시 TLS/HTTPS 사용 여부 | HIGH |
| 패스워드 해싱에 bcrypt/argon2/scrypt 사용 여부 | HIGH |

### A03: Injection

| 검사 항목 | 심각도 |
|-----------|--------|
| SQL 쿼리에 파라미터 바인딩/준비된 쿼리 사용 여부 | CRITICAL |
| 사용자 입력이 eval/exec/shell 명령에 전달되지 않는지 | CRITICAL |
| 템플릿 엔진에 사용자 입력 직접 렌더링 방지 여부 | HIGH |
| NoSQL 쿼리에 미검증 객체 직접 전달 방지 여부 | HIGH |

### A04: Insecure Design

| 검사 항목 | 심각도 |
|-----------|--------|
| 인증/API 엔드포인트에 Rate Limiting 적용 여부 | MEDIUM |
| API 입력에 스키마/타입 검증 존재 여부 | MEDIUM |
| 에러 응답에 내부 경로/스택 트레이스 노출 방지 여부 | MEDIUM |

### A05: Security Misconfiguration

| 검사 항목 | 심각도 |
|-----------|--------|
| 프로덕션 환경에서 디버그 모드 비활성화 확인 | HIGH |
| 기본 자격증명(admin/admin, root/root) 사용 금지 확인 | CRITICAL |
| 보안 헤더(X-Frame-Options, HSTS, CSP) 설정 여부 | MEDIUM |

### A06: Vulnerable Components

| 검사 항목 | 심각도 |
|-----------|--------|
| 새로 추가된 의존성에 알려진 취약점 존재 여부 | HIGH |
| 의존성 버전이 최신 보안 패치를 포함하는지 | MEDIUM |
| 불필요한 의존성 추가 여부 (공격 표면 최소화) | LOW |

### A07: Authentication Failures

| 검사 항목 | 심각도 |
|-----------|--------|
| JWT 서명 검증 및 만료 확인 로직 존재 여부 | CRITICAL |
| 세션 관리에 httpOnly, secure, SameSite 플래그 설정 여부 | HIGH |
| 로그인 실패 시 무차별 대입 방어(계정 잠금/지연) 적용 여부 | HIGH |

### A08: Data Integrity Failures

| 검사 항목 | 심각도 |
|-----------|--------|
| 역직렬화 시 입력 검증 수행 여부 (pickle, JSON.parse 후) | HIGH |
| CI/CD 파이프라인에서 아티팩트 무결성 검증 여부 | MEDIUM |
| 외부 소스 데이터의 무결성 확인 절차 존재 여부 | MEDIUM |

### A09: Logging and Monitoring

| 검사 항목 | 심각도 |
|-----------|--------|
| 인증 이벤트(로그인 성공/실패) 로깅 여부 | MEDIUM |
| 로그에 민감 데이터(패스워드, 토큰, PII) 포함 방지 여부 | HIGH |
| 사용자 입력이 로그에 새니타이즈 없이 기록되지 않는지 | MEDIUM |

### A10: SSRF

| 검사 항목 | 심각도 |
|-----------|--------|
| 사용자 입력 URL로 서버 측 요청 시 URL 검증 여부 | HIGH |
| 내부 네트워크 주소(127.0.0.1, 169.254.169.254) 접근 차단 여부 | CRITICAL |
| URL 검증 후 재요청 시 DNS 리바인딩 방어 여부 | HIGH |

## Blast Radius 분류

변경의 보안 영향 범위를 3단계로 분류하고, 각 단계에 비례하는 리뷰 깊이를 적용한다.

| 분류 | 기준 | 리뷰 깊이 |
|------|------|----------|
| **SMALL** | 단일 함수/파일 내부 로직 변경. 외부 인터페이스 불변. 인증/인가 비관련 | 해당 OWASP 카테고리만 체크. 시크릿 탐지 수행. 5분 이내 |
| **MEDIUM** | 모듈 간 경계 변경. API 시그니처 변경 포함. 입력 검증 로직 수정 | 관련 OWASP 카테고리 전수 체크. 시크릿 탐지 + 의존성 확인. 데이터 흐름 추적 |
| **LARGE** | 인증/인가 핵심 로직 변경. 암호화 방식 변경. 세션 관리 변경. 다수 모듈에 영향 | OWASP A01~A10 전체 체크. 시크릿 탐지 + 의존성 스캔 + 데이터 흐름 전수 추적. 에스컬레이션 검토 필수 |

## 시크릿 탐지 체크리스트

### 탐지 패턴

| 패턴 유형 | 정규식/패턴 |
|-----------|-----------|
| AWS 키 | `AKIA[0-9A-Z]{16}` |
| GitHub 토큰 | `gh[pousr]_[A-Za-z0-9_]{36,}` |
| Slack 토큰 | `xox[baprs]-[0-9a-zA-Z-]+` |
| 일반 시크릿 | `(?i)(password\|secret\|token\|api.?key)\s*[=:]\s*['"][^'"]{8,}['"]` |
| 변수명 기반 | 변수명에 `api_key`, `token`, `secret`, `password`, `credential` 포함 시 값 확인 |

### 확인 절차

1. 변경된 파일에서 위 패턴 매칭
2. 매칭된 값이 환경변수 참조인지 확인 (`process.env`, `os.environ`, `env::var`)
3. `.gitignore`에 시크릿 파일(`.env`, `*.pem`, `*.key`) 포함 여부 확인
4. 신규 추가된 설정 파일에 시크릿 하드코딩 여부 확인
5. 시크릿 발견 시 즉시 **CRITICAL** 이슈로 보고

## 에스컬레이션 기준

다음 항목이 발견되면 리뷰를 즉시 중단하고 에스컬레이션한다. 리뷰어 단독 판단으로 승인하지 않는다.

| 에스컬레이션 대상 | 심각도 | 조치 |
|-----------------|--------|------|
| 인증 우회 가능성 | CRITICAL | 인증 로직 변경이 우회 경로를 생성하는 경우. 보안 전문가 리뷰 필수 |
| 권한 상승 가능성 | CRITICAL | 일반 사용자가 관리자 기능에 접근 가능한 경로 발견 시. 즉시 차단 |
| 민감 데이터 노출 | CRITICAL | PII, 결제 정보, 인증 토큰이 로그/응답/URL에 노출되는 경우 |
| 암호화 무력화 | CRITICAL | TLS 비활성화, 약한 알고리즘 도입, 키 관리 약화 등 |
| 시크릿 하드코딩 | CRITICAL | 코드에 API 키, 패스워드, 토큰이 리터럴로 포함된 경우 |

## Output Format

```yaml
security_review:
  verdict: PASS | CONCERNS | ISSUES_FOUND
  blast_radius: SMALL | MEDIUM | LARGE
  owasp_findings:
    - category: "A03: Injection"
      severity: CRITICAL
      file: "src/api/users.ts:42"
      finding: "SQL 문자열 연결 사용"
      remediation: "파라미터 바인딩으로 변경"
  secrets_detected:
    count: 0
    items: []
  escalation_required: false
  escalation_items: []
  summary:
    critical: 0
    high: 0
    medium: 0
    low: 0
```

## Critical Rules

1. **Blast Radius 우선 평가**: 리뷰 시작 시 변경의 보안 영향 범위를 먼저 분류하고 그에 맞는 깊이로 리뷰
2. **시크릿 제로 정책**: 코드에 하드코딩된 시크릿 발견 시 무조건 CRITICAL, 예외 없음
3. **에스컬레이션 즉시 실행**: 에스컬레이션 대상 발견 시 리뷰 완료를 기다리지 않고 즉시 보고
4. **증거 기반 보고**: 모든 발견에 파일:라인 참조와 구체적 수정 방안 포함
5. **static-analysis 협력**: 도구 실행이 필요한 검증은 static-analysis에 위임, 중복 검사 방지

## 연관 스킬

| 스킬 | 용도 | 경로 |
|------|------|------|
| debug-static-analysis | 보안 도구 실행 및 심층 검사 (도구 기반 검증 위임) | `.claude/skills/debug-static-analysis/SKILL.md` |
| review-code-quality | SEC- 접두사 기본 보안 검사 (기본 계층 보안 이슈) | `.claude/skills/review-code-quality/SKILL.md` |
| review-requesting | 리뷰 요청 체크리스트 (리뷰 프로세스 통합) | `.claude/skills/review-requesting/SKILL.md` |

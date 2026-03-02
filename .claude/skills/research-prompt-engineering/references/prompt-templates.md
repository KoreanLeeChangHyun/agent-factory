# 용도별 프롬프트 템플릿

cc:prompt 프롬프트 정제 시 용도에 맞는 구조화된 템플릿을 제공한다. 각 템플릿에 좋은 예/나쁜 예 대조를 포함한다.

## 1. 기능 구현

### 템플릿

```
구현 대상: [함수명/모듈명/기능명]
요구사항:
  - [기능 요구사항 목록]
참조 패턴: [유사 구현 파일 경로] 참고
제약 조건:
  - [사용 가능 라이브러리]
  - [사용 불가 패턴]
검증 기준: [테스트 케이스 또는 성공 조건]
```

### 좋은 예

```
구현 대상: src/utils/validator.ts에 validatePhoneNumber 함수
요구사항:
  - 한국 휴대폰 번호 형식(010-XXXX-XXXX) 검증
  - 하이픈 유무 모두 허용
  - 국제 번호 형식(+82) 지원
참조 패턴: src/utils/validator.ts의 validateEmail 함수 참고
제약 조건:
  - 정규식 사용, 외부 라이브러리 사용 금지
  - 기존 ValidationResult 타입 반환
검증 기준:
  - "010-1234-5678" -> true
  - "01012345678" -> true
  - "+821012345678" -> true
  - "02-1234-5678" -> false (유선)
  - "abc" -> false
구현 후 npm test -- --grep "phone" 실행하여 확인
```

### XML 태그 버전

```xml
<goal>src/utils/validator.ts에 한국 휴대폰 번호(010-XXXX-XXXX, +82 형식 포함)를 검증하는 validatePhoneNumber 함수를 구현한다.</goal>
<target>src/utils/validator.ts</target>
<constraints>
  - 정규식 사용, 외부 라이브러리 사용 금지
  - 기존 ValidationResult 타입 반환 필수
  - validateEmail 함수와 동일한 패턴 준수
</constraints>
<criteria>
  "010-1234-5678", "01012345678", "+821012345678" 입력 시 true 반환
  "02-1234-5678", "abc" 입력 시 false 반환
  npm test -- --grep "phone" 실행 시 성공
</criteria>
<context>src/utils/validator.ts의 validateEmail 함수를 참고하여 동일한 패턴으로 구현</context>
<scope>validatePhoneNumber 함수만 추가, 기존 함수 수정 금지</scope>
```

### 나쁜 예

```
전화번호 검증 기능 만들어줘
```

문제점: 대상 파일 불명확, 어떤 전화번호 형식인지 미정, 검증 기준 없음, 기존 패턴 참조 없음.

---

## 2. 버그 수정

### 템플릿

```
증상: [오류 메시지 또는 비정상 동작 설명]
재현 방법: [단계별 재현 절차]
관련 위치: [src/경로/, 특히 [함수명] 확인]
검증 요청: 수정 후 [테스트 명령]으로 확인하여 성공 여부 보고
주의: 오류를 억제하지 말고 근본 원인을 수정하시오
```

### 좋은 예

```
증상: 로그인 후 리다이렉트 시 "Cannot read properties of undefined (reading 'token')" 오류 발생
재현 방법:
  1. /login 페이지에서 유효한 자격 증명 입력
  2. 로그인 버튼 클릭
  3. /dashboard로 리다이렉트 시점에 콘솔 오류 발생
관련 위치: src/auth/callback.ts의 handleRedirect 함수, 특히 session.user.token 접근 부분
검증 요청: 수정 후 npm test -- --grep "auth redirect" 실행하여 확인
주의: try-catch로 오류를 억제하지 말고 session 객체의 초기화 타이밍을 확인하여 근본 원인을 수정하시오
```

### XML 태그 버전

```xml
<goal>로그인 후 리다이렉트 시 발생하는 "Cannot read properties of undefined (reading 'token')" 오류를 근본 원인으로부터 수정한다.</goal>
<target>src/auth/callback.ts의 handleRedirect 함수</target>
<constraints>
  - try-catch로 오류를 억제하지 말 것 (근본 원인 수정 필수)
  - session 객체의 초기화 타이밍 확인 필수
  - 기존 리다이렉트 흐름 유지
</constraints>
<criteria>
  /login에서 유효한 자격 증명 입력 후 로그인 버튼 클릭 시 /dashboard로 정상 리다이렉트
  콘솔에 오류 메시지 없음
  npm test -- --grep "auth redirect" 실행 시 성공
</criteria>
<context>
  오류 발생 시점: /dashboard로 리다이렉트 직후
  문제 위치: session.user.token 접근 부분에서 session이 정의되지 않음
</context>
<approach>session 객체의 초기화 타이밍을 확인하여 handleRedirect 호출 순서 또는 session 객체 생성 로직 수정</approach>
```

### 나쁜 예

```
로그인이 안 돼요 고쳐주세요
```

문제점: 오류 메시지 없음, 재현 절차 없음, 관련 파일/함수 특정 불가, 검증 방법 없음.

---

## 3. 리팩토링

### 템플릿

```
대상 파일: [파일 경로]
리팩토링 목적: [성능/가독성/유지보수성 중 선택]
유지해야 할 동작: [외부 인터페이스, API 계약]
적용 기준: [현재 코드베이스의 기존 패턴] 준수
범위 제한: 요청된 변경 외 추가 개선 금지
```

### 좋은 예

```
대상 파일: src/services/orderService.ts
리팩토링 목적: 가독성 개선 - processOrder 함수가 280줄로 단일 책임 원칙 위반
유지해야 할 동작:
  - processOrder(order: Order): Promise<OrderResult> 시그니처 유지
  - 외부 API 호출 순서(재고확인 -> 결제 -> 배송) 유지
  - 기존 에러 핸들링 동작 유지
적용 기준: src/services/userService.ts의 패턴(단계별 private 메서드 분리) 준수
범위 제한: processOrder 함수 분리만 수행. 다른 함수나 타입 정의는 변경 금지
리팩토링 후 npm test -- --grep "order" 실행하여 기존 테스트 통과 확인
```

### XML 태그 버전

```xml
<goal>src/services/orderService.ts의 processOrder 함수(280줄)를 단계별 private 메서드로 분리하여 가독성을 개선한다.</goal>
<target>src/services/orderService.ts의 processOrder 함수</target>
<constraints>
  - processOrder(order: Order): Promise<OrderResult> 시그니처 유지 필수
  - 외부 API 호출 순서(재고확인 -> 결제 -> 배송) 변경 금지
  - 기존 에러 핸들링 동작 유지 필수
  - src/services/userService.ts의 private 메서드 분리 패턴 준수
</constraints>
<criteria>
  processOrder 함수를 단계별 private 메서드로 분리 완료
  npm test -- --grep "order" 실행 시 모든 기존 테스트 통과
  리팩토링 전후 외부 인터페이스 동작 동일함을 확인
</criteria>
<context>src/services/userService.ts에서 단계별 메서드 분리 패턴 참고 (참고 대상: private verifyUser, private createSession 등의 메서드)</context>
<scope>processOrder 함수 분리만 수행. 다른 함수나 타입 정의는 변경 금지</scope>
```

### 나쁜 예

```
orderService 코드가 지저분한데 깔끔하게 해줘
```

문제점: "깔끔하게"는 측정 불가, 유지해야 할 동작 미정, 범위 무제한, 기존 패턴 참조 없음.

---

## 4. 코드 리뷰

### 템플릿

```
리뷰 대상: [파일 또는 PR 범위]
중점 검토 항목:
  - [보안 취약점/성능/가독성 등]
출력 형식: 파일별로 라인 번호와 함께 구체적 피드백 제공
```

### 좋은 예

```
리뷰 대상: src/auth/ 디렉터리의 최근 변경 (git diff HEAD~3 -- src/auth/)
중점 검토 항목:
  - SQL 인젝션, XSS 등 보안 취약점
  - 인증 토큰 만료 처리 누락 여부
  - 에러 핸들링 일관성 (기존 ErrorHandler 패턴 준수 여부)
출력 형식:
  - 파일별로 그룹화
  - 각 이슈에 라인 번호, 심각도(Critical/Warning/Info), 구체적 개선 제안 포함
  - Critical 이슈는 반드시 코드 수정 예시 포함
```

### XML 태그 버전

```xml
<goal>src/auth/ 디렉터리의 최근 변경사항을 보안, 토큰 관리, 에러 핸들링 측면에서 검토하여 구체적 개선 제안을 제공한다.</goal>
<target>src/auth/ 디렉터리의 최근 변경사항</target>
<constraints>
  - 검토 범위: git diff HEAD~3 -- src/auth/
  - 보안 취약점(SQL 인젝션, XSS) 검토 필수
  - 기존 ErrorHandler 패턴 준수 여부 확인 필수
</constraints>
<criteria>
  각 이슈에 라인 번호와 심각도(Critical/Warning/Info) 표시
  Critical 이슈는 코드 수정 예시 포함
  파일별로 그룹화된 구체적 개선 제안 제시
</criteria>
<context>프로젝트의 기존 ErrorHandler 패턴 참조 (위치: src/middleware/errorHandler.ts)</context>
<approach>
  1. 보안 취약점(SQL 인젝션, XSS) 우선 검토
  2. 인증 토큰 만료 처리 누락 여부 확인
  3. 에러 핸들링의 기존 패턴 준수 여부 검증
</approach>
```

### 나쁜 예

```
코드 좀 봐줘
```

문제점: 리뷰 대상 파일 불명확, 검토 관점 없음, 출력 형식 미정.

---

## 5. 연구 조사

### 템플릿

```
조사 주제: [명확한 연구 질문]
성공 기준: [조사 결과물의 구체적 형태]
정보 출처 우선순위: [공식 문서 > 기술 블로그 > 커뮤니티]
결과 형식: [요약/비교표/참고 링크 목록]
```

### 좋은 예

```
조사 주제: Python 비동기 HTTP 클라이언트 라이브러리 비교 (aiohttp vs httpx vs requests-async)
성공 기준: 3개 라이브러리의 성능, API 설계, 유지보수 현황을 비교하여 프로젝트에 적합한 1개를 추천
정보 출처 우선순위: 공식 문서 > PyPI 통계 > 벤치마크 블로그
결과 형식:
  - 비교표 (기능 / 성능 / 커뮤니티 / 최근 릴리즈)
  - 각 라이브러리의 장단점 3줄 요약
  - 최종 추천과 근거
```

### XML 태그 버전

```xml
<goal>Python 비동기 HTTP 클라이언트 라이브러리 3개(aiohttp, httpx, requests-async)를 성능, API 설계, 유지보수 측면에서 비교하여 프로젝트에 적합한 1개를 추천한다.</goal>
<target>비동기 HTTP 클라이언트 라이브러리 선택</target>
<constraints>
  - 비교 대상: aiohttp, httpx, requests-async 3개 라이브러리
  - 정보 출처 우선순위: 공식 문서 > PyPI 통계 > 벤치마크 블로그
  - Python 3.8+ 지원 라이브러리만 대상
</constraints>
<criteria>
  각 라이브러리의 성능, API 설계, 커뮤니티 활성도, 최근 릴리즈 주기 비교
  비교표 형식 (기능 / 성능 / 커뮤니티 / 최근 릴리즈) 포함
  각 라이브러리의 장단점 3줄 이상 요약
  최종 추천과 근거 제시 (프로젝트 요구사항과의 적합도 포함)
</criteria>
<context>현재 프로젝트의 기술 스택: FastAPI, asyncio 기반 비동기 처리</context>
<reference>
  - aiohttp 공식 문서: https://docs.aiohttp.org/
  - httpx 공식 문서: https://www.python-httpx.org/
  - requests-async 문서
</reference>
```

### 나쁜 예

```
비동기 HTTP 라이브러리 뭐가 좋아?
```

문제점: 비교 대상 미정, 평가 기준 없음, 결과물 형태 불명확.

---

## 6. 아키텍처 설계

### 템플릿

```
설계 대상: [시스템/모듈/컴포넌트]
요구사항:
  - 기능 요구사항: [목록]
  - 비기능 요구사항: [성능, 확장성 등]
제약 조건: [기술 스택, 팀 역량, 일정]
산출물: [다이어그램/ADR/구현 계획]
결정 시 트레이드오프 명시 요청
```

### 좋은 예

```
설계 대상: 실시간 알림 시스템 (사용자 수 10만, 동시 접속 1만)
요구사항:
  - 기능: 푸시 알림, 인앱 알림, 이메일 알림 3채널 지원
  - 비기능: 알림 전달 지연 3초 이내, 일 처리량 100만 건 이상
제약 조건:
  - 기술 스택: Python + FastAPI, PostgreSQL, Redis (기존 인프라)
  - 일정: 2주 내 MVP, 4주 내 프로덕션
  - 팀: 백엔드 2명, 프론트 1명
산출물:
  - 시스템 구성도 (mermaid 다이어그램)
  - 컴포넌트별 책임 정의
  - 기술 결정 문서 (ADR) 3개 이내
  - 2주 MVP 범위 정의
각 기술 결정에서 선택한 방식과 대안의 트레이드오프를 명시하시오
```

### XML 태그 버전

```xml
<goal>실시간 알림 시스템(사용자 10만, 동시 접속 1만)을 설계하여 3채널(푸시/인앱/이메일) 알림을 3초 내 전달하고 일 100만 건 이상을 처리할 수 있는 아키텍처를 제시한다.</goal>
<target>실시간 알림 시스템 아키텍처</target>
<constraints>
  - 기술 스택: Python + FastAPI, PostgreSQL, Redis (기존 인프라)
  - 일정: 2주 MVP, 4주 프로덕션
  - 팀 규모: 백엔드 2명, 프론트 1명
  - 지원 채널: 푸시 알림, 인앱 알림, 이메일 알림 3가지
</constraints>
<criteria>
  - 알림 전달 지연: 3초 이내
  - 일 처리량: 100만 건 이상
  - 시스템 구성도(mermaid) 포함
  - 컴포넌트별 책임 정의 명확
  - 기술 결정 문서(ADR) 3개 이내로 각 선택사항의 트레이드오프 명시
  - 2주 MVP 범위와 4주 프로덕션 완성 로드맵 제시
</criteria>
<context>
  - 사용자 규모: 10만 사용자, 동시 접속 1만
  - 기존 인프라: PostgreSQL, Redis 운영 중
  - 팀 역량: FastAPI 경험 있는 백엔드 개발자 2명
</context>
<approach>
  1. 메시지 큐(Redis 또는 메시지 브로커) 기반 비동기 처리
  2. 채널별 발송 서비스 분리 (푸시, 이메일 등)
  3. 데이터베이스 설계 (알림 템플릿, 사용자 구독 정보, 발송 이력)
</approach>
<scope>MVP 범위: 기본 시스템 아키텍처 및 알림 생성/발송 흐름 설계. 세부 구현 코드는 제외.</scope>
```

### 나쁜 예

```
알림 시스템 설계해줘
```

문제점: 규모 불명, 요구사항 없음, 기술 스택 미정, 산출물 형태 불명확, 제약 조건 없음.

---

## 공통 원칙

### 프롬프트 작성 시 확인 사항

1. **동사 선택**: "확인해줘" 대신 "구현하시오", "수정하시오", "분석하시오" 등 명확한 동사 사용
2. **파일 경로 명시**: 대상 파일을 절대 경로 또는 프로젝트 루트 기준 상대 경로로 지정
3. **기존 패턴 참조**: "~와 동일한 패턴으로" 형식으로 기존 코드 참조 포함
4. **검증 포함**: 구현/수정 후 실행할 검증 명령어를 마지막에 명시
5. **범위 한정**: "이 파일만", "이 함수만" 등으로 작업 범위를 명시적으로 제한

### XML 태그 사용 시 주의사항

1. **태그 내부는 자연어 서술**: XML 태그(`<goal>`, `<target>`, `<constraints>`, `<criteria>` 등) 내부의 내용은 자연어로 명확하게 서술하며, 추가 마크업이나 코드 블록을 포함하지 않을 것
2. **중첩 태그 지양**: 태그 내부에 다른 XML 태그를 중첩하지 말 것 (예: `<goal><target>...</target></goal>` 금지). 복수의 항목은 리스트 또는 개행으로 구분
3. **태그 외부 자연어 허용(하이브리드)**: XML 태그와 자연어 텍스트를 섞어 사용 가능 (예: 개요는 자연어로, 구체적 요구사항은 XML 태그로). 태그로만 구성할 필요 없음

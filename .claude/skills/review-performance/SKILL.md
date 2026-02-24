---
name: review-performance
description: "Performance-specialized code review skill. Validates algorithm complexity, detects N+1 queries, reviews caching strategies, checks index adequacy, and identifies framework-specific performance anti-patterns. Use for performance review: DB query changes, algorithm implementations, caching/index configuration changes. Triggers: '성능 리뷰', 'performance review', '쿼리 리뷰', 'DB 리뷰', 'N+1'."
license: "Apache-2.0"
---

# Performance Code Review

성능 관점에서 코드를 전문적으로 리뷰하는 스킬. 알고리즘 복잡도, 데이터베이스 쿼리 효율, 캐싱 전략, 인덱스 설계를 체계적으로 검증한다.

## Overview

성능 리뷰는 코드 변경이 시스템 응답 시간, 처리량, 리소스 사용에 미치는 영향을 사전에 식별한다.

**적용 시점:**
- DB 쿼리가 추가/변경된 코드 리뷰
- 알고리즘 로직이 변경된 코드 리뷰
- 캐싱 계층 도입/변경 리뷰
- 인덱스 추가/삭제/변경 리뷰
- 대용량 데이터 처리 로직 리뷰
- 루프/반복문 구조가 변경된 코드 리뷰

**핵심 원칙:** 측정 없는 최적화는 추측이다. 성능 이슈는 증거 기반으로 식별하고, 개선 효과를 정량적으로 추정한다.

## review-code-quality PERF- 체계와의 관계

review-performance는 review-code-quality의 PERF- 접두사 체계를 확장하는 전문 리뷰 체크리스트다.

| 항목 | review-code-quality (PERF-) | review-performance |
|------|--------------------------------------|---------------------------|
| **역할** | 코드 메트릭 기반 성능 이슈 기본 탐지 | 성능 관점 전문 리뷰 체크리스트 |
| **PERF-ALG-** | O(n^2) 이상 알고리즘 경고 | Big O 심층 분석, 대안 알고리즘 제시, 입력 크기별 영향 추정 |
| **PERF-DB-** | N+1 쿼리, 인덱스 기본 경고 | ORM별 N+1 패턴 탐지, 인덱스 설계 검증, 쿼리 플랜 분석 관점 |
| **PERF-CFG-** | 패키지/라이브러리 설정 경고 | 캐싱 TTL/키 설계/무효화 전략 전문 리뷰 |
| **PERF-PTN-** | 아키텍처 패턴 성능 경고 | 프레임워크별 안티패턴 상세 탐지 및 개선 방안 |
| **트리거** | implement/refactor 시 자동 | review 명령어 + 성능 키워드 감지 시 |
| **출력** | Code Quality Score의 일부 | 독립 성능 리뷰 결과 (YAML) |

**두 스킬 동시 로드 시:** code-quality-checker가 PERF- 메트릭을 산출하고, review-performance가 해당 메트릭을 심화 분석하여 구체적 개선 방안을 제시한다.

## 알고리즘 복잡도 리뷰

### 검사 항목

| # | 체크 항목 | 심각도 기준 | 탐지 패턴 |
|---|----------|-----------|----------|
| 1 | **중첩 루프** | O(n^2) 이상 시 high | `for...for`, `forEach...forEach`, 리스트 컴프리헨션 중첩 |
| 2 | **루프 내 검색** | O(n*m) 시 high | 루프 내 `list.index()`, `Array.find()`, `filter()` |
| 3 | **불필요한 정렬** | 이미 정렬된 데이터 재정렬 시 medium | `sort()` 호출 후 재 `sort()`, 정렬된 컬렉션 재정렬 |
| 4 | **비효율적 자료구조** | 조회가 잦은데 배열 사용 시 medium | 반복 `includes()`/`in` 검사를 Set/Map으로 대체 가능 |
| 5 | **재귀 깊이** | 메모이제이션 없는 지수적 재귀 시 high | 피보나치형 중복 호출, 트리 탐색 중복 방문 |

### 분석 관점

1. **입력 크기 추정**: 실제 운영 환경의 데이터 크기를 기준으로 복잡도 영향 평가
2. **최악 케이스 분석**: 평균이 아닌 최악 케이스(Worst Case) 기준으로 판단
3. **공간 복잡도 포함**: 시간 복잡도뿐 아니라 메모리 사용량도 함께 검토
4. **대안 제시**: O(n^2)를 O(n log n) 또는 O(n)으로 개선 가능한 경우 구체적 방법 제시

## N+1 쿼리 탐지

### ORM별 N+1 패턴

#### Django

| 패턴 | 문제 | 해결 |
|------|------|------|
| `for obj in queryset: obj.related.field` | 루프마다 JOIN 쿼리 발생 | `select_related('related')` 추가 |
| `for obj in queryset: obj.related_set.all()` | 루프마다 역참조 쿼리 발생 | `prefetch_related('related_set')` 추가 |
| `serializer.data` 내 nested serializer | 시리얼라이즈 시 N+1 발생 | queryset에 `select_related`/`prefetch_related` 적용 |
| `.values()` 없이 전체 모델 로드 | 불필요한 컬럼 로드 | `.values()` 또는 `.only()` 로 필요 컬럼만 조회 |

#### SQLAlchemy

| 패턴 | 문제 | 해결 |
|------|------|------|
| `for obj in query.all(): obj.relationship` | lazy loading으로 N+1 | `joinedload(Model.relationship)` 옵션 추가 |
| `relationship(lazy='select')` 기본값 | 접근 시마다 쿼리 | `lazy='joined'` 또는 `lazy='subquery'`로 변경 |
| 중첩 관계 접근 | 깊이별 N+1 누적 | `contains_eager()` 또는 다단계 `joinedload` |

#### Prisma

| 패턴 | 문제 | 해결 |
|------|------|------|
| `findMany()` 후 루프 내 `findUnique()` | 루프마다 쿼리 발생 | `include: { relation: true }` 사용 |
| 중첩 `include` 없이 관계 접근 | 암묵적 추가 쿼리 | 필요한 관계를 `include`/`select`로 명시 |
| `$transaction` 없이 다수 쓰기 | 트랜잭션 격리 부재 + 성능 | `$transaction([])` 배치 처리 |

### 범용 N+1 탐지 패턴

```
루프 내 개별 쿼리 실행 패턴:
- for/forEach/map 내부에서 DB 호출 함수 실행
- Promise.all() 없이 루프 내 async DB 호출
- 배치 가능한 작업을 개별 처리 (INSERT/UPDATE를 건별 실행)
```

## 캐싱 전략 리뷰

### 캐시 무효화 전략

| # | 체크 항목 | 심각도 | 설명 |
|---|----------|--------|------|
| 1 | **쓰기 시 무효화** | high | 데이터 변경 시 관련 캐시 키를 삭제/갱신하는 로직 존재 여부 |
| 2 | **일관성 범위** | high | 캐시-DB 간 불일치 허용 범위(eventual consistency) 정의 여부 |
| 3 | **계단식 무효화** | medium | 부모 엔티티 변경 시 자식 캐시도 함께 무효화하는지 확인 |
| 4 | **무효화 누락 경로** | high | 캐시 설정 경로와 무효화 경로가 1:1 매핑인지 확인 |

### TTL 적정성

| 데이터 유형 | 권장 TTL | 근거 |
|------------|---------|------|
| 사용자 세션 | 15-30분 | 보안 요구사항 |
| 설정/메타데이터 | 1-24시간 | 변경 빈도 낮음 |
| 검색 결과 | 5-15분 | 실시간성 요구 |
| 정적 리소스 | 1-7일 | 변경 시 버전 키 사용 |

### 캐시 키 설계

| # | 체크 항목 | 심각도 |
|---|----------|--------|
| 1 | 키 충돌 가능성 (네임스페이스 분리) | high |
| 2 | 키에 가변 요소(사용자 ID, 로케일 등) 포함 여부 | medium |
| 3 | 키 길이 적정성 (과도하게 긴 키는 메모리 낭비) | low |
| 4 | 키 패턴의 일관성 (프로젝트 전체에서 동일 규칙 적용) | medium |

### 캐시 스탬피드 방지

| 패턴 | 설명 | 적용 시점 |
|------|------|----------|
| **Lock/Mutex** | 캐시 미스 시 하나의 요청만 원본 조회, 나머지는 대기 | 고비용 쿼리, 높은 동시성 |
| **Early Expiry** | TTL 만료 전 백그라운드에서 선제적 갱신 | 예측 가능한 갱신 주기 |
| **Stale-While-Revalidate** | 만료된 캐시를 즉시 반환하고 비동기로 갱신 | 약간의 stale 데이터 허용 가능 |
| **Jitter** | TTL에 랜덤 오프셋을 추가하여 동시 만료 분산 | 다수 키가 동일 TTL인 경우 |

## 인덱스 검증

### 쿼리 패턴 매칭

| # | 체크 항목 | 심각도 |
|---|----------|--------|
| 1 | WHERE 절의 컬럼에 인덱스 존재 여부 | high |
| 2 | JOIN 조건 컬럼에 인덱스 존재 여부 | high |
| 3 | ORDER BY 컬럼이 인덱스에 포함되는지 | medium |
| 4 | 범위 검색(BETWEEN, >, <)에 적합한 인덱스 유형 | medium |
| 5 | LIKE 패턴의 선두 와일드카드(`LIKE '%foo'`) 인덱스 무효화 | medium |

### 복합 인덱스 순서

```
복합 인덱스 컬럼 순서 원칙:
1. 등치 조건(=) 컬럼을 선두에 배치
2. 범위 조건(>, <, BETWEEN) 컬럼을 후미에 배치
3. 정렬(ORDER BY) 컬럼은 범위 조건 뒤에 배치
4. 선택도(cardinality)가 높은 컬럼을 우선 배치

예시: WHERE status = 'active' AND created_at > '2024-01-01' ORDER BY score
권장 인덱스: (status, created_at, score)
```

### 불필요한 인덱스

| # | 패턴 | 조치 |
|---|------|------|
| 1 | 중복 인덱스 (A, B)와 (A, B, C)가 모두 존재 시 (A, B) 제거 가능 | 제거 권고 |
| 2 | 사용되지 않는 인덱스 (쿼리 패턴과 무관) | 제거 권고 |
| 3 | 카디널리티가 극히 낮은 컬럼의 단독 인덱스 (boolean 등) | 제거 또는 복합 인덱스로 전환 권고 |
| 4 | 쓰기 빈도가 극히 높은 테이블의 과다 인덱스 | 쓰기 성능 영향 경고 |

## 프레임워크별 성능 안티패턴

### Django

| 안티패턴 | 심각도 | 설명 | 개선 방안 |
|----------|--------|------|----------|
| N+1 쿼리 | high | `select_related`/`prefetch_related` 미사용 | 위 N+1 섹션 참조 |
| 미분리 시리얼라이저 | medium | 목록 API에 상세 시리얼라이저 사용 | 목록용/상세용 시리얼라이저 분리 |
| `QuerySet` 전체 평가 | high | `list(queryset)` 또는 `len(queryset)` 으로 전체 로드 | `.count()`, `.exists()`, 페이지네이션 사용 |
| 시그널 남용 | medium | `post_save` 시그널 내 무거운 로직 | 비동기 태스크(Celery 등)로 분리 |
| 마이그레이션 내 데이터 조작 | high | 대용량 테이블 `RunPython`에서 전체 순회 | 배치 처리, `iterator()` 사용 |

### React

| 안티패턴 | 심각도 | 설명 | 개선 방안 |
|----------|--------|------|----------|
| useEffect 남용 | medium | 파생 상태를 useEffect로 계산 | `useMemo` 또는 렌더링 중 계산으로 전환 |
| 불필요한 리렌더링 | medium | 부모 리렌더링 시 자식 전체 리렌더링 | `React.memo`, `useMemo`, `useCallback` 적용 |
| 인라인 객체/함수 props | medium | 매 렌더링마다 새 참조 생성 | 상위 스코프에서 선언 또는 메모이제이션 |
| 대용량 리스트 직접 렌더링 | high | 수천 항목을 직접 DOM에 렌더링 | `react-window`, `react-virtualized` 등 가상화 라이브러리 |
| 번들 크기 미관리 | medium | 전체 라이브러리 임포트 | Tree shaking, dynamic import, 코드 스플리팅 |

### Node.js

| 안티패턴 | 심각도 | 설명 | 개선 방안 |
|----------|--------|------|----------|
| 동기 I/O | high | `fs.readFileSync`, `child_process.execSync` 사용 | 비동기 API(`fs.promises`, `exec`) 사용 |
| 메모리 누수 | high | 이벤트 리스너 미해제, 클로저 내 대용량 참조 유지 | `removeListener`, WeakRef, 스코프 정리 |
| 이벤트 루프 블로킹 | high | CPU 집약 작업을 메인 스레드에서 실행 | Worker Threads, 청크 분할 처리 |
| 스트림 미사용 | medium | 대용량 파일을 `readFile`로 전체 로드 | `createReadStream`으로 스트리밍 처리 |
| 커넥션 풀 미설정 | medium | 요청마다 DB 커넥션 생성 | 커넥션 풀 설정 (pool size, idle timeout) |

## Output Format

```yaml
verdict: PASS | CONCERNS | ISSUES_FOUND
performance_score: {0-100}
summary: "{리뷰 대상 요약 및 주요 성능 영향}"

algorithm_review:
  issues_found: {count}
  worst_complexity: "{Big O 표기}"
  details:
    - id: "PERF-ALG-001"
      severity: high
      file: "src/service.ts:42"
      finding: "중첩 루프로 O(n^2) 복잡도"
      current: "O(n^2)"
      suggested: "O(n) - Map 기반 조회로 전환"
      estimated_impact: "1000건 기준 ~100ms -> ~1ms"

query_review:
  n_plus_one_detected: {count}
  details:
    - id: "PERF-DB-001"
      severity: high
      file: "src/views.py:85"
      finding: "N+1 쿼리 - select_related 누락"
      orm: "Django"
      suggested_action: "queryset에 select_related('author') 추가"

caching_review:
  issues:
    - id: "PERF-CFG-001"
      severity: medium
      file: "src/cache.ts:20"
      finding: "캐시 무효화 경로 누락"
      suggested_action: "write 경로에 캐시 삭제 로직 추가"

index_review:
  issues:
    - id: "PERF-DB-002"
      severity: high
      file: "migrations/0042.py"
      finding: "WHERE 절 컬럼에 인덱스 없음"
      suggested_action: "user_id 컬럼에 인덱스 추가"

framework_antipatterns:
  framework: "{Django|React|Node.js}"
  issues:
    - id: "PERF-PTN-001"
      severity: medium
      file: "src/components/List.tsx:15"
      finding: "대용량 리스트 직접 렌더링"
      suggested_action: "react-window 가상화 적용"
```

## Critical Rules

1. **증거 기반 분석**: 모든 성능 이슈는 파일:라인 참조와 복잡도/쿼리 수 등 정량적 근거를 포함한다
2. **입력 크기 고려**: 알고리즘 복잡도는 실제 운영 환경의 데이터 크기를 기준으로 영향을 평가한다. 소규모 데이터에서의 O(n^2)는 심각도를 낮출 수 있다
3. **조기 최적화 경계**: 측정 가능한 성능 문제만 이슈로 보고한다. 추측에 기반한 최적화 제안은 하지 않는다
4. **ORM 구체성**: N+1 탐지 시 사용 중인 ORM을 식별하고 해당 ORM의 구체적 해결 방법을 제시한다
5. **트레이드오프 명시**: 성능 개선 제안 시 가독성/유지보수성과의 트레이드오프를 함께 언급한다

## 연관 스킬

| 스킬 | 용도 | 경로 |
|------|------|------|
| review-code-quality | PERF- 접두사 기본 성능 메트릭 산출 | `.claude/skills/review-code-quality/SKILL.md` |
| review-requesting | 리뷰 체크리스트 및 이슈 분류 기준 | `.claude/skills/review-requesting/SKILL.md` |

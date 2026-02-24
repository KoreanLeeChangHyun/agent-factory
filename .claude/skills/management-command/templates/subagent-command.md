# 서브에이전트 명령어 템플릿

`context: fork`를 사용하여 격리된 서브에이전트에서 실행되는 명령어입니다.
대화 히스토리 없이 독립적으로 작업을 수행합니다.

## 언제 사용하는가?

- 격리된 환경에서 작업이 필요할 때
- 특정 에이전트 타입의 도구/권한이 필요할 때
- 대화 컨텍스트가 필요 없는 독립 작업

## 템플릿

```yaml
---
name: <명령어-이름>
description: <무엇을 하는지>
context: fork
agent: <Explore|Plan|general-purpose|custom-agent>
---

$ARGUMENTS에 대해 수행:

<작업 지침>
```

## 에이전트 타입

| 에이전트 | 특징 | 용도 |
|----------|------|------|
| `Explore` | 읽기 전용 도구, 빠른 탐색 | 코드베이스 탐색, 리서치 |
| `Plan` | 읽기 전용, 계획 수립 | 구현 계획, 아키텍처 설계 |
| `general-purpose` | 모든 도구 (기본값) | 범용 작업 |
| `<custom>` | `.claude/agents/`의 커스텀 에이전트 | 특수 작업 |

## 예시: 심층 리서치 명령어

```yaml
---
name: research-deep
description: 주제에 대한 심층 조사
context: fork
agent: Explore
---

$ARGUMENTS에 대해 철저히 조사:

1. Glob과 Grep으로 관련 파일 검색
2. 코드 읽고 분석
3. 구체적인 파일 참조와 함께 요약
```

## 예시: 구현 계획 명령어

```yaml
---
name: plan-impl
description: 기능 구현 계획 수립
context: fork
agent: Plan
---

$ARGUMENTS 기능 구현 계획:

1. 기존 코드베이스 분석
2. 영향 범위 파악
3. 단계별 구현 계획
4. 잠재적 위험 요소
5. 테스트 전략
```

## 예시: 의존성 분석 명령어

```yaml
---
name: analyze-deps
description: 프로젝트 의존성 분석
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob, Bash(npm *, yarn *, pnpm *)
---

프로젝트 의존성 분석:

1. package.json / requirements.txt 등 확인
2. 직접 vs 간접 의존성 구분
3. 버전 충돌 검사
4. 보안 취약점 검사 (`npm audit` 등)
5. 사용하지 않는 의존성 탐지
```

## 예시: 테스트 커버리지 분석 명령어

```yaml
---
name: coverage-analysis
description: 테스트 커버리지 분석 및 개선 제안
context: fork
agent: Explore
---

테스트 커버리지 분석:

1. 현재 테스트 파일 탐색
2. 테스트되지 않은 코드 식별
3. 커버리지 우선순위 결정
4. 테스트 케이스 제안
```

## 예시: 커스텀 에이전트 사용

```yaml
---
name: review-with-checker
description: 커스텀 checker 에이전트로 코드 리뷰
context: fork
agent: checker
---

$ARGUMENTS 파일 리뷰:

checker 에이전트의 규칙에 따라 코드 검사 수행.
```

## 주의사항

1. `context: fork`는 명시적 지침이 있는 명령어에만 적합
2. 서브에이전트는 대화 히스토리에 접근 불가
3. "이 규칙 따라" 같은 가이드라인만 있는 명령어는 부적합
4. 결과는 요약되어 메인 대화로 반환됨

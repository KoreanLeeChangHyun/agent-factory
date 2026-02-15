---
name: review-feedback-handler
description: "Review feedback receive/evaluate/implement protocol skill. Applies no-uncritical-acceptance principle with technical verification -> merit evaluation -> implementation -> test workflow, integrated with TODO tracking. Use for feedback handling: after receiving review feedback, entering REWORK stage, implementing review modifications. Triggers: '리뷰 반영', 'review feedback', '피드백 구현', '리뷰 수정', '리뷰 대응'."
license: "Apache-2.0"
---

# Review Feedback Handler

리뷰 피드백을 수신한 후 체계적으로 평가하고 구현하는 프로토콜 스킬.

**핵심 원칙:** 무비판적 수용 금지. 모든 피드백은 기술적 검증을 거친 후 수용한다.

## Overview

리뷰 피드백 처리의 목적은 코드 품질 향상이지, 리뷰어의 모든 의견을 무조건 반영하는 것이 아니다. 피드백을 받으면 먼저 기술적 타당성을 검증하고, 메리트를 평가한 뒤, 수용 여부를 결정한다. 리뷰어가 틀릴 수 있고, 구현자가 더 나은 맥락을 가질 수 있다. 근거 없는 수용은 코드 품질을 오히려 저하시킨다.

이 스킬은 `command-requesting-code-review`의 "피드백 처리" 섹션(Critical/Important/Minor/리뷰어가 틀린 경우)을 확장하여, 피드백 수신부터 구현 완료까지의 전체 프로토콜을 정의한다.

## 핵심 원칙

### 1. 무비판적 수용 금지

모든 피드백에 대해 기술적 타당성을 먼저 검증한다. "리뷰어가 말했으니까"는 수용 근거가 아니다.

- 피드백의 기술적 정확성을 코드/문서/스펙으로 확인
- 현재 구현의 의도와 제약 조건을 고려
- 피드백이 실제 문제를 지적하는지, 스타일 선호인지 구분

### 2. 근거 기반 반박 허용

기술적 근거가 있으면 리뷰어에게 반론을 제시한다. 건설적 반박은 코드 품질 향상에 기여한다.

- 동작을 증명하는 코드/테스트 제시
- 설계 결정의 트레이드오프 설명
- 대안이 야기하는 부작용 명시
- 명확화 요청으로 피드백의 의도 확인

### 3. 체계적 처리

피드백을 한 번에 하나씩 순서대로 처리한다. 한꺼번에 여러 항목을 수정하면 디버깅이 어려워진다.

- 심각도 순서로 처리 (Critical -> Important -> Minor)
- 각 항목별 독립 커밋 권장
- 처리 결과를 항목별로 기록

## 피드백 처리 워크플로우

5단계 순차 처리 워크플로우를 따른다.

### Step 1: 기술적 검증

피드백의 기술적 정확성을 확인한다.

- 피드백이 지적하는 문제가 실제로 존재하는가?
- 제안된 수정이 기술적으로 올바른가?
- 피드백이 현재 코드의 동작을 정확히 이해하고 있는가?
- 관련 테스트, 문서, 스펙을 확인하여 근거 수집

**판정:**
- 기술적으로 정확 -> Step 2로 진행
- 기술적으로 부정확 -> Invalid로 분류, 근거와 함께 반박 준비

### Step 2: 이해 확인

피드백의 의도와 맥락을 파악한다.

- 리뷰어가 실제로 원하는 변경이 무엇인가?
- 표면적 지적 이면의 근본 우려가 무엇인가?
- 피드백의 범위: 해당 파일만? 전체 설계?
- 불명확한 경우 리뷰어에게 명확화 요청

### Step 3: 메리트 평가

수정의 가치 대비 비용을 평가하고 판정한다.

| 판정 | 기준 | 후속 행동 |
|------|------|----------|
| Accept | 기술적으로 타당하고, 코드 품질을 명확히 개선 | Step 4로 진행 |
| Discuss | 타당하지만 트레이드오프 존재, 대안 논의 필요 | 리뷰어와 토론 후 재판정 |
| Defer | 유효하지만 현재 스코프 밖, 후속 작업으로 분리 | TODO로 기록, 현재는 미수정 |
| Reject | 기술적 근거로 반박 가능, 현재 구현이 더 나음 | 근거 제시 후 미수정 |

### Step 4: 개별 구현

수용된 항목을 하나씩 구현한다.

- Critical 항목부터 순서대로 처리
- 각 수정 사항에 대해 변경 전/후 비교
- 가능한 한 항목별 독립 커밋
- 수정이 다른 기능에 미치는 영향 확인

### Step 5: 테스트

수정 사항이 기존 동작을 깨뜨리지 않는지 검증한다.

- 기존 테스트 스위트 전체 실행
- 수정 관련 테스트 추가 (필요 시)
- 수정이 엣지 케이스를 새로 만들지 않는지 확인
- lint, type-check 통과 확인

## 피드백 분류 매트릭스

| 분류 | 정의 | 처리 방침 | 예시 |
|------|------|----------|------|
| Critical | 수정하지 않으면 버그/보안/데이터 손실 발생 | 즉시 수용, 수정 후 재리뷰 요청 | 인증 우회 가능, NPE 발생, SQL 인젝션 |
| Important | 코드 품질/유지보수성에 유의미한 영향 | 검토 후 대부분 수용, 합리적 사유로 Defer 가능 | 에러 처리 누락, 타입 안전성 부족, 테스트 갭 |
| Minor | 개선하면 좋지만 필수는 아닌 항목 | 선택적 수용, 합리적 사유로 거부 가능 | 네이밍 개선, 코드 스타일, 주석 추가, 미세 최적화 |
| Invalid | 기술적으로 부정확하거나 현재 맥락에 부적합 | 기술적 근거로 반박, 코드/테스트로 증명 | 이미 처리된 케이스, 오해에 기반한 지적, 스펙과 불일치 |

## TODO 추적 통합

피드백 처리 상태를 TODO 형식으로 추적한다.

### 추적 형식

```markdown
## Feedback Tracking

### Accepted
- [x] FB-01: [Critical] 인증 토큰 만료 검사 누락 수정 (file.ts:42)
- [x] FB-02: [Important] 에러 핸들러에 로깅 추가 (handler.ts:78)
- [ ] FB-03: [Important] 캐시 무효화 로직 개선 (cache.ts:15)

### Deferred
- FB-04: [Minor] 변수명 리팩토링 -> 다음 태스크에서 처리 (사유: 현재 스코프 밖)

### Rejected
- FB-05: [Minor] Map -> Object 변환 제안 -> 거부 (사유: Map이 O(1) lookup에 적합, 벤치마크 결과 첨부)
```

### 추적 규칙

- 수용된 항목: 구현 완료 시 `[x]` 체크
- 지연 항목: Deferred 섹션에 사유와 함께 기록
- 거부 항목: Rejected 섹션에 기술적 근거와 함께 기록
- 모든 Critical/Important 항목은 반드시 Accept 또는 명시적 Reject (암묵적 무시 금지)

## Output Format

```markdown
# Feedback Processing Result

## Summary
- 총 피드백 항목: N건
- 수용(Accept): N건
- 논의(Discuss): N건
- 지연(Defer): N건
- 거부(Reject): N건

## Feedback Items

### FB-01: [Critical] {피드백 제목}
- **리뷰어 지적:** {원문 또는 요약}
- **기술적 검증:** {검증 결과}
- **판정:** Accept / Discuss / Defer / Reject
- **사유:** {판정 근거}
- **수정 내역:** {변경 파일:라인, 변경 전/후 요약}

### FB-02: [Important] {피드백 제목}
...

## TODO Tracking
{위 추적 형식 참조}

## Test Results
- 기존 테스트: PASS / FAIL
- 추가 테스트: {테스트명} - PASS / FAIL
- lint/type-check: PASS / FAIL
```

## Related Skills

| 스킬 | 경로 | 관계 |
|------|------|------|
| command-requesting-code-review | `.claude/skills/command-requesting-code-review/SKILL.md` | 상위 스킬. 리뷰 요청 및 기본 피드백 분류(Critical/Important/Minor) 정의. 본 스킬은 해당 분류를 확장하여 처리 프로토콜 제공 |

## Critical Rules

1. **무비판적 수용 금지** - 모든 피드백은 기술적 검증(Step 1)을 거친 후에만 수용. "리뷰어가 말했으니까"는 수용 근거가 아님
2. **Critical은 즉시 처리** - Critical 분류 항목은 Defer/Reject 불가, 반드시 즉시 수용하여 수정
3. **한 번에 하나씩** - 여러 피드백 항목을 동시에 수정하지 않음. 심각도 순서로 하나씩 처리하여 변경 추적 가능성 확보
4. **근거 없는 거부 금지** - Reject 판정 시 반드시 기술적 근거(코드, 테스트, 벤치마크, 스펙)를 함께 제시
5. **모든 항목 추적** - Critical/Important 피드백은 암묵적 무시 금지. Accept, Defer, Reject 중 하나로 명시적 판정 기록

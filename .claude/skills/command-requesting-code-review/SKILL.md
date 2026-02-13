---
name: command-requesting-code-review
description: "태스크 완료, 주요 기능 구현, 머지 전에 코드 리뷰를 요청하여 품질을 검증하는 스킬. 리뷰 체크리스트 기반 사전 검증, 이슈 분류(Critical/Important/Minor), 프로덕션 준비 상태 평가. 사용 시점: 태스크 완료 후, 주요 기능 구현 후, 머지 전, 복잡한 버그 수정 후. 트리거: 'code review', '코드 리뷰', '리뷰 요청', 'review before merge'."
---

# Requesting Code Review

작업 완료 후 코드 리뷰를 요청하여 이슈를 조기에 발견하는 스킬.

**핵심 원칙:** 일찍 리뷰, 자주 리뷰.

## When to Request Review

**필수:**
- 각 태스크 완료 후
- 주요 기능 구현 완료 후
- main 브랜치 머지 전

**선택적이지만 유용:**
- 막혔을 때 (새로운 관점 확보)
- 리팩토링 전 (기준선 체크)
- 복잡한 버그 수정 후

## How to Request

**1. Git SHA 확인:**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # 또는 origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**2. 리뷰 정보 정리:**

| 항목 | 설명 |
|------|------|
| WHAT_WAS_IMPLEMENTED | 구현한 내용 |
| PLAN_OR_REQUIREMENTS | 요구사항/계획서 |
| BASE_SHA | 시작 커밋 |
| HEAD_SHA | 종료 커밋 |
| DESCRIPTION | 간략 요약 |

**3. 피드백 처리:**
- Critical 이슈: 즉시 수정
- Important 이슈: 진행 전 수정
- Minor 이슈: 나중에 처리 가능
- 리뷰어가 틀린 경우: 기술적 근거로 반박

## Review Checklist

### Code Quality
- [ ] 관심사의 적절한 분리?
- [ ] 적절한 에러 처리?
- [ ] 타입 안전성 (해당 시)?
- [ ] DRY 원칙 준수?
- [ ] 엣지 케이스 처리?

### Architecture
- [ ] 건전한 설계 결정?
- [ ] 확장성 고려?
- [ ] 성능 영향?
- [ ] 보안 우려사항?

### Testing
- [ ] 실제 로직을 테스트 (목만 테스트하지 않음)?
- [ ] 엣지 케이스 커버?
- [ ] 필요한 곳에 통합 테스트?
- [ ] 모든 테스트 통과?

### Requirements
- [ ] 모든 계획 요구사항 충족?
- [ ] 구현이 스펙과 일치?
- [ ] 범위 확대 없음?
- [ ] 브레이킹 체인지 문서화?

### Production Readiness
- [ ] 마이그레이션 전략 (스키마 변경 시)?
- [ ] 하위 호환성 고려?
- [ ] 문서화 완료?
- [ ] 명백한 버그 없음?

## Output Format

```markdown
### Strengths
[잘된 점. 구체적으로.]

### Issues

#### Critical (Must Fix)
[버그, 보안 이슈, 데이터 손실 위험, 기능 장애]

#### Important (Should Fix)
[아키텍처 문제, 누락된 기능, 부실한 에러 처리, 테스트 갭]

#### Minor (Nice to Have)
[코드 스타일, 최적화 기회, 문서 개선]

**각 이슈마다:**
- 파일:라인 참조
- 문제점
- 중요한 이유
- 수정 방법 (명확하지 않은 경우)

### Assessment
**머지 준비?** [Yes/No/With fixes]
**근거:** [1-2문장 기술 평가]
```

## Integration with Workflows

**워크플로우 WORK 단계:**
- 각 태스크 완료 후 리뷰 수행
- 이슈가 복합되기 전에 발견
- 다음 태스크 이동 전 수정

**워크플로우 REPORT 단계:**
- 최종 리뷰 결과를 보고서에 포함
- 머지 전 최종 검증

## Red Flags

**절대 하지 말 것:**
- "간단하니까" 리뷰 건너뛰기
- Critical 이슈 무시
- 미수정 Important 이슈와 함께 진행
- 유효한 기술적 피드백과 싸움

**리뷰어가 틀린 경우:**
- 기술적 근거로 반박
- 동작을 증명하는 코드/테스트 제시
- 명확화 요청

## Example

```
[태스크 2 완료: 검증 함수 추가]

1. 코드 리뷰 요청

BASE_SHA=$(git log --oneline | grep "Task 1" | head -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse HEAD)

  WHAT_WAS_IMPLEMENTED: 대화 인덱스 검증 및 복구 함수
  PLAN_OR_REQUIREMENTS: docs/plans/deployment-plan.md 태스크 2
  BASE_SHA: a7981ec
  HEAD_SHA: 3df7661
  DESCRIPTION: verifyIndex()와 repairIndex() 추가, 4가지 이슈 타입

[리뷰 결과]:
  Strengths: 클린 아키텍처, 실제 테스트
  Issues:
    Important: 진행 표시기 누락
    Minor: 매직 넘버 (100) 보고 간격
  Assessment: 진행 가능

2. [진행 표시기 수정]
3. [태스크 3으로 이동]
```

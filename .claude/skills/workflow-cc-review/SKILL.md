---
name: workflow-cc-review
description: "Workflow command skill for cc:review. Performs code review with severity-based assessment. Auto-loads keyword-based review skills for security, architecture, frontend, performance, comprehensive, feedback, and PR integration."
disable-model-invocation: true
---

# Review Command

코드 리뷰를 수행하는 워크플로우 커맨드 스킬.

상세 실행 절차는 `.claude/commands/cc/review.md`를 참조한다.

## 메타데이터

### 키워드-스킬 매핑

| 트리거 키워드 | 로드 스킬 |
|--------------|----------|
| 보안, security, 취약점, vulnerability, OWASP | review-security |
| 아키텍처, architecture, 구조, 설계, 레이어 | review-architecture |
| 프론트엔드, frontend, React, UI, 컴포넌트 | review-frontend |
| 성능, performance, 쿼리, DB, N+1 | review-performance |
| 종합, comprehensive, 전체, full review | review-comprehensive |
| 리뷰 반영, review feedback, 피드백 구현, 리뷰 수정, 리뷰 대응 | review-feedback-handler |
| PR 리뷰, pull request review, PR 검증, PR 체크 | review-pr-integration |

## 참조

이 스킬의 실행 절차는 대응 커맨드 파일(`.claude/commands/cc/review.md`)이 Single Source of Truth이다.

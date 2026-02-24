---
name: workflow-cc-review
description: "Workflow command skill for cc:review. Performs code review with severity-based assessment. Auto-loads keyword-based review skills for security, architecture, frontend, performance, comprehensive, feedback, and PR integration."
disable-model-invocation: true
---

# Review Command

코드 리뷰를 수행하는 워크플로우 커맨드 스킬.

## 실행 옵션

| 옵션 | 모드명 | 설명 | Phase Order |
|------|--------|------|-------------|
| `-np` | noplan | PLAN 단계 스킵 | INIT -> WORK -> REPORT -> DONE |
| `-nr` | noreport | REPORT 단계 스킵 | INIT -> PLAN -> WORK -> DONE |
| `-np -nr` | noplan+noreport | 둘 다 스킵 | INIT -> WORK -> DONE |

## 심각도 기준

| 심각도 | 기준 |
|--------|------|
| Critical | 즉시 수정 필요 - 보안, 데이터 손실, 기능 장애 |
| Important | 수정 권장 - 아키텍처, 성능, 잠재적 버그 |
| Minor | 개선 제안 - 스타일, 최적화, 문서 |

## 관련 스킬

| 스킬 | 용도 | 경로 |
|------|------|------|
| review-requesting | 리뷰 체크리스트 및 사전 검증 | `.claude/skills/review-requesting/SKILL.md` |
| review-code-quality | 기본 로드 - 정량적 품질 검사, Code Quality Score 산출 | `.claude/skills/review-code-quality/SKILL.md` |
| review-security | 키워드 조건부 로드 - 보안 전문 리뷰 | `.claude/skills/review-security/SKILL.md` |
| review-architecture | 키워드 조건부 로드 - 아키텍처 전문 리뷰 | `.claude/skills/review-architecture/SKILL.md` |
| review-frontend | 키워드 조건부 로드 - 프론트엔드 전문 리뷰 | `.claude/skills/review-frontend/SKILL.md` |
| review-performance | 키워드 조건부 로드 - 성능 전문 리뷰 | `.claude/skills/review-performance/SKILL.md` |
| review-comprehensive | 키워드 조건부 로드 - 종합 리뷰 | `.claude/skills/review-comprehensive/SKILL.md` |
| review-feedback-handler | 키워드 조건부 로드 - 피드백 처리 | `.claude/skills/review-feedback-handler/SKILL.md` |
| review-pr-integration | 키워드 조건부 로드 - PR 리뷰 통합 | `.claude/skills/review-pr-integration/SKILL.md` |

## 프로젝트 플로우 연동

워크플로우가 `.kanbanboard` 컨텍스트 내에서 실행될 때, REPORT 완료 후 칸반보드를 자동 갱신한다.

### 후처리 조건

1. 프로젝트 루트에서 `.kanbanboard` 파일 존재 여부 확인
2. 존재하지 않으면 후처리 스킵
3. 존재하면 아래 갱신 절차 실행

### 갱신 절차

```bash
bash .claude/skills/design-strategy/scripts/update-kanban.sh <kanbanboard_path> <workflow_id> <status>
```

| 인자 | 값 |
|------|-----|
| `kanbanboard_path` | 프로젝트 루트의 `.kanbanboard` 파일 경로 |
| `workflow_id` | 현재 워크플로우 ID |
| `status` | `completed` 또는 `failed` |

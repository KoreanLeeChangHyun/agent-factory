---
description: 코드 리뷰 수행. 파일, 디렉토리, PR 등을 리뷰합니다.
---

# Review

**입력:**
- `command`: review

## 심각도 기준

| 심각도 | 기준 |
|--------|------|
| Critical | 즉시 수정 필요 - 보안, 데이터 손실, 기능 장애 |
| Important | 수정 권장 - 아키텍처, 성능, 잠재적 버그 |
| Minor | 개선 제안 - 스타일, 최적화, 문서 |

## 관련 스킬

| 스킬 | 용도 | 경로 |
|------|------|------|
| command-requesting-code-review | 리뷰 체크리스트 및 사전 검증 | `.claude/skills/command-requesting-code-review/SKILL.md` |
| command-code-quality-checker | 기본 로드 - 정량적 품질 검사, Code Quality Score 산출 | `.claude/skills/command-code-quality-checker/SKILL.md` |
| command-review-security | 키워드 조건부 로드 - 보안 전문 리뷰 | `.claude/skills/command-review-security/SKILL.md` |
| command-review-architecture | 키워드 조건부 로드 - 아키텍처 전문 리뷰 | `.claude/skills/command-review-architecture/SKILL.md` |
| command-review-frontend | 키워드 조건부 로드 - 프론트엔드 전문 리뷰 | `.claude/skills/command-review-frontend/SKILL.md` |
| command-review-performance | 키워드 조건부 로드 - 성능 전문 리뷰 | `.claude/skills/command-review-performance/SKILL.md` |
| review-comprehensive | 키워드 조건부 로드 - 종합 리뷰 | `.claude/skills/review-comprehensive/SKILL.md` |
| review-feedback-handler | 키워드 조건부 로드 - 피드백 처리 | `.claude/skills/review-feedback-handler/SKILL.md` |
| review-pr-integration | 키워드 조건부 로드 - PR 리뷰 통합 | `.claude/skills/review-pr-integration/SKILL.md` |

## 실행 옵션

| 옵션 | 모드명 | 설명 | Phase Order |
|------|--------|------|-------------|
| `-np` | noplan | PLAN 단계를 스킵하고 즉시 WORK로 진행 | INIT -> WORK -> REPORT -> DONE |
| `-nr` | noreport | REPORT 단계를 스킵하고 WORK 완료 후 즉시 DONE으로 진행 | INIT -> PLAN -> WORK -> DONE |
| `-np -nr` | noplan+noreport | PLAN과 REPORT 모두 스킵 | INIT -> WORK -> DONE |

## 프로젝트 플로우 연동

워크플로우가 프로젝트 플로우(`.kanbanboard`) 컨텍스트 내에서 실행될 때, REPORT 단계 완료 후 칸반보드를 자동 갱신한다.

### 후처리 조건

1. 프로젝트 루트 디렉토리에서 `.kanbanboard` 파일을 검색한다
2. `.kanbanboard` 파일이 존재하지 않으면 후처리를 스킵한다
3. `.kanbanboard` 파일이 존재하면 아래 갱신 절차를 실행한다

### 갱신 절차

REPORT 단계가 완료(DONE 상태 전이)된 후 다음을 수행한다:

```bash
bash .claude/skills/command-strategy/scripts/update-kanban.sh <kanbanboard_path> <workflow_id> <status>
```

| 인자 | 값 |
|------|-----|
| `kanbanboard_path` | 프로젝트 루트의 `.kanbanboard` 파일 경로 |
| `workflow_id` | 현재 워크플로우 ID (예: WF-1) |
| `status` | `completed` (정상 완료 시) 또는 `failed` (실패 시) |

### 동작 요약

- 완료된 워크플로우의 체크박스를 `[x]`로 전환
- 해당 마일스톤의 상태 카운터(N/M 완료)를 자동 갱신
- 모든 워크플로우가 완료된 마일스톤을 Done 컬럼으로 이동

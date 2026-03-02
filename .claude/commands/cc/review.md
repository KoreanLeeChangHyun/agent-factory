---
description: "코드 리뷰 수행. 파일, 디렉토리, PR 등을 리뷰합니다. Use when: 코드 리뷰, PR 리뷰, 보안 리뷰, 성능 리뷰, 아키텍처 리뷰 / Do not use when: 코드 수정이 목적일 때 (cc:implement 사용)"
argument-hint: "리뷰 대상 파일, 디렉터리, 또는 PR 번호"
---

> **워크플로우 스킬 로드**: 이 명령어는 워크플로우 오케스트레이션 스킬을 사용합니다. 실행 시작 전 `.claude/skills/workflow-orchestration/SKILL.md`를 Read로 로드하세요.

## `<command>` 태그 검증

이 검증은 워크플로우 오케스트레이션 스킬의 Step 1(INIT) 완료 후, Step 2(PLAN) 시작 전에 수행된다.

### 검증 절차

오케스트레이터가 INIT Step에서 `user_prompt.txt`를 생성한 후, PLAN Step 진입 전에 다음을 수행한다:

1. `user_prompt.txt` 첫 번째 줄을 파싱하여 `<command>XXX</command>` 패턴을 추출한다
2. 검증 규칙을 적용한다:
   - `<command>` 태그가 존재하고 값이 `review`가 **아닌** 경우: AskUserQuestion으로 경고 메시지를 표시한다
     - 메시지: `"prompt.txt에 <command>{값}</command>으로 지정되어 있지만 cc:review를 실행했습니다."`
     - 선택지: `"계속 진행"` (현재 커맨드로 진행) / `"중단"` (워크플로우 종료)
   - `<command>` 태그가 존재하지 않는 경우: 경고 없이 정상 진행 (하위 호환)
   - `<command>review</command>`인 경우: 정상 진행

# Review

**입력:**
- `command`: review

## 기본 리뷰 절차

1. **대상 파악** - 리뷰 대상 파일/디렉터리/PR을 식별하고 변경 범위를 확인한다
2. **코드 읽기** - 변경 내용을 맥락(의도, 설계, 의존성)과 함께 이해한다
3. **이슈 식별** - 버그, 보안, 성능, 아키텍처 문제를 탐지한다
4. **심각도 분류** - 식별된 이슈를 Critical/Important/Minor 기준으로 분류한다
5. **피드백 작성** - 구체적 개선안과 근거를 포함한 리뷰 코멘트를 생성한다

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

## 스킬 우선순위 정책

| 상황 | 로드 스킬 | 비고 |
|------|----------|------|
| 종합 리뷰 키워드 (종합, comprehensive, 전체) | `review-comprehensive` 단독 | 다른 전문 스킬 비활성 |
| 전문 키워드 (보안, 성능, 아키텍처, 프론트엔드) | 해당 전문 스킬 단독 | `review-comprehensive` 비활성 |
| 혼합 (종합 + 전문 키워드 동시) | `review-comprehensive` 우선 | 전문 스킬 추가 로드 생략 |

## 동적 컨텍스트

리뷰 대상에 따라 컨텍스트 주입 방식이 달라진다.

### PR 번호가 인수로 전달된 경우

PR 동적 컨텍스트를 활성화하여 PR의 diff와 기존 코멘트를 자동 수집한다.

```
!gh pr diff <PR번호>
!gh pr view <PR번호> --comments
```

### 파일 또는 디렉터리가 대상인 경우

로컬 diff 기반 컨텍스트를 사용한다.

```
!git diff HEAD -- <파일경로>
!git log --oneline -5 -- <파일경로>
```

## 프로젝트 플로우 연동

워크플로우가 프로젝트 플로우(`.kanbanboard`) 컨텍스트 내에서 실행될 때, REPORT 단계 완료 후 칸반보드를 자동 갱신한다.

### 후처리 조건

1. 프로젝트 루트 디렉토리에서 `.kanbanboard` 파일을 검색한다
2. `.kanbanboard` 파일이 존재하지 않으면 후처리를 스킵한다
3. `.kanbanboard` 파일이 존재하면 아래 갱신 절차를 실행한다

### 갱신 절차

REPORT 단계가 완료(DONE 상태 전이)된 후 다음을 수행한다:

```bash
bash .claude/skills/design-strategy/scripts/update-kanban.sh <kanbanboard_path> <workflow_id> <status>
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

---
name: workflow-wf-review
description: "Workflow command skill for wf review. Performs code review with severity-based assessment. Auto-loads keyword-based review skills for security, architecture, frontend, performance, comprehensive, feedback, and PR integration."
disable-model-invocation: true
license: "Apache-2.0"
---

# Review Command

코드 리뷰를 수행하는 워크플로우 커맨드 스킬.

## 워크플로우 스킬 로드

실행 시작 전 Read 도구로 `.claude/skills/workflow-orchestration/SKILL.md`를 로드하여 PLAN→WORK→REPORT→DONE FSM 절차를 확인한다.

## 기본 리뷰 절차

1. **대상 파악** - 리뷰 대상 파일/디렉터리/PR을 식별하고 변경 범위를 확인한다
2. **코드 읽기** - 변경 내용을 맥락(의도, 설계, 의존성)과 함께 이해한다
3. **이슈 식별** - 버그, 보안, 성능, 아키텍처 문제를 탐지한다
4. **심각도 분류** - 식별된 이슈를 Critical/Important/Minor 기준으로 분류한다
5. **피드백 작성** - 구체적 개선안과 근거를 포함한 리뷰 코멘트를 생성한다.<br>코드 수정이 필요한 이슈를 발견한 경우 보고서에 수정 방안(파일, 위치, 변경 내용)을 기술하되 직접 수정하지 않는다.

## 코드 수정 금지 제약

> **WARNING**: 리뷰 워크플로우에서 Edit/Write 도구로 소스 코드를 수정하는 행위는 절대 금지된다. T-092 사고에서 리뷰 워커가 common.js, kanban.js, kanban.css를 직접 수정하여 Submit 컬럼을 잘못 추가한 월권이 발생하였다. 이 제약은 동일 사고 재발을 방지하기 위해 명문화된 것이다.

| 구분 | 대상 | 허용 여부 |
|------|------|----------|
| 허용 | 보고서 파일(report.md, work/*.md) 읽기/쓰기 | O |
| 금지 | 소스 코드 파일(.js, .ts, .py, .css, .html 등) 수정 (Edit/Write 도구) | X |

코드 수정이 필요한 경우 보고서에 수정 방안을 기술하고 별도 implement 사이클에서 처리한다.

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
| review-code-quality | 기본 로드 - 정량적 품질 검사 | `.claude/skills/review-code-quality/SKILL.md` |
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
| 종합 리뷰 키워드 | `review-comprehensive` 단독 | 다른 전문 스킬 비활성 |
| 전문 키워드 | 해당 전문 스킬 단독 | `review-comprehensive` 비활성 |
| 혼합 | `review-comprehensive` 우선 | 전문 스킬 추가 로드 생략 |

## 키워드-스킬 매핑

| 트리거 키워드 | 로드 스킬 |
|--------------|----------|
| 보안, security, 취약점, vulnerability, OWASP | review-security |
| 아키텍처, architecture, 구조, 설계, 레이어 | review-architecture |
| 프론트엔드, frontend, React, UI, 컴포넌트 | review-frontend |
| 성능, performance, 쿼리, DB, N+1 | review-performance |
| 종합, comprehensive, 전체, full review | review-comprehensive |
| 리뷰 반영, review feedback, 피드백 구현, 리뷰 수정, 리뷰 대응 | review-feedback-handler |
| PR 리뷰, pull request review, PR 검증, PR 체크 | review-pr-integration |

## 동적 컨텍스트

### PR 번호가 인수로 전달된 경우

```bash
gh pr diff <PR번호>
gh pr view <PR번호> --comments
```

### 파일 또는 디렉터리가 대상인 경우

```bash
git diff HEAD -- <파일경로>
git log --oneline -5 -- <파일경로>
```

## 프로젝트 플로우 연동

REPORT 단계 완료 후 티켓 상태를 자동 전이한다.

### 전이 절차

```bash
flow-kanban move T-NNN review
```

티켓 파일은 `.kanban/T-NNN.xml`이다.

### cleanup 절차

워크플로우 완료 시 tmux 윈도우 자동 종료가 이중 안전장치로 동작한다:

- **1차 (finalization.py Step 5)**: `flow-finish` 실행 시 3초 지연 후 tmux 윈도우를 백그라운드(nohup+sleep)로 kill. `flow-claude end` 배너 출력이 보장된 후 종료
- **2차 (PostToolUse hook)**: `flow-claude end` Bash 호출 감지 시 5초 지연 후 tmux 윈도우를 추가로 kill. 1차 안전장치 실패 시 보완
- **비tmux 환경**: `TMUX_PANE` 미설정 시 양쪽 모두 자동 스킵 (멱등성 보장)

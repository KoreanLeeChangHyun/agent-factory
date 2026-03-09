---
description: "코드 리뷰 수행. 파일, 디렉토리, PR 등을 리뷰합니다. Use when: 코드 리뷰, PR 리뷰, 보안 리뷰, 성능 리뷰, 아키텍처 리뷰 / Do not use when: 코드 수정이 목적일 때 (cc:implement 사용)"
argument-hint: "[-n] [#N] 리뷰 대상 파일, 디렉터리, 또는 PR 번호"
---

> **워크플로우 스킬 로드**: 이 명령어는 워크플로우 오케스트레이션 스킬을 사용합니다. 실행 시작 전 `.claude/skills/workflow-orchestration/SKILL.md`를 Read로 로드하세요.

## `-n` 강제 승인 요청 플래그

기본 동작은 자동 승인입니다. 오케스트레이터는 별도 플래그 없이 `autoApprove=true`로 설정하여 PLAN 완료 후 자동으로 WORK 단계로 진행합니다.

`$ARGUMENTS`에 `-n` 플래그가 포함되면 오케스트레이터가 `autoApprove=false`로 설정합니다. planner는 정상 실행하되, PLAN Step 2b에서 사용자 승인(AskUserQuestion 3옵션: 승인/수정 요청/중지)을 요청합니다.

- `-n` 미포함: 기본 동작 → planner 완료 후 자동 승인, WORK 즉시 진행
- `-n` 포함: planner 완료 후 AskUserQuestion 3옵션 제시 (승인/수정 요청/중지)

`plan_validator.py`가 계획서 검증 중 경고를 발생시키면, `-n` 플래그 여부와 무관하게 자동 승인이 차단되고 사용자 확인을 요청합니다.

## `#N` 티켓 번호 인자

`$ARGUMENTS`에서 `#N` 패턴(예: `#1`, `#12`, `#123`)을 파싱하여 티켓 번호를 추출합니다. 추출된 번호는 3자리 zero-padding하여 `.kanban/*-T-NNN.txt` glob 패턴으로 현재 상태 파일을 자동 탐색합니다.

- `#N` 지정 시: `.kanban/*-T-NNN.txt` glob 패턴으로 탐색한 파일을 읽어 `user_prompt.txt`로 사용
- `#N` 미지정 시: `.kanban/board.md`에서 Open 상태 티켓을 자동 선택
  - Open 티켓 1개: 해당 티켓 자동 선택
  - Open 티켓 복수: 메뉴로 사용자에게 선택 요청
  - Open 티켓 0개: `$ARGUMENTS` 텍스트를 그대로 사용 (기존 동작 호환)

## `<command>` 태그 검증

이 검증은 워크플로우 오케스트레이션 스킬의 Step 1(INIT) 완료 후, Step 2(PLAN) 시작 전에 수행된다.

### 검증 절차

오케스트레이터가 INIT Step에서 `user_prompt.txt`를 생성한 후, PLAN Step 진입 전에 다음을 수행한다:

1. `user_prompt.txt` 첫 번째 줄을 파싱하여 `<command>XXX</command>` 패턴을 추출한다
2. 검증 규칙을 적용한다:
   - `<command>` 태그가 존재하고 값이 `review`가 **아닌** 경우: AskUserQuestion으로 경고 메시지를 표시한다
     - 메시지: `"티켓 파일에 <command>{값}</command>으로 지정되어 있지만 cc:review를 실행했습니다."`
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

워크플로우가 프로젝트 플로우(`.kanban/board.md`) 컨텍스트 내에서 실행될 때, REPORT 단계 완료 후 티켓 상태를 자동 전이한다.

### 후처리 조건

1. 프로젝트 루트 디렉터리에서 `.kanban/board.md` 파일을 검색한다
2. `.kanban/board.md` 파일이 존재하지 않으면 후처리를 스킵한다
3. `.kanban/board.md` 파일이 존재하면 아래 전이 절차를 실행한다

### 전이 절차

REPORT 단계가 완료(DONE 상태 전이)된 후 다음을 수행한다:

```bash
python3 .claude/scripts/flow/kanban.py move T-NNN review
```

| 인자 | 값 |
|------|-----|
| `T-NNN` | 현재 워크플로우와 연결된 티켓 번호 (예: T-001) |
| `review` | 리뷰 완료 후 전이할 상태 |

### 동작 요약

- 리뷰가 완료된 티켓을 Review 상태로 전이한다
- 티켓 번호는 워크플로우 초기화 시 파싱된 `#N` 인자 또는 자동 선택된 티켓에서 가져온다

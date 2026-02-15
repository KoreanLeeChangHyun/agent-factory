---
name: review-pr-integration
description: "PR review integration skill. Performs gh CLI-based PR diff extraction, inline comment generation, CI status checks, and checklist auto-verification. Use for PR review: PR review requests, final verification before PR merge. Triggers: 'PR 리뷰', 'pull request review', 'PR 검증', 'PR 체크'."
license: "Apache-2.0"
---

# PR Review Integration

gh CLI 기반으로 PR 리뷰의 전 과정(diff 추출, 코드 리뷰, 인라인 코멘트, CI 검증, 체크리스트 확인)을 통합 수행하는 스킬.

**핵심 목적:** PR을 머지하기 전에 코드 변경사항을 체계적으로 검증하고, 리뷰 결과를 GitHub PR에 직접 반영한다.

## pr-summary 및 github-integration과의 역할 분리

| 항목 | pr-summary | github-integration | review-pr-integration |
|------|-----------|-------------------|----------------------|
| 역할 | PR 제목/본문 자동 생성 | GitHub API 범용 연동 (커밋, 푸시, 이슈) | PR 리뷰 전용 워크플로우 |
| 입력 | git diff, 커밋 히스토리 | 사용자 명령 | PR 번호 또는 현재 브랜치 PR |
| 출력 | PR 제목, 본문, 테스트 계획 | git/gh 명령 실행 결과 | 리뷰 코멘트, CI 상태, 판정 |
| 시점 | PR 생성 전 | 수시 (커밋, 푸시, 이슈 등) | PR 생성 후 리뷰 단계 |
| 관점 | 작성자 (PR을 만드는 사람) | 작업자 (GitHub 조작) | 리뷰어 (PR을 검증하는 사람) |

**보완 관계:** pr-summary로 PR을 생성한 뒤, review-pr-integration으로 해당 PR을 리뷰한다. github-integration은 두 스킬 모두에서 gh CLI 실행의 기반이 된다.

## PR Diff 추출 워크플로우

### 1단계: PR 정보 수집

```bash
# PR 번호로 조회
gh pr view <PR_NUMBER> --json number,title,body,state,baseRefName,headRefName,files,additions,deletions

# 현재 브랜치의 PR 자동 감지
gh pr view --json number,title,body,state,baseRefName,headRefName,files,additions,deletions
```

### 2단계: Diff 추출

```bash
# PR diff 전체 추출
gh pr diff <PR_NUMBER>

# 특정 파일만 추출
gh pr diff <PR_NUMBER> -- <파일경로>

# stat 요약
gh pr diff <PR_NUMBER> --stat
```

### 3단계: 변경 파일 목록 생성

```bash
# 변경 파일 목록 (JSON)
gh pr view <PR_NUMBER> --json files --jq '.files[].path'

# 변경 라인 수 집계
gh pr view <PR_NUMBER> --json additions,deletions --jq '"additions: \(.additions), deletions: \(.deletions)"'
```

### 4단계: 리뷰 대상 분류

| 분류 | 기준 | 리뷰 깊이 |
|------|------|----------|
| 핵심 변경 | 비즈니스 로직, API 계약, 보안 관련 | 라인별 정밀 검토 |
| 구조 변경 | 파일 이동, 리네이밍, 디렉토리 재구성 | 변경 의도 확인 |
| 설정 변경 | 의존성, 환경 설정, CI 설정 | 영향 범위 확인 |
| 문서 변경 | README, 주석, 문서 파일 | 정확성 확인 |
| 테스트 변경 | 테스트 추가/수정 | 커버리지 확인 |

## 인라인 코멘트 생성

### 단일 코멘트 작성

```bash
# PR에 인라인 리뷰 코멘트 추가
gh api repos/{owner}/{repo}/pulls/<PR_NUMBER>/comments \
  -f body="[SEVERITY] 설명" \
  -f commit_id="<COMMIT_SHA>" \
  -f path="<FILE_PATH>" \
  -F line=<LINE_NUMBER> \
  -f side="RIGHT"
```

### 리뷰 제출 (여러 코멘트 일괄)

```bash
# 리뷰 생성 (PENDING 상태)
gh api repos/{owner}/{repo}/pulls/<PR_NUMBER>/reviews \
  -f body="리뷰 요약" \
  -f event="COMMENT" \
  -f 'comments[][path]="file.ts"' \
  -f 'comments[][position]=10' \
  -f 'comments[][body]="[Important] 에러 처리 누락"'
```

### 심각도 태그 형식

인라인 코멘트에 심각도를 태그로 표기한다:

| 태그 | 의미 | 예시 |
|------|------|------|
| `[Critical]` | 즉시 수정 필요 | `[Critical] SQL 인젝션 취약점` |
| `[Important]` | 수정 권장 | `[Important] 에러 처리 누락` |
| `[Minor]` | 개선 제안 | `[Minor] 변수명 개선 권장` |
| `[Question]` | 확인 필요 | `[Question] 이 로직의 의도?` |
| `[Praise]` | 좋은 구현 | `[Praise] 깔끔한 에러 처리` |

## CI 상태 확인

### CI 파이프라인 상태 조회

```bash
# PR 체크 상태 확인
gh pr checks <PR_NUMBER>

# JSON 형식 상세 조회
gh pr checks <PR_NUMBER> --json name,state,conclusion,startedAt,completedAt
```

### CI 실패 시 처리 절차

1. **실패 체크 식별**: `gh pr checks`에서 `FAILURE` 상태 체크 확인
2. **로그 추출**: 실패한 체크의 상세 로그 확인
   ```bash
   # 실패한 체크의 로그 URL 확인
   gh pr checks <PR_NUMBER> --json name,state,detailsUrl --jq '.[] | select(.state == "FAILURE")'
   ```
3. **영향 평가**: 실패가 PR 변경과 직접 관련인지 판단
4. **결과 반영**: CI 실패를 리뷰 판정에 반영 (CI 실패 시 머지 불가 권고)

### 머지 전제조건 검증

| 조건 | 확인 방법 | 필수 여부 |
|------|----------|----------|
| CI 전체 통과 | `gh pr checks` 전체 SUCCESS | 필수 |
| 리뷰 승인 | `gh pr view --json reviewDecision` | 필수 |
| 충돌 없음 | `gh pr view --json mergeable` | 필수 |
| 브랜치 최신 | base 브랜치 대비 최신 상태 | 권장 |

## 체크리스트 자동 검증

### PR 본문 체크리스트 파싱

PR 본문에서 마크다운 체크리스트 항목을 추출하고 상태를 확인한다:

```bash
# PR 본문 추출
gh pr view <PR_NUMBER> --json body --jq '.body'
```

**체크리스트 패턴 인식:**

| 패턴 | 상태 |
|------|------|
| `- [x] 항목` | 완료 |
| `- [ ] 항목` | 미완료 |
| `- [X] 항목` | 완료 (대문자) |

### 검증 절차

1. **체크리스트 추출**: PR 본문에서 `- [ ]` / `- [x]` 패턴 파싱
2. **완료율 산출**: 완료 항목 / 전체 항목 비율 계산
3. **미완료 항목 알림**: 미체크 항목을 리뷰 코멘트로 알림
4. **판정 반영**: 필수 체크리스트 미완료 시 머지 불가 권고

### 체크리스트 검증 결과 보고

```
Checklist Status:
  Total: 8 items
  Completed: 6/8 (75%)
  Pending:
    - [ ] 엔드포인트 응답 확인
    - [ ] 에러 처리 테스트
```

## Output Format

```markdown
## PR Review Result

### PR Info
- **PR**: #<NUMBER> <TITLE>
- **Author**: <AUTHOR>
- **Base**: <BASE_BRANCH> <- <HEAD_BRANCH>
- **Changes**: +<ADDITIONS> -<DELETIONS> across <FILE_COUNT> files

### Diff Summary
| Category | Files | Key Changes |
|----------|-------|-------------|
| Core Logic | N | <요약> |
| Tests | N | <요약> |
| Config | N | <요약> |
| Docs | N | <요약> |

### CI Status
| Check | Status | Duration |
|-------|--------|----------|
| <CHECK_NAME> | PASS/FAIL | <DURATION> |

**CI Verdict**: ALL_PASS / HAS_FAILURES

### Review Comments
| # | File | Line | Severity | Comment |
|---|------|------|----------|---------|
| 1 | <PATH> | <LINE> | Critical | <설명> |
| 2 | <PATH> | <LINE> | Important | <설명> |

### Checklist Status
- Completion: <N>/<TOTAL> (<PERCENT>%)
- Pending items: <목록>

### Verdict
**Decision**: APPROVE / REQUEST_CHANGES / COMMENT
**Reason**: <1-2문장 근거>
**Merge Ready**: Yes / No / With fixes

### Issues Summary
- Critical: <N>
- Important: <N>
- Minor: <N>
```

## Critical Rules

1. **gh CLI 필수**: 모든 PR 조작은 `gh` CLI를 통해 수행한다. 직접 GitHub API를 curl로 호출하지 않는다
2. **CI 통과 전 머지 금지**: CI 체크가 하나라도 실패하면 머지 불가로 판정한다
3. **인라인 코멘트 심각도 필수**: 모든 인라인 코멘트에 `[Critical]`, `[Important]`, `[Minor]` 중 하나의 심각도 태그를 반드시 포함한다
4. **PR 본문 체크리스트 존중**: PR 본문의 체크리스트를 자의적으로 체크하지 않는다. 실제 검증 후에만 상태를 변경한다
5. **리뷰 판정 근거 명시**: APPROVE/REQUEST_CHANGES 판정 시 반드시 기술적 근거를 1-2문장으로 기술한다

## 연관 스킬

| 스킬 | 경로 | 관계 |
|------|------|------|
| pr-summary | `.claude/skills/pr-summary/SKILL.md` | PR 생성 시 제목/본문 생성 (작성자 관점) |
| github-integration | `.claude/skills/github-integration/SKILL.md` | gh CLI 기반 GitHub 범용 연동 |
| command-requesting-code-review | `.claude/skills/command-requesting-code-review/SKILL.md` | 코드 리뷰 요청 체크리스트 및 판정 기준 |

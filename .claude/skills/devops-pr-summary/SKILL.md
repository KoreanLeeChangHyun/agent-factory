---
name: devops-pr-summary
description: "Auto-generates PR title, summary, change list, and test plan by analyzing the current branch's PR diff. Uses dynamic context injection for real-time diff data. Use for PR authoring: (1) PR creation requests, (2) PR writing during REPORT stage, (3) before gh pr create execution. Triggers: 'PR', 'pull request', 'PR 요약', 'PR 생성'."
license: "Apache-2.0"
---

# PR Summary

현재 브랜치의 변경사항을 분석하여 GitHub PR 제목/본문을 자동 생성한다.

## 동적 컨텍스트 주입

이 스킬의 핵심은 동적 컨텍스트 주입으로 실시간 diff 데이터를 수집하는 것이다.

**PR diff 수집:**
```
!`git diff main...HEAD --stat`
```

**상세 diff 수집 (파일별):**
```
!`git diff main...HEAD`
```

**커밋 히스토리 수집:**
```
!`git log main...HEAD --oneline`
```

**기존 PR이 있을 경우:**
```
!`gh pr diff`
!`gh pr view --json title,body,labels`
```

참고: 베이스 브랜치가 `main`이 아닌 경우, 실제 브랜치명으로 대체한다.

## PR 제목 생성 규칙

### Conventional Commits 기반

커밋 히스토리를 분석하여 PR 제목을 생성한다:

| 패턴 | PR 제목 접두사 | 예시 |
|------|--------------|------|
| feat 커밋이 주요 | `feat:` | feat: 로그인 기능 추가 |
| fix 커밋이 주요 | `fix:` | fix: 세션 타임아웃 수정 |
| refactor 커밋이 주요 | `refactor:` | refactor: 인증 모듈 개선 |
| 혼합 커밋 | 가장 중요한 변경 기준 | feat: 로그인 기능 및 UI 개선 |

**제목 규칙:**
- 70자 이내
- 명령형 현재 시제 사용
- 한국어/영어 프로젝트 컨벤션 따름

### 단일 커밋인 경우

커밋 메시지를 그대로 PR 제목으로 사용한다.

## PR 본문 템플릿

```markdown
## Summary
<변경사항 1-3줄 요약>

## Changes
<변경 파일별 요약 목록>

### Added
- <새로 추가된 파일/기능>

### Modified
- <수정된 파일/기능>

### Removed
- <삭제된 파일/기능>

## Test plan
- [ ] <테스트 항목 1>
- [ ] <테스트 항목 2>

## Breaking changes
<해당 사항이 있을 때만 포함>
- <Breaking change 설명>

---
Generated with [Claude Code](https://claude.com/claude-code)
```

## 변경사항 분석 방법

### 1. 파일별 요약

`git diff --stat`에서 변경된 파일 목록을 수집하고, 각 파일의 변경 내용을 요약한다:

```
src/auth/login.ts    | 42 +++++++
src/auth/session.ts  | 15 ++--
tests/auth.test.ts   | 28 +++++++
```

위 diff를 다음과 같이 요약:
- `src/auth/login.ts`: 로그인 엔드포인트 신규 구현
- `src/auth/session.ts`: 세션 타임아웃 로직 수정
- `tests/auth.test.ts`: 인증 테스트 추가

### 2. 커밋 기반 그룹화

여러 커밋이 있을 경우, 커밋별로 변경사항을 그룹화한다:

```markdown
## Changes

### feat: 로그인 기능 추가 (abc1234)
- `src/auth/login.ts` 신규 생성
- `src/routes/index.ts`에 라우트 추가

### fix: 세션 관리 수정 (def5678)
- `src/auth/session.ts` 타임아웃 로직 수정
```

### 3. 대규모 PR 처리

변경 파일이 20개 이상일 경우:
- 디렉토리 단위로 그룹화하여 요약
- 핵심 변경사항만 상세 기술
- 전체 파일 목록은 접기(details)로 처리

```markdown
## Changes

### Core changes
- 인증 모듈 전면 재구현 (8개 파일)
- API 라우팅 구조 변경 (5개 파일)

<details>
<summary>All changed files (23)</summary>

- src/auth/login.ts
- src/auth/session.ts
- ...
</details>
```

## 테스트 계획 자동 생성

변경 내용을 분석하여 테스트 체크리스트를 자동 생성한다:

| 변경 유형 | 테스트 항목 |
|----------|-----------|
| 새 API 엔드포인트 | 엔드포인트 응답 확인, 인증 테스트, 에러 처리 |
| UI 컴포넌트 | 렌더링 확인, 사용자 인터랙션, 반응형 |
| 데이터 모델 변경 | 마이그레이션 확인, 기존 데이터 호환성 |
| 설정 변경 | 설정 적용 확인, 기본값 검증 |
| 리팩토링 | 기존 테스트 통과, 동작 변경 없음 |

## 워크플로우

```
1. 베이스 브랜치 확인
   - main/master 또는 사용자 지정 브랜치
      ↓
2. diff 수집 (동적 주입 또는 Bash)
   - git diff, git log, gh pr diff
      ↓
3. 변경사항 분석
   - 파일별 변경 요약
   - 커밋 메시지 분석
   - Breaking changes 감지
      ↓
4. PR 제목 생성
   - Conventional Commits 기반
   - 70자 이내
      ↓
5. PR 본문 생성
   - 템플릿에 맞춰 작성
   - 테스트 계획 포함
      ↓
6. 출력 또는 PR 생성
   - 콘솔 출력 (검토용)
   - gh pr create 실행 (직접 생성)
```

## 사용 예시

### PR 요약 생성

```
"현재 브랜치로 PR 요약 만들어줘"
→ diff 수집 → 분석 → PR 제목/본문 출력
```

### PR 직접 생성

```
"PR 생성해줘"
→ diff 수집 → 분석 → gh pr create --title "..." --body "..."
```

### REPORT 단계 통합

REPORT 단계에서 report/SKILL.md와 연동:
1. 작업 완료 후 변경사항 수집
2. PR 제목/본문 자동 생성
3. 사용자 검토 후 gh pr create 실행

## 참고

- devops-github 스킬과 보완 관계 (devops-github은 커밋/푸시, devops-pr-summary는 PR 생성)
- GitHub CLI(gh)가 설치되어 있어야 `gh pr` 관련 기능 사용 가능
- 동적 컨텍스트 주입 패턴은 Claude Code Skills 공식 문서 참고

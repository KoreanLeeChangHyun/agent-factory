---
name: workflow-system-report-output
description: "REPORT 단계 산출물(CHANGELOG, 릴리스 노트, PR 요약) 자동 생성 스킬. Git 커밋 히스토리와 브랜치 diff를 분석하여 구조화된 CHANGELOG, 릴리스 노트, PR 제목/본문을 생성한다. Triggers: 'changelog', 'release notes', '변경 이력', '릴리스 노트', 'PR', 'pull request', 'PR 요약', 'PR 생성'."
license: "Apache-2.0"
---

# Report Output Generator

REPORT 단계에서 사용하는 산출물 생성 스킬. CHANGELOG/릴리스 노트와 PR 요약을 자동 생성한다.

## 1. 동적 컨텍스트 주입

Git 로그와 diff 데이터를 실시간으로 수집하는 패턴.

**커밋 히스토리 수집:**
```
!`git log --oneline -20`
!`git log --pretty=format:"%h|%s|%an|%ad" --date=short -30`
```

**특정 범위의 커밋:**
```
!`git log --oneline v1.0.0..HEAD`
!`git log --oneline --since="2026-02-01"`
```

**PR diff 수집:**
```
!`git diff main...HEAD --stat`
!`git diff main...HEAD`
!`git log main...HEAD --oneline`
```

**기존 PR이 있을 경우:**
```
!`gh pr diff`
!`gh pr view --json title,body,labels`
```

참고: 베이스 브랜치가 `main`이 아닌 경우, 실제 브랜치명으로 대체한다.

## 2. Conventional Commits 패턴 인식

커밋 메시지에서 다음 접두사를 인식하여 분류한다:

| 접두사 | CHANGELOG 섹션 | 설명 |
|--------|---------------|------|
| `feat:` | Added | 새 기능 |
| `fix:` | Fixed | 버그 수정 |
| `refactor:` | Changed | 코드 개선 |
| `docs:` | Documentation | 문서 변경 |
| `chore:` | Maintenance | 유지보수 |
| `perf:` | Performance | 성능 개선 |
| `test:` | Tests | 테스트 추가/수정 |
| `style:` | Style | 코드 스타일 변경 |
| `ci:` | CI/CD | CI/CD 변경 |
| `build:` | Build | 빌드 시스템 변경 |

**Breaking Changes 감지:**
- `BREAKING CHANGE:` 또는 `!` 접미사 포함 시 별도 섹션으로 하이라이트
- 예: `feat!: 인증 API 엔드포인트 변경`

**Conventional Commits 미사용 프로젝트:**
- 키워드 기반 분류: "추가", "수정", "삭제", "리팩토링", "add", "fix", "remove", "update" 등

## 3. CHANGELOG 생성

### CHANGELOG.md 포맷

```markdown
# Changelog

## [v1.2.0] - 2026-02-05

### BREAKING CHANGES
- 인증 API 엔드포인트 `/auth/login` -> `/api/v2/auth/login` 변경

### Added
- 로그인 기능 추가 (#feat)
- 대시보드 위젯 추가

### Fixed
- 회원가입 이메일 검증 오류 수정

### Changed
- 인증 모듈 리팩토링

### Documentation
- API 문서 업데이트
```

### 날짜별 그룹화 포맷 (버전 태그 미사용 프로젝트)

```markdown
# Changelog

## 2026-02-05

### Added
- feat: 로그인 기능 추가 (5e301f5)

### Changed
- refactor: 워크플로우 저장 경로 접두사 제거 (c479e27)
```

### CLAUDE.md Recent Changes 포맷

```markdown
- **2026-02-05 18:00**: <작업 제목> (작업 ID: <workId>)
  - <주요 변경 내용 1>
  - <주요 변경 내용 2>
  - 보고서: `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/report.md`
```

### CHANGELOG 생성 워크플로우

```
1. Git 로그 수집 (동적 주입 또는 Bash)
2. 커밋 메시지 파싱 (Conventional Commits 접두사 인식)
3. 분류 및 그룹화 (유형별, 버전/날짜별, Breaking Changes 분리)
4. 마크다운 생성 (템플릿 + 커밋 해시 참조)
5. 출력 (CHANGELOG.md 생성/갱신 또는 CLAUDE.md Recent Changes 갱신)
```

## 4. PR Summary 생성

### PR 제목 생성 규칙

| 패턴 | PR 제목 접두사 | 예시 |
|------|--------------|------|
| feat 커밋이 주요 | `feat:` | feat: 로그인 기능 추가 |
| fix 커밋이 주요 | `fix:` | fix: 세션 타임아웃 수정 |
| refactor 커밋이 주요 | `refactor:` | refactor: 인증 모듈 개선 |
| 혼합 커밋 | 가장 중요한 변경 기준 | feat: 로그인 기능 및 UI 개선 |
| 단일 커밋 | 커밋 메시지 그대로 사용 | - |

- 70자 이내, 명령형 현재 시제, 프로젝트 컨벤션 따름

### PR 본문 템플릿

```markdown
## Summary
<변경사항 1-3줄 요약>

## Changes

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

---
Generated with [Claude Code](https://claude.com/claude-code)
```

### 변경사항 분석

**파일별 요약:** `git diff --stat`에서 변경 파일 목록을 수집하고 각 파일의 변경 내용을 요약한다.

**커밋 기반 그룹화:** 여러 커밋이 있을 경우 커밋별로 변경사항을 그룹화한다.

**대규모 PR 처리 (20개+ 파일):**
- 디렉토리 단위로 그룹화하여 요약
- 핵심 변경사항만 상세 기술, 전체 파일 목록은 `<details>`로 처리

### 테스트 계획 자동 생성

| 변경 유형 | 테스트 항목 |
|----------|-----------|
| 새 API 엔드포인트 | 엔드포인트 응답 확인, 인증 테스트, 에러 처리 |
| UI 컴포넌트 | 렌더링 확인, 사용자 인터랙션, 반응형 |
| 데이터 모델 변경 | 마이그레이션 확인, 기존 데이터 호환성 |
| 설정 변경 | 설정 적용 확인, 기본값 검증 |
| 리팩토링 | 기존 테스트 통과, 동작 변경 없음 |

### PR Summary 생성 워크플로우

```
1. 베이스 브랜치 확인 (main/master 또는 사용자 지정)
2. diff 수집 (git diff, git log, gh pr diff)
3. 변경사항 분석 (파일별 요약, 커밋 분석, Breaking changes 감지)
4. PR 제목 생성 (Conventional Commits 기반, 70자 이내)
5. PR 본문 생성 (템플릿 + 테스트 계획)
6. 출력 또는 PR 생성 (콘솔 출력 또는 gh pr create 실행)
```

## 5. 워크플로우 통합 (REPORT 단계)

이 스킬은 REPORT 단계에서 `workflow-agent-reporter`와 연동하여 동작한다.

### REPORT 단계 흐름

```
작업 완료
   ↓
1. 해당 작업 관련 커밋 수집
2. 커밋 메시지를 분석하여 변경 사항 요약
3. CHANGELOG / CLAUDE.md Recent Changes 갱신
4. PR 제목/본문 자동 생성
5. 사용자 검토 후 gh pr create 실행
```

### 사용 예시

```
"최근 커밋 기반으로 CHANGELOG.md를 생성해줘"
"v1.0.0부터 현재까지의 릴리스 노트를 작성해줘"
"현재 브랜치로 PR 요약 만들어줘"
"PR 생성해줘"
```

## 참고

- Conventional Commits: https://www.conventionalcommits.org/
- GitHub CLI(gh)가 설치되어 있어야 `gh pr` 관련 기능 사용 가능
- 동적 컨텍스트 주입 패턴은 Claude Code Skills 공식 문서 참고

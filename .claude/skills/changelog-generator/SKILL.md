---
name: changelog-generator
description: "Auto-generates CHANGELOG and release notes by analyzing Git commit history. Recognizes Conventional Commits patterns and outputs in markdown format. Use for change documentation: (1) REPORT stage change summary, (2) CLAUDE.md Recent Changes update, (3) release notes authoring. Triggers: 'changelog', 'release notes', '변경 이력', '릴리스 노트'."
license: "Apache-2.0"
---

# Changelog Generator

Git 커밋 히스토리를 분석하여 구조화된 CHANGELOG / 릴리스 노트를 자동 생성한다.

## 동적 컨텍스트 주입

이 스킬은 동적 컨텍스트 주입을 활용하여 최신 Git 로그를 자동으로 수집한다.

**SKILL.md 또는 커맨드 파일에서 사용하는 패턴:**
```
최근 커밋 내역:
!`git log --oneline -20`
```

**더 상세한 정보가 필요할 때:**
```
!`git log --pretty=format:"%h|%s|%an|%ad" --date=short -30`
```

**특정 범위의 커밋:**
```
!`git log --oneline v1.0.0..HEAD`
!`git log --oneline --since="2026-02-01"`
```

## Conventional Commits 패턴 인식

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
- 커밋 메시지에 `BREAKING CHANGE:` 또는 `!` 접미사 포함 시 별도 섹션으로 하이라이트
- 예: `feat!: 인증 API 엔드포인트 변경`

**Conventional Commits 미사용 프로젝트:**
- 커밋 메시지 내용을 분석하여 유형을 추론
- 키워드 기반 분류: "추가", "수정", "삭제", "리팩토링", "add", "fix", "remove", "update" 등

## 출력 포맷

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
- 세션 타임아웃 버그 수정

### Changed
- 인증 모듈 리팩토링
- API 응답 포맷 통일

### Documentation
- API 문서 업데이트
- README 설치 가이드 추가

---

## [v1.1.0] - 2026-01-20

### Added
- ...
```

### CLAUDE.md Recent Changes 포맷

REPORT 단계에서 CLAUDE.md의 Recent Changes 섹션 갱신 시 사용:

```markdown
- **2026-02-05 18:00**: <작업 제목> (작업 ID: <workId>)
  - <주요 변경 내용 1>
  - <주요 변경 내용 2>
  - 보고서: `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/report.md`
```

### 날짜별 그룹화 포맷 (버전 태그 미사용 프로젝트)

```markdown
# Changelog

## 2026-02-05

### Added
- feat: 로그인 기능 추가 (5e301f5)
- feat: StatusLine 설정 스킬 추가 (209b7b5)

### Changed
- refactor: 워크플로우 저장 경로 접두사 제거 (c479e27)

---

## 2026-02-04
...
```

## 워크플로우

```
1. Git 로그 수집 (동적 주입 또는 Bash)
   - git log 명령어로 커밋 히스토리 수집
   - 범위: 마지막 태그부터 HEAD, 또는 지정 기간
      ↓
2. 커밋 메시지 파싱
   - Conventional Commits 접두사 인식
   - 커밋 해시, 저자, 날짜 추출
      ↓
3. 분류 및 그룹화
   - 유형별 분류 (feat/fix/refactor/...)
   - 버전별 또는 날짜별 그룹화
   - Breaking Changes 별도 분리
      ↓
4. 마크다운 생성
   - 템플릿에 맞춰 구조화된 CHANGELOG 생성
   - 각 항목에 커밋 해시 참조 포함
      ↓
5. 출력
   - CHANGELOG.md 파일 생성/갱신
   - 또는 CLAUDE.md Recent Changes 섹션 갱신
```

## 사용 예시

### 전체 CHANGELOG 생성

```
"최근 커밋 기반으로 CHANGELOG.md를 생성해줘"
→ git log 수집 → Conventional Commits 파싱 → CHANGELOG.md 생성
```

### REPORT 단계 통합

REPORT 단계에서 report/SKILL.md와 연동:
1. 작업 완료 후 해당 작업 관련 커밋 수집
2. 커밋 메시지를 분석하여 변경 사항 요약
3. CLAUDE.md Recent Changes 섹션에 항목 추가

### 릴리스 노트 생성

```
"v1.0.0부터 현재까지의 릴리스 노트를 작성해줘"
→ git log v1.0.0..HEAD → 분류 → 릴리스 노트 생성
```

## 참고

- report/SKILL.md와 연동하여 REPORT 단계에서 자동 실행 가능
- Conventional Commits: https://www.conventionalcommits.org/
- 동적 컨텍스트 주입 패턴은 Claude Code Skills 공식 문서 참고

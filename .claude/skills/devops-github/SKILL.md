---
name: devops-github
description: "gh CLI-based GitHub integration skill. Performs commit/push, PR creation/management, issue viewing/creation, branch management, and other GitHub workflows. Use for GitHub operations: pushing work results, PR creation, issue management, branch management. Triggers: 'github', 'push', 'PR', 'pull request', '푸시', '커밋', '이슈'."
license: "Apache-2.0"
---

# GitHub 연동 가이드

## 설명
gh CLI를 사용하여 작업 결과를 GitHub에 커밋/푸시하고, PR/이슈를 관리하는 방법을 안내합니다.

## 사용 시기
- 작업 결과를 GitHub에 커밋/푸시할 때
- PR(Pull Request)을 생성하거나 관리할 때
- GitHub 이슈를 조회하거나 생성할 때
- 브랜치를 생성하거나 관리할 때

---

## 기본 Git 워크플로우

### 커밋 및 푸시
```bash
# 변경사항 확인
git status
git diff

# 스테이징 및 커밋
git add <파일명>
git commit -m "feat: 작업 내용 요약"

# 푸시
git push origin <브랜치명>
```

### 커밋 메시지 형식 (Conventional Commits)
```
<type>: <description>

[optional body]

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**타입:**
| 타입 | 설명 |
|------|------|
| feat | 새 기능 |
| fix | 버그 수정 |
| refactor | 코드 리팩토링 |
| docs | 문서 변경 |
| test | 테스트 추가/수정 |
| chore | 빌드/설정 변경 |

## gh CLI 사용법

### PR 관리
```bash
# PR 생성
gh pr create --title "PR 제목" --body "설명"

# PR 목록 조회
gh pr list

# PR 상세 조회
gh pr view <PR번호>

# PR 체크아웃
gh pr checkout <PR번호>

# PR 머지
gh pr merge <PR번호>
```

### 이슈 관리
```bash
# 이슈 목록
gh issue list

# 이슈 생성
gh issue create --title "이슈 제목" --body "설명"

# 이슈 조회
gh issue view <이슈번호>
```

### 저장소 정보
```bash
# 저장소 상태
gh repo view

# 릴리스 목록
gh release list
```

## 브랜치 전략

### 기본 브랜치 관리
```bash
# 새 브랜치 생성
git checkout -b feature/<기능명>

# 원격 브랜치 추적 설정
git push -u origin feature/<기능명>

# 메인 브랜치 최신 상태 반영
git fetch origin
git rebase origin/main
```

## 주의사항
- Git 저장소 초기화 및 원격 저장소 연결 필요
- GitHub 인증 설정 필요 (SSH 키 또는 gh auth login)
- force push는 공유 브랜치에서 사용하지 않음
- 커밋 전 민감 정보(.env, credentials) 포함 여부 확인

---

## 참고
- `.claude/settings.json` - 프로젝트 설정 확인
- `git:commit` 명령어 - 프로젝트 커밋 워크플로우
- `devops-pr-summary` 스킬 - PR 요약 자동 생성

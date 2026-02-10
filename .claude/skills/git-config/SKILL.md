---
name: git-config
description: ".claude.env 파일에서 Git 설정을 읽어 git config를 자동 설정하는 스킬. Use for Git configuration tasks: (1) .claude.env에서 사용자명/이메일 읽어 git config 설정, (2) SSH 키 경로 설정, (3) Git 환경 초기화. 트리거: 'git config', 'git 설정', 'Git 사용자 설정', 'git:config'."
---

# Git Config 스킬

`.claude.env` 파일에서 Git 설정 정보를 읽어 `git config`를 자동으로 설정합니다.

## 지원 환경변수

| 변수명 | 필수 | 설명 | 예시 |
|--------|------|------|------|
| CLAUDE_CODE_GIT_USER_NAME | O | Git 사용자 이름 | `Changhyun Lee` |
| CLAUDE_CODE_GIT_USER_EMAIL | O | Git 이메일 | `lwrc01@kusrc.co.kr` |
| CLAUDE_CODE_GITHUB_USERNAME | X | GitHub 사용자명 (현재 미사용) | `lwrc01_kusrc` |
| CLAUDE_CODE_SSH_KEY_GITHUB | X | GitHub SSH 키 경로 | `$HOME/.ssh/id_ed25519` |
| CLAUDE_CODE_SSH_CONFIG | X | SSH config 경로 | `~/.ssh/config` |

## .env 파일 형식

```bash
# .claude.env (표준 dotenv 형식: KEY=value)
CLAUDE_CODE_GIT_USER_NAME=Changhyun Lee
CLAUDE_CODE_GIT_USER_EMAIL=lwrc01@kusrc.co.kr
# CLAUDE_CODE_GITHUB_USERNAME=lwrc01_kusrc  # 현재 미사용 - 향후 GitHub API 연동 예정
CLAUDE_CODE_SSH_KEY_GITHUB=$HOME/.ssh/key-gen/github/git/id_ed25519
# CLAUDE_CODE_SSH_CONFIG=~/.ssh/config
```

> **참고**: 값에 따옴표(`"value"`, `'value'`)를 사용해도 자동으로 제거됩니다. `$HOME` 및 `~` 경로도 자동 확장됩니다.

## 설정 범위

| 옵션 | 설명 | git config 플래그 |
|------|------|------------------|
| `--global` | 전역 설정 (~/.gitconfig) | `git config --global` |
| `--local` | 로컬 설정 (.git/config) | `git config --local` |

기본값: `--global`

## 실행 절차

### 1. 공통 유틸리티 로드 및 환경변수 파싱

```bash
# 경로 설정 (PROJECT_ROOT 기반 절대경로)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.claude.env"

# 파일 존재 확인
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE 파일이 존재하지 않습니다."
    exit 1
fi

# 공통 env 파싱 유틸리티 로드 (_env-utils.sh)
source "$SCRIPT_DIR/_env-utils.sh"

# 환경변수 파싱 (read_env: 따옴표 제거, $HOME/~ 확장, 중복 키 head -1 방어 포함)
GIT_USER_NAME=$(read_env "CLAUDE_CODE_GIT_USER_NAME")
GIT_USER_EMAIL=$(read_env "CLAUDE_CODE_GIT_USER_EMAIL")
# 현재 미사용 - 향후 GitHub API 연동 예정
GITHUB_USERNAME=$(read_env "CLAUDE_CODE_GITHUB_USERNAME")
SSH_KEY_GITHUB=$(read_env "CLAUDE_CODE_SSH_KEY_GITHUB")
```

### 2. 필수 필드 검증

```bash
# 필수 필드 확인
if [ -z "$GIT_USER_NAME" ]; then
    echo "ERROR: CLAUDE_CODE_GIT_USER_NAME이 .env에 설정되지 않았습니다."
    exit 1
fi

if [ -z "$GIT_USER_EMAIL" ]; then
    echo "ERROR: CLAUDE_CODE_GIT_USER_EMAIL이 .env에 설정되지 않았습니다."
    exit 1
fi
```

### 3. Before 상태 확인

```bash
echo "=== Before ==="
echo "user.name: $(git config --global user.name 2>/dev/null || echo '(미설정)')"
echo "user.email: $(git config --global user.email 2>/dev/null || echo '(미설정)')"
echo "core.sshCommand: $(git config --global core.sshCommand 2>/dev/null || echo '(미설정)')"
```

### 4. Git Config 설정

```bash
# 범위 설정 (기본: --global)
SCOPE="${1:---global}"

# user.name 설정
git config $SCOPE user.name "$GIT_USER_NAME"

# user.email 설정
git config $SCOPE user.email "$GIT_USER_EMAIL"
```

### 5. SSH 키 설정 (선택)

```bash
# SSH 키가 설정되어 있고, 파일이 존재하는 경우
# 참고: read_env에서 $HOME/~ 경로가 이미 확장된 상태
if [ -n "$SSH_KEY_GITHUB" ]; then
    if [ -f "$SSH_KEY_GITHUB" ]; then
        # 경로에 공백이 있을 수 있으므로 내부 따옴표로 보호
        git config $SCOPE core.sshCommand "ssh -i \"$SSH_KEY_GITHUB\" -o IdentitiesOnly=yes"
        echo "SSH 키 설정 완료: $SSH_KEY_GITHUB"
    else
        echo "WARNING: SSH 키 파일이 존재하지 않습니다: $SSH_KEY_GITHUB"
    fi
fi
```

### 6. After 상태 확인

```bash
echo "=== After ==="
echo "user.name: $(git config $SCOPE user.name)"
echo "user.email: $(git config $SCOPE user.email)"
echo "core.sshCommand: $(git config $SCOPE core.sshCommand 2>/dev/null || echo '(미설정)')"
```

### 7. Before/After 비교 출력

```
| 설정 | Before | After |
|------|--------|-------|
| user.name | (미설정) | Changhyun Lee |
| user.email | (미설정) | lwrc01@kusrc.co.kr |
| core.sshCommand | (미설정) | ssh -i /path/to/key -o IdentitiesOnly=yes |
```

## 오류 처리

| 오류 | 원인 | 대응 |
|------|------|------|
| `.env 파일 미존재` | `.claude.env` 파일 없음 | 에러 메시지 출력 후 중단 |
| `CLAUDE_CODE_GIT_USER_NAME 미설정` | 필수 필드 누락 | 에러 메시지 출력 후 중단 |
| `CLAUDE_CODE_GIT_USER_EMAIL 미설정` | 필수 필드 누락 | 에러 메시지 출력 후 중단 |
| `SSH 키 파일 미존재` | 경로 오류 | WARNING 출력, SSH 설정 스킵 |

## 전체 스크립트 예시

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.claude.env"
SCOPE="${1:---global}"

# 1. 파일 존재 확인
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE 파일이 존재하지 않습니다."
    exit 1
fi

# 2. 공통 유틸리티 로드 + 환경변수 파싱
source "$SCRIPT_DIR/_env-utils.sh"

GIT_USER_NAME=$(read_env "CLAUDE_CODE_GIT_USER_NAME")
GIT_USER_EMAIL=$(read_env "CLAUDE_CODE_GIT_USER_EMAIL")
SSH_KEY_GITHUB=$(read_env "CLAUDE_CODE_SSH_KEY_GITHUB")

# 3. 필수 필드 검증
if [ -z "$GIT_USER_NAME" ]; then
    echo "ERROR: CLAUDE_CODE_GIT_USER_NAME이 설정되지 않았습니다."
    exit 1
fi

if [ -z "$GIT_USER_EMAIL" ]; then
    echo "ERROR: CLAUDE_CODE_GIT_USER_EMAIL이 설정되지 않았습니다."
    exit 1
fi

# 4. Before 상태 저장
BEFORE_NAME=$(git config $SCOPE user.name 2>/dev/null || echo "(미설정)")
BEFORE_EMAIL=$(git config $SCOPE user.email 2>/dev/null || echo "(미설정)")
BEFORE_SSH=$(git config $SCOPE core.sshCommand 2>/dev/null || echo "(미설정)")

# 5. 설정 적용
git config $SCOPE user.name "$GIT_USER_NAME"
git config $SCOPE user.email "$GIT_USER_EMAIL"

# 6. SSH 설정 (선택) - 경로 공백 보호를 위한 내부 따옴표 포함
if [ -n "$SSH_KEY_GITHUB" ]; then
    if [ -f "$SSH_KEY_GITHUB" ]; then
        git config $SCOPE core.sshCommand "ssh -i \"$SSH_KEY_GITHUB\" -o IdentitiesOnly=yes"
    else
        echo "WARNING: SSH 키 파일이 존재하지 않습니다: $SSH_KEY_GITHUB"
    fi
fi

# 7. After 상태
AFTER_NAME=$(git config $SCOPE user.name)
AFTER_EMAIL=$(git config $SCOPE user.email)
AFTER_SSH=$(git config $SCOPE core.sshCommand 2>/dev/null || echo "(미설정)")

# 8. 비교 출력
echo ""
echo "| 설정 | Before | After |"
echo "|------|--------|-------|"
echo "| user.name | $BEFORE_NAME | $AFTER_NAME |"
echo "| user.email | $BEFORE_EMAIL | $AFTER_EMAIL |"
echo "| core.sshCommand | $BEFORE_SSH | $AFTER_SSH |"
echo ""
echo "Git 설정이 완료되었습니다. ($SCOPE)"
```

## 검증

설정 완료 후 확인:

```bash
# 전역 설정 확인
git config --global --list | grep -E "user\.|core\.sshCommand"

# GitHub SSH 연결 테스트
ssh -T git@github.com
```

## 공통 유틸리티 (`_env-utils.sh`)

`.claude.env` 파싱 로직은 `_env-utils.sh`에 통합되어 있으며, 다음 3개 스크립트에서 공유합니다:

- `git-config.sh` - Git config 자동 설정
- `init-claude.sh` - Claude Code 사용자 환경 초기화
- `slack-common.sh` - Slack 공용 함수 라이브러리

`read_env` 함수는 다음을 자동 처리합니다:
- 중복 키 방어: `head -1`로 첫 번째 매칭만 사용
- 따옴표 제거: 앞뒤 큰따옴표/작은따옴표 제거
- `$HOME` 확장: `$HOME`을 실제 홈 디렉토리로 치환
- `~` 확장: 선두 `~`를 실제 홈 디렉토리로 치환

## 참고

- 이 스킬은 `git:config` 명령어에서 호출됩니다.
- `.env` 파일 형식은 표준 dotenv (KEY=value)입니다.
- SSH 설정은 `core.sshCommand`를 사용하여 특정 키를 지정합니다.
- SSH 키 경로에 공백이 포함될 수 있으므로 내부 따옴표로 보호합니다.

---
description: .claude.env에서 Git 설정을 읽어 git config를 자동 설정합니다.
argument-hint: "[--global | --local]"
---

# Git Config

`.claude.env` 파일에서 Git 설정 정보를 읽어 `git config`를 자동으로 설정합니다.

## 입력: $ARGUMENTS

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `--global` | 전역 설정 (~/.gitconfig) | O (기본값) |
| `--local` | 로컬 설정 (.git/config) | |

## 스크립트

`.claude/scripts/init/git_config.py` - 옵션: `[--global|--local]`

## 오케스트레이션 흐름

이 명령어는 대화형 부분이 없으므로 스크립트를 직접 실행하고 결과만 출력합니다.

### Step 1. Git Config 설정

$ARGUMENTS에 따라 Bash 도구로 실행:

```bash
python3 .claude/scripts/init/git_config.py $ARGUMENTS
```

$ARGUMENTS가 없으면 기본값 `--global` 적용:

```bash
python3 .claude/scripts/init/git_config.py --global
```

### Step 2. 결과 출력

스크립트의 stdout 출력을 그대로 사용자에게 표시합니다.

스크립트가 다음 내용을 자동 처리합니다:
- `.claude.env` 파일에서 환경변수 로드
- 필수 환경변수 검증 (CLAUDE_CODE_GIT_USER_NAME, CLAUDE_CODE_GIT_USER_EMAIL)
- Before 상태 수집
- git config 설정 적용
- After 상태 수집
- Before/After 비교 테이블 출력

---

## 사용 예시

```bash
# 전역 설정 (기본값)
git:config

# 전역 설정 (명시적)
git:config --global

# 로컬 설정 (현재 저장소만)
git:config --local
```

## 오류 처리

| 오류 상황 | 대응 |
|----------|------|
| `.claude.env` 파일 없음 | 에러 메시지 출력 후 중단 |
| `CLAUDE_CODE_GIT_USER_NAME` 미설정 | 에러 메시지 출력 후 중단 |
| `CLAUDE_CODE_GIT_USER_EMAIL` 미설정 | 에러 메시지 출력 후 중단 |
| SSH 키 파일 없음 | WARNING 출력, SSH 설정 스킵 |

## 주의사항

- `--global` 설정은 모든 Git 저장소에 적용됩니다.
- `--local` 설정은 현재 저장소 내에서만 유효합니다.
- 기존 설정이 있으면 덮어씌워집니다. Before 출력으로 백업 가능합니다.
- SSH 키 설정은 `core.sshCommand`를 사용하므로 기존 SSH 설정과 충돌할 수 있습니다.

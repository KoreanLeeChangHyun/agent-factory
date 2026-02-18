---
name: dangerous-command-guard
description: "Safety guard that blocks dangerous commands (rm -rf, git reset --hard, git push --force, etc.) via PreToolUse hooks. Use for safety enforcement: (1) pre-blocking dangerous system/Git commands, (2) preventing data loss and repository corruption, (3) hook-based automated safety verification. Triggers: 'rm -rf', 'git reset --hard', 'git push --force', '위험 명령어', 'dangerous command'."
license: "Apache-2.0"
---

# Dangerous Command Guard

위험한 시스템/Git 명령어를 PreToolUse Hook으로 감지하고 차단하는 안전 가드 스킬입니다.

## 목적

- 실수로 실행되는 위험한 명령어를 사전에 차단
- 데이터 손실, 저장소 손상, 보안 위험을 방지
- 차단 시 안전한 대안을 제시하여 작업 지속 가능

## 동작 방식

### Hook 이벤트

- **이벤트**: `PreToolUse`
- **매처**: `Bash`
- **스크립트**: `.claude/hooks/pre-tool-use/dangerous-command-guard.py` (thin wrapper -> `.claude/scripts/guards/dangerous_command_guard.py`)

### 차단 대상 패턴

| 카테고리 | 패턴 | 위험도 | 설명 |
|----------|------|--------|------|
| 파일 삭제 | `rm -rf /`, `rm -rf ~`, `rm -rf .` | Critical | 루트/홈/현재 디렉토리 전체 삭제 |
| 파일 삭제 | `rm -rf *` (루트 경로) | Critical | 와일드카드 전체 삭제 |
| Git 리셋 | `git reset --hard` | High | 커밋되지 않은 변경사항 전체 삭제 |
| Git 푸시 | `git push --force`, `git push -f` | High | 원격 히스토리 덮어쓰기 |
| Git 클린 | `git clean -f`, `git clean -fd` | High | 추적되지 않는 파일 전체 삭제 |
| Git 브랜치 | `git branch -D` (main/master) | High | 주요 브랜치 강제 삭제 |
| Git 체크아웃 | `git checkout .`, `git restore .` | High | 모든 변경사항 되돌리기 |
| DB 삭제 | `DROP TABLE`, `DROP DATABASE` | Critical | 데이터베이스/테이블 삭제 |
| 권한 변경 | `chmod 777` | Medium | 과도한 권한 부여 |
| 디스크 | `mkfs`, `dd if=` | Critical | 디스크 포맷/덮어쓰기 |

### 화이트리스트

다음 경로/패턴은 차단하지 않습니다:
- `/tmp/` 하위 디렉토리의 `rm -rf` (임시 파일 정리)
- `.workflow/` 하위의 `rm -rf` (워크플로우 정리)
- `git push --force-with-lease` (안전한 force push)

### 안전한 대안 제시

차단 시 다음과 같은 대안을 제시합니다:

| 위험 명령어 | 안전한 대안 |
|------------|-----------|
| `rm -rf /path` | `rm -ri /path` (대화형 삭제) 또는 파일 목록 먼저 확인 |
| `git reset --hard` | `git stash` (변경사항 임시 저장) |
| `git push --force` | `git push --force-with-lease` (안전한 force push) |
| `git clean -f` | `git clean -n` (드라이런으로 삭제 대상 확인) |
| `git checkout .` | `git stash` (변경사항 임시 저장) |
| `chmod 777` | `chmod 755` 또는 필요한 최소 권한만 부여 |

## Hook 스크립트

**경로**: `.claude/hooks/pre-tool-use/dangerous-command-guard.py` (thin wrapper -> `.claude/scripts/guards/dangerous_command_guard.py`)

### 입력 (stdin JSON)

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /some/path"
  }
}
```

### 출력

**차단 시:**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "위험한 명령어가 감지되었습니다: rm -rf. 안전한 대안: rm -ri 또는 파일 목록을 먼저 확인하세요."
  }
}
```

**통과 시:**
빈 출력 (stdout에 아무것도 출력하지 않음)

## settings.json 등록

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/pre-tool-use/dangerous-command-guard.py",
            "statusMessage": "위험 명령어 검사 중..."
          }
        ]
      }
    ]
  }
}
```

## 적용 단계

- **범용**: 모든 워크플로우 단계에서 Bash 도구 사용 시 자동 실행

## zsh Read-Only 변수 호환성

현재 셸이 **zsh**인 환경에서, Claude Code의 Bash 도구는 zsh로 명령을 실행합니다. zsh에는 대입이 불가능한 read-only 내장 변수가 존재하며, LLM이 생성한 bash 코드에서 이 변수명을 사용하면 `read-only variable` 에러가 발생합니다.

### 금지 변수명

| 변수명 | zsh에서의 역할 | 위험도 |
|--------|---------------|--------|
| `status` | `$?`(직전 명령 종료 코드)의 별칭 | High |
| `pipestatus` | 파이프라인 종료 코드 배열 | High |
| `ERRNO` | 시스템 에러 번호 | High |
| `ZSH_SUBSHELL` | 서브셸 깊이 | Medium |
| `HISTCMD` | 현재 히스토리 이벤트 번호 | Medium |

### 안전한 대체 변수명

| 금지 변수명 | 안전한 대체 변수명 |
|------------|-------------------|
| `status` | `file_status`, `cmd_status`, `result_status`, `exit_code` |
| `pipestatus` | `pipe_results`, `pipe_exit_codes` |
| `ERRNO` | `err_code`, `error_num` |
| `ZSH_SUBSHELL` | `subshell_depth`, `shell_level` |
| `HISTCMD` | `hist_num`, `history_id` |

### 규칙

Bash 도구에서 for 루프, 임시 변수, 스크립트 생성 시 위 변수명을 **절대 사용하지 않습니다**.

### 예시

```bash
# 잘못된 예시 (zsh에서 에러 발생)
for f in file1 file2; do
  status=$(git diff --name-only "$f")  # read-only variable: status
done

# 올바른 예시
for f in file1 file2; do
  diff_result=$(git diff --name-only "$f")
  file_status=$(git status --short "$f")
done
```

```bash
# 잘못된 예시
pipestatus=(0 1 0)  # read-only variable: pipestatus

# 올바른 예시
pipe_results=(0 1 0)
```

## 참고

- Hook 스크립트: `.claude/hooks/pre-tool-use/dangerous-command-guard.py` (thin wrapper -> `.claude/scripts/guards/dangerous_command_guard.py`)
- 설정 파일: `.claude/settings.json`
- 관련 스킬: `safety-fallback` (에이전트 안전장치 가이드)

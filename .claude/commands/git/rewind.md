---
description: 특정 커밋 시점으로 되돌립니다.
argument-hint: "<커밋해시 또는 HEAD~N> [--mode soft|mixed|hard|revert]"
---

# Git Rewind

특정 커밋 시점으로 되돌립니다. 변경사항 보존 방식을 선택할 수 있습니다.

## 입력: $ARGUMENTS

| 인자 | 설명 | 필수 | 기본값 |
|------|------|------|--------|
| `<target>` | 되돌릴 커밋 해시 또는 `HEAD~N` | 아니오 (없으면 선택 UI) | - |
| `--mode <mode>` | 되돌리기 방식 | 아니오 | `soft` |

### 모드 설명

| 모드 | 명령어 | 효과 |
|------|--------|------|
| `soft` | `git reset --soft <target>` | 변경사항을 staging area에 유지 |
| `mixed` | `git reset <target>` | 변경사항을 working directory에 유지 (unstaged) |
| `hard` | `git stash` + `git reset --hard <target>` | 변경사항 완전 삭제 (stash로 백업) |
| `revert` | `git revert --no-commit <target>..HEAD` + `git commit` | 새 커밋으로 되돌리기 (공유 브랜치에 안전) |

## 절차

### 1. Git 저장소 확인

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

Git 저장소가 아닌 경우: "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료.

### 2. 대상 커밋 결정

**인자가 없는 경우:**

최근 커밋 목록을 표시하고 사용자에게 선택을 요청합니다:

```bash
git log --oneline --graph --decorate -15
```

AskUserQuestion으로 되돌릴 커밋을 물어봅니다:

```
AskUserQuestion(
  questions: [{
    question: "되돌릴 커밋 해시 또는 HEAD~N을 입력해 주세요. (예: abc1234, HEAD~3)",
    header: "되돌릴 커밋 선택"
  }]
)
```

**인자가 있는 경우:**

`$ARGUMENTS`에서 대상 커밋과 모드를 파싱합니다:
- 첫 번째 인자 (해시 또는 `HEAD~N`): 대상 커밋
- `--mode` 뒤의 값: 모드 (없으면 `soft`)

대상 커밋이 유효한지 확인합니다:

```bash
git rev-parse --verify <target> 2>/dev/null
```

유효하지 않은 경우: "유효하지 않은 커밋입니다: <target>" 출력 후 종료.

### 3. 되돌려질 커밋 목록 표시

되돌려질 커밋들의 목록을 보여줍니다:

```bash
git log --oneline <target>..HEAD
```

되돌려질 커밋이 없는 경우 (HEAD가 이미 해당 커밋이거나 그 이전인 경우): "이미 해당 커밋 시점이거나 되돌릴 커밋이 없습니다." 출력 후 종료.

### 4. 사용자 승인 (AskUserQuestion 필수)

되돌려질 커밋 목록과 모드를 보여주고 **반드시 AskUserQuestion 도구를 사용하여** 사용자 승인을 받습니다:

```
## 되돌리기 계획

**대상 커밋**: <target> (<커밋 메시지>)
**되돌려질 커밋**: N개
**모드**: <mode> - <모드 설명>

<되돌려질 커밋 목록>
```

```
AskUserQuestion(
  questions: [{
    question: "위 내용으로 되돌리기를 진행하시겠습니까?",
    header: "되돌리기 승인",
    options: [
      { label: "승인 (Recommended)", description: "<모드> 모드로 되돌리기를 실행합니다" },
      { label: "모드 변경", description: "다른 모드를 선택합니다 (soft/mixed/hard/revert)" },
      { label: "취소", description: "되돌리기를 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **승인** | Step 5로 진행 (되돌리기 실행) |
| **모드 변경** | 사용자 입력으로 받은 모드를 반영하여 Step 4 재실행 |
| **취소** | "되돌리기가 취소되었습니다." 출력 후 종료 |

### 5. 되돌리기 실행

사용자 승인 후에만 실행합니다. 선택된 모드에 따라 실행:

#### soft 모드 (기본)

```bash
git reset --soft <target>
```

#### mixed 모드

```bash
git reset <target>
```

#### hard 모드

hard 모드는 stash 안전장치를 먼저 수행합니다:

```bash
git stash push -m "rewind-backup-$(date +%Y%m%d-%H%M%S)"
git reset --hard <target>
```

**devops-dangerous-guard 차단 대응:**

`git reset --hard`가 devops-dangerous-guard에 의해 차단될 수 있습니다. 차단된 경우:

1. 사용자에게 안내: "devops-dangerous-guard에 의해 `git reset --hard`가 차단되었습니다."
2. 대안 제시: "`--mode soft`로 되돌리면 변경사항이 staging area에 보존됩니다. soft 모드로 진행하시겠습니까?"
3. AskUserQuestion으로 soft 모드 전환 여부 확인

#### revert 모드

```bash
git revert --no-commit <target>..HEAD
git commit -m "revert: <target>까지 되돌리기"
```

**충돌 발생 시:**

1. 사용자에게 충돌 안내: "revert 중 충돌이 발생했습니다."
2. 충돌 파일 목록 표시: `git diff --name-only --diff-filter=U`
3. 대응 방법 안내:
   - "충돌을 수동으로 해결한 후 `git revert --continue`를 실행하세요."
   - "또는 `git revert --abort`로 revert를 취소할 수 있습니다."

### 6. 결과 표시

실행 후 현재 상태를 보여줍니다:

```bash
git log --oneline -5
```

모드별 추가 안내:

| 모드 | 추가 안내 |
|------|----------|
| `soft` | "변경사항이 staging area에 있습니다. `git status`로 확인하세요." |
| `mixed` | "변경사항이 working directory에 있습니다. `git status`로 확인하세요." |
| `hard` | "stash에 백업이 저장되었습니다. `git stash list`로 확인, `git stash pop`으로 복원할 수 있습니다." |
| `revert` | "새 revert 커밋이 생성되었습니다." |

## 에러 처리

| 상황 | 대응 |
|------|------|
| **Git 저장소가 아님** | "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료 |
| **유효하지 않은 커밋 해시** | "유효하지 않은 커밋입니다: <target>" 출력 후 종료 |
| **되돌릴 커밋 없음** | "이미 해당 커밋 시점이거나 되돌릴 커밋이 없습니다." 출력 후 종료 |
| **revert 충돌** | 충돌 파일 목록 + `--abort`/수동 해결 안내 |
| **hard 모드 차단** | soft 모드 전환 안내 + AskUserQuestion |
| **stash 실패** | "stash 생성에 실패했습니다. 변경사항이 없을 수 있습니다." 안내 후 계속 진행 |
| **기타 git 에러** | 에러 메시지를 그대로 출력하고 종료 |

## 주의사항

- `--hard` 모드는 반드시 `git stash`로 백업 후 실행합니다
- 공유 브랜치(main, master, develop 등)에서는 `--mode revert` 사용을 권장합니다
- 커밋 메시지에 Claude 관련 내용 포함하지 않음 (revert 커밋 메시지)
- Co-Authored-By 추가하지 않음 (이 명령어의 규칙이 시스템 프롬프트 기본 규칙보다 우선)

### zsh read-only 변수 사용 금지

현재 셸이 **zsh**이므로, Bash 도구로 실행하는 스크립트에서 다음 변수명을 **절대 사용하지 않아야** 합니다. 이 변수들은 zsh의 read-only 내장 변수이며, 대입 시 `read-only variable` 에러가 발생합니다.

**금지 변수명**: `status`, `pipestatus`, `ERRNO`, `ZSH_SUBSHELL`, `HISTCMD`

```bash
# 잘못된 예시 (에러 발생)
for f in file1 file2; do
  status=$(git diff --name-only "$f")  # read-only variable: status
done

# 올바른 예시
for f in file1 file2; do
  diff_result=$(git diff --name-only "$f")
  file_status=$(git status --short "$f")
done
```

---
description: 브랜치 전환, 생성, 파일 복원을 수행합니다.
argument-hint: "[브랜치명 | -b <이름> [베이스] | -- <파일> | <커밋해시>]"
---

# Git Checkout

브랜치 전환, 새 브랜치 생성, 파일 복원, detached HEAD 체크아웃, 원격 브랜치 자동 추적을 단일 명령어로 제공합니다.

## 입력: $ARGUMENTS

| 인자 형식 | 설명 |
|-----------|------|
| (없음) | 브랜치 목록 표시 후 선택 UI |
| `<브랜치명>` | 해당 브랜치로 전환 |
| `-b <이름> [베이스]` | 새 브랜치 생성 후 전환 |
| `-- <파일>` | 파일을 HEAD 상태로 복원 |
| `<커밋> -- <파일>` | 파일을 특정 커밋 시점으로 복원 |
| `<커밋해시>` | detached HEAD 상태로 전환 |

## 절차

### 1. Git 저장소 확인

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

Git 저장소가 아닌 경우: "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료.

### 2. 인자 파싱 및 모드 판별

`$ARGUMENTS`를 분석하여 아래 5가지 모드 중 하나를 결정합니다:

| 조건 | 모드 |
|------|------|
| 인자 없음 | **브랜치 선택 UI** |
| `-b <이름> [베이스]` | **새 브랜치 생성** |
| `-- <파일>` 또는 `<커밋> -- <파일>` | **파일 복원** |
| 40자리 hex 또는 짧은 해시 패턴 (브랜치 목록에 없음) | **detached HEAD** |
| 그 외 단일 문자열 | **브랜치 전환** |

### 3. [인자 없음] 브랜치 선택 UI

브랜치 목록을 표시하고 사용자에게 선택을 요청합니다:

```bash
git branch -a --sort=-committerdate
```

AskUserQuestion으로 전환할 브랜치를 물어봅니다:

```
AskUserQuestion(
  questions: [{
    question: "전환할 브랜치를 입력해 주세요.",
    header: "브랜치 선택"
  }]
)
```

사용자 입력을 받은 후 **Step 4 (브랜치 전환)** 로 진행합니다.

### 4. [브랜치 전환] `<브랜치명>`

#### 4-1. Dirty working directory 감지

```bash
git diff_output=$(git status --porcelain)
```

변경사항이 있는 경우 (`diff_output`이 비어있지 않음) AskUserQuestion으로 처리 방법을 묻습니다:

```
## 저장되지 않은 변경사항 감지

현재 working directory에 변경사항이 있습니다.
브랜치 전환 시 충돌이 발생할 수 있습니다.
```

```
AskUserQuestion(
  questions: [{
    question: "변경사항을 어떻게 처리하시겠습니까?",
    header: "Working Directory 변경사항 처리",
    options: [
      { label: "stash 후 진행 (Recommended)", description: "변경사항을 stash에 임시 저장 후 브랜치를 전환합니다" },
      { label: "그대로 진행", description: "변경사항을 유지한 채 브랜치를 전환합니다 (충돌 가능)" },
      { label: "취소", description: "브랜치 전환을 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **stash 후 진행** | `git stash push -m "checkout-backup-$(date +%Y%m%d-%H%M%S)"` 실행 후 Step 4-2로 진행 |
| **그대로 진행** | 그대로 Step 4-2로 진행 |
| **취소** | "브랜치 전환이 취소되었습니다." 출력 후 종료 |

#### 4-2. 로컬/원격 브랜치 확인 및 전환

로컬 브랜치 존재 여부 확인:

```bash
git branch --list <브랜치명>
```

로컬에 없으면 원격 브랜치 확인:

```bash
git branch -r | grep "origin/<브랜치명>"
```

| 상황 | 처리 |
|------|------|
| 로컬 브랜치 존재 | `git checkout <브랜치명>` |
| 로컬에 없고 원격에 존재 | `git checkout --track origin/<브랜치명>` (원격 브랜치 자동 추적) |
| 둘 다 없음 | "브랜치를 찾을 수 없습니다: <브랜치명>. 새 브랜치를 생성하려면 `-b <이름>` 옵션을 사용하세요." 출력 후 종료 |

#### 4-3. 결과 표시

```bash
git branch --show-current
git log --oneline -3
```

stash를 사용한 경우: "stash에 백업이 저장되었습니다. 작업 완료 후 `git stash pop`으로 복원할 수 있습니다." 안내

### 5. [새 브랜치 생성] `-b <이름> [베이스]`

`$ARGUMENTS`에서 브랜치 이름과 선택적 베이스를 파싱합니다:
- `-b <이름>`: 현재 HEAD에서 새 브랜치 생성
- `-b <이름> <베이스>`: 지정된 베이스(브랜치명 또는 커밋)에서 새 브랜치 생성

```bash
git checkout -b <이름> [베이스]
```

결과 표시:

```bash
git branch --show-current
git log --oneline -3
```

### 6. [파일 복원] `-- <파일>` 또는 `<커밋> -- <파일>`

파일을 특정 시점으로 복원합니다. **현재 변경사항이 영구적으로 손실됩니다.**

복원 계획을 표시합니다:

```
## 파일 복원 계획

**대상 파일**: <파일경로>
**복원 시점**: <커밋해시 또는 HEAD>
**주의**: 현재 파일의 변경사항이 영구적으로 삭제됩니다.
```

**반드시 AskUserQuestion 도구를 사용하여** 사용자 승인을 받습니다:

```
AskUserQuestion(
  questions: [{
    question: "파일을 복원하시겠습니까? 현재 변경사항은 영구적으로 손실됩니다.",
    header: "파일 복원 확인",
    options: [
      { label: "복원 진행", description: "<파일경로>을(를) <시점>으로 복원합니다" },
      { label: "취소 (Recommended)", description: "파일 복원을 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **복원 진행** | `git checkout [<커밋>] -- <파일>` 실행 후 결과 표시 |
| **취소** | "파일 복원이 취소되었습니다." 출력 후 종료 |

복원 후 결과 표시:

```bash
git diff HEAD -- <파일>
```

"파일이 복원되었습니다: <파일경로>" 출력

### 7. [detached HEAD] `<커밋해시>`

커밋 해시로 직접 이동하면 detached HEAD 상태가 됩니다. 진입 전 경고를 표시합니다:

```
## Detached HEAD 경고

**커밋**: <커밋해시>
**커밋 메시지**: <메시지>

Detached HEAD 상태에서는 커밋이 어떤 브랜치에도 속하지 않습니다.
이 상태에서 생성한 커밋은 브랜치 전환 후 접근하기 어려워집니다.
변경사항을 유지하려면 새 브랜치를 생성하세요: `git checkout -b <새브랜치명>`
```

커밋 유효성 확인:

```bash
git rev-parse --verify <커밋해시> 2>/dev/null
```

유효하지 않은 경우: "유효하지 않은 커밋입니다: <커밋해시>" 출력 후 종료.

AskUserQuestion으로 진행 여부를 확인합니다:

```
AskUserQuestion(
  questions: [{
    question: "Detached HEAD 상태로 진입하시겠습니까?",
    header: "Detached HEAD 확인",
    options: [
      { label: "진입", description: "<커밋해시> 시점으로 이동합니다 (detached HEAD)" },
      { label: "새 브랜치로 생성", description: "해당 커밋을 베이스로 새 브랜치를 생성합니다 (권장)" },
      { label: "취소", description: "체크아웃을 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **진입** | `git checkout <커밋해시>` 실행 |
| **새 브랜치로 생성** | 브랜치 이름을 AskUserQuestion으로 입력받아 `git checkout -b <이름> <커밋해시>` 실행 |
| **취소** | "체크아웃이 취소되었습니다." 출력 후 종료 |

결과 표시:

```bash
git log --oneline -3
```

## 에러 처리

| 상황 | 대응 |
|------|------|
| **Git 저장소가 아님** | "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료 |
| **유효하지 않은 브랜치명** | "브랜치를 찾을 수 없습니다: <브랜치명>" 출력. `-b <이름>` 안내 |
| **유효하지 않은 커밋 해시** | "유효하지 않은 커밋입니다: <커밋해시>" 출력 후 종료 |
| **파일 없음** | "파일을 찾을 수 없습니다: <파일경로>" 출력 후 종료 |
| **브랜치 전환 중 충돌** | git 에러 메시지 출력 + "충돌이 발생했습니다. 변경사항을 stash하거나 커밋한 후 다시 시도하세요." 안내 |
| **원격 브랜치 추적 실패** | "원격 브랜치 추적에 실패했습니다. `git fetch`를 실행한 후 다시 시도하세요." 안내 |
| **브랜치 이름 이미 존재** (`-b` 옵션) | "이미 존재하는 브랜치입니다: <이름>" 출력 후 종료 |
| **기타 git 에러** | 에러 메시지를 그대로 출력하고 종료 |

## 주의사항

- 파일 복원(`-- <파일>`) 실행 전 반드시 AskUserQuestion으로 사용자 승인을 받습니다
- dirty working directory 감지 시 stash 제안을 통해 변경사항 손실을 방지합니다
- 원격 브랜치는 `git fetch` 후 최신 상태가 반영됩니다
- 공유 브랜치(main, master, develop 등)에서 직접 파일 복원 시 주의합니다

### zsh read-only 변수 사용 금지

현재 셸이 **zsh**이므로, Bash 도구로 실행하는 스크립트에서 다음 변수명을 **절대 사용하지 않아야** 합니다. 이 변수들은 zsh의 read-only 내장 변수이며, 대입 시 `read-only variable` 에러가 발생합니다.

**금지 변수명**: `status`, `pipestatus`, `ERRNO`, `ZSH_SUBSHELL`, `HISTCMD`

```bash
# 잘못된 예시 (에러 발생)
status=$(git status --porcelain)  # read-only variable: status

# 올바른 예시
diff_output=$(git status --porcelain)
branch_result=$(git branch --show-current)
```

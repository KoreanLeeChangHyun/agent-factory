---
description: 브랜치를 전환하거나 새 브랜치를 생성합니다.
argument-hint: "[브랜치명 | -c <이름> [베이스] | -]"
---

# Git Switch

브랜치 전환, 새 브랜치 생성, 이전 브랜치 복귀를 제공합니다. 파일 복원과 detached HEAD 체크아웃은 `git checkout`을 사용하세요.

## 입력: $ARGUMENTS

| 인자 형식 | 설명 |
|-----------|------|
| (없음) | 브랜치 목록 표시 후 선택 UI |
| `<브랜치명>` | 해당 브랜치로 전환 |
| `-c <이름> [베이스]` | 새 브랜치 생성 후 전환 |
| `-` | 이전 브랜치로 복귀 |

## 절차

### 1. Git 저장소 확인

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

Git 저장소가 아닌 경우: "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료.

### 2. 인자 파싱 및 모드 판별

`$ARGUMENTS`를 분석하여 아래 4가지 모드 중 하나를 결정합니다:

| 조건 | 모드 |
|------|------|
| 인자 없음 | **브랜치 선택 UI** |
| `-c <이름> [베이스]` | **새 브랜치 생성** |
| `-` (하이픈 단독) | **이전 브랜치 복귀** |
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
diff_output=$(git status --porcelain)
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
| **stash 후 진행** | `git stash push -m "switch-backup-$(date +%Y%m%d-%H%M%S)"` 실행 후 Step 4-2로 진행 |
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
| 로컬 브랜치 존재 | `git switch <브랜치명>` |
| 로컬에 없고 원격에 존재 | `git switch --track origin/<브랜치명>` (원격 브랜치 자동 추적) |
| 둘 다 없음 | "브랜치를 찾을 수 없습니다: <브랜치명>. 새 브랜치를 생성하려면 `-c <이름>` 옵션을 사용하세요." 출력 후 종료 |

전환 대상이 `main` 또는 `master`인 경우, `git switch <브랜치명>` 완료 후 자동으로 pull을 실행합니다:

```bash
git pull origin <브랜치명>
```

pull 실패 시 (네트워크 오류 등): "자동 pull에 실패했습니다. 오프라인 상태이거나 원격 저장소에 연결할 수 없습니다." 경고 출력 후 계속 진행합니다.

#### 4-3. 결과 표시

```bash
git branch --show-current
git log --oneline -3
```

main/master 전환 시 pull 결과도 표시합니다:
- pull로 새 커밋이 반영된 경우: "자동 pull 완료: N개 커밋이 업데이트되었습니다." 출력
- 이미 최신 상태인 경우: "이미 최신 상태입니다." 출력

stash를 사용한 경우: "stash에 백업이 저장되었습니다. 작업 완료 후 `git stash pop`으로 복원할 수 있습니다." 안내

### 5. [새 브랜치 생성] `-c <이름> [베이스]`

`$ARGUMENTS`에서 브랜치 이름과 선택적 베이스를 파싱합니다:
- `-c <이름>`: `origin/main` 기반으로 새 브랜치 생성 (자동 fetch 후)
- `-c <이름> <베이스>`: 지정된 베이스(브랜치명 또는 커밋)에서 새 브랜치 생성

원격 최신 상태를 동기화하기 위해 먼저 fetch를 실행합니다:

```bash
git fetch origin
```

fetch 실패 시 (네트워크 오류 등): "원격 저장소에 연결할 수 없습니다. 오프라인 상태에서 로컬 기준으로 진행합니다." 경고 출력 후 계속 진행합니다.

베이스 지정 여부에 따라 분기합니다:

| 조건 | 실행 명령 |
|------|----------|
| 베이스 미지정 | `git switch -c <이름> origin/main` |
| 베이스 지정 | `git switch -c <이름> <베이스>` |

결과 표시:

```bash
git branch --show-current
git log --oneline -3
```

### 6. [이전 브랜치 복귀] `-`

#### 6-1. Dirty working directory 감지

Step 4-1과 동일한 방식으로 dirty working directory를 감지하고 stash/그대로 진행/취소 처리를 수행합니다.

#### 6-2. 이전 브랜치로 전환

```bash
git switch -
```

이전 브랜치가 없는 경우 (git 에러 발생): "이전 브랜치 기록이 없습니다. 처음 체크아웃하는 경우이거나 브랜치 이력이 초기화되었습니다." 출력 후 종료.

#### 6-3. 결과 표시

```bash
git branch --show-current
git log --oneline -3
```

## 에러 처리

| 상황 | 대응 |
|------|------|
| **Git 저장소가 아님** | "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료 |
| **브랜치 없음** | "브랜치를 찾을 수 없습니다: <브랜치명>. 새 브랜치를 생성하려면 `-c <이름>` 옵션을 사용하세요." 출력 후 종료 |
| **전환 중 충돌** | git 에러 메시지 출력 + "충돌이 발생했습니다. 변경사항을 stash하거나 커밋한 후 다시 시도하세요." 안내 |
| **브랜치 이름 이미 존재** (`-c` 시) | "이미 존재하는 브랜치입니다: <이름>" 출력 후 종료 |
| **fetch 실패 (네트워크)** | "원격 저장소에 연결할 수 없습니다. 오프라인 상태에서 로컬 기준으로 진행합니다." 안내 후 계속 진행 |
| **pull 실패 (네트워크)** | "자동 pull에 실패했습니다. 오프라인 상태이거나 원격 저장소에 연결할 수 없습니다." 경고 후 계속 진행 |
| **이전 브랜치 없음** (`-` 시) | "이전 브랜치 기록이 없습니다. 처음 체크아웃하는 경우이거나 브랜치 이력이 초기화되었습니다." 출력 후 종료 |

## 주의사항

- dirty working directory 감지 시 stash 제안을 통해 변경사항 손실을 방지합니다
- 원격 브랜치는 `--track` 옵션으로 자동 추적이 설정됩니다
- `git switch`는 브랜치 전환/생성 전용 명령어입니다. 파일 복원(`-- <파일>`)과 detached HEAD(`<커밋해시>`) 체크아웃은 `/git:checkout`을 사용하세요

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

---
description: 현재 브랜치를 원격 저장소에 푸시합니다.
argument-hint: "[--force | --force-with-lease | --tags | --delete <브랜치명>]"
---

# Git Push

현재 브랜치를 원격 저장소(origin)에 푸시합니다. upstream 미설정 브랜치는 자동으로 `-u` 옵션이 적용됩니다. force push 및 원격 브랜치 삭제 등 파괴적 동작 전에는 반드시 사용자 승인을 받습니다.

## 입력: $ARGUMENTS

| 인자 형식 | 설명 |
|-----------|------|
| (없음) | 현재 브랜치를 origin에 push (upstream 미설정 시 `-u` 자동 추가) |
| `--force` | Force push (AskUserQuestion 승인 필수, main/master 대상 시 추가 경고) |
| `--force-with-lease` | 안전한 force push (AskUserQuestion 승인 필수) |
| `--tags` | 로컬 태그를 origin에 push |
| `--delete <브랜치명>` | 원격 브랜치 삭제 (AskUserQuestion 승인 필수) |

## 절차

### 1. Git 저장소 확인

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

Git 저장소가 아닌 경우: "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료.

### 2. 인자 파싱 및 모드 판별

`$ARGUMENTS`를 분석하여 아래 모드 중 하나를 결정합니다:

| 조건 | 모드 |
|------|------|
| 인자 없음 | **일반 push** |
| `--force` | **force push** |
| `--force-with-lease` | **force-with-lease push** |
| `--tags` | **태그 push** |
| `--delete <브랜치명>` | **원격 브랜치 삭제** |

### 3. [일반 push / force / force-with-lease / tags] 푸시 계획 표시

#### 3-1. 현재 브랜치 및 upstream 확인

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null
```

| 상황 | 처리 |
|------|------|
| upstream 설정됨 | `git log --oneline @{u}..HEAD` 로 푸시할 커밋 수 확인 |
| upstream 미설정 | upstream 미설정 상태로 표시, 푸시 시 `-u origin <브랜치명>` 자동 추가 예정임을 안내 |

#### 3-2. 푸시 계획 출력

아래 형식으로 푸시 계획을 출력합니다:

```
## 푸시 계획

**현재 브랜치**: <브랜치명>
**대상**: origin/<브랜치명>
**upstream**: <설정됨 / 미설정 (-u 자동 추가 예정)>
**푸시할 커밋**: N개
<git log --oneline @{u}..HEAD 결과 (upstream 설정 시)>
```

### 4. [일반 push] 푸시 실행

사용자 승인 없이 즉시 실행합니다:

upstream 설정 여부에 따라 분기합니다:

| 조건 | 실행 명령 |
|------|----------|
| upstream 설정됨 | `git push origin <브랜치명>` |
| upstream 미설정 | `git push -u origin <브랜치명>` |

### 5. [force push] 파괴적 동작 보호 및 실행

**반드시 AskUserQuestion 도구를 사용하여** 사용자 승인을 받습니다.

현재 브랜치가 `main` 또는 `master`인 경우 추가 경고를 먼저 출력합니다:

```
## 경고: 보호된 브랜치에 대한 Force Push

main 브랜치에 대한 force push는 매우 위험합니다.
원격 저장소의 히스토리를 덮어쓰며, 다른 팀원의 작업에 영향을 줄 수 있습니다.
```

```
AskUserQuestion(
  questions: [{
    question: "Force push는 원격 히스토리를 덮어씁니다. 진행하시겠습니까?",
    header: "Force Push 확인",
    options: [
      { label: "진행", description: "git push --force origin <브랜치명> 을 실행합니다" },
      { label: "--force-with-lease로 변경", description: "원격 브랜치가 예상과 다른 경우 실패하는 안전한 방식으로 변경합니다" },
      { label: "취소 (Recommended)", description: "푸시를 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **진행** | `git push --force origin <브랜치명>` 실행 |
| **--force-with-lease로 변경** | Step 6 (`--force-with-lease`) 로 전환 |
| **취소** | "푸시가 취소되었습니다." 출력 후 종료 |

### 6. [force-with-lease push] 안전한 force push 실행

**반드시 AskUserQuestion 도구를 사용하여** 사용자 승인을 받습니다:

```
AskUserQuestion(
  questions: [{
    question: "Force-with-lease push를 진행하시겠습니까? 원격 브랜치가 예상과 다르면 자동으로 실패합니다.",
    header: "Force-with-lease Push 확인",
    options: [
      { label: "진행 (Recommended)", description: "git push --force-with-lease origin <브랜치명> 을 실행합니다" },
      { label: "취소", description: "푸시를 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **진행** | `git push --force-with-lease origin <브랜치명>` 실행 |
| **취소** | "푸시가 취소되었습니다." 출력 후 종료 |

### 7. [태그 push] 태그 푸시 실행

로컬 태그 목록을 먼저 표시합니다:

```bash
git tag --sort=-creatordate | head -10
```

사용자 승인 없이 즉시 실행합니다:

```bash
git push origin --tags
```

### 8. [원격 브랜치 삭제] 파괴적 동작 보호 및 실행

삭제 대상 원격 브랜치 정보를 표시합니다:

```bash
git log --oneline -3 origin/<브랜치명> 2>/dev/null
```

**반드시 AskUserQuestion 도구를 사용하여** 사용자 승인을 받습니다:

```
AskUserQuestion(
  questions: [{
    question: "원격 브랜치 '<브랜치명>'을 삭제합니다. 되돌릴 수 없습니다. 진행하시겠습니까?",
    header: "원격 브랜치 삭제 확인",
    options: [
      { label: "삭제 진행", description: "origin/<브랜치명> 원격 브랜치를 영구 삭제합니다" },
      { label: "취소 (Recommended)", description: "삭제를 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **삭제 진행** | `git push origin --delete <브랜치명>` 실행 |
| **취소** | "삭제가 취소되었습니다." 출력 후 종료 |

### 9. 결과 표시

푸시 완료 후 결과를 표시합니다:

```bash
git log --oneline -5
git branch -vv
```

- 일반 push 성공 시: "푸시 완료: origin/<브랜치명>" 출력
- upstream이 새로 설정된 경우: "upstream이 설정되었습니다: origin/<브랜치명>" 출력
- force push 성공 시: "Force push 완료: origin/<브랜치명>" 출력
- 태그 push 성공 시: "태그 푸시 완료" 출력
- 원격 브랜치 삭제 성공 시: "원격 브랜치 삭제 완료: origin/<브랜치명>" 출력

## 에러 처리

| 상황 | 대응 |
|------|------|
| **Git 저장소가 아님** | "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료 |
| **현재 브랜치 없음 (detached HEAD)** | "Detached HEAD 상태에서는 push할 수 없습니다. `git checkout -b <브랜치명>`으로 브랜치를 생성하세요." 출력 후 종료 |
| **원격 저장소 연결 실패** | git 에러 메시지 출력 + "원격 저장소에 연결할 수 없습니다. 네트워크 상태를 확인하세요." 안내 |
| **non-fast-forward 거절** | git 에러 메시지 출력 + "원격 브랜치가 로컬보다 앞서 있습니다. `git pull`로 최신 상태를 동기화한 후 다시 push하세요." 안내 |
| **force-with-lease 실패** | git 에러 메시지 출력 + "원격 브랜치가 예상과 다릅니다. `git fetch`로 최신 상태를 확인하세요." 안내 |
| **인증 실패** | git 에러 메시지 출력 + "인증에 실패했습니다. SSH 키 또는 자격증명을 확인하세요." 안내 |
| **원격 브랜치 없음 (--delete)** | "삭제할 원격 브랜치를 찾을 수 없습니다: <브랜치명>" 출력 후 종료 |
| **태그 없음 (--tags)** | "푸시할 로컬 태그가 없습니다." 출력 후 종료 |
| **기타 git 에러** | 에러 메시지를 그대로 출력하고 종료 |

## 주의사항

- `--force`와 `--delete` 등 파괴적 동작 전에는 반드시 AskUserQuestion으로 사용자 승인을 받습니다
- 원격 저장소명은 `origin`을 기본으로 사용합니다
- main/master 브랜치에 대한 force push는 추가 경고를 표시합니다
- upstream 미설정 브랜치는 `-u` 옵션으로 자동 설정하여 이후 `git push` 단축 사용이 가능해집니다
- `--force-with-lease`는 `--force`보다 안전하며, 원격 브랜치가 예상과 다를 경우 자동으로 실패합니다

### zsh read-only 변수 사용 금지

현재 셸이 **zsh**이므로, Bash 도구로 실행하는 스크립트에서 다음 변수명을 **절대 사용하지 않아야** 합니다. 이 변수들은 zsh의 read-only 내장 변수이며, 대입 시 `read-only variable` 에러가 발생합니다.

**금지 변수명**: `status`, `pipestatus`, `ERRNO`, `ZSH_SUBSHELL`, `HISTCMD`

```bash
# 잘못된 예시 (에러 발생)
status=$(git push origin main)  # read-only variable: status

# 올바른 예시
push_result=$(git push origin main)
branch_name=$(git rev-parse --abbrev-ref HEAD)
```

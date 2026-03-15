---
description: 브랜치를 현재 브랜치에 병합합니다.
argument-hint: "[소스 브랜치명] [--no-ff | --squash | --abort]"
---

# Git Merge

브랜치를 현재 브랜치에 병합합니다. 충돌 발생 시 파일 목록 표시 및 해결 안내를 제공합니다.

## 입력: $ARGUMENTS

| 인자 형식 | 설명 |
|-----------|------|
| (없음) | 브랜치 목록 표시 후 선택 UI |
| `<브랜치명>` | 해당 브랜치를 현재 브랜치에 병합 (fast-forward 가능하면 ff, 아니면 merge commit) |
| `--no-ff <브랜치명>` | 항상 merge commit 생성 (fast-forward 금지) |
| `--squash <브랜치명>` | 모든 커밋을 하나로 합쳐서 병합 (커밋 미완료 상태로 staging) |
| `--abort` | 진행 중인 머지 중단 |

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
| 인자 없음 | **브랜치 선택 UI** |
| `--abort` | **머지 중단** |
| `--no-ff <브랜치명>` | **no-ff 병합** |
| `--squash <브랜치명>` | **squash 병합** |
| `<브랜치명>` (그 외) | **기본 병합** |

### 3. [인자 없음] 브랜치 선택 UI

브랜치 목록을 표시하고 사용자에게 선택을 요청합니다:

```bash
git branch -a --sort=-committerdate
```

현재 브랜치 확인:

```bash
git branch --show-current
```

AskUserQuestion으로 병합할 소스 브랜치를 물어봅니다:

```
AskUserQuestion(
  questions: [{
    question: "현재 브랜치에 병합할 소스 브랜치를 입력해 주세요.",
    header: "소스 브랜치 선택"
  }]
)
```

사용자 입력을 받은 후 **Step 4 (머지 계획 표시)** 로 진행합니다.

### 4. [--abort] 머지 중단

진행 중인 머지를 중단합니다:

```bash
git merge --abort
```

중단 후: "머지가 중단되었습니다. 작업 디렉토리가 머지 이전 상태로 복원되었습니다." 출력 후 종료.

머지가 진행 중이 아닌 경우 (`MERGE_HEAD` 파일 없음): "현재 진행 중인 머지가 없습니다." 출력 후 종료.

### 5. 머지 계획 표시

현재 브랜치와 소스 브랜치를 확인하고 병합될 커밋 목록을 표시합니다:

```bash
git branch --show-current
git log --oneline <현재브랜치>..<소스브랜치>
```

아래 형식으로 머지 계획을 출력합니다:

```
## 머지 계획

**현재 브랜치 (대상)**: <현재브랜치>
**소스 브랜치**: <소스브랜치>
**머지 방식**: <기본 병합 | no-ff (merge commit 강제) | squash (단일 커밋으로 합치기)>
**병합될 커밋**: N개

<병합될 커밋 목록 (git log --oneline)>
```

병합될 커밋이 없는 경우: "소스 브랜치에 병합할 커밋이 없습니다. 이미 최신 상태입니다." 출력 후 종료.

소스 브랜치가 존재하지 않는 경우: "브랜치를 찾을 수 없습니다: <소스브랜치>" 출력 후 종료.

### 6. 사용자 승인 (AskUserQuestion 필수)

**반드시 AskUserQuestion 도구를 사용하여** 사용자 승인을 받습니다:

```
AskUserQuestion(
  questions: [{
    question: "위 머지 계획으로 진행하시겠습니까?",
    header: "머지 승인",
    options: [
      { label: "승인 (Recommended)", description: "위 내용으로 머지를 실행합니다" },
      { label: "방식 변경", description: "머지 방식을 변경합니다 (기본/no-ff/squash)" },
      { label: "취소", description: "머지를 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **승인** | Step 7로 진행 (머지 실행) |
| **방식 변경** | 사용자 입력으로 받은 방식을 반영하여 Step 5 재실행 |
| **취소** | "머지가 취소되었습니다." 출력 후 종료 |

### 7. 머지 실행

사용자 승인 후에만 실행합니다. 선택된 방식에 따라 실행:

#### 기본 병합

```bash
git merge <소스브랜치>
```

#### no-ff 병합

```bash
git merge --no-ff <소스브랜치>
```

#### squash 병합

```bash
git merge --squash <소스브랜치>
```

squash 완료 후: "커밋이 staging area에 준비되었습니다. `git commit`으로 단일 커밋을 생성하세요." 안내.

### 8. 충돌 처리

머지 중 충돌이 발생한 경우:

충돌 파일 목록을 표시합니다:

```bash
git diff --name-only --diff-filter=U
```

아래 안내 메시지를 출력합니다:

```
## 충돌 발생

다음 파일에서 충돌이 발생했습니다:
<충돌 파일 목록>

**해결 방법:**
1. 위 파일들을 직접 편집하여 충돌 마커(`<<<<<<<`, `=======`, `>>>>>>>`)를 제거하고 내용을 정리합니다.
2. 각 파일을 해결한 후 `git add <파일>`로 staging합니다.
3. 모든 충돌 해결 후 `git commit`으로 머지를 완료합니다.

**머지 중단:** `git merge --abort`로 머지를 취소하고 이전 상태로 돌아갈 수 있습니다.
```

### 9. 결과 표시

충돌 없이 머지가 완료된 경우:

```bash
git log --oneline -5
```

"머지가 완료되었습니다." 출력 및 최근 커밋 히스토리를 표시합니다.

## 에러 처리

| 상황 | 대응 |
|------|------|
| **Git 저장소가 아님** | "현재 디렉토리는 Git 저장소가 아닙니다." 출력 후 종료 |
| **소스 브랜치 없음** | "브랜치를 찾을 수 없습니다: <소스브랜치>" 출력 후 종료 |
| **병합할 커밋 없음** | "소스 브랜치에 병합할 커밋이 없습니다. 이미 최신 상태입니다." 출력 후 종료 |
| **충돌 발생** | 충돌 파일 목록 표시 + 수동 해결 안내 + `--abort` 안내 |
| **현재 진행 중인 머지 없음** (`--abort`) | "현재 진행 중인 머지가 없습니다." 출력 후 종료 |
| **현재 브랜치가 소스와 동일** | "현재 브랜치에 자기 자신을 병합할 수 없습니다." 출력 후 종료 |
| **기타 git 에러** | 에러 메시지를 그대로 출력하고 종료 |

## 주의사항

- squash 병합 후에는 `git commit`을 별도로 실행해야 단일 커밋이 생성됩니다
- 공유 브랜치(main, master, develop 등)에 병합 시 팀 협의 후 진행을 권장합니다
- 커밋 메시지에 Claude 관련 내용 포함하지 않음
- Co-Authored-By 추가하지 않음 (이 명령어의 규칙이 시스템 프롬프트 기본 규칙보다 우선)

### zsh read-only 변수 사용 금지

현재 셸이 **zsh**이므로, Bash 도구로 실행하는 스크립트에서 다음 변수명을 **절대 사용하지 않아야** 합니다. 이 변수들은 zsh의 read-only 내장 변수이며, 대입 시 `read-only variable` 에러가 발생합니다.

**금지 변수명**: `status`, `pipestatus`, `ERRNO`, `ZSH_SUBSHELL`, `HISTCMD`

```bash
# 잘못된 예시 (에러 발생)
status=$(git merge --squash <브랜치명>)  # read-only variable: status

# 올바른 예시
merge_result=$(git merge --squash <브랜치명>)
branch_info=$(git branch --show-current)
```

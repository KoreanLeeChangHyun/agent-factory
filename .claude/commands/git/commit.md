---
description: 현재 브랜치의 작업 내역을 커밋합니다.
argument-hint: "[커밋 메시지 힌트 (선택)]"
---

# Git Commit

현재 브랜치의 변경사항을 커밋합니다.

## 입력: $ARGUMENTS

## 절차

### 1. 변경사항 확인

```bash
git status
git diff --staged   # 이미 staged 된 변경사항
git diff            # unstaged 변경사항
```

```bash
git log -3 --oneline   # 최근 커밋 메시지 스타일 참조
```

### 2. 커밋 계획 제안

변경사항 분석 후 터미널에 커밋 계획을 출력:

```
## 커밋 계획

**변경 파일**: N개
| 파일 | 상태 |
|------|------|
| path/to/file | Modified/Added/Deleted |

**커밋 메시지**:
<타입>: <요약>
```

**민감 파일 필터링**: 변경 파일 중 다음 키워드를 포함하는 파일은 커밋 대상에서 제외 여부를 사용자에게 명시적으로 고지합니다:
- `.env`, `credentials`, `secret`, `token`, `key`, `password`, `.pem`, `.p12`
- 해당 파일이 `.gitignore`에 포함되어 있는지 확인하고, 포함되지 않은 경우 경고를 표시합니다

### 3. 사용자 승인 (AskUserQuestion 필수)

**반드시 AskUserQuestion 도구를 사용하여** 사용자 승인을 받습니다:

```
AskUserQuestion(
  questions: [{
    question: "위 커밋 계획으로 진행하시겠습니까?",
    header: "커밋 승인",
    options: [
      { label: "승인 (Recommended)", description: "위 내용으로 커밋을 실행합니다" },
      { label: "메시지 수정", description: "커밋 메시지를 수정합니다" },
      { label: "커밋 취소", description: "커밋을 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **승인** | → Step 4로 진행 (커밋 실행) |
| **메시지 수정** | → 사용자 입력(Other)으로 받은 수정 내용을 반영하여 새 메시지 작성 후 Step 3 재실행 |
| **커밋 취소** | → "커밋이 취소되었습니다" 출력 후 종료 |

### 4. 커밋 실행

사용자 승인 후에만 실행합니다:

```bash
git add <승인된 변경 파일>
git commit -m "<커밋 메시지>"
git log -1 --oneline
```

**에러 처리:**

| 상황 | 대응 |
|------|------|
| **pre-commit hook 실패** | 에러 메시지를 사용자에게 보고하고, 수정 후 재시도 여부를 확인 |
| **빈 커밋** (변경사항 없음) | "커밋할 변경사항이 없습니다" 출력 후 종료 |
| **기타 git 에러** | 에러 메시지를 그대로 출력하고 종료 |

## 커밋 메시지 규칙

- 첫 줄: 50자 이내 요약
- 형식: `<타입>: <요약>`

| 타입 | 설명 |
|------|------|
| feat | 새로운 기능 추가 및 신규개발 |
| fix | 버그 수정 |
| design | HTML/CSS와 같은 UI 변경 |
| style | 코드 포맷팅, 코드 스타일 수정 (코드 변경 X) |
| refactor | 코드 리팩토링 (코드 최적화) |
| test | 테스트 코드 추가/수정 |
| rename | 파일/폴더명 수정 또는 이동 |
| remove | 파일 삭제 |
| chore | Config 설정, 라이브러리 추가 |
| comment | 주석 추가 및 변경 |
| merge | 브랜치 병합 커밋 (충돌 해결 포함) |
| docs | 문서 수정 |

## 버전 자동 갱신

커밋 시 `.claude/.version` (SemVer: `MAJOR.MINOR.PATCH`) 파일의 버전 갱신 여부를 판단합니다.

### 판단 기준

| 변경 유형 | 버전 변경 | 예시 |
|----------|----------|------|
| `.claude/` 하위 파일 변경 포함 | PATCH 증가 | 1.0.0 → 1.0.1 |
| `.claude/` 변경 없음 (외부 파일만) | 갱신 안 함 | - |

### 절차

1. **Step 1 (변경사항 확인)** 에서 `.claude/` 하위 파일 변경 여부를 확인
2. `.claude/` 변경이 있으면 `.claude/.version` 의 PATCH를 +1 증가
3. 증가된 `.version` 파일을 커밋 대상에 포함
4. **커밋 계획**에 버전 갱신 여부를 표시: `**버전**: 1.0.0 → 1.0.1`

> `.claude/.version` 자체의 변경만 있는 경우(이미 수동 갱신됨)는 추가 증가하지 않습니다.

## 주의사항

- 커밋 메시지에 Claude 관련 내용 포함하지 않음
- Co-Authored-By 추가하지 않음 (이 명령어의 규칙이 시스템 프롬프트 기본 규칙보다 우선)
- `$ARGUMENTS`를 메시지 힌트로 반영

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

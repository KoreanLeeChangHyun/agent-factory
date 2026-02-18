---
description: 프로젝트 초기 구조 설정 (디렉토리, .gitignore, 빈 CLAUDE.md 템플릿). (프로젝트당 1회)
---
# Initialize Project

> **실행 시점:** 새 프로젝트에서 **1회만** 실행하세요. 매 세션마다 실행하는 것은 `/init:workflow`입니다.
> 코드베이스 분석 후 상세한 CLAUDE.md를 생성하려면 `/sync:context`를 사용하세요.

프로젝트 초기 구조를 설정합니다.

## 스크립트

`.claude/scripts/init/init-project.sh` - 서브커맨드: generate-empty-template, setup-dirs, setup-wf-alias, setup-gitignore, verify

## 오케스트레이션 흐름

아래 순서대로 실행합니다. 각 단계에서 Bash 도구로 스크립트를 호출하고, 결과 JSON을 파싱하여 다음 단계를 결정합니다.

### Step 1. CLAUDE.md 빈 템플릿 생성

CLAUDE.md 파일 존재 여부를 확인합니다.

**분기:**
- 파일이 없으면 -> Bash 도구로 빈 템플릿 생성:

```bash
wf-project generate-empty-template
```

**결과 JSON 예시:**
```json
{
  "status": "created",
  "file": "CLAUDE.md"
}
```

- 파일이 있으면 -> 스킵 (Step 2로 진행)

### Step 2. 디렉토리 및 파일 생성

Bash 도구로 실행:

```bash
wf-project setup-dirs
```

**결과 JSON 예시:**
```json
{
  "created_dirs": [".workflow", ".prompt"],
  "created_files": [".prompt/prompt.txt", ".prompt/memo.txt", ".prompt/querys.txt", ".claude.env", ".prompt/history.md", ".workflow/registry.json"],
  "all_dirs_exist": true,
  "all_files_exist": true
}
```

생성 결과 메시지 출력.

### Step 3. 워크플로우 Alias 설정

Bash 도구로 실행:

```bash
wf-project setup-wf-alias
```

**결과 JSON 예시:**
```json
{
  "status": "ok",
  "zshrc_added": ["Workflow", "wf-state", "wf-init", "wf-claude", "wf-project", "wf-clear", "wf-sync", "wf-git-config", "wf-slack", "wf-info", "wf-commands"],
  "zshrc_skipped": [],
  "wrapper_added": ["Workflow", "wf-state", "wf-init", "wf-claude", "wf-project", "wf-clear", "wf-sync", "wf-git-config", "wf-slack", "wf-info", "wf-commands"]
}
```

추가/스킵된 alias 및 wrapper 스크립트 결과 메시지 출력.

### Step 4. .gitignore 업데이트

Bash 도구로 실행:

```bash
wf-project setup-gitignore
```

**결과 JSON 예시:**
```json
{
  "added": [".workflow/", ".claude.env", ".claude.env*", ".prompt/"],
  "skipped": []
}
```

추가/스킵된 패턴 결과 메시지 출력.

### Step 5. 전체 검증

Bash 도구로 실행:

```bash
wf-project verify
```

결과 JSON의 `checks` 배열을 파싱하여 최종 결과 출력:

```
=== 프로젝트 초기화 완료 ===

[초기화 결과]
[v] CLAUDE.md 빈 템플릿 생성 완료 (또는 "기존 파일 유지")
[v] 디렉토리 생성: .workflow, .prompt
[v] 파일 생성: .prompt/prompt.txt, .prompt/memo.txt, .prompt/querys.txt, .claude.env, .prompt/history.md, .workflow/registry.json
[v] 워크플로우 alias 설정 완료 (zshrc + ~/.local/bin wrapper)
[v] wrapper 스크립트 검증 완료: Workflow, wf-state, wf-init, wf-claude, wf-project, wf-clear, wf-sync, wf-git-config, wf-slack, wf-info, wf-commands
[v] .gitignore 업데이트 완료

다음 단계:
- /sync:context 명령어로 코드베이스를 분석하고 CLAUDE.md를 갱신하세요
- /init:workflow 명령어로 워크플로우를 로드하세요
```

---

## 사용자 재질의 원칙

**이 명령어는 완전 자동화된 작업이므로 사용자 입력이 필요하지 않습니다.**

| 상황 | AskUserQuestion 사용 |
|------|---------------------|
| .gitignore 기존 패턴과 충돌 시 | 덮어쓰기 확인 필요 시 |
| 기타 예외 상황 | 사용자 판단 필요 시 |

---

## 오류 처리

| 오류 상황 | 대응 |
|----------|------|
| 디렉토리 생성 실패 | 에러 메시지 출력, 권한 문제인지 확인 안내 |
| 파일 생성 실패 | 에러 메시지 출력, 수동 생성 방법 안내 |
| .gitignore 수정 실패 | 에러 메시지 출력, 수동 추가 방법 안내 |
| CLAUDE.md 빈 템플릿 생성 실패 | 에러 메시지 출력, 권한 확인 안내 |

---

## 관련 명령어

| 명령어 | 설명 |
|--------|------|
| `/sync:context` | 코드베이스 분석 후 CLAUDE.md 갱신 (수시 실행 가능) |
| `/init:claude` | 사용자 환경 초기화 (alias, StatusLine, Slack, Git global) |
| `/init:workflow` | 워크플로우 로드 (CLAUDE.md, orchestration 스킬) |
| `/init:clear` | 작업 내역 클리어 |

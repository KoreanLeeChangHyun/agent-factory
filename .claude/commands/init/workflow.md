---
description: 워크플로우 초기화. CLAUDE.md 로드, workflow-orchestration 스킬 로드. (매 세션마다)
---
# Initialize Workflow

> **실행 시점:** 매 대화 세션 시작 시 **자동 실행**됩니다. (`cc` alias에 의해)

매 대화 세션 시작 시 워크플로우를 초기화합니다.

## 사용 안내

이 명령어는 `cc` alias에서 `--system-prompt` 옵션으로 **자동 실행**됩니다.

```bash
# cc alias 정의 (자동 실행)
alias cc='claude --dangerously-skip-permissions "/init:workflow"'
```

수동 실행도 가능합니다:
```
/init:workflow
```

## 1. 프로젝트 컨텍스트 로드

CLAUDE.md를 읽어 프로젝트 구조와 최근 변경사항을 파악합니다.

## 2. workflow-orchestration 스킬 로드

`.claude/skills/workflow-orchestration/SKILL.md`를 로드합니다.

- **이 스킬만 메인 에이전트가 로드**합니다
- 나머지 워크플로우 스킬(routing, plan, work, report)은 **각 에이전트가 자율적으로 로드**합니다
- 상세 워크플로우 가이드는 orchestration 스킬을 참조하세요

## 금지 행위

> **절대 금지:** 이 명령어(`/init:workflow`) 실행 중 `init-workflow.sh`를 Bash 도구로 직접 호출하지 않습니다.

- `init-workflow.sh`는 **cc:* 명령어 실행 시 init 에이전트가 Step 3에서만 호출**하는 스크립트입니다
- `/init:workflow`는 **세션 초기화 전용**이며, 역할은 CLAUDE.md 로드 + workflow-orchestration 스킬 로드뿐입니다
- 셸 스크립트 실행, 디렉터리 생성, 상태 파일 생성 등은 이 명령어의 범위가 아닙니다

> **절대 금지:** 이 명령어(`/init:workflow`) 실행 중 `Workflow` (workflow-banner.sh) 배너를 호출하지 않습니다.

- 배너는 **`cc:*` 워크플로우 명령어 실행 시에만 오케스트레이터가 호출**합니다
- `/init:workflow`는 세션 초기화 전용이므로 배너 출력 대상이 아닙니다

## 3. 워크플로우 필수 준수 원칙

이후 모든 cc:* 명령어는 `workflow-orchestration` 스킬의 워크플로우를 **반드시** 따릅니다.

1. 모든 단계 **절대 생략 불가**, **순서대로** 수행
2. 각 단계 완료 후 **반드시 다음 단계로 진행**
3. 모든 작업 내역은 `.workflow/` 디렉터리에 자동 저장

## 사용 가능한 명령어

터미널에서 `wf-commands`를 실행하면 `.claude/commands/cc/*.md`를 동적 스캔하여 최신 명령어 목록을 확인할 수 있습니다.

```bash
wf-commands
```

## 사용자 재질의 원칙

**이 명령어 실행 중 사용자 입력이 필요한 경우 반드시 `AskUserQuestion` 도구를 사용합니다.**

| 상황 | AskUserQuestion 사용 |
|------|---------------------|
| CLAUDE.md 없을 때 생성 여부 확인 | ✅ 선택적 |
| 워크플로우 스킬 로드 실패 시 | ✅ 재시도 여부 확인 |

> 참고: 이 명령어는 대부분 자동 로드되므로 사용자 입력이 필요한 경우가 드뭅니다.

---

## 관련 명령어

- `/init:claude` - 사용자 환경 초기화 (alias, StatusLine, Slack, Git)
- `/init:project` - 프로젝트 초기화 (디렉토리, 파일, .gitignore)
- `/init:context` - 코드베이스 분석 후 CLAUDE.md 갱신
- `/init:clear` - 작업 내역 클리어

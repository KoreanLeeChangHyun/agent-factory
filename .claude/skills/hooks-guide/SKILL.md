---
name: hooks-guide
description: "Claude Code의 Hooks 시스템 사용법 가이드. Hook 이벤트, 실행 타이밍, 새 Hook 추가/수정 방법을 안내합니다. 사용 시점: Hook 설정 확인, Hook 추가/수정, PreToolUse Hook 동작 이해 시. 트리거: 'hook', '훅', 'PreToolUse', 'PostToolUse', 'Hook 설정'."
---

# Hooks 시스템 가이드

## 설명
Claude Code의 Hooks 시스템 사용법과 현재 프로젝트의 Hook 설정을 안내합니다.

## 사용 시기
- Hook 이벤트와 실행 타이밍을 알고 싶을 때
- 새로운 Hook을 추가하거나 수정할 때
- 현재 등록된 Hook의 동작을 이해하고 싶을 때

---

## Hooks 시스템

### 개요

Claude Code Hooks는 특정 이벤트 발생 시 자동으로 실행되는 스크립트입니다. `.claude/settings.json`의 `hooks` 섹션에 정의되며, 도구 사용 전/후에 검증, 알림 등의 작업을 수행합니다.

### 지원 이벤트

| 이벤트 | 설명 | 실행 시점 |
|--------|------|-----------|
| `PreToolUse` | 도구 사용 전 | 도구 호출 직전 (차단/경고 가능) |
| `PostToolUse` | 도구 사용 후 | 도구 실행 완료 후 |
| `SessionStart` | 세션 시작 시 | Claude Code 세션 시작 |
| `UserPromptSubmit` | 사용자 입력 제출 시 | 프롬프트 전송 시 |
| `Stop` | Claude 응답 완료 시 | 자동 중단 직전 (차단 가능) |

### 디렉터리 구조

```
.claude/hooks/                          # 복수형 (공식 컨벤션)
├── _utils/                             # 공통 유틸리티 (접두사 _ = 비실행)
│   ├── env-utils.sh                    # 환경변수 파싱
│   ├── slack-common.sh                 # Slack 공통 함수
│   └── resolve-workflow.py             # 워크플로우 경로 해석
├── event/                              # Hook 이벤트 핸들러 (settings.json 등록)
│   ├── pre-tool-use/
│   │   ├── dangerous-command-guard.sh
│   │   ├── tdd-guard.sh
│   │   ├── workflow-transition-guard.sh
│   │   ├── workflow-agent-guard.sh
│   │   └── slack-ask.sh
│   └── stop/
│       └── workflow-auto-continue.sh
├── init/                               # 초기화/설정 스크립트 (alias 호출)
│   ├── init-workflow.sh
│   ├── init-claude.sh
│   ├── init-project.sh
│   ├── init-clear.sh
│   ├── init-sync.sh
│   └── git-config.sh
├── workflow/                           # 워크플로우 런타임 유틸리티
│   ├── update-state.sh
│   ├── banner.sh
│   └── info.sh
└── slack/                              # Slack 알림 (alias 호출)
    └── slack.sh
```

### 현재 프로젝트 Hook 설정

현재 `.claude/settings.json`에 등록된 Hook은 총 6개입니다: PreToolUse 5개, Stop 1개.

#### PreToolUse Hooks

##### 1. Slack 질문 알림 (AskUserQuestion)

```json
{
  "matcher": "AskUserQuestion",
  "hooks": [
    {
      "type": "command",
      "command": "bash .claude/hooks/event/pre-tool-use/slack-ask.sh",
      "async": true,
      "statusMessage": "Slack 알림 전송 중..."
    }
  ]
}
```

- **트리거**: AskUserQuestion 도구 호출 시
- **동작**: Slack으로 "사용자 입력 대기 중" 알림 전송
- **비동기**: async: true (도구 실행을 차단하지 않음)
- **스크립트**: `.claude/hooks/event/pre-tool-use/slack-ask.sh`
- **사전 조건**: `.workflow/registry.json`에 워크플로우 등록 필요
- **관련 스킬**: `workflow-plan` (PLAN 단계에서 사용자 승인 대기 시)

##### 2. 위험 명령어 차단 (Bash)

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "bash .claude/hooks/event/pre-tool-use/dangerous-command-guard.sh",
      "statusMessage": "위험 명령어 검사 중..."
    }
  ]
}
```

- **트리거**: Bash 도구 호출 시
- **동작**: `rm -rf`, `git reset --hard`, `git push --force` 등 위험 명령어 감지 시 실행 차단
- **동기**: 도구 실행을 차단할 수 있음
- **스크립트**: `.claude/hooks/event/pre-tool-use/dangerous-command-guard.sh`
- **관련 스킬**: `dangerous-command-guard`

##### 3. TDD 가드 (Write|Edit)

```json
{
  "matcher": "Write|Edit",
  "hooks": [
    {
      "type": "command",
      "command": "bash .claude/hooks/event/pre-tool-use/tdd-guard.sh",
      "statusMessage": "TDD 가드 검사 중..."
    }
  ]
}
```

- **트리거**: Write 또는 Edit 도구 호출 시
- **동작**: 테스트 없이 소스 파일을 수정하려는 시도 감지 시 경고
- **동기**: 경고만 표시 (차단하지 않음)
- **스크립트**: `.claude/hooks/event/pre-tool-use/tdd-guard.sh`
- **관련 스킬**: `tdd-guard-hook`

##### 4. 워크플로우 Phase 전이 검증 (Bash)

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "bash .claude/hooks/event/pre-tool-use/workflow-transition-guard.sh",
      "statusMessage": "워크플로우 전이 검증 중..."
    }
  ]
}
```

- **트리거**: Bash 도구 호출 시
- **동작**: 워크플로우 Phase 전이가 올바른 순서로 진행되는지 검증 (INIT -> PLAN -> WORK -> REPORT)
- **동기**: 잘못된 Phase 전이 시 차단 가능
- **스크립트**: `.claude/hooks/event/pre-tool-use/workflow-transition-guard.sh`
- **관련**: `.workflow/registry.json`의 워크플로우 상태 참조

##### 5. 워크플로우 에이전트 호출 검증 (Task)

```json
{
  "matcher": "Task",
  "hooks": [
    {
      "type": "command",
      "command": "bash .claude/hooks/event/pre-tool-use/workflow-agent-guard.sh",
      "statusMessage": "워크플로우 에이전트 검증 중..."
    }
  ]
}
```

- **트리거**: Task(서브에이전트) 도구 호출 시
- **동작**: 워크플로우 단계에 맞는 에이전트만 호출되는지 검증 (예: WORK 단계에서 planner 호출 차단)
- **동기**: 잘못된 에이전트 호출 시 차단 가능
- **스크립트**: `.claude/hooks/event/pre-tool-use/workflow-agent-guard.sh`
- **관련**: `.workflow/registry.json`의 워크플로우 상태 참조

#### Stop Hooks

##### 6. 워크플로우 자동 계속 (Stop)

```json
{
  "matcher": "",
  "hooks": [
    {
      "type": "command",
      "command": "bash .claude/hooks/event/stop/workflow-auto-continue.sh",
      "statusMessage": "워크플로우 자동 계속 확인 중..."
    }
  ]
}
```

- **트리거**: Claude 응답 완료 시 (Stop 이벤트)
- **동작**: 활성 워크플로우가 진행 중(INIT/WORK/REPORT phase)이면 자동 중단 차단
- **안전장치**: 연속 3회 차단 시 허용 (무한 루프 방지), PLAN phase 예외 (AskUserQuestion 대기 존중)
- **bypass**: `WORKFLOW_GUARD_DISABLE=1` 환경변수 또는 `.workflow/bypass` 파일
- **스크립트**: `.claude/hooks/event/stop/workflow-auto-continue.sh`
- **출력 형식**: `{"decision":"block","reason":"..."}`
- **관련**: `.workflow/registry.json`의 워크플로우 상태 참조

### 설정 구조

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "<도구명 또는 패턴>",
        "hooks": [
          {
            "type": "command",
            "command": "<실행할 명령어>",
            "async": false,
            "statusMessage": "<상태 메시지>"
          }
        ]
      }
    ]
  }
}
```

**주요 필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `matcher` | string | 도구 이름 매칭 패턴 (`\|`로 여러 도구 지정 가능) |
| `type` | string | `"command"` (셸 명령어 실행) |
| `command` | string | 실행할 셸 명령어 |
| `async` | boolean | 비동기 실행 여부 (기본값: false) |
| `statusMessage` | string | 실행 중 표시할 상태 메시지 |

### 새 Hook 추가 방법

1. **스크립트 작성**: `.claude/hooks/event/<이벤트>/` 디렉터리에 셸 스크립트 생성
2. **실행 권한 부여**: `chmod +x .claude/hooks/event/<이벤트>/<스크립트명>.sh`
3. **settings.json 등록**: `hooks.<이벤트>` 배열에 새 Hook 추가
4. **테스트**: 해당 도구 사용 시 Hook이 정상 동작하는지 확인

**예시: 새 PostToolUse Hook 추가**
```json
{
  "hooks": {
    "PreToolUse": [ ... ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/event/post-tool-use/post-bash-hook.sh",
            "statusMessage": "후처리 중..."
          }
        ]
      }
    ]
  }
}
```

---

## Hook 스크립트 목록

### 이벤트 핸들러 (settings.json 등록, 6개)

| 파일 | 역할 | 이벤트 | 매칭 도구 |
|------|------|--------|-----------|
| `.claude/hooks/event/pre-tool-use/slack-ask.sh` | Slack 질문 알림 전송 | PreToolUse | AskUserQuestion |
| `.claude/hooks/event/pre-tool-use/dangerous-command-guard.sh` | 위험 명령어 차단 | PreToolUse | Bash |
| `.claude/hooks/event/pre-tool-use/tdd-guard.sh` | TDD 원칙 위반 경고 | PreToolUse | Write, Edit |
| `.claude/hooks/event/pre-tool-use/workflow-transition-guard.sh` | 워크플로우 Phase 전이 검증 | PreToolUse | Bash |
| `.claude/hooks/event/pre-tool-use/workflow-agent-guard.sh` | 워크플로우 에이전트 호출 검증 | PreToolUse | Task |
| `.claude/hooks/event/stop/workflow-auto-continue.sh` | 워크플로우 자동 계속 (Stop 차단) | Stop | (전체) |

### 초기화/설정 스크립트 (alias 호출, 6개)

| 파일 | alias | 용도 |
|------|-------|------|
| `.claude/hooks/init/init-workflow.sh` | wf-init | 워크플로우 시작 |
| `.claude/hooks/init/init-claude.sh` | wf-claude | 사용자 환경 초기화 |
| `.claude/hooks/init/init-project.sh` | wf-project | 프로젝트 설정 |
| `.claude/hooks/init/init-clear.sh` | wf-clear | 워크플로우 삭제 |
| `.claude/hooks/init/init-sync.sh` | wf-sync | 설정 동기화 |
| `.claude/hooks/init/git-config.sh` | wf-git-config | Git 설정 |

### 워크플로우 유틸리티 (alias/내부 호출, 3개)

| 파일 | alias/호출 방식 | 용도 |
|------|----------------|------|
| `.claude/hooks/workflow/update-state.sh` | wf-state | 워크플로우 상태 관리 |
| `.claude/hooks/workflow/banner.sh` | Workflow | 배너 출력 |
| `.claude/hooks/workflow/info.sh` | wf-info | 워크플로우 정보 조회 |

### Slack 관련 (1개 + 공통 모듈)

| 파일 | 용도 |
|------|------|
| `.claude/hooks/slack/slack.sh` | Slack 완료 알림 (alias: wf-slack) |
| `.claude/hooks/_utils/slack-common.sh` | 공통 함수 라이브러리 |

### 공통 유틸리티 (2개)

| 파일 | 용도 |
|------|------|
| `.claude/hooks/_utils/env-utils.sh` | 환경변수 파싱 유틸리티 |
| `.claude/hooks/_utils/resolve-workflow.py` | 워크플로우 경로 해석 |

## 참고
- `.claude/hooks/` 디렉터리에서 각 Hook 스크립트 확인
- `.claude/settings.json`에서 현재 활성화된 Hooks 확인
- `dangerous-command-guard` 스킬 - 차단 패턴 상세 정보
- `tdd-guard-hook` 스킬 - TDD 가드 상세 정보

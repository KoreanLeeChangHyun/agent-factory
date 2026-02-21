---
name: hooks-guide
description: "Claude Code Hooks system usage guide. Covers hook events, execution timing, and how to add/modify hooks. Use for hook management: hook configuration review, hook addition/modification, PreToolUse hook behavior understanding. Triggers: 'hook', '훅', 'PreToolUse', 'PostToolUse', 'Hook 설정'."
license: "Apache-2.0"
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
.claude/hooks/                          # Hook thin wrappers (이벤트별 디렉터리)
├── pre-tool-use/
│   ├── hooks-self-guard.py             # -> scripts/guards/hooks_self_guard.py
│   ├── dangerous-command-guard.py      # -> scripts/guards/dangerous_command_guard.py
│   ├── workflow-transition-guard.py    # -> scripts/guards/workflow_transition_guard.py
│   ├── workflow-agent-guard.py         # -> scripts/guards/workflow_agent_guard.py
│   ├── slack-ask.py                    # -> scripts/slack/slack_ask.py
│   └── task-history-sync.py            # history_sync.py 호출 (인라인)
├── stop/
│   └── workflow-auto-continue.py       # -> scripts/guards/auto_continue_guard.py
└── subagent-stop/
    ├── usage-tracker.py                # -> scripts/workflow/sync/usage_sync.py
    ├── completion-notify.py            # -> scripts/workflow/hooks/completion_notify.py
    └── history-sync-trigger.py         # history_sync.py 호출 (인라인)

.claude/scripts/                        # 실제 로직 스크립트
├── utils/                              # 공통 유틸리티
│   ├── env_utils.py                    # 환경변수 파싱
│   ├── slack_common.py                 # Slack 공통 함수
│   └── resolve-workflow.py             # 워크플로우 경로 해석
├── guards/                             # 가드 스크립트
│   ├── hooks_self_guard.py
│   ├── dangerous_command_guard.py
│   ├── workflow_transition_guard.py
│   ├── workflow_agent_guard.py
│   └── auto_continue_guard.py
├── init/                               # 초기화/설정 스크립트 (alias 호출)
│   ├── init_workflow.py
│   ├── init_claude.py
│   ├── init_project.py
│   ├── init_clear.py
│   ├── git_config.py
│   ├── reload_prompt.py
│   └── cleanup_zombie.py
├── workflow/                           # 워크플로우 런타임 유틸리티
│   ├── state/                         # 상태 관리
│   │   ├── update_state.py
│   │   └── fsm-transitions.json
│   ├── banner/                        # 배너 출력
│   │   ├── step_start_banner.sh
│   │   ├── step_change_banner.sh
│   │   └── step_end_banner.sh
│   ├── sync/                          # 동기화 및 레지스트리
│   │   ├── sync_code.py
│   │   ├── history_sync.py
│   │   ├── registry.py
│   │   ├── archive_workflow.py
│   │   └── usage_sync.py
│   ├── hooks/                         # Hook 스크립트
│   │   └── completion_notify.py
│   └── data/                          # 정적 데이터
│       └── help.txt
└── slack/                              # Slack 알림 (alias 호출)
    ├── slack_notify.py
    └── slack_ask.py
```

### 현재 프로젝트 Hook 설정

현재 `.claude/settings.json`에 등록된 Hook은 총 5개입니다: PreToolUse 4개, Stop 1개.

#### PreToolUse Hooks

##### 1. Slack 질문 알림 (AskUserQuestion)

```json
{
  "matcher": "AskUserQuestion",
  "hooks": [
    {
      "type": "command",
      "command": "python3 .claude/hooks/pre-tool-use/slack-ask.py",
      "async": true,
      "statusMessage": "Slack 알림 전송 중..."
    }
  ]
}
```

- **트리거**: AskUserQuestion 도구 호출 시
- **동작**: Slack으로 "사용자 입력 대기 중" 알림 전송
- **비동기**: async: true (도구 실행을 차단하지 않음)
- **스크립트**: `.claude/hooks/pre-tool-use/slack-ask.py` (thin wrapper -> `.claude/scripts/slack/slack_ask.py`)
- **사전 조건**: `.workflow/registry.json`에 워크플로우 등록 필요
- **관련 스킬**: `workflow-plan` (PLAN 단계에서 사용자 승인 대기 시)

##### 2. 위험 명령어 차단 (Bash)

```json
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
```

- **트리거**: Bash 도구 호출 시
- **동작**: `rm -rf`, `git reset --hard`, `git push --force` 등 위험 명령어 감지 시 실행 차단
- **동기**: 도구 실행을 차단할 수 있음
- **스크립트**: `.claude/hooks/pre-tool-use/dangerous-command-guard.py` (thin wrapper -> `.claude/scripts/guards/dangerous_command_guard.py`)
- **관련 스킬**: `dangerous-command-guard`

##### 3. 워크플로우 Phase 전이 검증 (Bash)

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python3 .claude/hooks/pre-tool-use/workflow-transition-guard.py",
      "statusMessage": "워크플로우 전이 검증 중..."
    }
  ]
}
```

- **트리거**: Bash 도구 호출 시
- **동작**: 워크플로우 Phase 전이가 올바른 순서로 진행되는지 검증 (INIT -> PLAN -> WORK -> REPORT)
- **동기**: 잘못된 Phase 전이 시 차단 가능
- **스크립트**: `.claude/hooks/pre-tool-use/workflow-transition-guard.py` (thin wrapper -> `.claude/scripts/guards/workflow_transition_guard.py`)
- **관련**: `.workflow/registry.json`의 워크플로우 상태 참조

##### 4. 워크플로우 에이전트 호출 검증 (Task)

```json
{
  "matcher": "Task",
  "hooks": [
    {
      "type": "command",
      "command": "python3 .claude/hooks/pre-tool-use/workflow-agent-guard.py",
      "statusMessage": "워크플로우 에이전트 검증 중..."
    }
  ]
}
```

- **트리거**: Task(서브에이전트) 도구 호출 시
- **동작**: 워크플로우 단계에 맞는 에이전트만 호출되는지 검증 (예: WORK 단계에서 planner 호출 차단)
- **동기**: 잘못된 에이전트 호출 시 차단 가능
- **스크립트**: `.claude/hooks/pre-tool-use/workflow-agent-guard.py` (thin wrapper -> `.claude/scripts/guards/workflow_agent_guard.py`)
- **관련**: `.workflow/registry.json`의 워크플로우 상태 참조

#### Stop Hooks

##### 5. 워크플로우 자동 계속 (Stop)

```json
{
  "matcher": "",
  "hooks": [
    {
      "type": "command",
      "command": "python3 .claude/hooks/stop/workflow-auto-continue.py",
      "statusMessage": "워크플로우 자동 계속 확인 중..."
    }
  ]
}
```

- **트리거**: Claude 응답 완료 시 (Stop 이벤트)
- **동작**: 활성 워크플로우가 진행 중(INIT/WORK/REPORT phase)이면 자동 중단 차단
- **안전장치**: 연속 3회 차단 시 허용 (무한 루프 방지), PLAN phase 예외 (AskUserQuestion 대기 존중)
- **bypass**: `WORKFLOW_GUARD_DISABLE=1` 환경변수 또는 `.workflow/bypass` 파일
- **스크립트**: `.claude/hooks/stop/workflow-auto-continue.py` (thin wrapper -> `.claude/scripts/guards/auto_continue_guard.py`)
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

1. **로직 스크립트 작성**: `.claude/scripts/<적절한-디렉터리>/` 에 셸 스크립트 생성
2. **thin wrapper 작성**: `.claude/hooks/<이벤트>/` 에 thin wrapper 생성 (scripts/ 호출)
3. **실행 권한 부여**: `chmod +x` (로직 스크립트 + thin wrapper 모두)
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
            "command": "python3 .claude/hooks/post-tool-use/post-bash-hook.py",
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

### 이벤트 핸들러 (settings.json 등록, thin wrapper)

| thin wrapper | 실제 로직 | 역할 | 이벤트 | 매칭 도구 |
|------|------|--------|-----------|-----------|
| `.claude/hooks/pre-tool-use/hooks-self-guard.py` | `.claude/scripts/guards/hooks_self_guard.py` | hooks/scripts 자기 보호 | PreToolUse | Write, Edit, Bash |
| `.claude/hooks/pre-tool-use/slack-ask.py` | `.claude/scripts/slack/slack_ask.py` | Slack 질문 알림 전송 | PreToolUse | AskUserQuestion |
| `.claude/hooks/pre-tool-use/dangerous-command-guard.py` | `.claude/scripts/guards/dangerous_command_guard.py` | 위험 명령어 차단 | PreToolUse | Bash |
| `.claude/hooks/pre-tool-use/workflow-transition-guard.py` | `.claude/scripts/guards/workflow_transition_guard.py` | 워크플로우 Phase 전이 검증 | PreToolUse | Bash |
| `.claude/hooks/pre-tool-use/workflow-agent-guard.py` | `.claude/scripts/guards/workflow_agent_guard.py` | 워크플로우 에이전트 호출 검증 | PreToolUse | Task |
| `.claude/hooks/stop/workflow-auto-continue.py` | `.claude/scripts/guards/auto_continue_guard.py` | 워크플로우 자동 계속 (Stop 차단) | Stop | (전체) |

### 초기화/설정 스크립트 (슬래시 커맨드로 호출)

| 파일 | 슬래시 커맨드 | 용도 |
|------|-------------|------|
| `.claude/scripts/init/init_workflow.py` | `/init:workflow` | 워크플로우 시작 |
| `.claude/scripts/init/init_claude.py` | `/init:claude` | 사용자 환경 초기화 |
| `.claude/scripts/init/init_project.py` | `/init:project` | 프로젝트 설정 |
| `.claude/scripts/init/init_clear.py` | `/init:clear` | 워크플로우 삭제 |
| `.claude/scripts/workflow/sync/sync_code.py` | `/sync:code` | 설정 동기화 |
| `.claude/scripts/init/git_config.py` | `/git:config` | Git 설정 |

### 워크플로우 유틸리티

| 파일 | 호출 방식 | 용도 |
|------|----------|------|
| `.claude/scripts/workflow/state/update_state.py` | `python3` 직접 호출 | 워크플로우 상태 관리 |
| `.claude/scripts/workflow/banner/step_start_banner.sh` | `step-start` alias | 배너 출력 (Phase 시작) |
| `.claude/scripts/workflow/banner/step_change_banner.sh` | `step-change` alias | 배너 출력 (상태 전이 시각화) |
| `.claude/scripts/workflow/banner/step_end_banner.sh` | `step-end` alias | 배너 출력 (Phase 완료) |

### Slack 관련

| 파일 | 용도 |
|------|------|
| `.claude/scripts/slack/slack_notify.py` | Slack 완료 알림 |
| `.claude/scripts/utils/slack_common.py` | 공통 함수 라이브러리 |

### 공통 유틸리티

| 파일 | 용도 |
|------|------|
| `.claude/scripts/utils/env_utils.py` | 환경변수 파싱 유틸리티 |
| `.claude/scripts/utils/resolve-workflow.py` | 워크플로우 경로 해석 |

## 참고
- `.claude/hooks/` 디렉터리에서 thin wrapper Hook 스크립트 확인
- `.claude/scripts/` 디렉터리에서 실제 로직 스크립트 확인
- `.claude/settings.json`에서 현재 활성화된 Hooks 확인
- `dangerous-command-guard` 스킬 - 차단 패턴 상세 정보

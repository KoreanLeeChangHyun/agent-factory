---
name: workflow-system-hooks-guide
description: "Claude Code Hooks system usage guide and dangerous command blocking. Covers hook events, execution timing, how to add/modify hooks, and safety guard patterns (rm -rf, git reset --hard, git push --force). Use for hook management: hook configuration review, hook addition/modification, PreToolUse hook behavior understanding, dangerous command blocking. Triggers: 'hook', '훅', 'PreToolUse', 'PostToolUse', 'Hook 설정', 'rm -rf', 'git reset --hard', 'git push --force', '위험 명령어', 'dangerous command'."
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
.claude/hooks/                          # Hook 디스패처 (이벤트별 단일 파일)
├── dispatcher.py                       # 공통 디스패치 유틸리티 (플래그 로드, 프로세스 실행)
├── pre-tool-use.py                     # PreToolUse 이벤트 디스패처
└── subagent-stop.py                    # SubagentStop 이벤트 디스패처

.claude/scripts/                        # 실제 로직 스크립트
├── banner/                             # 배너 출력
│   ├── flow_claude_banner.sh           # 워크플로우 시작/종료 배너
│   ├── flow_phase_banner.sh            # WORK 페이즈 배너
│   ├── flow_step_banner.sh             # 스텝 시작/종료 배너
│   └── flow_update_banner.sh           # 상태 전이 배너
├── data/                               # 정적 데이터
│   ├── colors.sh                       # 터미널 색상 상수 (shell)
│   └── constants.py                    # 통합 상수 (FSM, 패턴, 매핑)
├── flow/                               # 워크플로우 흐름 제어
│   ├── initialization.py               # 워크플로우 초기화
│   ├── finalization.py                 # 워크플로우 마무리
│   ├── update_state.py                 # 상태 전이
│   ├── reload_prompt.py                # 프롬프트 리로드
│   └── garbage_collect.py              # 좀비 워크플로우 정리
├── guards/                             # 가드 스크립트
│   ├── hooks_self_guard.py             # hooks/scripts 자기 보호
│   └── dangerous_command_guard.py      # 위험 명령어 차단
├── common.py                           # 공통 함수 + 환경변수 파싱 + 워크플로우 해석
├── git/                                # Git 관련
│   └── git_config.py                   # Git config 자동 설정
├── slack/                              # Slack 알림
│   ├── slack_ask.py                    # Slack 질문 알림
│   ├── slack_common.py                 # Slack 공통 함수
│   └── slack_notify.py                 # Slack 완료 알림
├── statusline.py                       # CLI 하단 상태줄
└── sync/                               # 동기화
    ├── catalog_sync.py                 # 스킬 카탈로그 동기화
    ├── history_sync.py                 # 작업 내역 동기화
    └── usage_sync.py                   # 토큰 사용량 추적 (track/batch 서브커맨드)
```

### 현재 프로젝트 Hook 설정

현재 `.claude/settings.json`에 등록된 Hook은 총 3개입니다: SessionStart 1개, PreToolUse 1개 (디스패처), SubagentStop 1개 (디스패처).

#### SessionStart Hook

##### 1. 히스토리 동기화

```json
{
  "matcher": "startup|resume|compact",
  "hooks": [
    {
      "type": "command",
      "command": "python3 -u .claude/scripts/sync/history_sync.py sync && python3 -u .claude/scripts/sync/history_sync.py archive",
      "timeout": 30,
      "async": true
    }
  ]
}
```

- **트리거**: 세션 시작/재개/컴팩트 시
- **동작**: 작업 내역 동기화 및 아카이브
- **비동기**: async: true (세션 시작을 차단하지 않음)
- **스크립트**: `.claude/scripts/sync/history_sync.py`

#### PreToolUse Hook (디스패처)

##### 2. Pre-tool-use 디스패처

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "python3 -u .claude/hooks/pre-tool-use.py",
      "statusMessage": "pre-tool-use 디스패처 실행 중..."
    }
  ]
}
```

단일 디스패처가 tool_name에 따라 라우팅합니다:

| 도구 | 가드 스크립트 | 동작 | 모드 |
|------|-------------|------|------|
| Write, Edit, Bash | `guards/hooks_self_guard.py` | hooks/scripts 자기 보호 | sync (차단 가능) |
| AskUserQuestion | `slack/slack_ask.py` | Slack 질문 알림 전송 | async |
| Bash | `guards/dangerous_command_guard.py` | 위험 명령어 차단 | sync (차단 가능) |

- **플래그 제어**: `.claude.env`의 `HOOK_*` 환경변수로 개별 가드 활성화/비활성화

#### SubagentStop Hook (디스패처)

##### 3. Subagent-stop 디스패처

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "python3 -u .claude/hooks/subagent-stop.py",
      "timeout": 30,
      "statusMessage": "subagent-stop 디스패처 실행 중..."
    }
  ]
}
```

서브에이전트 종료 시 실행:

| 핸들러 | 스크립트 | 동작 | 모드 |
|--------|---------|------|------|
| usage-tracker | `sync/usage_sync.py` | 토큰 사용량 추적 | async |
| history-sync-trigger | (인라인) | history_sync.py 동기화 트리거 | async |

- **플래그 제어**: `.claude.env`의 `HOOK_*` 환경변수로 개별 핸들러 활성화/비활성화

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

### 이벤트 디스패처 (settings.json 등록)

| 디스패처 | 이벤트 | 라우팅 대상 |
|----------|--------|------------|
| `.claude/hooks/pre-tool-use.py` | PreToolUse | hooks_self_guard, slack_ask, dangerous_command_guard |
| `.claude/hooks/subagent-stop.py` | SubagentStop | usage_sync, history_sync_trigger (인라인) |

### 가드 스크립트 (디스패처에서 호출)

| 파일 | 역할 | 매칭 도구 |
|------|------|-----------|
| `.claude/scripts/guards/hooks_self_guard.py` | hooks/scripts 자기 보호 | Write, Edit, Bash |
| `.claude/scripts/guards/dangerous_command_guard.py` | 위험 명령어 차단 | Bash |

## Dangerous Command Guard 상세

위험한 시스템/Git 명령어를 PreToolUse Hook으로 감지하고 차단하는 안전 가드입니다.

### 차단 대상 패턴

| 카테고리 | 패턴 | 위험도 | 설명 |
|----------|------|--------|------|
| 파일 삭제 | `rm -rf /`, `rm -rf ~`, `rm -rf .` | Critical | 루트/홈/현재 디렉토리 전체 삭제 |
| 파일 삭제 | `rm -rf *` (루트 경로) | Critical | 와일드카드 전체 삭제 |
| Git 리셋 | `git reset --hard` | High | 커밋되지 않은 변경사항 전체 삭제 |
| Git 푸시 | `git push --force`, `git push -f` | High | 원격 히스토리 덮어쓰기 |
| Git 클린 | `git clean -f`, `git clean -fd` | High | 추적되지 않는 파일 전체 삭제 |
| Git 브랜치 | `git branch -D` (main/master) | High | 주요 브랜치 강제 삭제 |
| Git 체크아웃 | `git checkout .`, `git restore .` | High | 모든 변경사항 되돌리기 |
| DB 삭제 | `DROP TABLE`, `DROP DATABASE` | Critical | 데이터베이스/테이블 삭제 |
| 권한 변경 | `chmod 777` | Medium | 과도한 권한 부여 |
| 디스크 | `mkfs`, `dd if=` | Critical | 디스크 포맷/덮어쓰기 |

### 화이트리스트

다음 경로/패턴은 차단하지 않습니다:
- `/tmp/` 하위 디렉토리의 `rm -rf` (임시 파일 정리)
- `.workflow/` 하위의 `rm -rf` (워크플로우 정리)
- `git push --force-with-lease` (안전한 force push)

### 안전한 대안 제시

차단 시 다음과 같은 대안을 제시합니다:

| 위험 명령어 | 안전한 대안 |
|------------|-----------|
| `rm -rf /path` | `rm -ri /path` (대화형 삭제) 또는 파일 목록 먼저 확인 |
| `git reset --hard` | `git stash` (변경사항 임시 저장) |
| `git push --force` | `git push --force-with-lease` (안전한 force push) |
| `git clean -f` | `git clean -n` (드라이런으로 삭제 대상 확인) |
| `git checkout .` | `git stash` (변경사항 임시 저장) |
| `chmod 777` | `chmod 755` 또는 필요한 최소 권한만 부여 |

### zsh Read-Only 변수 호환성

현재 셸이 **zsh**인 환경에서, Claude Code의 Bash 도구는 zsh로 명령을 실행합니다. zsh에는 대입이 불가능한 read-only 내장 변수가 존재하며, LLM이 생성한 bash 코드에서 이 변수명을 사용하면 `read-only variable` 에러가 발생합니다.

#### 금지 변수명

| 변수명 | zsh에서의 역할 | 위험도 |
|--------|---------------|--------|
| `status` | `$?`(직전 명령 종료 코드)의 별칭 | High |
| `pipestatus` | 파이프라인 종료 코드 배열 | High |
| `ERRNO` | 시스템 에러 번호 | High |
| `ZSH_SUBSHELL` | 서브셸 깊이 | Medium |
| `HISTCMD` | 현재 히스토리 이벤트 번호 | Medium |

#### 안전한 대체 변수명

| 금지 변수명 | 안전한 대체 변수명 |
|------------|-------------------|
| `status` | `file_status`, `cmd_status`, `result_status`, `exit_code` |
| `pipestatus` | `pipe_results`, `pipe_exit_codes` |
| `ERRNO` | `err_code`, `error_num` |
| `ZSH_SUBSHELL` | `subshell_depth`, `shell_level` |
| `HISTCMD` | `hist_num`, `history_id` |

#### 예시

```bash
# 잘못된 예시 (zsh에서 에러 발생)
for f in file1 file2; do
  status=$(git diff --name-only "$f")  # read-only variable: status
done

# 올바른 예시
for f in file1 file2; do
  diff_result=$(git diff --name-only "$f")
  file_status=$(git status --short "$f")
done
```

```bash
# 잘못된 예시
pipestatus=(0 1 0)  # read-only variable: pipestatus

# 올바른 예시
pipe_results=(0 1 0)
```

---

### 초기화/설정 스크립트

| 파일 | 호출 방식 | 용도 |
|------|----------|------|
| `.claude/scripts/flow/initialization.py` | `/init:workflow` 커맨드 | 워크플로우 초기화 |
| `.claude/scripts/git/git_config.py` | `/git:config` 커맨드 | Git 설정 |

### 워크플로우 유틸리티

| 파일 | 호출 방식 | 용도 |
|------|----------|------|
| `.claude/scripts/flow/update_state.py` | `flow-update` alias | 워크플로우 상태 관리 |
| `.claude/scripts/flow/finalization.py` | `flow-finish` alias | 워크플로우 마무리 처리 |
| `.claude/scripts/flow/reload_prompt.py` | `flow-reload` alias | 프롬프트 리로드 |
| `.claude/scripts/flow/garbage_collect.py` | `flow-gc` alias | 좀비 워크플로우 정리 |
| `.claude/scripts/banner/flow_claude_banner.sh` | `flow-claude` alias | 워크플로우 시작/종료 배너 |
| `.claude/scripts/banner/flow_step_banner.sh` | `flow-step` alias | 스텝 시작/종료 배너 |
| `.claude/scripts/banner/flow_phase_banner.sh` | `flow-phase` alias | WORK 페이즈 배너 |
| `.claude/scripts/banner/flow_update_banner.sh` | `flow-update` alias (update_state.py와 공유) | 상태 전이 시각화 배너 |

### 동기화

| 파일 | 용도 |
|------|------|
| `.claude/scripts/sync/usage_sync.py` | 토큰 사용량 추적 (track/batch 서브커맨드) |
| `.claude/scripts/sync/history_sync.py` | 작업 내역 동기화/아카이브 |
| `.claude/scripts/sync/catalog_sync.py` | 스킬 카탈로그 동기화 |

### Slack 관련

| 파일 | 용도 |
|------|------|
| `.claude/scripts/slack/slack_ask.py` | Slack 질문 알림 |
| `.claude/scripts/slack/slack_notify.py` | Slack 완료 알림 |
| `.claude/scripts/slack/slack_common.py` | 공통 함수 라이브러리 |

### 공통 유틸리티

| 파일 | 용도 |
|------|------|
| `.claude/scripts/common.py` | 공통 함수 + 환경변수 파싱 + 워크플로우 해석 |
| `.claude/scripts/statusline.py` | CLI 하단 상태줄 |

## 참고
- `.claude/hooks/` 디렉터리에서 thin wrapper Hook 스크립트 확인
- `.claude/scripts/` 디렉터리에서 실제 로직 스크립트 확인
- `.claude/settings.json`에서 현재 활성화된 Hooks 확인

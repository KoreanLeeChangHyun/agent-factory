# Hooks 시스템 가이드 (상세)

Claude Code Hooks 시스템 사용법과 현재 프로젝트의 Hook 설정 상세.

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
| `SubagentStop` | 서브에이전트 종료 시 | 서브에이전트 작업 완료 후 |

### 디렉터리 구조

```
.claude.workflow/hooks/                          # Hook 디스패처 (이벤트별 단일 파일)
├── dispatcher.py                       # 공통 디스패치 유틸리티 (플래그 로드, 프로세스 실행)
├── pre-tool-use.py                     # PreToolUse 이벤트 디스패처
├── post-tool-use.py                    # PostToolUse 이벤트 디스패처
└── subagent-stop.py                    # SubagentStop 이벤트 디스패처

.claude.workflow/scripts/                        # 실제 로직 스크립트
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

현재 `.claude/settings.json`에 등록된 Hook은 총 5개: SessionStart 2개, PreToolUse 1개 (디스패처), PostToolUse 1개 (디스패처), SubagentStop 1개 (디스패처).

#### SessionStart Hook

##### 1. 히스토리 동기화

```json
{
  "matcher": "startup|resume|compact",
  "hooks": [
    {
      "type": "command",
      "command": "python3 -u .claude.workflow/scripts/sync/history_sync.py sync && python3 -u .claude.workflow/scripts/sync/history_sync.py archive",
      "timeout": 30,
      "async": true
    }
  ]
}
```

- **트리거**: 세션 시작/재개/컴팩트 시
- **동작**: 작업 내역 동기화 및 아카이브
- **비동기**: async: true (세션 시작을 차단하지 않음)

##### 2. 워크플로우 세션 전용 프롬프트 주입

```json
{
  "matcher": "startup|resume|compact",
  "hooks": [
    {
      "type": "command",
      "command": "python3 -u .claude.workflow/scripts/hooks/session_start_system_prompt.py",
      "timeout": 5
    }
  ]
}
```

- **트리거**: 세션 시작/재개/컴팩트 시
- **동작**: 환경변수(`TMUX_PANE` + 세션 이름 T-* 여부)로 세션 유형을 판별하여 워크플로우 세션인 경우에만 system-prompt-wf.xml을 stdout에 출력 → 세션 컨텍스트에 자동 주입
- **동기**: async 미지정 (동기 실행으로 stdout이 컨텍스트에 주입되도록 보장)
- **분기 조건**:
  - `TMUX_PANE` 환경변수 있고 세션 이름이 `T-` 접두사로 시작 → `.claude.workflow/prompt/system-prompt-wf.xml`
  - 그 외(메인 세션) → 주입 없음 (CLAUDE.md + `.claude/rules/workflow.md`가 담당)

#### PreToolUse Hook (디스패처)

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "python3 -u .claude.workflow/hooks/pre-tool-use.py",
      "statusMessage": "pre-tool-use 디스패처 실행 중..."
    }
  ]
}
```

단일 디스패처가 tool_name에 따라 라우팅:

| 도구 | 가드 스크립트 | 동작 | 모드 |
|------|-------------|------|------|
| Write, Edit, Bash | `guards/hooks_self_guard.py` | hooks/scripts 자기 보호 | sync (차단 가능) |
| AskUserQuestion | `slack/slack_ask.py` | Slack 질문 알림 전송 | async |
| Bash | `guards/dangerous_command_guard.py` | 위험 명령어 차단 | sync (차단 가능) |

- **플래그 제어**: `.claude.workflow/.env`의 `HOOK_*` 환경변수로 개별 가드 활성화/비활성화

#### PostToolUse Hook (디스패처)

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "python3 -u .claude.workflow/hooks/post-tool-use.py",
      "timeout": 30,
      "async": true,
      "statusMessage": "post-tool-use 디스패처 실행 중..."
    }
  ]
}
```

| 도구 | 핸들러 | 스크립트 | 동작 | 모드 |
|------|--------|----------|------|------|
| Write, Edit | catalog_sync | `.claude.workflow/scripts/sync/catalog_sync.py` | SKILL.md 변경 시 카탈로그 자동 갱신 | async |
| Bash | session_cleanup | 인라인(`post-tool-use.py` 내부) | `flow-claude end` 감지 시 세션 지연 종료 | async |

- **플래그 제어**: `.claude.workflow/.env`의 `HOOK_CATALOG_SYNC` 환경변수로 핸들러 활성화/비활성화

#### SubagentStop Hook (디스패처)

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "python3 -u .claude.workflow/hooks/subagent-stop.py",
      "timeout": 10,
      "statusMessage": "subagent-stop 디스패처 실행 중..."
    }
  ]
}
```

| 핸들러 | 스크립트 | 동작 | 모드 |
|--------|---------|------|------|
| usage-tracker | `.claude.workflow/scripts/sync/usage_sync.py` | 토큰 사용량 추적 | async |

> **비고**: history-sync-trigger는 `finalization.py`에서 직접 호출하므로 SubagentStop에서는 비활성

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

| 필드 | 타입 | 설명 |
|------|------|------|
| `matcher` | string | 도구 이름 매칭 패턴 (`\|`로 여러 도구 지정 가능) |
| `type` | string | `"command"` (셸 명령어 실행) |
| `command` | string | 실행할 셸 명령어 |
| `async` | boolean | 비동기 실행 여부 (기본값: false) |
| `statusMessage` | string | 실행 중 표시할 상태 메시지 |

### 새 Hook 추가 방법

1. **로직 스크립트 작성**: `.claude.workflow/scripts/<적절한-디렉터리>/`에 Python 스크립트 생성
2. **thin wrapper 작성**: `.claude.workflow/hooks/<event>.py` 플랫 파일 패턴으로 디스패처 생성
3. **실행 권한 부여**: `chmod +x` (로직 스크립트 + thin wrapper 모두)
4. **settings.json 등록**: `hooks.<이벤트>` 배열에 새 Hook 추가
5. **테스트**: 해당 도구 사용 시 Hook이 정상 동작하는지 확인

---

## Dangerous Command Guard 상세

위험한 시스템/Git 명령어를 PreToolUse Hook으로 감지하고 차단하는 안전 가드.

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

- `/tmp/` 하위 디렉토리의 `rm -rf` (임시 파일 정리)
- `.workflow/` 하위의 `rm -rf` (워크플로우 정리)
- `git push --force-with-lease` (안전한 force push)

### 안전한 대안 제시

| 위험 명령어 | 안전한 대안 |
|------------|-----------|
| `rm -rf /path` | `rm -ri /path` (대화형 삭제) 또는 파일 목록 먼저 확인 |
| `git reset --hard` | `git stash` (변경사항 임시 저장) |
| `git push --force` | `git push --force-with-lease` |
| `git clean -f` | `git clean -n` (드라이런으로 삭제 대상 확인) |
| `git checkout .` | `git stash` (변경사항 임시 저장) |
| `chmod 777` | `chmod 755` 또는 필요한 최소 권한만 부여 |

### zsh Read-Only 변수 호환성

zsh에서 Claude Code의 Bash 도구는 zsh로 명령을 실행합니다. 다음 변수명은 read-only로 대입 불가:

| 변수명 | zsh에서의 역할 | 안전한 대체 변수명 |
|--------|---------------|-------------------|
| `status` | `$?`(직전 명령 종료 코드)의 별칭 | `file_status`, `cmd_status`, `exit_code` |
| `pipestatus` | 파이프라인 종료 코드 배열 | `pipe_results`, `pipe_exit_codes` |
| `ERRNO` | 시스템 에러 번호 | `err_code`, `error_num` |
| `ZSH_SUBSHELL` | 서브셸 깊이 | `subshell_depth`, `shell_level` |
| `HISTCMD` | 현재 히스토리 이벤트 번호 | `hist_num`, `history_id` |

```bash
# 잘못된 예시 (zsh에서 에러 발생)
status=$(git diff --name-only "$f")  # read-only variable: status

# 올바른 예시
diff_result=$(git diff --name-only "$f")
file_status=$(git status --short "$f")
```

---

## Hook 스크립트 목록

### 이벤트 디스패처

| 디스패처 | 이벤트 | 라우팅 대상 |
|----------|--------|------------|
| `.claude.workflow/hooks/pre-tool-use.py` | PreToolUse | hooks_self_guard, slack_ask, dangerous_command_guard |
| `.claude.workflow/hooks/post-tool-use.py` | PostToolUse | catalog_sync, session_cleanup |
| `.claude.workflow/hooks/subagent-stop.py` | SubagentStop | usage_sync |

### 가드 스크립트

| 파일 | 역할 | 매칭 도구 |
|------|------|-----------|
| `.claude.workflow/scripts/guards/hooks_self_guard.py` | hooks/scripts 자기 보호 | Write, Edit, Bash |
| `.claude.workflow/scripts/guards/dangerous_command_guard.py` | 위험 명령어 차단 | Bash |

### 워크플로우 유틸리티

| 파일 | 호출 방식 | 용도 |
|------|----------|------|
| `.claude.workflow/scripts/flow/update_state.py` | `flow-update` alias | 워크플로우 상태 관리 |
| `.claude.workflow/scripts/flow/finalization.py` | `flow-finish` alias | 워크플로우 마무리 처리 |
| `.claude.workflow/scripts/flow/reload_prompt.py` | `flow-reload` alias | 프롬프트 리로드 |
| `.claude.workflow/scripts/flow/garbage_collect.py` | `flow-gc` alias | 좀비 워크플로우 정리 |
| `.claude.workflow/scripts/banner/flow_claude_banner.sh` | `flow-claude` alias | 워크플로우 시작/종료 배너 |
| `.claude.workflow/scripts/banner/flow_step_banner.sh` | `flow-step` alias | 스텝 시작/종료 배너 |
| `.claude.workflow/scripts/banner/flow_phase_banner.sh` | `flow-phase` alias | WORK 페이즈 배너 |
| `.claude.workflow/scripts/banner/flow_update_banner.sh` | `flow-update` alias | 상태 전이 시각화 배너 |

## 참고

- `.claude.workflow/hooks/` — thin wrapper Hook 스크립트
- `.claude.workflow/scripts/` — 실제 로직 스크립트
- `.claude/settings.json` — 현재 활성화된 Hooks 확인

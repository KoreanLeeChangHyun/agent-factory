---
name: reference-claude-code
description: "Use when you need Claude Code configuration reference: hooks event types and JSON schemas, settings.json keys and their types, built-in slash commands, CLI flags, keybindings, MCP integration, skills/agents frontmatter, or any Claude Code-specific API/behavior details."
license: Apache-2.0
---

# Claude Code Reference

Claude Code 공식 문서 기반 레퍼런스. 설정·훅·커맨드·키바인딩·MCP 연동의 전체 스펙을 다룬다.

공식 문서 인덱스: [https://code.claude.com/docs/llms.txt](https://code.claude.com/docs/llms.txt)

---

## 1. Settings (settings.json)

**파일 위치 및 스코프**

| 스코프 | 위치 | 팀 공유 |
|--------|------|---------|
| Managed | 시스템 레벨 `managed-settings.json` | 예 (IT 배포) |
| User | `~/.claude/settings.json` | 아니오 |
| Project | `.claude/settings.json` | 예 (git 커밋) |
| Local | `.claude/settings.local.json` | 아니오 |

우선순위: Managed > User > Project > Local

참고: [https://code.claude.com/docs/en/settings](https://code.claude.com/docs/en/settings)

### 일반 설정 키

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `model` | string | 시스템 기본 | 기본 모델 오버라이드 (예: `claude-sonnet-4-6`) |
| `language` | string | English | Claude 응답 언어 |
| `outputStyle` | string | none | 시스템 프롬프트 스타일 조정 |
| `cleanupPeriodDays` | number | 30 | 비활성 세션 삭제 기준 일수 (0: 즉시 삭제) |
| `autoUpdatesChannel` | string | "latest" | 업데이트 채널: `stable` 또는 `latest` |
| `showTurnDuration` | boolean | true | 응답 시간 메트릭 표시 |
| `alwaysThinkingEnabled` | boolean | false | Extended Thinking 기본 활성화 |
| `plansDirectory` | string | `~/.claude/plans` | 플랜 파일 저장 위치 |
| `respectGitignore` | boolean | true | 파일 피커가 `.gitignore` 준수 |
| `companyAnnouncements` | array | none | 시작 시 랜덤 메시지 표시 |
| `spinnerVerbs` | object | 기본값 | 처리 중 스피너 텍스트 커스터마이즈 |
| `spinnerTipsEnabled` | boolean | true | 작업 중 팁 표시 |
| `terminalProgressBarEnabled` | boolean | true | 터미널 프로그레스 바 표시 |
| `disableAllHooks` | boolean | false | 모든 훅 비활성화 |
| `env` | object | - | 세션에 적용할 환경변수 (`{"KEY": "value"}`) |

### 권한 설정 (`permissions` 객체 내)

```json
{
  "permissions": {
    "allow": ["Bash(npm run lint)", "Read"],
    "ask": ["Bash(git push *)"],
    "deny": ["Read(./.env)"],
    "additionalDirectories": ["../docs/"],
    "defaultMode": "acceptEdits",
    "disableBypassPermissionsMode": "disable"
  }
}
```

`defaultMode` 옵션: `default` | `acceptEdits` | `plan` | `bypassPermissions`

**권한 규칙 패턴 문법:**
- `Bash(git *)` - git으로 시작하는 모든 bash 명령어
- `Read(./.env)` - 특정 파일 읽기 차단
- `Skill(deploy *)` - 특정 스킬 차단
- `MCPSearch` - MCP 검색 도구 차단

### 샌드박스 설정 (`sandbox` 객체 내)

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `sandbox.enabled` | boolean | false | Bash 샌드박싱 활성화 |
| `sandbox.autoAllowBashIfSandboxed` | boolean | true | 샌드박스 명령어 자동 승인 |
| `sandbox.excludedCommands` | array | none | 샌드박스 외부 실행 명령어 |
| `sandbox.network.allowedDomains` | array | none | 아웃바운드 도메인 화이트리스트 |
| `sandbox.network.allowLocalBinding` | boolean | false | localhost 바인딩 허용 (macOS) |

### 인증 및 프로바이더 설정

| 키 | 타입 | 설명 |
|----|------|------|
| `apiKeyHelper` | string | 인증 값 생성 스크립트 (`/bin/sh` 실행) |
| `forceLoginMethod` | string | 로그인 방법 제한: `claudeai` 또는 `console` |
| `forceLoginOrgUUID` | string | 로그인 시 조직 자동 선택 |
| `awsAuthRefresh` | string | AWS 자격증명 갱신 스크립트 |
| `awsCredentialExport` | string | AWS 자격증명 JSON 출력 스크립트 |
| `otelHeadersHelper` | string | OpenTelemetry 헤더 생성 스크립트 |

### MCP 서버 설정

| 키 | 타입 | 설명 |
|----|------|------|
| `enableAllProjectMcpServers` | boolean | 프로젝트 MCP 서버 전체 자동 승인 |
| `enabledMcpjsonServers` | array | 승인할 특정 MCP 서버 목록 |
| `disabledMcpjsonServers` | array | 거부할 특정 MCP 서버 목록 |
| `allowedMcpServers` | array | (Managed) MCP 서버 허용 목록 |
| `deniedMcpServers` | array | (Managed) MCP 서버 차단 목록 |

### 플러그인 설정

| 키 | 타입 | 설명 |
|----|------|------|
| `enabledPlugins` | object | 플러그인 활성화/비활성화 토글 |
| `extraKnownMarketplaces` | object | 추가 플러그인 소스 |
| `strictKnownMarketplaces` | array | (Managed) 마켓플레이스 소스 제한 |

### Attribution 설정 (`attribution` 객체 내)

```json
{
  "attribution": {
    "commit": "Generated with Claude Code",
    "pr": "Generated with Claude Code"
  }
}
```

---

## 2. Hooks

**위치**: `settings.json`의 `hooks` 키 내부 또는 Skill/Agent frontmatter

참고: [https://code.claude.com/docs/en/hooks](https://code.claude.com/docs/en/hooks)

### 이벤트 타입

**세션 이벤트**

| 이벤트 | 발생 시점 | Matcher |
|--------|---------|---------|
| `SessionStart` | 세션 시작/재개 | `startup`, `resume`, `clear`, `compact` |
| `SessionEnd` | 세션 종료 | `clear`, `logout`, `prompt_input_exit`, `other` |
| `InstructionsLoaded` | CLAUDE.md 로드 시 | 없음 |

**사용자 입력 이벤트**

| 이벤트 | 발생 시점 |
|--------|---------|
| `UserPromptSubmit` | 사용자 프롬프트 제출 전 |

**도구 실행 이벤트**

| 이벤트 | 발생 시점 | Matcher (도구명) |
|--------|---------|----------|
| `PreToolUse` | 도구 실행 전 | `Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `Agent`, `WebFetch`, `WebSearch`, `mcp__*` |
| `PostToolUse` | 도구 성공 후 | 동일 |
| `PostToolUseFailure` | 도구 실패 후 | 동일 |
| `PermissionRequest` | 권한 요청 시 | 동일 |

**에이전트 이벤트**

| 이벤트 | 발생 시점 | Matcher |
|--------|---------|---------|
| `SubagentStart` | 서브에이전트 생성 | `Bash`, `Explore`, `Plan`, 커스텀명 |
| `SubagentStop` | 서브에이전트 완료 | 동일 |
| `Stop` | 메인 에이전트 완료 | 없음 |
| `TeammateIdle` | 팀 멤버 대기 | 없음 |
| `TaskCompleted` | 작업 완료 | 없음 |

**시스템 이벤트**

| 이벤트 | Matcher |
|--------|---------|
| `Notification` | `permission_prompt`, `idle_prompt`, `auth_success`, `elicitation_dialog` |
| `ConfigChange` | `user_settings`, `project_settings`, `local_settings`, `policy_settings`, `skills` |
| `PreCompact` / `PostCompact` | `manual`, `auto` |
| `WorktreeCreate` / `WorktreeRemove` | 없음 |
| `Elicitation` / `ElicitationResult` | 없음 |

### Exit Code 의미

| Exit Code | 의미 |
|-----------|------|
| 0 | 성공. stdout JSON 파싱 후 처리 |
| 2 | 블로킹 에러. stderr가 에러 메시지로 사용 |
| 기타 | 비블로킹 에러 (실행 계속) |

**Exit Code 2의 이벤트별 효과:**
- `PreToolUse`: 도구 호출 차단
- `PermissionRequest`: 권한 거부
- `UserPromptSubmit`: 프롬프트 차단
- `Stop` / `SubagentStop`: Claude 계속 작동
- `ConfigChange`: 설정 변경 차단
- `Elicitation`: 요청 거부

### 공통 입력 JSON

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/current/working/dir",
  "permission_mode": "default|plan|acceptEdits|dontAsk|bypassPermissions",
  "hook_event_name": "EventName",
  "agent_id": "agent-id",
  "agent_type": "에이전트명"
}
```

### 공통 출력 JSON

```json
{
  "continue": true,
  "stopReason": "메시지",
  "suppressOutput": false,
  "systemMessage": "경고 메시지"
}
```

### Decision Control 패턴

**PreToolUse** (permissionDecision):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "설명",
    "updatedInput": {},
    "additionalContext": "추가컨텍스트"
  }
}
```

**UserPromptSubmit / PostToolUse / Stop / ConfigChange** (decision):
```json
{
  "decision": "block",
  "reason": "설명"
}
```

**PermissionRequest** (hookSpecificOutput.decision):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow|deny",
      "updatedInput": {},
      "message": "메시지"
    }
  }
}
```

### 훅 핸들러 타입

**Command Hook:**
```json
{
  "type": "command",
  "command": "./script.sh",
  "async": false,
  "timeout": 600,
  "statusMessage": "메시지",
  "once": true
}
```

**HTTP Hook:**
```json
{
  "type": "http",
  "url": "http://localhost:8080/hook",
  "headers": { "Authorization": "Bearer $TOKEN" },
  "allowedEnvVars": ["TOKEN"],
  "timeout": 30
}
```

**Prompt Hook:**
```json
{
  "type": "prompt",
  "prompt": "평가할 내용: $ARGUMENTS",
  "model": "claude-haiku",
  "timeout": 30
}
```

**Agent Hook:**
```json
{
  "type": "agent",
  "prompt": "검증: $ARGUMENTS",
  "model": "claude-haiku",
  "timeout": 60
}
```

### 훅 위치 및 범위

| 위치 | 범위 | 공유 |
|------|------|------|
| `~/.claude/settings.json` | 모든 프로젝트 | 아니오 |
| `.claude/settings.json` | 단일 프로젝트 | 예 (버전 관리) |
| `.claude/settings.local.json` | 단일 프로젝트 | 아니오 |
| Skill/Agent frontmatter | 컴포넌트 활성화 시 | 예 |

### Skill/Agent 훅 정의 (YAML frontmatter)

```yaml
---
name: secure-operations
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/security-check.sh"
---
```

---

## 3. Skills (스킬)

참고: [https://code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills)

### 파일 구조

```
.claude/skills/<skill-name>/
├── SKILL.md          # 필수 (frontmatter + 지침)
├── reference.md      # 선택 (상세 참조)
└── scripts/
    └── helper.py     # 선택 (실행 스크립트)
```

### Frontmatter 레퍼런스

```yaml
---
name: my-skill
description: "What and when"
argument-hint: "[issue-number]"
disable-model-invocation: true
user-invocable: false
allowed-tools: Read, Grep
model: claude-sonnet-4-6
context: fork
agent: Explore
hooks:
  PreToolUse: [...]
license: Apache-2.0
---
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `name` | 아니오 | 디렉터리명 사용 (소문자, 숫자, 하이픈, 최대 64자) |
| `description` | 권장 | Claude가 자동 호출 여부 결정에 사용 |
| `argument-hint` | 아니오 | 자동완성 힌트 (예: `[filename] [format]`) |
| `disable-model-invocation` | 아니오 | true: 수동 호출만 허용 |
| `user-invocable` | 아니오 | false: `/` 메뉴에서 숨김 |
| `allowed-tools` | 아니오 | 스킬 활성 시 승인 없이 사용 가능한 도구 |
| `model` | 아니오 | 스킬 활성 시 사용할 모델 |
| `context` | 아니오 | `fork`: 격리된 서브에이전트로 실행 |
| `agent` | 아니오 | `context: fork` 시 서브에이전트 타입 |
| `hooks` | 아니오 | 스킬 수명주기 훅 |

**호출 제어 매트릭스:**

| 설정 | 사용자 호출 | Claude 자동 호출 | 컨텍스트 로드 |
|------|------------|----------------|-------------|
| (기본) | 예 | 예 | 항상 (description만) |
| `disable-model-invocation: true` | 예 | 아니오 | 로드 안 됨 |
| `user-invocable: false` | 아니오 | 예 | 항상 (description만) |

### 문자열 치환

| 변수 | 설명 |
|------|------|
| `$ARGUMENTS` | 호출 시 전달된 모든 인자 |
| `$ARGUMENTS[N]` | N번째 인자 (0-based) |
| `$N` | `$ARGUMENTS[N]` 단축형 |
| `${CLAUDE_SESSION_ID}` | 현재 세션 ID |
| `${CLAUDE_SKILL_DIR}` | 스킬 디렉터리 절대경로 |

### Dynamic Context Injection

```yaml
---
name: pr-summary
context: fork
agent: Explore
---
## PR 컨텍스트
- diff: !`gh pr diff`
- 코멘트: !`gh pr view --comments`
```

`!`command`` 문법: 스킬 실행 전 쉘 명령어 실행 후 출력으로 대체

---

## 4. Bundled Skills (내장 스킬)

| 스킬 | 용도 |
|------|------|
| `/batch <instruction>` | 코드베이스 대규모 변경을 병렬 에이전트로 처리 |
| `/claude-api` | Claude API 레퍼런스 로드 (anthropic import 시 자동 활성화) |
| `/debug [description]` | 현재 세션 디버그 로그 분석 |
| `/loop [interval] <prompt>` | 인터벌 반복 프롬프트 실행 |
| `/simplify [focus]` | 변경 파일 품질 검토 후 수정 (3개 병렬 에이전트) |

---

## 5. Built-in Commands (내장 커맨드)

참고: [https://code.claude.com/docs/en/commands](https://code.claude.com/docs/en/commands)

| 커맨드 | 설명 |
|--------|------|
| `/add-dir <path>` | 세션에 작업 디렉터리 추가 |
| `/agents` | 에이전트 설정 관리 |
| `/btw <question>` | 대화 이력에 남기지 않고 빠른 질문 |
| `/clear` | 대화 이력 초기화 (별칭: `/reset`, `/new`) |
| `/compact [instructions]` | 대화 압축 |
| `/config` | 설정 인터페이스 열기 (별칭: `/settings`) |
| `/context` | 컨텍스트 사용량 시각화 |
| `/copy` | 마지막 응답 클립보드 복사 |
| `/diff` | 미커밋 변경사항 diff 뷰어 |
| `/doctor` | 설치 및 설정 진단 |
| `/effort [low\|medium\|high\|max\|auto]` | 모델 effort 레벨 설정 |
| `/export [filename]` | 대화 내보내기 |
| `/fork [name]` | 현재 지점에서 대화 분기 |
| `/help` | 도움말 및 사용 가능한 커맨드 표시 |
| `/hooks` | 훅 설정 보기 |
| `/init` | CLAUDE.md 초기화 |
| `/keybindings` | 키바인딩 설정 파일 열기/생성 |
| `/mcp` | MCP 서버 연결 관리 및 OAuth 인증 |
| `/memory` | CLAUDE.md 메모리 파일 편집 |
| `/model [model]` | AI 모델 선택/변경 |
| `/permissions` | 권한 보기/업데이트 (별칭: `/allowed-tools`) |
| `/plan` | 플랜 모드 진입 |
| `/plugin` | 플러그인 관리 |
| `/pr-comments [PR]` | GitHub PR 코멘트 가져오기 |
| `/reload-plugins` | 플러그인 재로드 |
| `/rename [name]` | 세션 이름 변경 |
| `/resume [session]` | 세션 재개 (별칭: `/continue`) |
| `/rewind` | 대화/코드 이전 지점으로 되감기 (별칭: `/checkpoint`) |
| `/security-review` | 현재 브랜치 보안 취약점 분석 |
| `/skills` | 사용 가능한 스킬 목록 |
| `/stats` | 일별 사용량, 세션 이력, 스트릭, 모델 선호도 |
| `/status` | 설정 인터페이스 상태 탭 (버전, 모델, 계정) |
| `/statusline` | 상태라인 설정 |
| `/tasks` | 백그라운드 작업 목록 관리 |
| `/theme` | 컬러 테마 변경 |
| `/usage` | 플랜 사용량 및 rate limit 상태 |
| `/vim` | Vim / Normal 편집 모드 전환 |

MCP 프롬프트 커맨드: `/mcp__<server>__<prompt>` 형식으로 동적 생성

---

## 6. CLI Flags

참고: [https://code.claude.com/docs/en/cli-reference](https://code.claude.com/docs/en/cli-reference)

| 플래그 | 설명 |
|--------|------|
| `--add-dir` | 추가 작업 디렉터리 지정 |
| `--agent` | 세션 에이전트 지정 |
| `--allowedTools` | 승인 없이 실행할 도구 목록 |
| `--append-system-prompt` | 기본 시스템 프롬프트에 텍스트 추가 |
| `--append-system-prompt-file` | 파일에서 시스템 프롬프트 추가 |
| `--betas` | 베타 헤더 포함 (API 키 사용자만) |
| `-c`, `--continue` | 가장 최근 대화 재개 |
| `--dangerously-skip-permissions` | 모든 권한 프롬프트 건너뜀 |
| `--debug` | 디버그 모드 활성화 |
| `--disable-slash-commands` | 모든 스킬/커맨드 비활성화 |
| `--disallowedTools` | 컨텍스트에서 제거할 도구 |
| `--effort` | effort 레벨 설정: `low`, `medium`, `high`, `max` |
| `--fork-session` | 재개 시 새 세션 ID 생성 |
| `--from-pr` | GitHub PR과 연결된 세션 재개 |
| `--max-budget-usd` | API 호출 최대 예산 (print 모드) |
| `--max-turns` | 에이전트 턴 수 제한 (print 모드) |
| `--mcp-config` | JSON 파일에서 MCP 서버 로드 |
| `--model` | 세션 모델 설정 |
| `-n`, `--name` | 세션 이름 설정 |
| `--no-session-persistence` | 세션 저장 비활성화 (print 모드) |
| `--output-format` | 출력 형식: `text`, `json`, `stream-json` |
| `--permission-mode` | 권한 모드: `default`, `plan`, `acceptEdits`, `bypassPermissions` |
| `-p`, `--print` | 비인터랙티브 print 모드 |
| `-r`, `--resume` | 세션 ID/이름으로 재개 |
| `--strict-mcp-config` | `--mcp-config`만 사용, 다른 MCP 무시 |
| `--system-prompt` | 시스템 프롬프트 교체 |
| `--system-prompt-file` | 파일로 시스템 프롬프트 교체 |
| `--tools` | 사용 가능한 도구 제한 |
| `--verbose` | 상세 로깅 |
| `-v`, `--version` | 버전 출력 |
| `-w`, `--worktree` | 격리된 git worktree에서 시작 |

---

## 7. Keybindings

참고: [https://code.claude.com/docs/en/keybindings](https://code.claude.com/docs/en/keybindings)

설정 파일: `~/.claude/keybindings.json` (`/keybindings` 명령으로 생성/열기)

```json
{
  "$schema": "https://www.schemastore.org/claude-code-keybindings.json",
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "ctrl+e": "chat:externalEditor",
        "ctrl+u": null
      }
    }
  ]
}
```

### 컨텍스트 목록

`Global`, `Chat`, `Autocomplete`, `Settings`, `Confirmation`, `Tabs`, `Help`, `Transcript`, `HistorySearch`, `Task`, `ThemePicker`, `Attachments`, `Footer`, `MessageSelector`, `DiffDialog`, `ModelPicker`, `Select`, `Plugin`

### 주요 기본 키바인딩

**Global (앱 전역)**

| 액션 | 기본 키 | 설명 |
|------|---------|------|
| `app:interrupt` | Ctrl+C | 현재 작업 취소 |
| `app:exit` | Ctrl+D | Claude Code 종료 |
| `app:toggleTodos` | Ctrl+T | 작업 목록 토글 |
| `app:toggleTranscript` | Ctrl+O | 상세 트랜스크립트 토글 |

**Chat**

| 액션 | 기본 키 | 설명 |
|------|---------|------|
| `chat:submit` | Enter | 메시지 제출 |
| `chat:cycleMode` | Shift+Tab | 권한 모드 순환 |
| `chat:modelPicker` | Cmd+P / Meta+P | 모델 피커 열기 |
| `chat:thinkingToggle` | Cmd+T / Meta+T | Extended Thinking 토글 |
| `chat:externalEditor` | Ctrl+G | 외부 에디터 열기 |
| `chat:stash` | Ctrl+S | 현재 프롬프트 스태시 |
| `chat:imagePaste` | Ctrl+V | 이미지 붙여넣기 |

**History**

| 액션 | 기본 키 |
|------|---------|
| `history:search` | Ctrl+R |
| `history:previous` | Up |
| `history:next` | Down |

### 키 문법

- 수정자: `ctrl`, `alt`, `shift`, `meta` (+ `+`로 연결)
- 코드: `ctrl+k ctrl+s` (공백으로 구분하는 chord)
- 특수 키: `escape`, `enter`, `tab`, `space`, `up`, `down`, `left`, `right`, `backspace`, `delete`
- 대문자는 Shift를 암시: `K` = `shift+k`
- 바인딩 해제: `null`로 설정

**예약 키 (재바인딩 불가):** `Ctrl+C`, `Ctrl+D`

---

## 8. MCP (Model Context Protocol)

참고: [https://code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp)

### MCP 서버 추가

```bash
# HTTP 서버
claude mcp add --transport http <name> <url>

# SSE 서버 (deprecated)
claude mcp add --transport sse <name> <url>

# Stdio 서버
claude mcp add [options] <name> -- <command> [args...]

# JSON에서 추가
claude mcp add-json <name> '<json>'
```

### 스코프

```bash
# Local (기본, 현재 프로젝트만)
claude mcp add --transport http myserver https://...

# Project (팀 공유, .mcp.json에 저장)
claude mcp add --transport http myserver --scope project https://...

# User (모든 프로젝트)
claude mcp add --transport http myserver --scope user https://...
```

### `.mcp.json` 포맷

```json
{
  "mcpServers": {
    "my-server": {
      "command": "/path/to/server",
      "args": [],
      "env": { "KEY": "${ENV_VAR:-default}" }
    },
    "remote-server": {
      "type": "http",
      "url": "${API_BASE_URL}/mcp",
      "headers": { "Authorization": "Bearer ${API_KEY}" }
    }
  }
}
```

환경변수 치환: `${VAR}`, `${VAR:-default}`

### MCP 관리 커맨드

```bash
claude mcp list              # 모든 서버 목록
claude mcp get <name>        # 특정 서버 상세정보
claude mcp remove <name>     # 서버 제거
claude mcp add-from-claude-desktop  # Claude Desktop에서 가져오기
```

### MCP 도구 매칭 패턴 (훅에서)

- `mcp__<server>__<tool>` - 특정 MCP 도구
- `mcp__memory__.*` - 특정 서버 모든 도구 (정규식)
- `mcp__.*__write.*` - 모든 서버의 write 도구

### Tool Search

MCP 도구가 컨텍스트의 10%를 초과하면 자동 활성화. `ENABLE_TOOL_SEARCH` 환경변수로 제어:

| 값 | 동작 |
|----|------|
| (미설정) | 기본 활성화 |
| `true` | 항상 활성화 |
| `auto` | 10% 초과 시 활성화 |
| `auto:<N>` | N% 초과 시 활성화 |
| `false` | 비활성화 |

---

## 9. 주요 환경변수

참고: [https://code.claude.com/docs/en/env-vars](https://code.claude.com/docs/en/env-vars)

| 변수 | 설명 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 키 |
| `ANTHROPIC_MODEL` | 기본 모델 오버라이드 |
| `CLAUDE_CODE_USE_BEDROCK` | AWS Bedrock 사용 |
| `CLAUDE_CODE_USE_VERTEX` | Google Vertex AI 사용 |
| `CLAUDE_CONFIG_DIR` | 설정 디렉터리 오버라이드 (기본: `~/.claude`) |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | 최대 출력 토큰 |
| `MAX_THINKING_TOKENS` | Extended Thinking 최대 토큰 |
| `BASH_DEFAULT_TIMEOUT_MS` | Bash 기본 타임아웃 (ms) |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 비필수 트래픽 비활성화 |
| `DISABLE_TELEMETRY` | 텔레메트리 비활성화 |
| `MCP_TIMEOUT` | MCP 서버 시작 타임아웃 (ms) |
| `MAX_MCP_OUTPUT_TOKENS` | MCP 도구 출력 최대 토큰 (기본: 25000) |
| `ENABLE_TOOL_SEARCH` | MCP Tool Search 제어 |
| `SLASH_COMMAND_TOOL_CHAR_BUDGET` | 스킬 description 최대 문자 수 |
| `CLAUDE_ENV_FILE` | 환경변수 영속화 파일 경로 (SessionStart 훅에서) |
| `ENABLE_CLAUDEAI_MCP_SERVERS` | Claude.ai MCP 서버 활성화 (`false`로 비활성화) |

---

## 10. Sub-agents (서브에이전트)

참고: [https://code.claude.com/docs/en/sub-agents](https://code.claude.com/docs/en/sub-agents)

서브에이전트 정의: `.claude/agents/<name>.md` 또는 `~/.claude/agents/<name>.md`

```yaml
---
name: my-agent
description: "Use when..."
model: claude-sonnet-4-6
allowed-tools: Read, Grep, Bash
skills: ["skill-name"]
hooks:
  PreToolUse: [...]
---
에이전트 지침...
```

내장 에이전트 타입: `Explore` (읽기 전용), `Plan` (계획), `general-purpose` (범용)

# Claude Code 에이전트 공식 가이드

> 출처: https://code.claude.com/docs/en/sub-agents

## 서브에이전트란?

서브에이전트는 특정 유형의 작업을 처리하는 전문화된 AI 어시스턴트입니다. 각 서브에이전트는:
- 자체 컨텍스트 윈도우에서 실행
- 커스텀 시스템 프롬프트 보유
- 특정 도구 접근 권한
- 독립적인 권한 설정

## 서브에이전트의 장점

1. **컨텍스트 보존**: 탐색과 구현을 메인 대화에서 분리
2. **제약 적용**: 사용 가능한 도구 제한
3. **재사용성**: 사용자 레벨 에이전트로 여러 프로젝트에서 사용
4. **전문화**: 특정 도메인을 위한 집중된 시스템 프롬프트
5. **비용 제어**: Haiku 같은 빠르고 저렴한 모델로 라우팅

## 내장 서브에이전트

### Explore
- **모델**: Haiku (빠른 속도)
- **도구**: 읽기 전용 (Write, Edit 제외)
- **용도**: 파일 검색, 코드 탐색

### Plan
- **모델**: 메인 대화 상속
- **도구**: 읽기 전용
- **용도**: 계획 모드에서 컨텍스트 수집

### General-purpose
- **모델**: 메인 대화 상속
- **도구**: 모든 도구
- **용도**: 복잡한 다단계 작업

## YAML Frontmatter 필드 상세

### 필수 필드

#### name (필수)
```yaml
name: code-reviewer
```
- 소문자와 하이픈만 허용
- 고유 식별자로 사용

#### description (필수)
```yaml
description: 코드 품질과 보안을 검토하는 전문가. 코드 변경 후 자동으로 사용됩니다.
```
- Claude가 언제 이 에이전트에 위임할지 결정하는 기준
- "proactively" 포함 시 자동 사용 권장

### 선택 필드

#### tools (에이전트) / allowed-tools (스킬)
```yaml
# 에이전트에서:
tools: Read, Glob, Grep, Bash
# 스킬에서:
allowed-tools: Read, Glob, Grep, Bash
```
- 허용할 도구 목록
- 에이전트에서는 `tools`, 스킬에서는 `allowed-tools` 키워드 사용
- `allowed-tools`로 지정된 도구는 스킬 활성 시 권한 요청 없이 사용 가능
- 생략 시 메인 대화의 모든 도구 상속

#### disallowedTools
```yaml
disallowedTools: Write, Edit
```
- 제외할 도구 목록
- tools와 함께 사용 가능

#### argument-hint
```yaml
argument-hint: "[issue-number]"
```
- 자동완성 메뉴에서 스킬 이름 옆에 표시되는 인자 힌트
- 사용자가 `/스킬명` 입력 시 필요한 인자를 안내
- 선택적 필드, 생략 시 힌트 표시 없음

#### user-invocable
```yaml
user-invocable: false  # true(기본값) | false
```
- `false` 설정 시 `/` 메뉴에서 숨김 (배경 지식 전용 스킬에 사용)
- `true` (기본값): 사용자 메뉴에 표시
- `disable-model-invocation: true`와 조합하여 완전히 숨길 수 있음

#### model
```yaml
model: sonnet  # sonnet | opus | haiku | inherit
```
- `sonnet`: 균형잡힌 성능 (권장)
- `opus`: 복잡한 추론
- `haiku`: 빠른 속도
- `inherit`: 메인 대화 모델 사용 (기본값)
- 에이전트와 스킬 모두에서 사용 가능 (스킬에서 지정하면 해당 스킬 활성 시 모델 전환)

#### permissionMode
```yaml
permissionMode: default  # default | acceptEdits | dontAsk | bypassPermissions | plan
```
- `default`: 표준 권한 확인
- `acceptEdits`: 파일 편집 자동 승인
- `dontAsk`: 권한 요청 자동 거부
- `bypassPermissions`: 모든 권한 검사 건너뜀 (주의!)
- `plan`: 읽기 전용 탐색 모드

#### skills
```yaml
skills:
  - api-conventions
  - error-handling-patterns
```
- 시작 시 주입할 스킬 목록
- 스킬 전체 내용이 컨텍스트에 주입됨

#### hooks
```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
```
- 도구 사용 전/후 실행할 명령

## 사용 가능한 도구 전체 목록

| 도구 | 설명 |
|------|------|
| Read | 파일 읽기 |
| Write | 새 파일 생성 |
| Edit | 기존 파일 수정 |
| Bash | 터미널 명령 실행 |
| Glob | 파일 패턴 검색 |
| Grep | 파일 내용 검색 (정규식) |
| WebSearch | 웹 검색 |
| WebFetch | 웹 페이지 가져오기 |
| Task | 서브에이전트 호출 |
| AskUserQuestion | 사용자에게 질문 |

## 에이전트 저장 위치

| 위치 | 범위 | 우선순위 |
|------|------|---------|
| `--agents` CLI 플래그 | 현재 세션 | 1 (최고) |
| `.claude/agents/` | 현재 프로젝트 | 2 |
| `~/.claude/agents/` | 모든 프로젝트 | 3 |
| 플러그인의 `agents/` | 플러그인 활성화 위치 | 4 (최저) |

## 에이전트 실행 모드

### Foreground (포그라운드)
- 메인 대화 차단
- 권한 요청과 질문이 사용자에게 전달됨

### Background (백그라운드)
- 메인 대화와 병렬 실행
- 사전에 필요한 권한 승인 필요
- `Ctrl+B`로 실행 중인 작업을 백그라운드로 전환 가능

## 훅 이벤트

### 에이전트 frontmatter 내 훅
| 이벤트 | 매처 입력 | 발생 시점 |
|--------|----------|----------|
| `PreToolUse` | 도구 이름 | 도구 사용 전 |
| `PostToolUse` | 도구 이름 | 도구 사용 후 |
| `Stop` | (없음) | 에이전트 종료 시 |
| `Notification` | 알림 유형 (permission_prompt, idle_prompt, auth_success, elicitation_dialog) | 알림 전송 시 |
| `PreCompact` | manual, auto | 컨텍스트 컴팩션 전 |
| `SessionEnd` | clear, logout, prompt_input_exit 등 | 세션 종료 시 |
| `TaskCompleted` | (없음) | 태스크 완료 시 (exit 2로 차단 가능) |
| `TeammateIdle` | (없음) | 팀원 idle 전환 시 (exit 2로 차단 가능) |

### 프로젝트 레벨 훅 (settings.json)
| 이벤트 | 매처 입력 | 발생 시점 |
|--------|----------|----------|
| `SessionStart` | startup, resume, clear, compact | 세션 시작/재개 |
| `UserPromptSubmit` | (항상 실행) | 사용자 프롬프트 제출 시 |
| `PreToolUse` | 도구 이름 | 도구 사용 전 |
| `PostToolUse` | 도구 이름 | 도구 사용 후 |
| `PostToolUseFailure` | 도구 이름 | 도구 실행 실패 후 |
| `PermissionRequest` | 도구 이름 | 권한 대화 표시 시 (allow/deny 결정 가능) |
| `Notification` | 알림 유형 | 알림 전송 시 |
| `SubagentStart` | 에이전트 이름 | 서브에이전트 시작 |
| `SubagentStop` | 에이전트 이름 | 서브에이전트 종료 |
| `Stop` | (없음) | 에이전트 응답 종료 시 |
| `TaskCompleted` | (없음) | 태스크 완료 시 |
| `TeammateIdle` | (없음) | 팀원 idle 전환 시 |
| `PreCompact` | manual, auto | 컨텍스트 컴팩션 전 |
| `SessionEnd` | clear, logout, prompt_input_exit 등 | 세션 종료 시 |

### 훅 핸들러 타입

훅 핸들러는 3종류가 있으며, 각각 다른 방식으로 검증/자동화를 수행합니다.

| 타입 | 설명 | 용도 |
|------|------|------|
| `command` | 셸 명령 실행 | 결정적 규칙 기반 검증, 포맷팅, 로깅. stdin으로 JSON 입력, stdout/exit code로 결과 반환 |
| `prompt` | LLM 단일턴 평가 (Haiku 기본) | 판단 기반 allow/block 결정. `{"ok": true}` 또는 `{"ok": false, "reason": "이유"}` 반환 |
| `agent` | 서브에이전트 스폰 (다턴, 도구 사용 가능) | 파일 검사, 테스트 실행 등 다단계 검증. prompt와 동일한 JSON 형식 반환 |

```yaml
# command 타입 예시
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh"

# prompt 타입 예시
hooks:
  PreToolUse:
    - matcher: "Edit"
      hooks:
        - type: prompt
          prompt: "이 편집이 코드 스타일 가이드를 준수하는지 평가하세요."

# agent 타입 예시
hooks:
  PostToolUse:
    - matcher: "Write"
      hooks:
        - type: agent
          prompt: "작성된 파일의 테스트를 실행하고 결과를 확인하세요."
```

## Skills 시스템

Skills는 Claude Code에 도메인 전문 지식을 주입하는 마크다운 기반 모듈이다. 각 스킬은 `SKILL.md` 파일을 엔트리포인트로 하며, YAML frontmatter로 메타데이터를 정의하고 마크다운 본문으로 지시사항을 작성한다.

### 스킬 저장 위치 우선순위

| 위치 | 범위 | 우선순위 |
|------|------|---------|
| Enterprise (managed settings) | 조직 전체 | 1 (최고) |
| `~/.claude/skills/` | 사용자 전 프로젝트 | 2 |
| `.claude/skills/` | 현재 프로젝트 | 3 |
| Plugin의 `skills/` | 플러그인 활성 범위 | 4 (최저) |

### 동적 컨텍스트 주입

스킬 본문에서 셸 명령의 출력을 동적으로 삽입할 수 있다.

**구문:**
```
!`command`
```

Claude가 스킬을 로드하기 전에 명령이 실행되어 결과가 치환된다. 예를 들어 `` !`gh pr diff` `` 를 스킬 본문에 포함하면 현재 PR의 diff가 동적으로 주입된다.

**사용 예시:**
- `` !`git log --oneline -10` `` - 최근 커밋 10개를 컨텍스트에 포함
- `` !`cat package.json | jq '.dependencies'` `` - 현재 의존성 목록 주입
- `` !`gh issue view 123 --json body -q .body` `` - 이슈 본문을 동적 로드

### 문자열 치환

스킬 본문에서 다음 변수가 자동 치환된다.

| 변수 | 설명 |
|------|------|
| `$ARGUMENTS` | 스킬 호출 시 전달된 전체 인자 문자열 |
| `$ARGUMENTS[N]` | N번째 인자 (0-based 인덱스) |
| `$N` | `$ARGUMENTS[N]`의 축약형 |
| `${CLAUDE_SESSION_ID}` | 현재 세션 고유 ID |

### 자동 디스커버리

- 프로젝트 하위 디렉토리의 `.claude/skills/`도 자동 탐색 (모노레포 지원)
- `--add-dir`로 추가된 디렉토리의 스킬도 즉시 로드
- 중첩 깊이에 관계없이 모든 `SKILL.md` 파일을 발견

### 컨텍스트 예산

- 스킬 컨텍스트는 전체 컨텍스트 윈도우의 **2%**로 동적 스케일링 (폴백: 16,000자)
- `/context` 명령으로 현재 예산 사용량 및 초과 여부 확인 가능
- `SLASH_COMMAND_TOOL_CHAR_BUDGET` 환경변수로 예산 한도 오버라이드 가능

## Agent Teams (실험적)

> **주의**: Agent Teams는 실험적 기능이며 GA(General Availability) 미선언 상태이다. 프로덕션 환경에서의 사용은 권장하지 않으며, API와 동작이 예고 없이 변경될 수 있다.

복수의 Claude Code 인스턴스가 팀으로 협업하는 멀티에이전트 기능이다.

### 구성 요소

- **팀 리드**: 전체 작업 조정, `delegate` 퍼미션 모드로 코드 수정 불가 (조정 전용)
- **팀원**: 각각 독립 컨텍스트 윈도우에서 실행
- **공유 태스크 리스트**: 팀 전체가 공유하는 작업 목록
- **메일박스**: 팀원 간 상호 메시징 및 챌린지 가능

### 서브에이전트와의 차이

| 항목 | 서브에이전트 | Agent Teams |
|------|-----------|-------------|
| 통신 방식 | 결과만 반환 | 상호 메시징/챌린지 가능 |
| 수명 | 작업 완료 시 종료 | 팀 리드가 관리 |
| 컨텍스트 | 부모와 격리 | 각자 독립 + 메일박스 공유 |

### 디스플레이 모드

- **in-process**: 같은 터미널에서 실행
- **split-panes**: tmux 또는 iTerm2를 활용한 분할 화면

### 활성화

```bash
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=true claude
```

### 최적 사용 사례

- 연구/리뷰 작업의 병렬 수행
- 독립 모듈의 동시 개발
- 경쟁 가설 디버깅
- 크로스 레이어 작업 (프론트엔드 + 백엔드 동시)

## 특정 에이전트 비활성화

settings.json에서:
```json
{
  "permissions": {
    "deny": ["Task(Explore)", "Task(my-custom-agent)"]
  }
}
```

또는 CLI 플래그:
```bash
claude --disallowedTools "Task(Explore)"
```

## Best Practices

### SKILL.md 작성 권장 사항

- **500줄 이하 권장**: SKILL.md 본문은 500줄 이하로 유지. 상세 레퍼런스, 예제, 카탈로그는 `references/` 디렉토리에 분리
- **Progressive Disclosure 3계층**: (1) 메타데이터 레벨 - 시작 시 description만 로드, (2) 코어 레벨 - 관련성 판단 시 전체 SKILL.md 로드, (3) 보충 레벨 - 필요 시 references/ 파일 로드

### Extended Thinking 활성화

스킬 콘텐츠에 `ultrathink` 키워드를 포함하면 Claude의 extended thinking이 자동으로 활성화된다. 복잡한 추론이 필요한 스킬에 활용한다.

### Description 품질 기준

효과적인 description은 Claude가 스킬을 적시에 자동 로드할 수 있게 한다.

| 기준 | 설명 | 예시 |
|------|------|------|
| **WHAT** | 스킬이 수행하는 작업 | "코드 리뷰 체크리스트를 적용하여 품질 게이트를 검증" |
| **WHEN** | 사용 시점/트리거 조건 | "Use when reviewing pull requests or code changes" |
| **키워드** | 자동 매칭에 사용되는 핵심 단어 | "PR, code review, quality gate, lint" |

- 최소 50자 이상 작성
- 3인칭 서술 권장: "Provides...", "Generates...", "Analyzes..." 또는 "~를 수행하는 스킬"
- 1024자 이내 유지

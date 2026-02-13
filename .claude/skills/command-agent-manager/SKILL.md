---
name: command-agent-manager
description: Claude Code 에이전트(서브에이전트) 생성 및 수정을 위한 통합 관리 스킬. 사용자가 에이전트를 생성, 수정, 업데이트할 때 사용합니다. 예시 트리거 - "에이전트 만들어줘", "새 에이전트 생성", "에이전트 수정해줘", "에이전트 업데이트", "/agent 생성", "agent 만들기", "create agent", "update agent", "modify agent", "서브에이전트 추가/수정". 이 스킬은 반드시 사용자로부터 모델 정보(sonnet/opus/haiku/inherit)와 도구 정보(Read, Edit, Bash 등)를 수집해야 합니다.
---

# Agent Manager

Claude Code 에이전트(서브에이전트) 생성 및 수정을 위한 통합 관리 가이드입니다.

## 필수 수집 정보

에이전트 생성 전 **반드시** 다음 정보를 사용자로부터 수집해야 합니다:

### 1. 기본 정보 (Required)
- **name**: 에이전트 이름 (소문자, 하이픈만 허용)
- **description**: 에이전트 용도 설명 (Claude가 언제 이 에이전트를 사용할지 판단하는 기준)

### 2. 모델 정보 (Required)
사용자에게 반드시 모델을 선택하도록 요청:
| 모델 | 용도 |
|------|------|
| `sonnet` | 균형잡힌 성능과 속도 (권장) |
| `opus` | 복잡한 추론이 필요한 작업 |
| `haiku` | 빠른 속도가 중요한 단순 작업 |
| `inherit` | 메인 대화의 모델 사용 (기본값) |

### 3. 도구 정보 (Required)
사용자에게 반드시 필요한 도구들을 선택하도록 요청:

| 도구 | 설명 | 용도 |
|------|------|------|
| `Read` | 파일 읽기 | 코드 분석, 문서 확인 |
| `Write` | 파일 생성 | 새 파일 작성 |
| `Edit` | 파일 수정 | 기존 파일 편집 |
| `Bash` | 터미널 명령 실행 | git, npm, 스크립트 실행 |
| `Glob` | 파일 패턴 검색 | 파일 찾기 (`**/*.ts`) |
| `Grep` | 내용 검색 | 코드 내 텍스트 검색 |
| `WebSearch` | 웹 검색 | 최신 정보 검색 |
| `WebFetch` | 웹 페이지 가져오기 | 문서/API 참조 |
| `Task` | 서브에이전트 호출 | 작업 위임 |
| `AskUserQuestion` | 사용자에게 질문 | 명확화 필요시 |

### 4. 선택 정보 (Optional)
- **permissionMode**: 권한 모드
- **disallowedTools**: 제외할 도구
- **skills**: 주입할 스킬
- **hooks**: 라이프사이클 훅

## 워크플로우 모드

워크플로우 WORK 단계에서 호출될 때는 AskUserQuestion을 사용하지 않고 계획서에 사전 확정된 사양을 기반으로 동작합니다.

### 감지 방법

prompt에 `planPath:` 키가 포함되어 있으면 워크플로우 모드로 판단합니다.

### 워크플로우 모드 동작

1. `planPath`에서 계획서(plan.md)를 읽어 해당 태스크의 필수 정보를 추출합니다:
   - **name**: 에이전트 이름
   - **description**: 에이전트 설명
   - **model**: 사용할 모델 (sonnet/opus/haiku/inherit)
   - **tools**: 허용 도구 목록
   - **기타**: permissionMode, skills, hooks 등 선택 정보
2. AskUserQuestion 호출을 **건너뜁니다** (Step 0, Step 1 생략)
3. 계획서에 명시된 정보만으로 Step 2(범위 결정)부터 진행합니다
4. 계획서에 정보가 누락된 경우 안전한 기본값을 사용합니다:
   - model: `inherit`
   - tools: 생략 (모든 도구 상속)
   - permissionMode: `default`
   - scope: 프로젝트 (`.claude/agents/`)

> **주의**: 워크플로우 모드에서는 Slack 대기 알림도 전송하지 않습니다.

## 에이전트 생성 절차

### Step 0: Slack 대기 알림 전송 (AskUserQuestion 전)

AskUserQuestion을 호출하기 **전에** Slack으로 대기 알림을 전송합니다.

**환경변수 확인:**
```bash
if [ -f ".claude.env" ]; then
    SLACK_BOT_TOKEN=$(grep "^CLAUDE_CODE_SLACK_BOT_TOKEN=" .claude.env | sed 's/^CLAUDE_CODE_SLACK_BOT_TOKEN=//')
    SLACK_CHANNEL_ID=$(grep "^CLAUDE_CODE_SLACK_CHANNEL_ID=" .claude.env | sed 's/^CLAUDE_CODE_SLACK_CHANNEL_ID=//')
fi
```

**알림 형식:**
```
[입력 대기] 에이전트 생성
정보 수집을 위해 사용자 응답을 대기합니다.
```

**API 호출:**
```bash
curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "'"${SLACK_CHANNEL_ID}"'",
    "text": "[입력 대기] 에이전트 생성\n정보 수집을 위해 사용자 응답을 대기합니다."
  }'
```

**비차단 원칙:** Slack 전송 실패 시 경고만 출력하고 AskUserQuestion 진행

### Step 1: 정보 수집
사용자에게 AskUserQuestion 도구를 사용하여 질문:

```
질문 예시:
1. "어떤 용도의 에이전트를 만들까요?" (description)
2. "에이전트 이름은 무엇으로 할까요?" (name)
3. "어떤 모델을 사용할까요?" (model: sonnet/opus/haiku/inherit)
4. "어떤 도구들이 필요한가요?" (tools)
```

### Step 2: 에이전트 범위 결정
| 범위 | 위치 | 용도 |
|------|------|------|
| 프로젝트 | `.claude/agents/` | 현재 프로젝트 전용 |
| 사용자 | `~/.claude/agents/` | 모든 프로젝트에서 사용 |

### Step 3: 파일 생성
에이전트는 YAML frontmatter가 있는 Markdown 파일입니다.

**파일 경로**: `<scope>/agents/<name>.md`

**파일 구조**:
```markdown
---
name: <에이전트-이름>
description: <설명>
tools: <도구1>, <도구2>, ...
model: <모델>
permissionMode: <권한모드>
---

<시스템 프롬프트>
```

### Step 4: 검증
- 파일이 올바른 위치에 생성되었는지 확인
- YAML frontmatter 형식 검증
- 도구 이름이 올바른지 확인

## YAML Frontmatter 스키마

```yaml
---
# 필수 필드
name: code-reviewer           # 소문자, 하이픈만 (필수)
description: "코드 리뷰 전문가..." # Claude가 위임 결정에 사용 (필수)

# 선택 필드
tools: Read, Glob, Grep, Bash # 허용 도구 (생략시 모든 도구 상속)
disallowedTools: Write, Edit  # 제외 도구
model: sonnet                 # sonnet/opus/haiku/inherit
permissionMode: default       # default/acceptEdits/dontAsk/bypassPermissions/plan
skills:                       # 주입할 스킬
  - api-conventions
hooks:                        # 라이프사이클 훅
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./validate.sh"
---
```

## Permission Modes

| 모드 | 동작 |
|------|------|
| `default` | 표준 권한 확인 (기본값) |
| `acceptEdits` | 파일 편집 자동 승인 |
| `dontAsk` | 권한 요청 자동 거부 |
| `bypassPermissions` | 모든 권한 검사 건너뜀 (주의) |
| `plan` | 읽기 전용 탐색 모드 |

## 에이전트 타입별 템플릿

### 코드 리뷰어 (Read-only)
```yaml
---
name: code-reviewer
description: 코드 품질과 보안을 검토하는 전문가. 코드 변경 후 자동으로 사용됩니다.
tools: Read, Grep, Glob, Bash
model: sonnet
---

코드 품질, 보안, 유지보수성을 검토합니다.

검토 항목:
- 코드 가독성
- 보안 취약점
- 에러 처리
- 테스트 커버리지

피드백 우선순위:
1. Critical (반드시 수정)
2. Warning (수정 권장)
3. Suggestion (개선 제안)
```

### 디버거 (Read/Write)
```yaml
---
name: debugger
description: 에러, 테스트 실패, 예상치 못한 동작을 디버깅합니다.
tools: Read, Edit, Bash, Grep, Glob
model: inherit
---

버그의 근본 원인을 분석하고 수정합니다.

디버깅 프로세스:
1. 에러 메시지 분석
2. 재현 단계 확인
3. 원인 분석
4. 최소한의 수정
5. 검증
```

### 연구자 (Read-only)
```yaml
---
name: researcher
description: 코드베이스 탐색과 정보 수집을 담당합니다.
tools: Read, Glob, Grep, WebSearch, WebFetch
model: haiku
---

코드베이스를 탐색하고 정보를 수집합니다.

조사 방법:
1. Glob으로 파일 검색
2. Grep으로 패턴 검색
3. Read로 상세 분석
4. 필요시 웹 검색
```

### 테스터 (Read/Write/Execute)
```yaml
---
name: tester
description: 테스트 작성과 실행을 담당합니다.
tools: Read, Write, Edit, Bash, Glob, Grep
model: inherit
---

테스트를 작성하고 실행합니다.

테스트 유형:
- 단위 테스트
- 통합 테스트
- E2E 테스트
```

## 에이전트 생성 예시 대화

```
사용자: 코드 리뷰어 에이전트 만들어줘

Claude: 에이전트 생성을 위해 몇 가지 정보가 필요합니다.

[AskUserQuestion 호출]
1. 모델 선택: sonnet (권장) / opus / haiku / inherit
2. 필요한 도구 선택: Read, Glob, Grep, Bash, Edit...
3. 범위 선택: 프로젝트 전용 / 전역 (모든 프로젝트)

사용자: sonnet, Read/Glob/Grep/Bash, 프로젝트 전용

Claude: [에이전트 파일 생성]
.claude/agents/code-reviewer.md 생성 완료!
```

## 참고 자료

- [Claude Agent SDK 공식 문서](https://platform.claude.com/docs/en/agent-sdk/overview)
- [서브에이전트 생성 가이드](https://code.claude.com/docs/en/sub-agents)
- [스킬 가이드](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)

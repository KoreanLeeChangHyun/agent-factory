---
name: management-command
description: "Unified management skill for creating and modifying Claude Code slash commands. Collects command name, purpose, and scope (project/personal), then creates or modifies .claude/commands/ files. Use for custom command management: creating, updating, or modifying slash commands. Triggers: '명령어 만들어줘', '커맨드 생성', 'create command', 'update command', '슬래시 명령어'."
license: "Apache-2.0"
---

# Command Manager

Claude Code 슬래시 명령어(커맨드) 생성 및 수정을 위한 통합 관리 가이드입니다.

## 핵심 개념

**슬래시 명령어 = 스킬**: Claude Code에서 `.claude/commands/`와 `.claude/skills/`는 동일한 `/command`를 생성합니다.

## 필수 수집 정보

슬래시 명령어 생성 전 **반드시** 사용자로부터 수집:

| 항목 | 설명 | 예시 |
|------|------|------|
| **name** | 명령어 이름 (소문자, 하이픈, 최대 64자) | `code-review`, `deploy` |
| **description** | 명령어 설명 + 언제 사용할지 | "코드 리뷰 수행. PR 생성 전 사용" |
| **scope** | 적용 범위 | 프로젝트 전용 / 개인(전역) |
| **용도** | 어떤 작업을 수행하는지 | 코드 리뷰, 배포, 문서 생성 등 |

## 워크플로우 모드

워크플로우 WORK 단계에서 호출될 때는 AskUserQuestion을 사용하지 않고 계획서에 사전 확정된 사양을 기반으로 동작합니다.

### 감지 방법

prompt에 `planPath:` 키가 포함되어 있으면 워크플로우 모드로 판단합니다.

### 워크플로우 모드 동작

1. `planPath`에서 계획서(plan.md)를 읽어 해당 태스크의 필수 정보를 추출합니다:
   - **name**: 명령어 이름
   - **description**: 명령어 설명 (용도와 사용 시점)
   - **scope**: 적용 범위 (프로젝트/개인)
   - **기타**: argument-hint, context, agent, disable-model-invocation 등 선택 정보
2. AskUserQuestion 호출을 **건너뜁니다** (Step 0, Step 1 생략)
3. 계획서에 명시된 정보만으로 Step 2(범위 결정)부터 진행합니다
4. 계획서에 정보가 누락된 경우 안전한 기본값을 사용합니다:
   - scope: 프로젝트 (`.claude/skills/`)
   - disable-model-invocation: 생략 (기본 동작)
   - context: 생략 (메인 대화에서 실행)

> **주의**: 워크플로우 모드에서는 Slack 대기 알림도 전송하지 않습니다.

## 생성 절차

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
[입력 대기] 슬래시 명령어 생성
정보 수집을 위해 사용자 응답을 대기합니다.
```

**API 호출:**
```bash
curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "'"${SLACK_CHANNEL_ID}"'",
    "text": "[입력 대기] 슬래시 명령어 생성\n정보 수집을 위해 사용자 응답을 대기합니다."
  }'
```

**비차단 원칙:** Slack 전송 실패 시 경고만 출력하고 AskUserQuestion 진행

### Step 1: 정보 수집
AskUserQuestion으로 필요 정보 수집:
```
1. "어떤 용도의 명령어를 만들까요?"
2. "명령어 이름은 무엇으로 할까요? (예: /review, /deploy)"
3. "이 프로젝트에서만 사용할까요, 모든 프로젝트에서 사용할까요?"
4. "인수가 필요한가요? (예: /fix-issue 123)"
```

### Step 2: 범위 결정

| 범위 | 위치 | 용도 |
|------|------|------|
| 프로젝트 | `.claude/skills/<name>/SKILL.md` | 현재 프로젝트 전용 |
| 개인 | `~/.claude/skills/<name>/SKILL.md` | 모든 프로젝트에서 사용 |

### Step 3: SKILL.md 생성

#### 기본 구조
```markdown
---
name: <명령어-이름>
description: <설명 + 언제 사용할지>
---

<명령어 실행시 Claude가 따를 지침>
```

#### Frontmatter 필드 참조

| 필드 | 필수 | 설명 |
|------|------|------|
| `name` | 권장 | 명령어 이름 (생략시 디렉토리명) |
| `description` | **권장** | Claude가 언제 사용할지 판단하는 기준 |
| `argument-hint` | 선택 | 자동완성시 표시할 인수 힌트 `[issue-number]` |
| `disable-model-invocation` | 선택 | `true`: 사용자만 호출 가능 |
| `user-invocable` | 선택 | `false`: / 메뉴에서 숨김 |
| `allowed-tools` | 선택 | 허용할 도구 목록 |
| `model` | 선택 | 사용할 모델 |
| `context` | 선택 | `fork`: 서브에이전트로 실행 |
| `agent` | 선택 | `context: fork`일 때 사용할 에이전트 |

## 변수 치환

스킬 내용에서 사용 가능한 변수:

| 변수 | 설명 | 예시 |
|------|------|------|
| `$ARGUMENTS` | 전체 인수 | `/fix-issue 123` → `123` |
| `$ARGUMENTS[N]` | N번째 인수 (0부터) | `$ARGUMENTS[0]` |
| `$0`, `$1`, ... | `$ARGUMENTS[N]` 축약형 | `/migrate A B` → `$0=A, $1=B` |
| `${CLAUDE_SESSION_ID}` | 현재 세션 ID | 로깅용 |

## 호출 제어

| 설정 | 사용자 호출 | Claude 호출 | 용도 |
|------|-------------|-------------|------|
| (기본) | O | O | 일반 명령어 |
| `disable-model-invocation: true` | O | X | /deploy, /commit 등 |
| `user-invocable: false` | X | O | 백그라운드 지식 |

## 템플릿 유형

자세한 템플릿은 [templates/](templates/) 참조:

### 1. 기본 명령어
부작용 없이 정보 제공 또는 분석 수행:
```yaml
---
name: explain-code
description: 코드를 다이어그램과 비유로 설명. "어떻게 동작해?", "설명해줘" 등에 반응
---

코드 설명시 포함할 내용:
1. 비유로 시작
2. ASCII 다이어그램
3. 단계별 설명
```

### 2. 작업 수행 명령어
특정 작업을 수행 (사용자만 호출):
```yaml
---
name: deploy
description: 프로덕션 배포
context: fork
disable-model-invocation: true
---

$ARGUMENTS 배포:
1. 테스트 실행
2. 빌드
3. 배포
4. 검증
```

### 3. GitHub 연동 명령어
동적 컨텍스트 주입:
```yaml
---
name: devops-pr-summary
description: PR 요약
context: fork
agent: Explore
---

## PR 컨텍스트
- diff: !`gh pr diff`
- comments: !`gh pr view --comments`

위 정보를 바탕으로 PR 요약...
```

## 생성 예시 대화

```
사용자: 코드 리뷰 명령어 만들어줘

Claude: 슬래시 명령어 생성을 위해 몇 가지 정보가 필요합니다.

[AskUserQuestion 호출]
1. 명령어 이름은? (예: review, code-review)
2. 이 프로젝트에서만 / 모든 프로젝트에서?
3. Claude가 자동으로 호출해도 될까요?

사용자: review, 프로젝트 전용, 자동 호출 안됨

Claude: [SKILL.md 생성]
.claude/skills/review/SKILL.md 생성 완료!

`/review` 명령어로 사용할 수 있습니다.
```

## 참고 자료

- 상세 frontmatter: [references/frontmatter-guide.md](references/frontmatter-guide.md)
- 템플릿 모음: [templates/](templates/)
- 공식 문서: https://code.claude.com/docs/en/skills

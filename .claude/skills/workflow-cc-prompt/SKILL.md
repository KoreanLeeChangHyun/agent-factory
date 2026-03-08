---
name: workflow-cc-prompt
description: "Workflow command skill for cc:prompt. Free-form conversational prompt co-authoring mode. Collaboratively writes and refines prompts through natural dialogue."
disable-model-invocation: true
skills:
  - research-prompt-engineering
---

# Prompt Command (자유 대화형 프롬프트 공동 작성)

`.prompt/prompt.txt`를 사용자와의 자유 대화를 통해 점진적으로 작성하거나 개선하는 워크플로우 커맨드 스킬. 워크플로우(FSM/가드/서브에이전트)와 무관한 독립 명령어.

상세 실행 절차는 `.claude/commands/cc/prompt.md`를 참조한다.

## 메타데이터

### 스킬 의존성

실행 시작 전 `.claude/skills/research-prompt-engineering/SKILL.md`를 Read로 로드한다.

용도 키워드 기반으로 하위 references를 선택적으로 추가 로드한다:

| 용도 키워드 | 추가 로드 대상 |
|------------|---------------|
| 구현, 기능, 함수, 모듈, 버그, 오류, 에러, 수정 | `references/prompt-templates.md` |
| 리팩토링, 정리, 분리, 리뷰, 검토 | `references/prompt-templates.md` |
| 조사, 비교, 연구, 설계, 아키텍처, 시스템 | `references/prompt-templates.md` |
| 에이전트, 서브에이전트, 도구 | `references/claude-code-patterns.md` |
| 용도 불명확 | `references/prompt-templates.md` + `references/claude-code-patterns.md` 모두 |

### 비워크플로우 독립 명령어

이 스킬은 워크플로우 FSM과 무관하게 독립 실행된다. 사용 가능 도구: Bash, Read, Write, AskUserQuestion, Glob, Grep, WebSearch, WebFetch. Task 도구 호출 금지. Bash는 Quick 모드(-q)에서만 허용.

## 참조

이 스킬의 실행 절차는 대응 커맨드 파일(`.claude/commands/cc/prompt.md`)이 Single Source of Truth이다.

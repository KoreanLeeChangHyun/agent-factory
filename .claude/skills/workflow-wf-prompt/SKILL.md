---
name: workflow-wf-prompt
description: "Workflow command skill for wf -o. Free-form conversational prompt co-authoring mode. Collaboratively writes and refines prompts through natural dialogue."
disable-model-invocation: true
skills:
  - research-prompt-engineering
license: "Apache-2.0"
---

# Prompt Command (자유 대화형 프롬프트 공동 작성)

`.kanban/T-NNN.xml` 티켓 파일을 사용자와의 자유 대화를 통해 점진적으로 작성하거나 개선하는 워크플로우 커맨드 스킬. 워크플로우(FSM/가드/서브에이전트)와 무관한 독립 명령어.

티켓 파일은 XML 구조를 사용합니다:
- 루트 요소: `<ticket>`
- `<metadata>` 래퍼: `<number>`, `<title>`, `<datetime>`, `<status>`, `<current>` (현재 활성 subnumber는 `<current>` 값으로 결정)
- `<submit>` 래퍼: active subnumber 목록
- `<history>` 래퍼: 비활성(이전 사이클) subnumber 목록
- 작업 단위: `<subnumber id="N">` (직하에 `<command>` 태그, `<prompt>` 래퍼 내에 goal/target/constraints/criteria/context)

상세 실행 절차는 `.claude/commands/wf.md`를 참조한다.

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

### XML 티켓 처리 규칙

- `<command>` 태그는 `<subnumber id="N">` 직하(자식)에 위치. `<prompt>` 래퍼 밖에 배치됨. 잠금 판정은 XML `<status>` 요소(`Open`/`In Progress`/`Review`)로 판별
- `<goal>`, `<target>`, `<constraints>`, `<criteria>`, `<context>` 태그는 subnumber 내부의 `<prompt>` 래퍼 안에 위치
- 사용자 입력 갱신은 현재 활성 subnumber(`<current>` 값) 내부의 `<prompt>` 래퍼 자식 요소를 대상으로 함
- 기존 티켓 편집 시 원시 XML 대신 읽기 쉬운 구조화 형식으로 출력

### 웹검색/코드탐색 자율 수행

대화 루프의 매 턴에서 LLM이 자율 판단으로 웹검색/코드베이스 탐색을 수행한다. 수행 여부를 사용자에게 사전에 묻지 않으며, 탐색/검색 결과는 핵심을 요약하여 제안·선택지 형태로 제공한다.

예: "코드베이스를 확인한 결과 `src/auth/token.ts`에 유사한 패턴이 있습니다. 이 패턴을 참고할까요?"

| 감지 신호 | 수행 액션 | 사용 도구 |
|----------|----------|----------|
| 함수, 모듈, 파일, 클래스, 컴포넌트, 변수, 메서드 | 코드베이스 탐색 | Grep, Glob, Read |
| API, 프레임워크, 패키지, 버전, 라이브러리, SDK, 외부 서비스 | 웹검색 | WebSearch, WebFetch |
| 양쪽 신호 모두 감지 | 코드베이스 탐색 + 웹검색 모두 수행 | Grep, Glob, Read, WebSearch, WebFetch |

### 비워크플로우 독립 명령어

이 스킬은 워크플로우 FSM과 무관하게 독립 실행된다. 사용 가능 도구: Bash, Read, Write, AskUserQuestion, Glob, Grep, WebSearch, WebFetch. Task 도구 호출 금지. Bash는 Step D(티켓 종료), done 폴백 복원, Step 2 새 티켓 생성에서 허용.

## 참조

이 스킬의 실행 절차는 대응 커맨드 파일(`.claude/commands/wf.md`)이 Single Source of Truth이다.

---
description: ".prompt/prompt.txt의 내용을 대화형으로 정제합니다. 모호한 프롬프트를 질의응답으로 개선합니다."
argument-hint: "[--clear] [--ccv]"
skills:
  - prompt-engineering-guide
---

# Prompt (Prompt Refinement)

`.prompt/prompt.txt`의 프롬프트를 대화형 질의응답으로 정제합니다. 워크플로우(FSM/가드/서브에이전트)와 무관한 독립 명령어입니다.

> **스킬 참조**: 이 명령어는 `prompt-engineering-guide` 스킬을 사용합니다. 분석 시작 전 `.claude/skills/prompt-engineering-guide/SKILL.md`를 Read로 로드하고, 필요 시 하위 references도 참조합니다.

## 입력: $ARGUMENTS

| 인자 | 설명 | 필수 |
|------|------|------|
| `--clear` | prompt.txt를 빈 파일로 초기화 | 아니오 |
| `--ccv` | Claude Code Vanilla 모드. 스킬 참조 없이 일반 Claude처럼 동작 | 아니오 |

## 실행 흐름

### 0. --clear 인자 확인

`$ARGUMENTS`에 `--clear`가 포함된 경우:

1. Write 도구로 `.prompt/prompt.txt`에 빈 문자열을 덮어쓰기
2. "prompt.txt가 초기화되었습니다." 출력 후 종료

AskUserQuestion 없이 즉시 실행합니다.

### 0.5. --ccv 인자 확인

`$ARGUMENTS`에 `--ccv`가 포함된 경우, **Claude Code Vanilla 모드**로 전환합니다.

이 모드에서는 다음과 같이 동작합니다:

1. **스킬 로드 건너뛰기**: `prompt-engineering-guide` 스킬을 로드하지 않습니다 (Step 1.5 생략)
2. **모호성 분석 생략**: 5대 모호성 유형 체크와 자가 점검 체크리스트를 적용하지 않습니다 (Step 2의 스킬 기반 분석 생략)
3. **구조화된 질의 생략**: AskUserQuestion 반복 루프를 사용하지 않습니다 (Step 3 생략)

대신 다음의 단순 흐름으로 전환합니다:

1. Read 도구로 `.prompt/prompt.txt`를 읽어 현재 내용을 확인합니다
2. 일반 Claude처럼 사용자와 자유 대화로 프롬프트를 정제합니다
3. 사용자가 만족하면 Write 도구로 `.prompt/prompt.txt`에 개선된 내용을 저장합니다
4. 완료 메시지를 출력합니다

> `--ccv` 모드에서는 프롬프트 구조화 5요소, 용도별 템플릿 등 스킬 기반 규칙을 적용하지 않습니다. 사용자의 의도와 대화 흐름에 따라 자연스럽게 프롬프트를 개선합니다.

### 1. prompt.txt 읽기

Read 도구로 `.prompt/prompt.txt`를 읽습니다.

**빈 파일 또는 공백만 있는 경우:**

"prompt.txt에 내용이 없습니다. 먼저 .prompt/prompt.txt에 프롬프트를 작성해주세요." 출력 후 종료합니다.

### 1.5. 스킬 로드

Read 도구로 `.claude/skills/prompt-engineering-guide/SKILL.md`를 읽어 모호성 분석 체크리스트, 프롬프트 구조화 5요소, 핵심 원칙을 로드합니다.

프롬프트 내용으로부터 **용도를 판별**합니다:

| 용도 키워드 | 추가 로드 대상 |
|------------|---------------|
| 구현, 기능, 함수, 모듈 | `references/prompt-templates.md` (기능 구현 템플릿) |
| 버그, 오류, 에러, 수정 | `references/prompt-templates.md` (버그 수정 템플릿) |
| 리팩토링, 정리, 분리 | `references/prompt-templates.md` (리팩토링 템플릿) |
| 리뷰, 검토 | `references/prompt-templates.md` (코드 리뷰 템플릿) |
| 조사, 비교, 연구 | `references/prompt-templates.md` (연구 조사 템플릿) |
| 설계, 아키텍처, 시스템 | `references/prompt-templates.md` (아키텍처 설계 템플릿) |
| 에이전트, 서브에이전트, 도구 | `references/claude-code-patterns.md` (Claude Code 특화 패턴) |

> 용도가 불명확하면 `references/prompt-templates.md`와 `references/claude-code-patterns.md`를 모두 로드합니다.

### 2. 현재 내용 표시 및 분석

터미널에 현재 prompt.txt 내용을 출력합니다:

```
## 현재 prompt.txt 내용

<prompt.txt 내용 전체>
```

**스킬 기반 모호성 분석**: 로드한 `prompt-engineering-guide` 스킬의 **모호성 분석 체크리스트** (5대 모호성 유형)와 **자가 점검 체크리스트** (7개 항목)를 기준으로 프롬프트를 분석합니다.

| # | 모호성 유형 | 판단 기준 |
|---|------------|----------|
| 1 | 대상 불명확 | 작업 대상 파일/컴포넌트/모듈이 특정되지 않음 |
| 2 | 요구사항 불완전 | 원하는 동작/결과가 구체적으로 기술되지 않음 |
| 3 | 컨텍스트 부족 | 배경 정보, 제약 조건, 기술 스택 등이 누락됨 |
| 4 | 범위 미정의 | 여러 해석이 가능한 요청, 무제한적 범위 표현 |
| 5 | 제약 조건 누락 | "빠르게", "깔끔하게" 같은 형용사형 목표, 측정 불가 기준 |

추가로 **자가 점검 체크리스트**를 적용합니다:

- 숫자 명확성: "빠른", "적절한" 대신 구체적 수치 포함 여부
- 단일 목표: 하나의 턴에 하나의 작업인지 (복합 요청 분리 필요 여부)
- 경계 조건: 엣지 케이스, 한계값, 예외 상황 정의 여부
- 긍정 지시: "~하지 마시오" 대신 "~을 사용하시오" 형태인지
- 공유 어휘: 전문 용어 사용 시 컨텍스트 제공 여부
- 검증 기준: 완료 기준이 측정 가능한지
- 기존 패턴: 유사한 기존 구현체 파일 참조 포함 여부

### 3. AskUserQuestion 반복 루프

분석된 모호성 항목을 기반으로 질문을 제시합니다. **스킬의 모호성 분석 체크리스트에서 발견된 항목 순서대로** 가장 중요한 모호성부터 질문합니다.

질문 생성 시 스킬의 **"개선 질문 예시"**를 참고하되, 프롬프트 내용에 맞게 구체화합니다. 또한 판별된 용도에 해당하는 **템플릿의 좋은 예/나쁜 예**를 참고하여, 현재 프롬프트가 "나쁜 예"에 가까운 부분을 "좋은 예" 수준으로 개선하는 방향으로 질문을 구성합니다.

```
AskUserQuestion(
  questions: [{
    question: "<스킬 체크리스트 기반 구체적 질문>",
    header: "프롬프트 개선",
    options: [
      { label: "<모호성 항목 A에 대한 구체적 옵션>", description: "<설명>" },
      { label: "<모호성 항목 B에 대한 구체적 옵션>", description: "<설명>" },
      { label: "현재 내용이 충분합니다 (완료)", description: "개선을 마치고 저장합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **구체적 옵션 선택** | 해당 항목을 프롬프트에 반영한 뒤 Step 3 재실행 |
| **사용자 직접 입력 (Other)** | 입력 내용을 프롬프트에 반영한 뒤 Step 3 재실행 |
| **"현재 내용이 충분합니다 (완료)"** | Step 4로 진행 |

> Step 3은 사용자가 "완료"를 선택할 때까지 반복합니다. 매 반복마다 스킬의 **모호성 분석 체크리스트 5항목**과 **자가 점검 체크리스트 7항목**을 재적용하여 남은 모호성을 재분석하고 질문을 갱신합니다.

### 4. 프롬프트 구조화 및 저장

개선된 프롬프트를 스킬의 **프롬프트 구조화 5요소** (명확한 목표, 구체적 대상, 제약 조건, 검증 기준, 참조 컨텍스트)에 맞춰 정리합니다. 용도에 맞는 **템플릿 구조**가 있으면 해당 구조를 적용합니다.

Write 도구로 `.prompt/prompt.txt`에 개선된 내용 전체를 덮어쓰기합니다.

터미널에 개선 전/후 변경 요약을 출력합니다:

```
## 변경 요약

**개선 전**: <원본 내용 요약 (1-2줄)>
**개선 후**: <개선된 내용 요약 (1-2줄)>
**주요 변경**: <추가/수정/구체화된 항목 나열>
**적용 스킬**: prompt-engineering-guide (<적용된 체크리스트/템플릿 항목>)
```

### 5. 완료 메시지

```
prompt.txt가 업데이트되었습니다. 이제 cc:implement, cc:research 등을 실행하세요.
```

## 완료 조건

| 조건 | 처리 |
|------|------|
| 사용자가 "완료" 선택 | 개선된 prompt.txt 저장 후 종료 |
| prompt.txt 빈 파일 | 안내 메시지 출력 후 종료 |
| `$ARGUMENTS`에 `--clear` 포함 | AskUserQuestion 없이 prompt.txt를 빈 파일로 초기화 후 종료 |
| `$ARGUMENTS`에 `--ccv` 포함 | 스킬 참조 없이 일반 Claude 대화로 prompt.txt 정제 후 저장 |

## 주의사항

1. **Task 도구 호출 금지**: 이 명령어는 비워크플로우 독립 명령어이므로 서브에이전트를 호출하지 않습니다
2. **Bash 도구 호출 금지**: 가드 스크립트 비간섭을 보장합니다. 셸 명령어 실행이 필요 없습니다
3. **사용 가능 도구**: Read, Write, AskUserQuestion만 사용합니다
4. **워크플로우 무관**: FSM 상태 전이, init_workflow.py, workflow_agent_guard.py, workflow_transition_guard.py와 완전히 무관합니다. 배너 출력, workDir 생성, status.json/registry.json 조작을 하지 않습니다
5. **--ccv 모드 제한**: --ccv 모드에서는 prompt-engineering-guide 스킬의 모호성 분석 체크리스트, 프롬프트 구조화 5요소, 용도별 템플릿을 참조하지 않는다. 사용자와의 자연스러운 대화를 통해 프롬프트를 개선한다

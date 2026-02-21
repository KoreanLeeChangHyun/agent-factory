---
description: ".prompt/prompt.txt의 내용을 대화형으로 정제합니다. 모호한 프롬프트를 질의응답으로 개선합니다."
argument-hint: "[--clear]"
---

# Prompt (Prompt Refinement)

`.prompt/prompt.txt`의 프롬프트를 대화형 질의응답으로 정제합니다. 워크플로우(FSM/가드/서브에이전트)와 무관한 독립 명령어입니다.

## 입력: $ARGUMENTS

| 인자 | 설명 | 필수 |
|------|------|------|
| `--clear` | prompt.txt를 빈 파일로 초기화 | 아니오 |

## 실행 흐름

### 0. --clear 인자 확인

`$ARGUMENTS`에 `--clear`가 포함된 경우:

1. Write 도구로 `.prompt/prompt.txt`에 빈 문자열을 덮어쓰기
2. "prompt.txt가 초기화되었습니다." 출력 후 종료

AskUserQuestion 없이 즉시 실행합니다.

### 1. prompt.txt 읽기

Read 도구로 `.prompt/prompt.txt`를 읽습니다.

**빈 파일 또는 공백만 있는 경우:**

"prompt.txt에 내용이 없습니다. 먼저 .prompt/prompt.txt에 프롬프트를 작성해주세요." 출력 후 종료합니다.

### 2. 현재 내용 표시 및 분석

터미널에 현재 prompt.txt 내용을 출력합니다:

```
## 현재 prompt.txt 내용

<prompt.txt 내용 전체>
```

내부적으로 다음 모호성 요소를 분석합니다:

| 모호성 유형 | 판단 기준 |
|------------|----------|
| 대상 불명확 | 작업 대상 파일/컴포넌트/모듈이 특정되지 않음 |
| 요구사항 불완전 | 원하는 동작/결과가 구체적으로 기술되지 않음 |
| 컨텍스트 부족 | 배경 정보, 제약 조건, 기술 스택 등이 누락됨 |

### 3. AskUserQuestion 반복 루프

분석된 모호성 항목을 기반으로 질문을 제시합니다.

```
AskUserQuestion(
  questions: [{
    question: "<분석된 모호성 기반 구체적 질문>",
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

> Step 3은 사용자가 "완료"를 선택할 때까지 반복합니다. 매 반복마다 개선된 프롬프트의 남은 모호성을 재분석하여 질문을 갱신합니다.

### 4. 개선된 prompt.txt 저장

Write 도구로 `.prompt/prompt.txt`에 개선된 내용 전체를 덮어쓰기합니다.

터미널에 개선 전/후 변경 요약을 출력합니다:

```
## 변경 요약

**개선 전**: <원본 내용 요약 (1-2줄)>
**개선 후**: <개선된 내용 요약 (1-2줄)>
**주요 변경**: <추가/수정/구체화된 항목 나열>
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

## 주의사항

1. **Task 도구 호출 금지**: 이 명령어는 비워크플로우 독립 명령어이므로 서브에이전트를 호출하지 않습니다
2. **Bash 도구 호출 금지**: 가드 스크립트 비간섭을 보장합니다. 셸 명령어 실행이 필요 없습니다
3. **사용 가능 도구**: Read, Write, AskUserQuestion만 사용합니다
4. **워크플로우 무관**: FSM 상태 전이, init_workflow.py, workflow_agent_guard.py, workflow_transition_guard.py와 완전히 무관합니다. 배너 출력, workDir 생성, status.json/registry.json 조작을 하지 않습니다

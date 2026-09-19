---
name: design-clickable-questions
description: Agent Factory 익스텐션 프로젝트에 적용합니다. Agent가 지정한 클릭 가능한 선택형 질문의 즉시 전송, 적용 범위와
  표 안의 번호 컨트롤을 설계하거나 구현할 때 적용합니다.
metadata:
  document-type: specification
  category: design
  domain: null
  name: clickable-questions
  specification-id: design-clickable-questions
  version: 1.1.0
  language: ko
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/design-clickable-questions/SKILL.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: design-clickable-questions
      description: Agent Factory 익스텐션 프로젝트에 적용합니다. Agent가 지정한 클릭 가능한 선택형 질문의 즉시 전송,
        적용 범위와 표 안의 번호 컨트롤을 설계하거나 구현할 때 적용합니다.
      metadata:
        document-type: specification
        category: design
        domain: null
        name: clickable-questions
        specification-id: design-clickable-questions
        version: 1.1.0
        semantic-revision: 2
        modified-at: '2026-09-17T14:04:17Z'
        language: ko
---


# 클릭 가능한 선택형 질문 설계

- 적용 대상은 Agent Factory 익스텐션입니다. 플러그인 내부 구현과 MCP 개발 규칙은 이 문서가 소유하지 않습니다.

- 수락된 Specification입니다. 문서 식별자는 `design-clickable-questions`이며 버전은 1.1.0입니다.

<!-- clause-id: clickable-questions.activation -->

<a id="선택-시-즉시-전송"></a>

## 1. 선택 시 즉시 전송

- 클릭 가능한 선택지를 활성화하면 선택한 답변을 즉시 전송해야 합니다. 별도의 전송 확인 단계를 두지 않습니다.

<!-- clause-id: clickable-questions.designation -->

<a id="agent가-지정한-질문에만-적용"></a>

## 2. Agent가 지정한 질문에만 적용

- 클릭 가능한 선택지는 Agent가 명시적으로 지정한 질문에만 적용해야 합니다. 임의의 비교표를 자동으로 클릭 가능한 선택지로 변환하지 않습니다.

<!-- clause-id: clickable-questions.option-numbers -->

<a id="선택-열의-번호를-클릭-가능한-컨트롤로-표시"></a>

## 3. 선택 열의 번호를 클릭 가능한 컨트롤로 표시

- Agent가 명시적으로 지정한 선택형 질문에서는 표의 선택 열에 있는 각 선택지 번호(예: 1, 2, 3) 자체가 해당 선택지에 연결된 클릭 가능한 컨트롤이어야 합니다. 첫 번째 선택지만이 아니라 모든 선택지에 적용합니다. 번호를 활성화하면 clickable-questions.activation 조항에 따라 해당 답변을 즉시 전송합니다.

- 이 질문에서는 일반적인 질문 버튼을 해당 선택지 전용 컨트롤로 대체합니다. 질문의 비교표와 선택지 설명·장점·단점은 유지하며, 컨트롤을 표 아래에 배치하거나 표를 카드로 대체하지 않습니다. clickable-questions.designation 조항에 따라 무관한 비교표에는 적용하지 않습니다.

<a id="구현-범위의-한계"></a>

## 4. 구현 범위의 한계

- 기술적 전송 형식, 수락된 컨트롤 배치 이외의 시각적 스타일, 영속화는 아직 정하지 않은 구현 세부사항입니다. 이 문서는 이를 추가 요구사항으로 규정하지 않으며 기능 구현 완료를 나타내지 않습니다. 문서 정체성과 인터뷰 완료에 관한 미해결 Human 결정은 없습니다.

<a id="정본-관리"></a>

## 5. 정본 관리

- `docs/skills/design-clickable-questions/SKILL.md`를 단일 정본으로 수정합니다.
- `.codex/skills/design-clickable-questions/SKILL.md`는 정본에서 자동 동기화한 파생본입니다.

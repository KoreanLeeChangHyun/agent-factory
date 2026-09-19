---
name: design-auto-execution-mode
description: Agent Factory 작성기의 메시지별 실행 액션과 일반 Main 직접 전송 계약을 적용합니다.
metadata:
  document-type: specification
  category: design
  domain: null
  name: auto-execution-mode
  specification-id: design-auto-execution-mode
  version: 2.0.0
  language: ko
  provenance:
    prior-provenance:
      authority: Human 요청에 따른 메시지별 실행 액션 전환, 2026-09-18 KST
      supersedes: 버전 1.1.0 semantic-revision 2의 자동 기본값과 영속 모드 선택
    merged-from:
    - docs/skills/design-auto-execution-mode/SKILL.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: design-auto-execution-mode
      description: Agent Factory 작성기의 메시지별 실행 액션과 일반 Main 직접 전송 계약을 적용합니다.
      metadata:
        document-type: specification
        category: design
        domain: null
        name: auto-execution-mode
        specification-id: design-auto-execution-mode
        version: 2.0.0
        semantic-revision: 3
        modified-at: '2026-09-17T18:21:09Z'
        language: ko
        provenance:
          authority: Human 요청에 따른 메시지별 실행 액션 전환, 2026-09-18 KST
          supersedes: 버전 1.1.0 semantic-revision 2의 자동 기본값과 영속 모드 선택
---


# 메시지별 실행 액션

- 적용 대상은 Agent Factory 익스텐션입니다. 기존 Skill identity는 참조 호환을 위해 유지합니다.
- 일반 Enter와 전송 버튼은 항상 Main 직접 실행입니다. 예전 자동·Work·검증 모드 저장값을 복원해도 다음 전송에 적용하지 않습니다.
- 작성기 메뉴에는 `work`, `plan`, `verification`, `plan-work`, `work-verification`, `plan-work-verification` 여섯 액션을 둡니다. 클릭하면 현재 초안과 첨부를 Main에 즉시 전송합니다. 다음 메시지로 선택을 저장하지 않습니다.
- Main은 메시지에 캡처된 액션을 받아 관리형 Agent를 조율합니다. Work는 실제 Work, Verification은 실제 Verification Agent를 실행합니다.
- Plan 단독은 Work의 실제 Codex Plan 협업 모드로 계획만 작성합니다. 문자 `/plan` 삽입으로 대체하지 않습니다.
- Plan·Work는 같은 Work 세션에서 Plan→실행으로 전환합니다. Plan·Work·Verification은 이후 같은 Work·Verification 세션을 재사용하는 수정·재검증 루프를 수행합니다.
- 독립 Verification은 명시한 대상을 우선하고, 없으면 현재 채팅에서 앞서 완료한 작업을 대상으로 합니다. 대상이 없거나 불명확하면 질문하며 Work 증거를 만들지 않습니다. 독립 receipt는 Work 루프 receipt와 구분합니다.
- 대기열은 입력별 액션을 보존하며 다른 액션끼리 병합하지 않습니다. 기존 실행을 취소하거나 그 액션을 바꾸지 않습니다.
- 업무 모드, 첨부, Goal 일회 적용과 별도 실행 권한 계약은 유지합니다. Verification 액션에는 Goal을 적용하지 않습니다.
- capability가 없으면 지원되지 않는 액션을 거부합니다. 과거 실행 기록의 경로를 재해석하지 않습니다.

<a id="이전-명세의-출처"></a>

## 1. 이전 명세의 출처

- 2026-09-17 버전 1.1.0은 새 채팅 자동 모드, 기존 선택 유지, 규모·영향에 따른 경로 판단을 규정했습니다. 이 정책은 위 Human 요청으로 대체되었으며 역사적 근거로만 남깁니다. 당시 구체적 자동 판정 알고리즘은 미확정이었습니다.

<a id="정본-관리"></a>

## 2. 정본 관리

- `docs/skills/design-auto-execution-mode/SKILL.md`가 정본이며 `.codex/skills/`는 단방향 동기화한 파생본입니다.

<a id="제출-액션-표시"></a>

## 3. 제출 액션 표시

- Human이 승인한 메시지 렌더링 요청(2026-09-18 KST)에 따라 선택한 액션은 해당 메시지의 제출 메타데이터로 남깁니다. Work·Plan·Verification과 조합은 명시한 순서로 표시하며 일반 direct에는 추가 배지를 표시하지 않습니다.
- 대기열·수락·채팅 복원에서도 제출 값을 유지하고 실행 중·완료 상태와 구분합니다. 실제 전달된 앱 추가 지침과 원문 표시는 [채팅 설계](../design-main-chat/SKILL.md)의 계약을 따릅니다.

<a id="작성기-아이콘의-동작-구분"></a>

## 4. 작성기 아이콘의 동작 구분

- 선택·메뉴 열기에는 펼침 화살표를 사용합니다. 워크플로우·실행 액션 메뉴를 여는 동작과 항목의 즉시 제출을 구분합니다.
- 즉시 제출하는 메뉴 항목과 Goal에는 전송 화살표를 표시합니다. Goal은 라벨을 함께 표시하고 토글 상태를 갖지 않습니다.
- Fast와 자동 스크롤은 각각 `Fast`, `Scroll` 라벨과 SVG 스위치를 표시하며 켜짐·꺼짐을 손잡이 위치와 접근성 상태로 구분합니다. 색상이나 테두리 강조만으로 상태를 전달하지 않습니다.

<a id="통합-설정과-제출-메뉴"></a>

## 5. 통합 설정과 제출 메뉴

- 모델·추론 수준·권한은 하나의 설정 패널에서 관리합니다. 모델·추론은 Agent별, 권한은 다음 메시지에 적용되는 공통 설정으로 구분합니다. 실행 중 권한 변경은 막습니다.
- 일반 전송 버튼과 Enter는 Main 직접 전송입니다. 옆의 펼침 버튼은 워크플로우·작업·Goal 그룹의 제출 메뉴를 엽니다. 항목을 누르면 현재 초안을 즉시 해당 방식으로 제출하며 선택을 다음 메시지에 유지하지 않습니다.
- 작성기에는 별도 권한·워크플로우·작업·Goal 버튼을 두지 않습니다. `Fast`, `Scroll` 스위치를 유지합니다.
- 텍스트·첨부가 모두 없으면 전송하지 않고 입력창에 필요한 내용과 간단한 입력 예시를 안내합니다. 첨부만 있는 일반 요청과 문맥상 충분한 짧은 답변을 길이 기준으로 거부하지 않습니다. Goal은 목표 텍스트가 필요합니다.
- Main은 대화·첨부까지 확인한 뒤 내용이 부족하면 부족한 항목·필요한 이유·추가 입력 예시를 구체적으로 안내합니다. 이미 제공된 내용을 다시 요구하거나 의미를 추측해 완료 처리하지 않습니다. 이 AI 판단 계약은 플러그인의 Main 프롬프트가 소유합니다.

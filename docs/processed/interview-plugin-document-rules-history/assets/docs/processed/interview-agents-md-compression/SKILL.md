---
name: interview-agents-md-compression
description: 루트 AGENTS.md 압축에 관한 완료된 인터뷰의 비권위적 기록입니다.
metadata:
  document-type: processed
  category: interview
  domain: null
  name: agents-md-compression
  language: ko
  provenance:
    - "Main 인터뷰: run-20260917T122829141384Z-044c8184/result.md"
    - "Main 인터뷰: run-20260917T123113678366Z-de0b020b/result.md"
    - "Main 위임 요청: run-20260917T123633040236Z-261d8a48/request.md"
---

# AGENTS.md 압축 인터뷰 기록

## 성격과 출처

- 이 문서는 완료된 인터뷰를 정리한 비권위적 Processed 작업 지식입니다. 실행 지침이나 Specification으로 승격된 문서가 아닙니다.
- 질문·선택지·권고는 아래 Main 실행 기록에서 옮겼습니다. 표제는 한국어로 정리했으며, Human의 선택은 Main의 위임 요청에 근거합니다.
- 첫 질문 출처: `/home/deus/.agent-factory/projects/project-a27653322490497fa8b2009fc4f28352/agents/main-cbd4f7f1-f1cf-4378-903f-a906a154a0c6/runs/run-20260917T122829141384Z-044c8184/result.md`.
- 둘째 질문 출처: `/home/deus/.agent-factory/projects/project-a27653322490497fa8b2009fc4f28352/agents/main-cbd4f7f1-f1cf-4378-903f-a906a154a0c6/runs/run-20260917T123113678366Z-de0b020b/result.md`.
- 선택 및 실행 범위 출처: `/home/deus/.agent-factory/projects/project-a27653322490497fa8b2009fc4f28352/agents/work-agents-md-compress-890618c4/runs/run-20260917T123633040236Z-261d8a48/request.md`.
- Main이 참고한 [공식 OpenAI AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md)의 요지는 루트에 저장소 공통 기대사항을 두고, 특수 규칙은 해당 코드 가까이에 배치하며, 지침을 간결하게 유지하는 것입니다. 이는 Main의 조사 결과를 기록한 것이며 Work의 별도 웹 검증 결과가 아닙니다.

## 최초 결정 목록과 질문 수

1. 루트 `AGENTS.md`를 어느 수준으로 압축할지 결정합니다.
2. 결과의 문서 분류와 완료 신호를 결정합니다. 최초 안내는 이를 “압축본을 완료된 Specification으로 승격할 때 사용할 이름·분류와 완료 확인”이라고 표현했습니다.

- 총 질문 수는 2개였으며 변경되지 않았습니다.
- 둘째 질문에서는 대상이 Provider 실행 지침이라는 소유권 근거를 반영하여, Specification 승격을 전제하지 않고 분류와 완료 신호를 선택하도록 구체화했습니다.

## 질문 1과 결정

질문: [1/2] 어느 수준으로 압축할까요?

| 선택지 | 결정 | 장점 | 단점 |
|---|---|---|---|
| 1 | 의미 보존형: 저장소 고유 의무와 경계를 모두 유지하고 중복·설명·링크 목록만 축약 | 기존 계약 손실 위험이 가장 낮음 | 길이 감소 폭은 중간 수준 |
| 2 | 핵심 규칙형: 일상 작업에 필요한 구조·소유권·변경 규칙만 남김 | 가장 짧고 읽기 쉬움 | 드물게 필요한 경로·예외를 Skill에서 다시 찾아야 함 |
| 3 | 최소 인덱스형: “관련 Skill을 읽고 따르라”는 안내와 핵심 정체성만 남김 | 토큰 사용량이 가장 적음 | 중요한 저장소 경계가 즉시 보이지 않아 누락 위험이 커짐 |

권고: **Option 1**을 권장합니다. 공식 문서의 간결성 원칙을 따르면서도 이 저장소의 중요한 소유권·저장 위치·기여 경계를 보존할 수 있습니다.

직전 결정:

- 없음

- Human 선택: **Option 2 — 핵심 규칙형**입니다.
- 권고는 Option 1이었지만 실제 결정은 Option 2입니다. 권고를 Human의 승인으로 취급하지 않습니다.

## 질문 2와 결정

질문: [2/2] 결과의 문서 분류와 완료 신호를 어떻게 정할까요?

| 선택지 | 결정 | 장점 | 단점 |
|---|---|---|---|
| 1 | 압축된 `AGENTS.md` 자체를 최종 Provider 지침으로 사용하고, 수정 및 자체 점검 완료를 워크플로 완료 신호로 간주 | 기존 소유권과 파일 역할을 보존하며 별도 중복 문서를 만들지 않음 | 별도의 Specification 표시 문서는 없음 |
| 2 | `AGENTS.md`를 수정하고 Client `rule-agent-factory-plugin-guidance` Specification도 함께 생성한 뒤 완료 처리 | 별도 규칙 문서가 명시적으로 남음 | Provider 지침을 Client Specification으로 중복하여 저장소 계약과 충돌할 수 있음 |
| 3 | 우선 Processed 인터뷰 기록과 압축 초안만 만들고, 완료 및 승격은 이후 확인으로 보류 | 검토 후 의미를 조정하기 쉬움 | 이번 요청에서 `AGENTS.md` 최종 수정이 완료되지 않음 |

권고: **Option 1**을 권장합니다. 대상이 이미 Provider 지침이므로 해당 파일을 간결하게 유지하는 것이 가장 정확합니다.

직전 결정:

- 핵심 규칙형으로 압축하여 일상 작업에 필요한 구조·소유권·변경 규칙만 유지

- Human 선택: **Option 1**입니다.
- 질문의 “자체 점검”은 위임 요청에서 **Main의 점검**으로 명시되었습니다. Work의 자체 검증이나 테스트 실행을 허용하지 않습니다.

## 전체 결정 이력과 최종 요약

1. Human은 첫 질문에서 Option 2를 선택하셨습니다. 일상 작업에 필요한 구조·소유권·저장 위치·기여 규칙을 유지하고 상세 참조 목록과 불필요한 표현을 제거합니다.
2. Human은 둘째 질문에서 Option 1을 선택하셨습니다. 압축된 `AGENTS.md` 자체가 최종 Provider 지침이며, 수정과 Main의 점검 완료가 워크플로 완료 신호입니다. 별도 Client Specification을 만들지 않습니다.

- 유지 대상은 공개 Skill `agent`·`convention`의 정체성, 소유 Skill과 참조의 사전 열람, `.codex/` 복제 금지, 체크아웃 외부 런타임, MCP 도메인 분리, 영어 Provider 지침, 공유 체크아웃과 무관한 작업 보존, Work의 자체 검증·커밋 금지, `tests/` 구성 및 development 소유 릴리스 규칙입니다.
- 완료된 인터뷰의 기록 의무에 따라 이 Processed 문서를 작성합니다. 이 문서의 작성이나 인터뷰 완료는 Specification 승격 또는 점검 통과를 뜻하지 않습니다.
- 제공된 기록에 추가 Human 정정이나 미해결 결정은 없습니다. Main의 점검은 Work 결과 이후에 수행할 절차이며, 이 기록은 그 완료를 주장하지 않습니다.

---
name: rule-layout
description: Apply Agent Factory SaaS's canonical names for the three basic layout
  regions when designing, implementing, documenting, reviewing, or discussing its
  interface.
metadata:
  document-type: specification
  category: rule
  domain: null
  name: layout
  language: ko
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/rule-layout/SKILL.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: rule-layout
      description: Apply Agent Factory SaaS's canonical names for the three basic
        layout regions when designing, implementing, documenting, reviewing, or discussing
        its interface.
---


# 기본 레이아웃 명칭

- Agent Factory SaaS의 기본 레이아웃은 화면 왼쪽부터 다음 세 영역으로 부른다.

| 순서 | 공식 명칭 | 가리키는 영역 |
| --- | --- | --- |
| 1 | 작업 목록 | 최상위 작업을 전환하는 왼쪽의 좁은 세로 영역 |
| 2 | 사이드바 | 선택한 작업의 탐색·목록·보조 동작을 표시하는 영역 |
| 3 | 패널 | 선택한 대상의 주 콘텐츠와 작업 화면을 표시하는 영역 |

- 요구사항, 설계 문서, 코드 설명, 리뷰, 사용자와의 대화에서는 **작업 목록 | 사이드바 | 패널**을 제품 용어로 사용한다. `Activity Bar`, `Primary Sidebar`, `Workspace area`, `작업 표시줄`, `작업 영역`은 외부 제품을 인용하거나 기존 구현 식별자를 설명할 때만 보조적으로 쓴다.

- 기존 CSS 클래스, `data-*` 속성, 접근성 landmark, API 이름은 기술적 호환 계약이므로 명칭 논의만으로 바꾸지 않는다. 실제 리팩터링이 요청된 경우에만 영향 범위와 테스트를 확인한 뒤 변경한다.

- 도메인 데이터로서의 작업 목록과 레이아웃 영역인 `작업 목록`이 한 문맥에 함께 나오면 전자는 `일정 작업 목록`, `실행 작업 목록`처럼 대상을 붙여 구분한다.

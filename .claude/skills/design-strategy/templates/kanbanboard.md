<!--
  .kanbanboard Template
  =====================
  strategy 명령어가 roadmap.md 생성 직후 이 템플릿을 기반으로 .kanbanboard 파일을 생성한다.

  치환 포인트({{placeholder}}) 목록:
    - {{project}}       : 프로젝트명 (roadmap.md의 H1 제목에서 추출)
    - {{roadmap_path}}  : roadmap.md 파일의 상대 경로 (.workflow/[타임스탬프]/[워크명]/strategy/roadmap.md)
    - {{created_date}}  : .kanbanboard 생성일 (YYYY-MM-DD)
    - {{updated_date}}  : .kanbanboard 최종 갱신일 (YYYY-MM-DD)
    - {{planned_cards}} : Planned 컬럼에 배치할 마일스톤 카드 블록 (아래 카드 템플릿 참조)
    - {{in_progress_cards}} : In Progress 컬럼에 배치할 마일스톤 카드 블록 (초기 생성 시 비어 있음)
    - {{done_cards}}    : Done 컬럼에 배치할 마일스톤 카드 블록 (초기 생성 시 비어 있음)

  마일스톤 카드 템플릿 ({{planned_cards}} 등에 삽입되는 단위):
    ### {{ms_id}}: {{ms_name}}
    - **ID**: {{ms_id}}
    - **완료 기준 (DoD)**:
      - [ ] {{dod_item_1}}
      - [ ] {{dod_item_2}}
      ...
    - **워크플로우**:
      - [ ] {{wf_id}}: {{wf_name}} ({{wf_command}})
      - [ ] {{wf_id}}: {{wf_name}} ({{wf_command}})
      ...
    - **상태**: 0/{{wf_total}} 완료

  SSOT 원칙:
    - roadmap.md = 계획 정보의 단일 진실 소스 (마일스톤 ID, 명칭, DoD, 워크플로우 체인)
    - .kanbanboard = 실행 상태 전용 (컬럼 배치, 워크플로우 체크 상태, 완료일)
    - 마일스톤 ID/명/DoD는 roadmap.md에서 그대로 복제
    - 워크플로우 체인의 ID/명/명령어를 마일스톤별로 그룹핑하여 카드에 기록

  컬럼 상태 전이 규칙:
    1. Planned -> In Progress
       - 조건: 마일스톤에 속한 첫 번째 워크플로우가 시작될 때
       - 동작: 해당 마일스톤 카드 블록을 Planned 섹션에서 제거하고 In Progress 섹션 하단에 삽입
    2. In Progress -> Done
       - 조건: 마일스톤의 모든 DoD 항목이 충족되고 모든 워크플로우가 완료(체크)되었을 때
       - 동작: 해당 마일스톤 카드 블록을 In Progress 섹션에서 제거하고 Done 섹션 하단에 삽입
       - 추가: 카드에 "완료일: YYYY-MM-DD" 항목 추가
    3. 프로젝트 완료 판단
       - 조건: 모든 마일스톤이 Done 컬럼에 위치할 때
       - 동작: strategy Judge 모드에서 "프로젝트 완료" 선언
-->
---
project: "{{project}}"
roadmap: "{{roadmap_path}}"
created: {{created_date}}
updated: {{updated_date}}
---

# {{project}} Kanban Board

## Planned

{{planned_cards}}

## In Progress

{{in_progress_cards}}

## Done

{{done_cards}}

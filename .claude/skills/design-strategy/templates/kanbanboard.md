<!--
  로드맵 진행 추적 템플릿
  =========================
  strategy 명령어가 roadmap.md 생성 직후 이 템플릿을 기반으로 로드맵 진행 상태를 기록한다.
  실행 상태는 .kanban/ 디렉터리의 T-NNN.xml 파일을 직접 스캔하여 관리한다.

  치환 포인트({{placeholder}}) 목록:
    - {{project}}       : 프로젝트명 (roadmap.md의 H1 제목에서 추출)
    - {{roadmap_path}}  : roadmap.md 파일의 상대 경로 (.workflow/[타임스탬프]/[워크명]/strategy/roadmap.md)
    - {{created_date}}  : 생성일 (YYYY-MM-DD)
    - {{updated_date}}  : 최종 갱신일 (YYYY-MM-DD)
    - {{open_cards}}    : Open 상태 마일스톤 카드 블록 (아래 카드 템플릿 참조)
    - {{in_progress_cards}} : In Progress 상태 마일스톤 카드 블록 (초기 생성 시 비어 있음)
    - {{done_cards}}    : Done 상태 마일스톤 카드 블록 (초기 생성 시 비어 있음)

  마일스톤 카드 템플릿 ({{open_cards}} 등에 삽입되는 단위):
    ### {{ms_id}}: {{ms_name}}
    - **ID**: {{ms_id}}
    - **완료 기준 (DoD)**:
      - [ ] {{dod_item_1}}
      - [ ] {{dod_item_2}}
      ...
    - **워크플로우**:
      - [ ] T-NNN: {{wf_name}} ({{wf_command}})
      - [ ] T-NNN: {{wf_name}} ({{wf_command}})
      ...
    - **상태**: 0/{{wf_total}} 완료

  티켓 자동 생성 절차 (마일스톤별 워크플로우 항목):
    1. roadmap.md의 각 워크플로우 항목마다 .kanban/active/T-NNN.xml 티켓 파일을 생성한다.
    2. 티켓 번호(NNN)는 .kanban/ 디렉터리의 XML 파일을 스캔하여 기존 최대 번호 + 1로 자동 채번한다.
    3. 티켓 파일 경로: .kanban/active/T-NNN.xml (표준 XML 티켓 형식)

  SSOT 원칙:
    - roadmap.md = 계획 정보의 단일 진실 소스 (마일스톤 ID, 명칭, DoD, 워크플로우 체인)
    - .kanban/active/T-NNN.xml = 워크플로우별 실행 상태 (XML <status> 요소로 관리)
    - 마일스톤 ID/명/DoD는 roadmap.md에서 그대로 복제
    - 워크플로우 체인의 ID/명/명령어를 마일스톤별로 그룹핑하여 카드에 기록

  마일스톤 상태 전이 규칙 (XML 스캔 기반):
    1. Open -> In Progress
       - 조건: 마일스톤에 속한 첫 번째 워크플로우 티켓이 In Progress 이상일 때
    2. In Progress -> Done
       - 조건: 마일스톤의 모든 DoD 항목이 충족되고 모든 워크플로우 티켓이 Done 상태일 때
    3. 프로젝트 완료 판단
       - 조건: 모든 마일스톤 소속 티켓이 Done 상태일 때
       - 동작: strategy Judge 모드에서 "프로젝트 완료" 선언
-->
---
project: "{{project}}"
roadmap: "{{roadmap_path}}"
created: {{created_date}}
updated: {{updated_date}}
---

# {{project}} Kanban Board

## Open

{{open_cards}}

## In Progress

{{in_progress_cards}}

## Done

{{done_cards}}

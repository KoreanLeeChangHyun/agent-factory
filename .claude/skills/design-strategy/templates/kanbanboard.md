<!--
  .kanban/board.md Template
  =========================
  strategy 명령어가 roadmap.md 생성 직후 이 템플릿을 기반으로 .kanban/board.md 파일을 갱신한다.

  치환 포인트({{placeholder}}) 목록:
    - {{project}}       : 프로젝트명 (roadmap.md의 H1 제목에서 추출)
    - {{roadmap_path}}  : roadmap.md 파일의 상대 경로 (.workflow/[타임스탬프]/[워크명]/strategy/roadmap.md)
    - {{created_date}}  : .kanban/board.md 생성일 (YYYY-MM-DD)
    - {{updated_date}}  : .kanban/board.md 최종 갱신일 (YYYY-MM-DD)
    - {{open_cards}}    : Open 컬럼에 배치할 마일스톤 카드 블록 (아래 카드 템플릿 참조)
    - {{in_progress_cards}} : In Progress 컬럼에 배치할 마일스톤 카드 블록 (초기 생성 시 비어 있음)
    - {{done_cards}}    : Done 컬럼에 배치할 마일스톤 카드 블록 (초기 생성 시 비어 있음)

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

  티켓 자동 생성 절차 (마일스톤 카드 내 워크플로우 항목):
    1. roadmap.md의 각 워크플로우 항목마다 .kanban/T-NNN.txt 티켓 파일을 생성한다.
    2. 티켓 번호(NNN)는 .kanban/board.md를 파싱하여 기존 최대 번호 + 1로 자동 채번한다.
    3. 생성된 티켓은 .kanban/board.md의 해당 마일스톤 카드 워크플로우 항목에
       `- [ ] T-NNN: {{wf_name}} ({{wf_command}})` 형식으로 기록한다.
    4. 티켓 파일 경로: .kanban/T-NNN.txt
       티켓 내용 형식: YAML frontmatter + XML 태그 본문 (T-NNN.txt 티켓 형식 규격 참조)

  SSOT 원칙:
    - roadmap.md = 계획 정보의 단일 진실 소스 (마일스톤 ID, 명칭, DoD, 워크플로우 체인)
    - .kanban/board.md = 실행 상태 전용 (컬럼 배치, 티켓 체크 상태, 완료일)
    - 마일스톤 ID/명/DoD는 roadmap.md에서 그대로 복제
    - 워크플로우 체인의 ID/명/명령어를 마일스톤별로 그룹핑하여 카드에 기록

  컬럼 상태 전이 규칙:
    1. Open -> In Progress
       - 조건: 마일스톤에 속한 첫 번째 워크플로우(티켓)가 시작될 때
       - 동작: 해당 마일스톤 카드 블록을 Open 섹션에서 제거하고 In Progress 섹션 하단에 삽입
    2. In Progress -> Done
       - 조건: 마일스톤의 모든 DoD 항목이 충족되고 모든 워크플로우(티켓)가 완료(체크)되었을 때
       - 동작: 해당 마일스톤 카드 블록을 In Progress 섹션에서 제거하고 Done 섹션 하단에 삽입
       - 추가: 카드에 "완료일: YYYY-MM-DD" 항목 추가
    3. 프로젝트 완료 판단
       - 조건: 모든 마일스톤이 Done 컬럼에 위치할 때
       - 동작: strategy Judge 모드에서 "프로젝트 완료" 선언

  티켓 항목 형식 (board.md 내 Open/In Progress/Done 컬럼):
    - 미완료: - [ ] T-NNN: 티켓제목 (command)
    - 완료:   - [x] T-NNN: 티켓제목 (command)

  티켓 컬럼 간 이동 규칙:
    - Open → In Progress: 워크플로우 시작 시 initialization.py가 board.md의 티켓 항목을 In Progress로 이동
    - In Progress → Done: 워크플로우 완료 시 finalization.py가 board.md의 티켓 항목을 Done으로 이동하고 [x]로 체크
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

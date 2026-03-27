# 워크플로우 시스템 상세 규칙

## DO
- 코드 수정은 기본적으로 /wf -e 로 티켓 생성/편집 후 /wf -s N 으로 실행
- 사용자가 직접 수정을 명시 요청한 경우에만 메인 세션에서 직접 수정
- 메인 세션은 기본적으로 티켓 관리·상태 확인·결과 리뷰 등 조율 역할 담당
- 자연어 요청도 워크플로우 명령으로 변환하여 처리 (아래 natural-language-mapping 참조)

## DO NOT
- PreToolUse Hook 활성 시 직접 수정 시도하지 않는다 — 차단되므로 토큰 낭비
- 서브에이전트(Task)를 통해 조사·수정을 직접 시도하지 않는다 — 티켓 생성 후 워크플로우로 처리
- flow-kanban 호출 시 alias-reference에 나열되지 않은 서브커맨드를 사용하지 않는다
- /clear 후 시스템 프롬프트가 소실되었다고 가정하지 않는다 — SessionStart hook이 자동 재주입
- 사용자 발화에 명시되지 않은 행위를 추론하여 수행하지 않는다 — "추가해주세요"는 추가만 의미
- python3 .claude.workflow/scripts/... 형태로 스크립트를 직접 호출하지 않는다 — flow-* alias 사용

> 실용적 이유: Hook 활성 시 DO NOT 항목은 차단되므로 시도 자체가 토큰 낭비. 처음부터 /wf 명령어로 진행할 것.

## Alias 레퍼런스

### flow-kanban 서브커맨드 (이 외 사용 금지)
create, move, done, delete, add-subnumber, update-title, update-subnumber, archive-subnumber, set-editing, list, board, show

예시:
  flow-kanban create "제목" --command implement
  flow-kanban add-subnumber T-001 --command implement --goal "목표" --target "대상"
  flow-kanban update-subnumber T-001 1 --goal "목표"   # --id 1도 허용
  flow-kanban archive-subnumber T-001
  flow-kanban move T-001 progress
  flow-kanban done T-001

### XML 필드 개행 컨벤션
복수 항목 필드(goal, target, constraints, criteria, context)에 여러 항목을 입력할 때는 반드시 `\n` 개행을 삽입한다 (MUST).

- 단일 문장: `--constraints "조건1"` (개행 불필요)
- 복수 항목: `--constraints "조건1\n조건2\n조건3"` (MUST)
- 대상 필드: goal, target, constraints, criteria, context 전체

> `\n`이 누락되면 XML 래핑이 실패하여 태그 직후에 텍스트가 붙는 형식 오류가 발생한다.

### 기타 alias
- flow-tmux: launch, cleanup
- flow-claude: start, end
- flow-update: status, both, task-start, task-status, context, link-session, usage-pending, usage, usage-finalize, env
- flow-finish: (registryKey 완료|실패 --ticket-number T-NNN)
- flow-step: start, end
- flow-phase: (registryKey N)
- flow-skillmap: (registryKey)
- flow-init: (command title [mode] [T-NNN])
- flow-reload: (workDir)
- flow-skill: archive|activate|list [skill_name]
- flow-validate: (plan_path)
- flow-validate-p: (prompt_file_path)
- flow-recommend: (task_description)
- flow-gc: [project_root]
- flow-history: sync [--dry-run] [--all], status, archive [registryKey]
- flow-catalog: [--dry-run]
- flow-gitconfig: [--global|--local]
- flow-detect: [프로젝트루트] [--generate]

> 스크립트 호출 시 반드시 위 alias를 사용 (MUST). python3 직접 경로 호출 금지 (MUST NOT).

## 워크플로우 요약
- entry-point: /wf 명령어 (단일 진입점)
- lifecycle: Open → In Progress → Review → Done
- commands:
  - /wf -o: 새 티켓 생성 및 프롬프트 작성
  - /wf -o N: 기존 티켓 편집
  - /wf -s N: 티켓 제출 및 워크플로우 실행
  - /wf -d N: 티켓 종료 (Done)
  - /wf -c N: 티켓 삭제
- 상세 참조: .claude/commands/wf.md, .claude/skills/workflow-orchestration/

## 자연어 매핑
| 자연어 | 워크플로우 명령 |
|--------|---------------|
| "이거 수정해줘" / "코드 고쳐줘" | /wf -e → /wf -s N |
| "분석해줘" / "조사해줘" | /wf -e (research) → /wf -s N |
| "티켓 만들어" | /wf -o |
| "리뷰해줘" | /wf -e (review) → /wf -s N |
| "종료해줘" | /wf -d N |
| "티켓 편집해줘" | /wf -e N |

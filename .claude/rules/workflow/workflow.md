# 워크플로우 시스템 상세 규칙

## 칸반 상태 흐름

### 5단계 FSM

```
To Do → Open → In Progress → Review → Done
```

- **To Do**: 미래에 할 백로그·아이디어 저장소 (박제 공간). 지금 당장 집중하지 않는 작업.
- **Open**: 지금 집중해야 하는 임박 작업. 워크플로우 실행(`/wf -s N`) 대상.
- **In Progress**: 워크플로우 실행 중인 상태.
- **Review**: 워크플로우 완료 후 사용자 리뷰 대기.
- **Done**: 완료.

### 전이 규칙

| 전이 | 방법 | 비고 |
|------|------|------|
| To Do → Open | `flow-kanban move T-NNN open` | 승격 |
| Open → To Do | `flow-kanban move T-NNN todo` | 강등 |
| Open → In Progress | `/wf -s N` | 워크플로우 실행 |
| In Progress → Review | 워크플로우 자동 전이 | |
| Review → Done | `/wf -d N` | |
| Review → Open | `/wf -e N` | 재작업 |

### 티켓 생성 규칙

티켓 생성 시 `--status todo` 또는 `--status open` 중 하나를 반드시 명시해야 한다 (MUST). 기본값(미지정)은 에러.

```bash
flow-kanban create "제목" --command implement --status todo   # 백로그 박제
flow-kanban create "제목" --command implement --status open   # 즉시 집중 대상
```

### 번호 영역 정책

| 영역 | 용도 | 채번 방식 |
|------|------|---------|
| T-001 ~ T-899 | 일반 작업 티켓 | 자동 채번 (max+1) 또는 `--number` 명시 |
| T-900 ~ T-999 | 디버그/일회성 검증 예약 | `--debug` 플래그로 자동 슬롯 배정, 또는 `--number 9NN` 명시 |

- 자동 채번이 T-900 에 도달하면 에러 (디버그 영역 침범 차단). 일반 영역 정리 후 재시도.
- 디버그 영역은 일회성 검증이 끝나면 `done` 또는 `delete` 로 정리해 다음 슬롯을 비운다.

### 디버그 티켓 (--debug)

```bash
flow-kanban create "rate-limit 회귀 검증" --status open --debug
# → T-900~T-999 첫 빈 슬롯 자동 배정
# → templates/debug-ticket.json 의 prompt 5필드 placeholder 시딩
# → title 에 "[DEBUG] " prefix 자동 적용
```

- 템플릿 위치: `.claude-organic/templates/debug-ticket.json` (수정 시 모든 디버그 티켓에 반영)
- `--debug` 와 `--number` 는 동시 사용 불가
- 시딩된 prompt 는 placeholder 이므로 실제 검증 시나리오에 맞게 `update-prompt` 로 갈아끼울 것 (MUST)

## DO
- 코드 수정은 기본적으로 /wf -e 로 티켓 생성/편집 후 /wf -s N 으로 실행
- 사용자가 직접 수정을 명시 요청한 경우에만 메인 세션에서 직접 수정
- 메인 세션은 기본적으로 티켓 관리·상태 확인·결과 리뷰 등 조율 역할 담당
- 자연어 요청도 워크플로우 명령으로 변환하여 처리 (아래 natural-language-mapping 참조)
- 티켓 생성 시 대화 맥락에서 관련 티켓이 있으면 `flow-kanban link`로 관계를 자동 연결한다 (SHOULD)
  - 기존 티켓 실행 중 발견된 버그/이슈 → `--derived-from` (파생)
  - 선행 작업이 필요한 경우 → `--depends-on` (의존)
  - 후속 작업을 차단하는 경우 → `--blocks` (차단)
- 티켓 생성 시 사용자 발화에 시작 상태가 명시되지 않았으면 번호 메뉴로 질의한다 (MUST, T-385 구현 이후)
  - 질의 형식: `1. To Do (백로그·미래에 할 일) / 2. Open (지금 집중 대상)`
  - AskUserQuestion 도구는 Board 터미널 미지원 → 텍스트 번호 메뉴로 제시
  - "박제/나중에/언젠가/백로그" → To Do 추천 (질의 유지)
  - "지금/바로/이번에/집중" → Open 추천 (질의 유지)
  - 사용자가 상태를 명시("Open으로 만들어줘" 등)한 경우에만 질의 생략
- `flow-kanban create` 호출 시 `--status` 플래그를 명시한다 (MUST) — 생략 시 에러

## DO NOT
- PreToolUse Hook 활성 시 직접 수정 시도하지 않는다 — 차단되므로 토큰 낭비
- 서브에이전트(Task)를 통해 조사·수정을 직접 시도하지 않는다 — 티켓 생성 후 워크플로우로 처리
- flow-kanban 호출 시 bin 레퍼런스에 나열되지 않은 서브커맨드를 사용하지 않는다
- /clear 후 시스템 프롬프트가 소실되었다고 가정하지 않는다 — SessionStart hook이 자동 재주입
- 사용자 발화에 명시되지 않은 행위를 추론하여 수행하지 않는다 — "추가해주세요"는 추가만 의미
- python3 .claude-organic/engine/... 형태로 스크립트를 직접 호출하지 않는다 — `.claude-organic/bin/flow-*` wrapper 사용
- derived-from 파생 티켓이 미완료(Done 아닌 상태)면 원본 티켓을 Done 처리하지 않는다 — Hook이 차단

> 실용적 이유: Hook 활성 시 DO NOT 항목은 차단되므로 시도 자체가 토큰 낭비. 처음부터 /wf 명령어로 진행할 것.

## bin wrapper 레퍼런스

`.claude-organic/bin/flow-*` 실행 파일을 직접 호출 (alias 아님). 대화형 zsh 셸은 PATH 등록되어 있을 수 있으나, 비대화형 Bash tool 환경에서는 절대/상대 경로로 호출한다 (MUST).

### flow-kanban 서브커맨드 (이 외 사용 금지)
create, move, done, delete, update-title, update, update-prompt, update-result, link, unlink, list, board, show

예시:
  .claude-organic/bin/flow-kanban create "제목" --command implement --status open
  .claude-organic/bin/flow-kanban update-prompt T-001 --goal "목표" --target "대상"
  .claude-organic/bin/flow-kanban update-result T-001 --registrykey "20260329-180635" --workdir "경로"
  .claude-organic/bin/flow-kanban link T-001 --derived-from T-000
  .claude-organic/bin/flow-kanban move T-001 progress
  .claude-organic/bin/flow-kanban done T-001

### XML 필드 개행 컨벤션
복수 항목 필드(goal, target, constraints, criteria, context)에 여러 항목을 입력할 때는 반드시 `\n` 개행을 삽입한다 (MUST).

- 단일 문장: `--constraints "조건1"` (개행 불필요)
- 복수 항목: `--constraints "조건1\n조건2\n조건3"` (MUST)
- 대상 필드: goal, target, constraints, criteria, context 전체

> `\n`이 누락되면 XML 래핑이 실패하여 태그 직후에 텍스트가 붙는 형식 오류가 발생한다.

### 기타 bin wrapper
- flow-claude: start, end
- flow-update: status, both, task-start, task-status, context, link-session, usage-pending, usage, usage-finalize, env
- flow-finish: (registryKey 완료|실패 --ticket-number T-NNN)
- flow-step: start, end
- flow-phase: (registryKey N)
- flow-skillmap: (registryKey)
- flow-init: (command title [--mode full] [--ticket T-NNN]) — 기존 위치 인자 [mode] [#N]도 하위호환 지원
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

> 스크립트 호출 시 반드시 위 bin wrapper를 사용 (MUST). python3 직접 경로 호출 금지 (MUST NOT).

## 워크플로우 요약
- entry-point: /wf 명령어 (단일 진입점)
- lifecycle: 위 "칸반 상태 흐름" 5단계 FSM 참조
- commands:
  - /wf -o: 새 티켓 생성 및 프롬프트 작성
  - /wf -o N: 기존 티켓 편집
  - /wf -s N: 티켓 제출 및 워크플로우 실행
  - /wf -d N: 티켓 종료 (Done)
  - /wf -c N: 티켓 삭제
- 상세 참조: .claude/commands/wf.md, .claude/skills/workflow-orchestration/

## 자연어 매핑
| 자연어 | 워크플로우 명령 | 비고 |
|--------|---------------|------|
| "이거 수정해줘" / "코드 고쳐줘" | /wf -e → /wf -s N | - |
| "분석해줘" / "조사해줘" | /wf -e (research) → /wf -s N | - |
| "티켓 만들어" | /wf -o | - |
| "리뷰해줘" | /wf -e (review) → /wf -s N | - |
| "종료해줘" | /wf -d N | - |
| "티켓 편집해줘" | /wf -e N | - |
| "박제해줘" / "나중에" / "언젠가" / "백로그" | /wf -o (--status todo) | To Do 상태로 생성 (미래 작업) |
| "지금 집중" / "바로 해야 함" / "이번에 하자" | /wf -o (--status open) | Open 상태로 생성 (임박 작업) |

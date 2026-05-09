# 워크플로우 시스템 상세 규칙

## 칸반 상태 흐름

### 5단계 FSM

> 이 5단계는 `kanban_status` 도메인이며 워크플로우 8상태(`workflow_phase`: NONE/INIT/PLAN/WORK/VALIDATE/REPORT/DONE/FAIL) 와 분리됨.

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

티켓은 **무조건 To Do 상태로 생성**한다 (MUST). 사용자가 즉시 집중하려면 칸반 DnD (To Do → Open) 한 번으로 충분하므로 생성 시점 상태 결정·메뉴 질의는 불필요한 낭비.

```bash
flow-kanban create "제목" --command implement --status todo   # 기본·유일 경로
```

> 과거 정책: `--status todo|open` 중 명시 강제 + 미명시 시 번호 메뉴 질의 (MUST) — 폐기 (2026-05-08 사용자 명시 정책 변경). 칸반 DnD 가 동등 작업을 1초 안에 처리하므로 생성 시점 결정 자체가 의미 없음.

### 번호 영역 정책

티켓 번호는 단일 영역 (T-001 ~ T-NNN). 자동 채번은 `max(전체) + 1`, 또는 `--number` 로 명시. 동일 번호 충돌 시 에러.

> 과거 T-900~T-999 디버그 예약 영역은 폐지됨 (2026-05-05). 일회성 검증 티켓도 일반 영역으로 채번.

## DO
- 코드 수정은 기본적으로 /wf -e 로 티켓 생성/편집 후 /wf -s N 으로 실행
- 사용자가 직접 수정을 명시 요청한 경우에만 메인 세션에서 직접 수정
- 메인 세션은 기본적으로 티켓 관리·상태 확인·결과 리뷰 등 조율 역할 담당
- 자연어 요청도 워크플로우 명령으로 변환하여 처리 (아래 natural-language-mapping 참조)
- 티켓 생성 시 대화 맥락에서 관련 티켓이 있으면 `flow-kanban link`로 관계를 자동 연결한다 (SHOULD)
  - 기존 티켓 실행 중 발견된 버그/이슈 → `--derived-from` (파생)
  - 선행 작업이 필요한 경우 → `--depends-on` (의존)
  - 후속 작업을 차단하는 경우 → `--blocks` (차단)
- 티켓 생성 시 상태 메뉴 질의 금지 (MUST NOT). 무조건 `--status todo` 로 생성한다. Open 승격은 사용자가 칸반 DnD 로 직접 수행
- 티켓 생성 전 사용자 요구사항이 모호하면 **인터뷰 식**으로 자연어 질문한다 (MUST). 메뉴 (1=A/2=B) 형태 질의 금지. 한 번에 1~2개씩만 묻고 답을 받아 다음 질문으로 진행
  - **호출 강제 (MUST)**: 아래 트리거 감지 시 description match 에 의존하지 말고 **즉시 Skill 도구로 `grill-me` 명시 호출**. 본 룰이 호출 강제의 단일 진실 공급원이며, 매 세션 자동 로드되어 호출 누락을 차단한다 (2026-05-08 사용자 명시 강제).
  - **트리거 키워드**: `티켓 만들어줘`, `/wf -o`, `박제해줘`, `grill me`, `캐물어줘`, `제대로 물어봐`, `인터뷰해줘`, 또는 **작업 범위·산출물 형태·제약·우선순위** 중 하나라도 모호한 신규 요청 발화.
  - 묻는 대상: 작업 범위 / 산출물 형태 / 제약 / 우선순위 등 연구·구현 방향에 결정적인 모호 포인트
  - 묻지 않는 대상: 티켓 상태 (자동 To Do), 기본 생성 옵션 (기본값 사용)
  - 상세 호출 절차 / 예시 / 반례 보충: `.claude/skills/grill-me/SKILL.md` (인터뷰), `.claude/skills/brainstorming/SKILL.md` (컨셉 정리). 룰 정의는 본 문서가 단일 진실 공급원이며 SKILL.md 는 reference + 호출 흐름·반례만 보유한다.
- 사용자가 설계·아키텍처·워크플로우·구조 제안을 공유하면 **사용자가 "어때요?" 명시 요청하기 전에 즉시 약점을 짚는다** (MUST). 시각화·옵션 질의("메모리 등록할까요? 티켓 생성할까요?") 만 하고 약점 분석을 미루는 것 금지 (MUST NOT). 점검 7축:
  1. **재시도/실패 처리 의미론**: 실패 사유 피드백 루프 / 재시도 범위 / MAX 도달 시 후속 처리
  2. **컴포넌트 간 책임 중복**: 같은 일을 두 곳에서 하지 않는가 / 책임이 비어있는 영역은 없는가
  3. **기존 인프라와의 매핑**: 신설 vs 흡수 vs 폐지 결정점 / 기존 가드·캐논과의 충돌
  4. **FSM 경계 명시**: 새 `workflow_phase` 가 기존 칸반 FSM(`kanban_status`) 의 어느 단계 안에 있는지 / 회귀 가능성
  5. **비용 vs 가치**: LLM 호출 추가 시 cost / skip 조건 정의 가능성
  6. **다른 모드와의 양립성**: 싱글/멀티/light/full 등 분기와 일관성
  7. **명명 모호성**: `phase_verify` (rule-based 단계 검증) vs `ticket_validate` (프롬프트 검수) 등 동음이의어 혼선 위험 — 동의어 페어마다 영어 식별자를 분리해 명명 사전(T-452 §4)에 박제
  - 7축으로 즉시 한 번 훑고 발견된 약점만 짚는다. 사용자가 명시 요청하지 않아도 짚는다 — grill-me 는 사용자가 더 잘 결정할 수 있도록 약점을 드러내는 게 본분.
  - 폐기 사례 (2026-05-09 사용자 명시 정정): 6-phase 워크플로우 설계 공유 받고 mermaid 시각화 + "메모리 등록? 티켓 생성?" 만 묻고 약점 분석 안 함 → 사용자가 "어때요?" 로 캐묻고 나서야 6개 약점 짚음.
- `flow-kanban create` 호출 시 `--status todo` 명시 (MUST) — 생략 시 에러는 동일하나 기본은 항상 todo

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
  .claude-organic/bin/flow-kanban create "제목" --command implement --status todo
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
- flow-step: start, end  # `work_step` 단위 진입/종료 배너 (WORK 내부 태스크 경계)
- flow-phase: (registryKey N)  # `workflow_phase` 전이 경계 배너 (INIT/PLAN/WORK/VALIDATE/REPORT)
- flow-skillmap: (registryKey)
- flow-init: (command title [--mode full] [--ticket T-NNN]) — 기존 위치 인자 [mode] [#N]도 하위호환 지원
- flow-reload: (workDir)
- flow-skill: archive|activate|list [skill_name]
- flow-validate: (plan_path)  # `ticket_validate` 후속 호출 — plan.md 산출물 검증 (`phase_verify`)
- flow-validate-p: (prompt_file_path)  # `ticket_validate` 본체 — 티켓 XML prompt 필드 완성도 검수
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
| "박제해줘" / "나중에" / "언젠가" / "백로그" | /wf -o | To Do 자동 (기본·유일 경로) |
| "지금 집중" / "바로 해야 함" / "이번에 하자" | /wf -o → DnD | To Do 생성 후 사용자가 칸반 DnD 로 Open 승격 |

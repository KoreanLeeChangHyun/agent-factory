# Common Reference

## Glossary (용어 사전)

워크플로우 시스템 전반에서 사용되는 핵심 용어의 정의입니다. 모든 에이전트, 스킬, 스크립트 문서는 아래 정의를 기준으로 용어를 사용합니다.

### 용어 분류: Workflow Skill vs Command Skill

시스템에서 "skill"은 두 가지 레벨로 구분됩니다. 혼동을 방지하기 위해 반드시 접두어를 사용합니다.

| 구분 | 접두어 | 수량 | 역할 | 경로 패턴 | 예시 |
|------|--------|------|------|----------|------|
| **Workflow Skill** | `workflow-` | 5개 | 워크플로우 단계(Phase) 관리 및 오케스트레이션 | `.claude/skills/workflow-*` | workflow-orchestration, workflow-init, workflow-plan, workflow-work, workflow-report |
| **Command Skill** | `command-` 또는 기능명 | 40+개 | 개별 명령어의 구체적 기능 수행 | `.claude/skills/<skill-name>` | command-code-quality-checker, command-research, tdd-guard-hook, deep-research |

- "skill"을 단독으로 사용할 때는 **두 가지 레벨을 포괄**하는 총칭을 의미합니다.
- 특정 레벨을 지칭할 때는 반드시 **"workflow skill"** 또는 **"command skill"** 접두어를 붙입니다.
- 문서 내에서 "5개 스킬"이라고 하면 workflow skill 5개를, "40+개 스킬"이라고 하면 command skill을 지칭합니다.

### 핵심 용어 정의

| 용어 (영문) | 한글 표기 | 정의 |
|-------------|----------|------|
| **Phase** | 단계 | 워크플로우의 실행 단위. INIT, PLAN, WORK, REPORT, COMPLETED, FAILED, CANCELLED, STALE 중 하나. |
| **command** | 명령어 | 사용자가 실행하는 작업 유형. implement, refactor, review, build, analyze, architect, framework, research, prompt 중 하나. |
| **agent** | 에이전트 | 특정 Phase를 전담하는 실행 주체. init, planner, worker, reporter 4개와 orchestrator(메인 에이전트)로 구성. |
| **sub-agent** | 서브에이전트 | orchestrator가 Task 도구로 호출하는 하위 에이전트. init, planner, worker, reporter가 해당. sub-agent 간 직접 호출은 금지. |
| **worker** | 워커 | WORK Phase를 전담하는 서브에이전트. 계획서의 태스크를 독립적으로 실행하며, 병렬 실행이 가능. |
| **orchestrator** | 오케스트레이터 | 워크플로우의 단계 순서(sequencing)와 에이전트 디스패치를 제어하는 메인 에이전트. Application Service 역할. |
| **workDir** | 작업 디렉토리 | 워크플로우의 모든 산출물이 저장되는 디렉토리. 형식: `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>` |
| **workId** | 작업 ID | 워크플로우를 식별하는 6자리 시간 기반 ID. 형식: `HHMMSS` (예: 143000). |
| **registryKey** | 레지스트리 키 | 워크플로우를 전역적으로 식별하는 키. 형식: `YYYYMMDD-HHMMSS`. registry.json에서 workDir로 해석됨. |
| **FSM** | 유한 상태 기계 | Finite State Machine. 워크플로우의 Phase 전이를 제어하는 상태 기계. 이중 가드(update-state.sh + transition-guard.sh)로 불법 전이를 차단. |
| **transition** | 전이 | FSM에서 한 Phase에서 다른 Phase로의 상태 변경. status.json의 transitions 배열에 이벤트 시퀀스로 기록됨. |
| **Aggregate** | 애그리거트 | DDD 전술적 설계 패턴. 워크플로우 시스템에서 status.json(워크플로우 상태)과 registry.json(전역 레지스트리)이 각각 Aggregate Root 역할. |
| **mode** | 모드 | 워크플로우 실행 모드. `full`(INIT->PLAN->WORK->REPORT), `no-plan`(INIT->WORK->REPORT), `prompt`(INIT->COMPLETED) 3가지. |
| **skill-map** | 스킬 맵 | Phase 0에서 생성되는 태스크별 command skill 매핑 결과. `<workDir>/work/skill-map.md`에 저장. |
| **Phase 0** | 준비 단계 | WORK Phase 시작 전 1개 worker가 수행하는 준비 작업. work 디렉토리 생성 및 skill-map 작성. full 모드에서만 실행. |
| **banner** | 배너 | 워크플로우 진행 상태를 터미널에 표시하는 시각적 알림. orchestrator가 Phase 시작/완료 시 호출. |

### 한영 표기 규약

| 규칙 | 설명 | 예시 |
|------|------|------|
| **시스템 내부 식별자** | 영문 원형 사용 | `phase`, `command`, `workDir`, `registryKey`, `status.json` |
| **에이전트 참조** | 영문 원형 사용 | init, planner, worker, reporter, orchestrator |
| **사용자 대면 문서** | 한글 병기 허용 | "Phase(단계)", "agent(에이전트)" |
| **계획서/보고서** | 한글 중심, 영문 병기 | "워커(worker)가 태스크를 실행합니다" |
| **코드/스크립트 주석** | 영문 사용 | `# Update phase transition` |
| **검색 일관성** | 최초 등장 시 한영 병기 후 이후 일관 사용 | 첫 번째: "에이전트(agent)", 이후: "에이전트" |

## Sub-agent Return Formats (REQUIRED)

> **WARNING: 반환값이 규격 줄 수를 초과하면 메인 에이전트 컨텍스트가 폭증하여 시스템 장애가 발생합니다.**
>
> 1. 모든 작업 결과는 `.workflow/` 파일에 기록 완료 후 반환
> 2. 반환값은 오직 상태 + 파일 경로만 포함
> 3. 코드, 목록, 테이블, 요약, 마크다운 헤더는 반환에 MUST NOT include
> 4. 규격 외 내용 1줄이라도 추가 시 시스템 장애 발생

### Common Rules

| Rule | Description |
|------|-------------|
| 작업 상세는 .workflow에 저장 | 서브에이전트는 모든 작업 상세를 파일로 기록 |
| 메인에 최소 반환 | 아래 에이전트별 형식만 반환 (추가 정보 MUST NOT) |
| 대량 내역 MUST NOT | 코드 변경 내용, 상세 로그, 파일 목록 테이블 등 반환 MUST NOT |

### init Return Format (7 lines)

```
request: <user_prompt.txt의 첫 50자>
workDir: .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>
workId: <workId>
date: <YYYYMMDD>
title: <제목>
workName: <작업이름>
근거: [1줄 요약]
```

**MUST NOT**: 요청 전문, 다음 단계 안내, 상세 설명, 마크다운 헤더, 판단 근거 상세, 변경 파일 목록, 예상 작업 시간 등 추가 정보

### planner Return Format (3 lines)

```
상태: 작성완료
계획서: <계획서 파일 경로>
태스크 수: N개
```

**MUST NOT**: 계획 요약, 태스크 목록, 다음 단계 안내 등

### worker Return Format (3 lines)

```
상태: 성공 | 부분성공 | 실패
작업 내역: <작업 내역 파일 경로>
변경 파일: N개
```

**MUST NOT**: 변경 파일 목록 테이블, 코드 스니펫, 작업 요약, 다음 단계 안내 등

### reporter Return Format (3 lines)

```
상태: 완료 | 실패
보고서: <보고서 파일 경로>
CLAUDE.md: 갱신완료 | 스킵 | 실패
```

**MUST NOT**: 요약, 태스크 수, 변경 파일 수, 다음 단계 등 추가 정보 일체

## Call Method Rules

| Target Type | Method | Example |
|-------------|--------|---------|
| Agent (4개) | Task | `Task(subagent_type="init", prompt="...")` |
| Skill (5개) | Skill | `Skill(skill="workflow-report")` |

**Agents:** init, planner, worker, reporter
**Skills:** workflow-orchestration, workflow-init, workflow-plan, workflow-work, workflow-report

> 에이전트별 색상 정보는 각 에이전트 정의 파일(`.claude/agents/*.md`)의 frontmatter 참조.

## State Update Methods

단계 전환 시 `both` 모드로 로컬 .context.json(agent)과 status.json(phase)을 동시 업데이트합니다. 각 단계별 `both` 호출은 서브에이전트 호출 섹션에 기재되어 있습니다.

```bash
# 로컬 .context.json의 agent 필드만 업데이트
wf-state context <registryKey> <agent>
# 로컬 status.json의 phase 변경
wf-state status <registryKey> <fromPhase> <toPhase>
# 로컬 context + status 동시 업데이트 (권장)
wf-state both <registryKey> <agent> <fromPhase> <toPhase>
# 전역 레지스트리에 워크플로우 등록 (INIT 완료 시)
wf-state register <registryKey>
# 전역 레지스트리에서 워크플로우 해제 (REPORT 완료 시)
wf-state unregister <registryKey>
# status.json의 linked_sessions 배열에 세션 ID 추가 (worker/reporter가 자체 호출)
wf-state link-session <registryKey> <sessionId>
```

> **Note**: `context` 모드와 `both` 모드는 로컬 `<workDir>/.context.json`의 `agent` 필드만 업데이트. 전역 `.workflow/registry.json`은 레지스트리 전용이며, `register`/`unregister` 모드로만 접근.
> **registryKey format**: `YYYYMMDD-HHMMSS` 형식의 워크플로우 식별자. 스크립트 내부에서 registry.json을 조회하여 전체 workDir 경로를 자동 해석. 전체 workDir 경로(`.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>`)도 하위 호환.

agent 값: INIT=`init`, PLAN=`planner`, WORK=`worker`, REPORT=`reporter`. 실패 시 경고만 출력, 워크플로우 정상 진행.

**Mode-aware State Update Examples:**

| Mode | WORK transition | Command |
|------|----------------|---------|
| full | PLAN -> WORK | `wf-state both <registryKey> worker PLAN WORK` |
| no-plan | INIT -> WORK | `wf-state both <registryKey> worker INIT WORK` |
| prompt | INIT -> COMPLETED | `wf-state status <registryKey> INIT COMPLETED` |

## State Management (status.json)

각 워크플로우 작업은 `status.json`으로 현재 단계와 전이 이력을 추적합니다.

> status.json 스키마(9개 필드)와 저장 위치는 workflow-init skill 참조. 저장 경로: `<workDir>/status.json` (workDir = `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>`)

### status.json `linked_sessions` Field

`linked_sessions`는 워크플로우에 참여한 세션 ID의 배열입니다. init이 초기 세션 ID로 배열을 생성하고, 이후 worker/reporter가 자신의 세션 ID를 `link-session` 모드로 추가합니다. 세션 재시작 시에도 새 세션 ID가 자동 병합됩니다.

- 용도: 워크플로우에 참여한 세션 ID 추적 (디버깅/감사 목적)
- 갱신: `wf-state link-session <registryKey> <sessionId>` (중복 자동 방지, 비차단)
- 오케스트레이터는 link-session을 직접 호출하지 않음 (worker/reporter가 자체 등록)

### FSM Transition Rules

**Mode-aware transitions** (status.json `mode` field determines allowed transitions):

| Mode | Normal Flow | Branches |
|------|-------------|----------|
| full (default) | `INIT -> PLAN -> WORK -> REPORT -> COMPLETED` | PLAN->CANCELLED, WORK/REPORT->FAILED, TTL->STALE |
| no-plan | `INIT -> WORK -> REPORT -> COMPLETED` | WORK/REPORT->FAILED, TTL->STALE |
| prompt | `INIT -> COMPLETED` | TTL->STALE |

불법 전이 시 시스템 가드가 차단. update-workflow-state.sh는 전이 미수행(no-op), PreToolUse Hook은 도구 호출 deny. 비상 시 WORKFLOW_SKIP_GUARD=1로 우회 가능.

> 업데이트 방법은 "State Update Methods" 섹션 참조. 비차단 원칙: 실패 시 경고만 출력, 워크플로우 정상 진행.
> `mode` 필드가 없는 기존 status.json은 기본값 `full`로 처리 (하위 호환).

## Error Handling

| Situation | Action |
|-----------|--------|
| INIT error | 최대 3회 재시도 (경고 로그 출력) |
| Step error (PLAN/WORK/REPORT) | 최대 3회 재시도 후 에러 보고 |
| Independent task failure | 다른 독립 태스크는 계속 진행 |
| Dependent task blocker failure | 해당 종속 체인 중단, 다른 체인 계속 |
| Total failure rate > 50% | 워크플로우 중단 및 AskUserQuestion으로 사용자 확인 |

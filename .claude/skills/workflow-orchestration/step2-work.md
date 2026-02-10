# Step 2: WORK (worker Agent)

> **State Update** before WORK start:
> ```bash
> # full mode (default): transition from PLAN
> wf-state both <registryKey> worker PLAN WORK
> # no-plan mode: transition from INIT (PLAN was skipped)
> wf-state both <registryKey> worker INIT WORK
> ```

> **WORK Phase Rules (REQUIRED)**
>
> | Category | Rule |
> |----------|------|
> | **Allowed calls** | worker, reporter 에이전트만 호출 가능 |
> | **Re-call MUST NOT** | planner, init 에이전트 재호출 MUST NOT |
> | **Reverse transition MUST NOT** | WORK->PLAN, WORK->INIT 등 역방향 phase 변경 MUST NOT |
> | **Autonomous judgment MUST NOT** | 오케스트레이터가 독자적으로 맥락 보강, 계획 수정, 태스크 추가/삭제/변경을 판단하지 않음 |
> | **Plan tasks only** | 계획서에 명시된 태스크만 순서대로 실행. 계획서에 없는 작업은 수행하지 않음 |
>
> 위반 시 워크플로우 무결성이 훼손됩니다. WORK phase에서 문제가 발생하면 worker 반환값의 "실패" 상태로 처리하고, 오케스트레이터가 임의로 PLAN으로 회귀하지 않습니다.

**Detailed Guide:** workflow-work skill 참조

> **Worker Internal Procedure (4 steps):** 각 worker는 호출 후 내부적으로 `계획서 확인 -> 스킬 로드 -> 작업 진행 -> 실행 내역 작성`의 4단계를 수행합니다. 상세는 workflow-work skill 및 worker.md 참조.

## No-Plan Mode Worker Call Pattern

> **no-plan 모드에서는 Phase 0과 Phase 1~N 대신 단일 Worker를 호출합니다.**

no-plan 모드 판별: status.json의 `mode` 필드가 `no-plan`이면 아래 패턴으로 실행합니다.

**State Update:**
```bash
wf-state both <registryKey> worker INIT WORK
```

**Single Worker Call (no planPath, no Phase 0):**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, workDir: <workDir>, mode: no-plan")
```

**no-plan 모드 특성:**

| 항목 | full 모드 | no-plan 모드 |
|------|----------|-------------|
| State transition | PLAN -> WORK | INIT -> WORK |
| Phase 0 (skill-map) | 필수 | 스킵 |
| planPath | 필수 | 없음 |
| Worker 수 | 다수 (W01~WNN) | 단일 (W01 고정) |
| 요구사항 소스 | 계획서 (plan.md) | user_prompt.txt |

no-plan Worker는 `<workDir>/user_prompt.txt`를 직접 읽어 요구사항을 파악하고, 명령어별 기본 스킬 매핑으로 스킬을 자동 결정하여 작업을 수행합니다.

---

## Full Mode: Phase 0 - Preparation (REQUIRED, Sequential 1 worker)

Phase 1~N 실행 전에 MUST execute Phase 0 먼저. Phase 0은 1개 worker가 순차로 실행합니다.

```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: phase0, planPath: <planPath>, workDir: <workDir>, mode: phase0")
```

Phase 0 기능: (1) `<workDir>/work/` 디렉터리 생성, (2) 계획서 태스크와 스킬을 매핑하여 `<workDir>/work/skill-map.md` 생성.

Phase 0 완료 후 skill-map.md를 참고하여 후속 worker 호출 시 skills 파라미터를 전달합니다.

## Phase 1~N: Task Execution

계획서의 Phase 순서대로 실행합니다:

**Independent tasks (parallel):**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, planPath: <planPath>, workDir: <workDir>, skills: <스킬명>")
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W02, planPath: <planPath>, workDir: <workDir>")
```

**Dependent tasks (sequential):**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W04, planPath: <planPath>, workDir: <workDir>")
```

> **skills parameter**: Phase 0에서 생성된 skill-map.md의 추천 스킬 또는 계획서에 명시된 스킬을 전달. 미명시 태스크는 worker가 자동 결정.

## Explore Sub-agent

계획서에서 `서브에이전트: Explore`로 지정된 태스크는 Explore(Haiku) 서브에이전트를 사용합니다.

**Explore Call Pattern:**
```
Task(subagent_type="explore", prompt="
다음 파일들을 분석하고 각 파일의 주요 기능과 구조를 요약하세요:
- <파일 경로 목록>

출력 형식: 파일별 1-3줄 요약
")
```

**Explore Usage Rules:**
- **Read-only tasks only**: 파일 수정이 필요 없는 대량 분석 태스크에만 사용
- **Parallel calls**: 여러 Explore 에이전트를 동시에 호출하여 파일 분배 가능
- **Worker combination**: Explore(읽기) 결과를 수집한 후 Worker(쓰기)에 전달하는 파이프라인 구성 가능
- **Plan compliance**: 계획서에 `서브에이전트: Explore`로 명시된 태스크만 Explore로 호출. 명시되지 않은 태스크는 Worker 사용

## Worker Return Value Processing (REQUIRED)

> **WARNING: Worker 반환값이 3줄을 초과하면 메인 컨텍스트가 폭증하여 시스템 장애가 발생합니다.**

Task(worker) 호출 후 반환값 처리 규칙:
1. 반환값에서 **첫 3줄만** 추출하여 컨텍스트에 보관 (4줄째부터는 MUST discard)
2. 나머지는 무시 (상세 내용은 .workflow/ 파일에 이미 저장됨)
3. 3줄 형식이 아닌 반환값이라도 첫 3줄만 사용, 초과분은 MUST NOT retain

**Normal Return Value (3 lines):**
```
상태: 성공 | 부분성공 | 실패
작업 내역: <파일 경로>
변경 파일: N개
```

- **Output:** 작업 내역 경로

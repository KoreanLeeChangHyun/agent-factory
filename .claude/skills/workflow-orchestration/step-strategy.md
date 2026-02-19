# STRATEGY (strategy Agent)

> **Agent-Skill Binding**
> - Agent: `strategy` (model: inherit, maxTurns: 50)
> - Skill: `workflow-strategy`
> - Task prompt: `command: strategy, workId: <workId>, request: <request>, workDir: <workDir>`

> **strategy 모드에서만 실행됩니다.** INIT 완료 후 Mode Branching에서 `mode == strategy`일 때 PLAN, WORK, REPORT를 모두 건너뛰고 STRATEGY Phase로 진행합니다.

## State Update (Before STRATEGY Start)

> **State Update** before STRATEGY start:
> ```bash
> python3 .claude/scripts/workflow/update_state.py both <registryKey> strategy INIT STRATEGY
> ```

## STRATEGY Banner

```bash
step-start <registryKey> STRATEGY
```

## Agent Call

```
Task(subagent_type="strategy", prompt="
command: strategy
workId: <workId>
request: <request>
workDir: <workDir>
")
```

- strategy 에이전트가 `workDir`을 기반으로 코드베이스/워크플로우 이력을 분석하고 로드맵을 생성
- `user_prompt.txt`는 strategy 에이전트가 직접 읽음 (`request`는 50자 요약본)
- **Output:** `roadmap.md` + `.kanbanboard`

## Return Values

strategy 에이전트는 3줄 규격으로 반환합니다:

```
상태: 성공 | 실패
로드맵: .workflow/<YYYYMMDD-HHMMSS>/<workName>/strategy/roadmap.md
워크플로우: N개
```

오케스트레이터는 **첫 3줄만 추출**하고 4줄째부터는 폐기합니다. 상세 정보는 `roadmap.md`와 `.kanbanboard`에 저장되어 있습니다.

## STRATEGY Completion Banner

strategy 에이전트가 정상 반환한 후, 오케스트레이터가 완료 배너를 호출합니다:

```bash
step-end <registryKey> STRATEGY
```

## Post-STRATEGY Flow (DONE)

STRATEGY 완료 후 DONE Phase로 진행합니다:

1. `step-start <registryKey> DONE` (DONE start banner)
2. Done agent call: `Task(subagent_type="done", prompt="registryKey: <registryKey>, workDir: <workDir>, command: strategy, title: <title>, reportPath: <reportPath>, status: <status>, workflow_id: <workflow_id>")`
3. `step-end <registryKey> DONE done` (DONE completion)
4. Terminate

## Error Handling

strategy 에이전트 호출 실패 시 최대 3회 재시도합니다. 3회 모두 실패하면 FAILED 상태로 전이합니다.

```
retry_count = 0
MAX_RETRIES = 3

while retry_count < MAX_RETRIES:
    result = Task(subagent_type="strategy", prompt="...")
    if result.status != "실패":
        break  # 성공 -> DONE 단계 진행
    retry_count += 1
    log("[WARN] STRATEGY 실패 (시도 {retry_count}/{MAX_RETRIES})")

if retry_count >= MAX_RETRIES:
    python3 .claude/scripts/workflow/update_state.py status <registryKey> STRATEGY FAILED
    python3 .claude/scripts/workflow/update_state.py unregister <registryKey>
    # 워크플로우 종료 (DONE 단계 스킵)
```

| 상황 | 처리 |
|------|------|
| strategy 호출 실패 | 최대 3회 재시도 |
| 3회 모두 실패 | STRATEGY -> FAILED 상태 전이 후 워크플로우 종료 |
| 재시도 중 성공 | 경고 로그만 남기고 정상 진행 (DONE 단계로 이동) |

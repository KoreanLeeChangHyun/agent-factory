# DONE (flow-finish + flow-claude end)

> **Done 에이전트는 삭제되었습니다.** 워크플로우 마무리는 오케스트레이터가 `flow-finish`(마무리 스크립트)와 `flow-claude end`(종료 배너)를 직접 호출하여 수행합니다.

reporter 완료 후, 오케스트레이터가 마무리 처리를 직접 수행합니다.

## 마무리 흐름 (Orchestrator-driven)

```bash
# 1. 상태 전이 (REPORT → DONE)
flow-update status <registryKey> DONE

# 2. 마무리 스크립트 실행 (history.md, usage, archive, kanban)
# <status>: "완료" 또는 "실패" (다른 값 사용 금지. "성공" 등은 무효)
flow-finish <registryKey> 완료 [--workflow-id <id>]

# 3. 종료 배너 출력 (Slack 알림 자동 수행)
flow-claude end <registryKey>
```

### flow-finish 5단계

`flow-finish`(`finalization.py`)가 수행하는 5단계:

1. **status.json 완료 처리** — `update_state.py status` (critical, 실패 시 exit 1)
2. **history.md 갱신** — `history_sync.py sync` (비차단)
3. **사용량 확정** — `update_state.py usage-finalize` (비차단, 성공 시만)
4. **아카이빙** — `history_sync.py archive` (비차단)
5. **.kanbanboard 갱신** — `update-kanban.sh` (workflow_id 있을 때만, 비차단)

### flow-claude end

`flow-claude end`(`flow_claude_banner.sh`)가 수행하는 작업:

1. **완료 배너 출력** — `[OK] <workId> · <title> (command) 워크플로우 완료`
2. **Slack 완료 알림** — 비동기, 비차단

### fromStep

REPORT 완료 후 DONE으로 전이: `REPORT → DONE`

## Error Handling

| 상황 | 처리 |
|------|------|
| flow-finish 실패 (status 전이) | 워크플로우 FAILED 처리, flow-claude end 스킵 |
| flow-finish 실패 (비차단 단계) | 경고만 출력, flow-claude end 정상 진행 |
| flow-claude end 실패 | 경고만 출력, 워크플로우 정상 종료 간주 |

> **근거:** 마무리 처리(history 기록, 사용량 확정, 아카이빙)는 보조적 정리 작업입니다. 이 단계에서 비차단 실패가 발생해도 WORK/REPORT 단계의 실제 작업 결과에는 영향을 주지 않습니다.

## Post-DONE Silence (REQUIRED)

**오케스트레이터가 `flow-claude end` Bash 호출 결과를 수신한 즉시, 추가 도구 호출 없이, 추가 텍스트 생성 없이, 현재 turn을 종료해야 합니다.**

> **행동 지시 (MANDATORY):** `flow-claude end <registryKey>` Bash 호출 결과를 수신한 즉시, 추가 도구 호출 없이, 추가 텍스트 생성 없이, 현재 turn을 종료하십시오. 이것이 워크플로우의 마지막 행위입니다.

다음 문구는 flow-claude end 이후 절대 출력 금지입니다:

- "Workflow already completed."
- "All tasks finished"
- 워크플로우 상태를 설명하는 모든 문장
- 완료를 재확인하는 모든 문장

**flow-claude end가 워크플로우의 마지막 출력이어야 합니다. flow-claude end Bash 호출 후 turn을 종료하라.**

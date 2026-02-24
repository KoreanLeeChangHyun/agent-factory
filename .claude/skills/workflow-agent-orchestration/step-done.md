# DONE (done Agent)

> **Agent-Skill Binding**
> - Agent: `done` (model: haiku, maxTurns: 15)
> - Skill: `workflow-agent-done`
> - Task prompt: `registryKey: <registryKey>, workDir: <workDir>, command: <command>, title: <title>, reportPath: <reportPath>, status: <status>, workflow_id: <workflow_id>`

**Detailed Guide:** workflow-agent-done skill 참조

reporter 완료 후, 오케스트레이터가 **DONE 시작 배너**를 호출한 뒤 **done 에이전트**를 디스패치합니다.

```bash
# 오케스트레이터: DONE 시작 배너
step-start <registryKey> DONE
```

```
Task(subagent_type="done", prompt="
registryKey: <registryKey>
workDir: <workDir>
command: <command>
title: <title>
reportPath: <reporter 반환 보고서 경로>
status: <reporter 반환 상태>
workflow_id: <workflow_id>
")
```

done 에이전트가 수행하는 작업:

1. **history.md 갱신** - summary.txt를 읽어 `.prompt/history.md`에 이력 행 추가
2. **status.json 완료 처리** - 성공: `python3 .claude/scripts/state/update_state.py status <registryKey> REPORT COMPLETED`, 실패: `python3 .claude/scripts/state/update_state.py status <registryKey> REPORT FAILED`
3. **사용량 확정** - 성공 시: `python3 .claude/scripts/state/update_state.py usage-finalize <registryKey>` (실패 시 경고만, 비차단)
4. **레지스트리 해제** - `python3 .claude/scripts/state/update_state.py unregister <registryKey>`
5. **워크플로우 아카이빙** - 최신 10개 워크플로우만 `.workflow/`에 유지, 나머지를 `.workflow/.history/`로 이동, history.md 링크 갱신
6. **.kanbanboard 갱신** - `workflow_id` 전달 시 `.kanbanboard` 파일의 워크플로우 완료 상태 반영 (`update-kanban.sh` 호출, 비차단)

## Error Handling

done 에이전트 실패 시 **비차단 원칙**을 적용합니다. done은 워크플로우의 마무리 단계이므로, 실패해도 워크플로우 자체는 정상 종료로 간주합니다.

| 상황 | 처리 |
|------|------|
| done 에이전트 호출 실패 | 경고만 출력, 워크플로우 정상 종료 |
| history.md 갱신 실패 | 경고만 출력, 후속 작업 계속 |
| usage-finalize 실패 | 경고만 출력, 후속 작업 계속 |
| unregister 실패 | 경고만 출력, 워크플로우 정상 종료 |
| 아카이빙 실패 | 경고만 출력, 워크플로우 정상 종료 |

> **근거:** done 에이전트의 작업(이력 기록, 레지스트리 해제, 아카이빙)은 보조적 정리 작업입니다. 이 단계에서 실패가 발생해도 WORK/REPORT 단계의 실제 작업 결과에는 영향을 주지 않으므로, 워크플로우를 FAILED로 전이하지 않고 경고만 출력합니다. 오케스트레이터는 done 실패와 무관하게 DONE 완료 배너를 호출하고 종료합니다.

### DONE 배너 (오케스트레이터 호출)

done 에이전트 반환 후, **오케스트레이터**가 DONE 완료 배너를 호출합니다:
```bash
step-end <registryKey> DONE done
```

> **주의**: 서브에이전트(Task) 내부의 Bash 출력은 사용자 터미널에 표시되지 않으므로, DONE 완료 배너는 반드시 오케스트레이터가 done 에이전트 반환 후 직접 호출해야 합니다.

> **책임 분리 원칙**: reporter는 보고서 생성 + summary.txt에 집중하고, 워크플로우 상태 관리(history.md, status.json, 레지스트리)는 done 에이전트가 담당합니다. DONE 배너는 오케스트레이터가 호출합니다.

> **아카이빙**: done 에이전트는 레지스트리 해제 후 워크플로우 아카이빙을 수행합니다. 아카이빙 실패는 비차단 원칙에 따라 경고만 출력합니다.

## Post-DONE Silence (REQUIRED)

**오케스트레이터가 DONE 완료 배너를 호출한 후, 어떤 텍스트도 출력하지 않고 즉시 종료해야 합니다.**

> **행동 지시 (MANDATORY):** `step-end <registryKey> DONE done` Bash 호출 결과를 수신한 즉시, 추가 도구 호출 없이, 추가 텍스트 생성 없이, 현재 turn을 종료하십시오. 이것이 워크플로우의 마지막 행위입니다. Bash, Task, Read, Write, Edit 등 어떠한 도구도 호출하지 마십시오. 어떠한 문자도 출력하지 마십시오. turn을 즉시 끝내십시오.

다음 문구는 DONE 배너 이후 절대 출력 금지입니다:

- "Workflow already completed."
- "All tasks finished"
- "DONE banner was issued"
- 워크플로우 상태를 설명하는 모든 문장
- 완료를 재확인하는 모든 문장

**DONE 배너가 워크플로우의 마지막 출력이어야 합니다. DONE 완료 배너 Bash 호출 후 turn을 종료하라.**

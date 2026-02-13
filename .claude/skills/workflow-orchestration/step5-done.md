# Step 5: END (done Agent)

> **Agent-Skill Binding**
> - Agent: `done` (model: haiku, maxTurns: 15)
> - Skill: `workflow-end`
> - Task prompt: `registryKey: <registryKey>, workDir: <workDir>, command: <command>, title: <title>, reportPath: <reportPath>, status: <status>`

**Detailed Guide:** workflow-end skill 참조

reporter 완료 후, 오케스트레이터가 **DONE 시작 배너**를 호출한 뒤 **done 에이전트**를 디스패치합니다.

```bash
# 오케스트레이터: DONE 시작 배너
Workflow <registryKey> DONE
```

```
Task(subagent_type="done", prompt="
registryKey: <registryKey>
workDir: <workDir>
command: <command>
title: <title>
reportPath: <reporter 반환 보고서 경로>
status: <reporter 반환 상태>
")
```

done 에이전트가 수행하는 작업:

1. **history.md 갱신** - summary.txt를 읽어 `.prompt/history.md`에 이력 행 추가
2. **status.json 완료 처리** - 성공: `wf-state status <registryKey> REPORT COMPLETED`, 실패: `wf-state status <registryKey> REPORT FAILED`
3. **사용량 확정** - 성공 시: `wf-state usage-finalize <registryKey>` (실패 시 경고만, 비차단)
4. **레지스트리 해제** - `wf-state unregister <registryKey>`

### DONE 배너 (오케스트레이터 호출)

done 에이전트 반환 후, **오케스트레이터**가 DONE 완료 배너를 호출합니다:
```bash
Workflow <registryKey> DONE done
```

> **주의**: 서브에이전트(Task) 내부의 Bash 출력은 사용자 터미널에 표시되지 않으므로, DONE 완료 배너는 반드시 오케스트레이터가 done 에이전트 반환 후 직접 호출해야 합니다.

> **책임 분리 원칙**: reporter는 보고서 생성 + summary.txt에 집중하고, 워크플로우 상태 관리(history.md, status.json, 레지스트리)는 done 에이전트가 담당합니다. DONE 배너는 오케스트레이터가 호출합니다.

## Post-DONE Silence (REQUIRED)

**오케스트레이터가 DONE 완료 배너를 호출한 후, 어떤 텍스트도 출력하지 않고 즉시 종료해야 합니다.**

다음 문구는 DONE 배너 이후 절대 출력 금지입니다:

- "Workflow already completed."
- "All tasks finished"
- "DONE banner was issued"
- 워크플로우 상태를 설명하는 모든 문장
- 완료를 재확인하는 모든 문장

**DONE 배너가 워크플로우의 마지막 출력이어야 합니다.**

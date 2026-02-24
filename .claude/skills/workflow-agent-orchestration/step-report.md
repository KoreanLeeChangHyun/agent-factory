# REPORT (reporter Agent)

## Noreport Mode Skip Condition

> **noreport/noplan+noreport 모드에서는 REPORT 단계가 스킵된다.** 오케스트레이터는 reporter를 호출하지 않고 WORK 완료 후 바로 DONE으로 직행한다.

| Mode | REPORT 실행 여부 | WORK 완료 후 경로 |
|------|-----------------|------------------|
| full | O (실행) | WORK -> REPORT -> DONE |
| noplan | O (실행) | WORK -> REPORT -> DONE |
| noreport | X (스킵) | WORK -> DONE (REPORT 스킵) |
| noplan+noreport | X (스킵) | WORK -> DONE (REPORT 스킵) |

**스킵 시 오케스트레이터 동작:**
1. WORK step-end 출력
2. `step-update both <registryKey> done WORK DONE` — REPORT를 거치지 않고 WORK에서 DONE으로 직행
3. `step-change <registryKey> WORK DONE` — 상태 전이 시각화 (REPORT 스킵)
4. DONE step-start → done agent call → DONE step-end
5. reporter를 호출하지 않으며 `reportPath`는 done 에이전트에 전달하지 않음

---

> **Agent-Skill Binding**
> - Agent: `reporter` (model: sonnet, maxTurns: 30, permissionMode: acceptEdits)
> - Skill: `workflow-agent-report`
> - Task prompt: `command: <command>, workId: <workId>, workDir: <workDir>, workPath: <workDir>/work/`

> **State Update** before REPORT start:
> ```bash
> step-update both <registryKey> reporter WORK REPORT
> ```

**Detailed Guide:** workflow-agent-report skill 참조

```
Task(subagent_type="reporter", prompt="
command: <command>
workId: <workId>
workDir: <workDir>
workPath: <workDir>/work/
")
```

- reporter가 `workDir`을 기반으로 보고서 경로를 `{workDir}/report.md`로 확정적 구성
- reporter가 보고서 작성 + summary.txt 생성
- **Output:** 보고서 경로

## Post-REPORT Flow (REPORT -> DONE 전이)

reporter 반환 후, 오케스트레이터가 REPORT 완료 배너를 호출하고 DONE 단계로 전이합니다:

```bash
# 1. REPORT 완료 배너
step-end <registryKey> REPORT reporter

# 2. 상태 업데이트 (REPORT -> DONE)
step-update both <registryKey> done REPORT DONE

# 3. 상태 전이 시각화
step-change <registryKey> REPORT DONE

# 4. DONE 시작 → step-done.md 참조
step-start <registryKey> DONE
```

> **Detailed Guide:** DONE 단계의 상세 흐름은 [step-done.md](step-done.md) 참조

## Error Handling

reporter 에이전트 호출 실패 시 최대 3회 재시도합니다. 3회 모두 실패하면 FAILED 상태로 전이합니다.

```
retry_count = 0
MAX_RETRIES = 3

while retry_count < MAX_RETRIES:
    result = Task(subagent_type="reporter", prompt="...")
    if result.status != "실패":
        break  # 성공 → DONE 단계 진행
    retry_count += 1
    log("[WARN] REPORT 실패 (시도 {retry_count}/{MAX_RETRIES})")

if retry_count >= MAX_RETRIES:
    step-update status <registryKey> REPORT FAILED
    step-update unregister <registryKey>
    # 워크플로우 종료 (DONE 단계 스킵)
```

| 상황 | 처리 |
|------|------|
| reporter 호출 실패 | 최대 3회 재시도 |
| 3회 모두 실패 | REPORT -> FAILED 상태 전이 후 워크플로우 종료 |
| 재시도 중 성공 | 경고 로그만 남기고 정상 진행 (DONE 단계로 이동) |

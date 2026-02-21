# REPORT (reporter Agent)

> **Agent-Skill Binding**
> - Agent: `reporter` (model: sonnet, maxTurns: 30, permissionMode: acceptEdits)
> - Skill: `workflow-report`
> - Task prompt: `command: <command>, workId: <workId>, workDir: <workDir>, workPath: <workDir>/work/`

> **State Update** before REPORT start:
> ```bash
> python3 .claude/scripts/state/update_state.py both <registryKey> reporter WORK REPORT
> ```

**Detailed Guide:** workflow-report skill 참조

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
    python3 .claude/scripts/state/update_state.py status <registryKey> REPORT FAILED
    python3 .claude/scripts/state/update_state.py unregister <registryKey>
    # 워크플로우 종료 (DONE 단계 스킵)
```

| 상황 | 처리 |
|------|------|
| reporter 호출 실패 | 최대 3회 재시도 |
| 3회 모두 실패 | REPORT -> FAILED 상태 전이 후 워크플로우 종료 |
| 재시도 중 성공 | 경고 로그만 남기고 정상 진행 (DONE 단계로 이동) |

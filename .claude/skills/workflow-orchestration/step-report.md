# REPORT (reporter Agent)

WORK 완료 후 REPORT Step으로 진행하여 reporter를 호출한다. Step order: WORK -> REPORT -> DONE.

---

> **Agent-Skill Binding**
> - Agent: `reporter` (model: sonnet, maxTurns: 30, permissionMode: acceptEdits)
> - Skill: `workflow-agent-reporter`
> - Task prompt: `command: <command>, workId: <workId>, workDir: <workDir>, workPath: <workDir>/work/`

> **State Update** before REPORT Step start:
> ```bash
> flow-update both <registryKey> reporter REPORT
> ```

**Detailed Guide:** workflow-agent-reporter skill 참조

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
- **Output:** 상태 (완료/실패)

## Post-REPORT Flow (REPORT -> DONE 전이)

reporter 반환 후, 오케스트레이터가 REPORT Step 완료 배너를 호출하고 DONE Step으로 전이합니다:

```bash
# 1. REPORT 완료 배너 (● + report.md 링크 + [OK])
flow-step end <registryKey> reportDone

# 2. 상태 업데이트 (REPORT -> DONE)
flow-update status <registryKey> DONE

# 3. 마무리 → step-done.md 참조
flow-finish <registryKey> <status>

# 4. 종료 (╚═══╝ closing border)
flow-claude end <registryKey>
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
    flow-update status <registryKey> FAILED
    # 워크플로우 종료 (DONE 단계 스킵)
```

| 상황 | 처리 |
|------|------|
| reporter 호출 실패 | 최대 3회 재시도 |
| 3회 모두 실패 | REPORT -> FAILED 상태 전이 후 워크플로우 종료 |
| 재시도 중 성공 | 경고 로그만 남기고 정상 진행 (DONE 단계로 이동) |

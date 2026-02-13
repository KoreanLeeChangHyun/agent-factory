# Step 4: REPORT (reporter Agent)

> **Agent-Skill Binding**
> - Agent: `reporter` (model: sonnet, maxTurns: 30, permissionMode: acceptEdits)
> - Skill: `workflow-report`
> - Task prompt: `command: <command>, workId: <workId>, workDir: <workDir>, workPath: <workDir>/work/`

> **State Update** before REPORT start:
> ```bash
> wf-state both <registryKey> reporter WORK REPORT
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

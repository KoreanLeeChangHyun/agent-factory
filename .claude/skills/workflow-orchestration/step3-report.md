# Step 3: REPORT (reporter Agent)

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
- reporter가 보고서 작성 + CLAUDE.md 갱신
- **Output:** 보고서 경로, CLAUDE.md 갱신 완료

## REPORT Completion and DONE Banner

> **REPORT 완료 후 DONE banner**: REPORT 완료 배너 호출 후, 오케스트레이터는 자유 텍스트 완료 메시지를 출력하지 않는다. 대신 DONE 배너를 호출하여 워크플로우 최종 종료를 사용자에게 알린다. DONE 배너 호출 후 즉시 종료.
>
> **DONE Banner Call Order**: REPORT 완료 배너 -> (reporter가 status.json 완료 처리 + 레지스트리 해제 수행) -> DONE 배너 호출 -> 종료
> ```bash
> Workflow <registryKey> DONE done
> ```
>
> **Note**: `status.json 완료 처리`(REPORT->COMPLETED)와 `레지스트리 해제`(unregister)는 reporter 에이전트가 전담 수행. 오케스트레이터는 이를 중복 호출하지 않는다.

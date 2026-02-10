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
- reporter가 보고서 작성 + history.md 갱신 + CLAUDE.md 갱신
- **Output:** 보고서 경로, CLAUDE.md 갱신 완료

## REPORT Completion: Orchestrator Post-Processing

reporter 완료 후, **오케스트레이터**가 다음 2가지 후처리를 수행합니다:

### 1. status.json 완료 처리

reporter가 성공적으로 반환된 경우:
```bash
wf-state status <registryKey> REPORT COMPLETED
```

reporter가 실패로 반환된 경우:
```bash
wf-state status <registryKey> REPORT FAILED
```

### 2. 레지스트리 해제

status.json 완료 처리 후, 전역 레지스트리에서 워크플로우를 해제합니다:
```bash
wf-state unregister <registryKey>
```

> **책임 분리 원칙**: reporter는 보고서 생성에 집중하고, 워크플로우 상태 관리(status.json, 레지스트리)는 오케스트레이터가 담당합니다. 이는 SRP(단일 책임 원칙)에 따른 설계입니다.

## DONE Banner

> **REPORT 완료 후 DONE banner**: 오케스트레이터가 status.json 완료 처리 + 레지스트리 해제를 수행한 후, DONE 배너를 호출하여 워크플로우 최종 종료를 사용자에게 알립니다. DONE 배너 호출 후 즉시 종료.
>
> **DONE Banner Call Order**: REPORT 완료 배너 -> 오케스트레이터가 status.json 완료 처리 -> 오케스트레이터가 레지스트리 해제 -> DONE 배너 호출 -> 종료
> ```bash
> Workflow <registryKey> DONE done
> ```

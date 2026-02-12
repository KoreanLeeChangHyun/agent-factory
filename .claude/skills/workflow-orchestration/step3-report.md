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
- reporter가 보고서 작성 + history.md 갱신
- **Output:** 보고서 경로

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

### 2. 사용량 확정

reporter가 성공적으로 반환된 경우, status 갱신 후 usage를 확정합니다:
```bash
wf-state usage-finalize <registryKey>
```

> 실패 시 경고만 출력하고 워크플로우를 블로킹하지 않습니다 (비차단 원칙).

### 3. 레지스트리 해제

status.json 완료 처리 후, 전역 레지스트리에서 워크플로우를 해제합니다:
```bash
wf-state unregister <registryKey>
```

> **책임 분리 원칙**: reporter는 보고서 생성에 집중하고, 워크플로우 상태 관리(status.json, 레지스트리)는 오케스트레이터가 담당합니다. 이는 SRP(단일 책임 원칙)에 따른 설계입니다.

## DONE Banner

> **REPORT 완료 후 DONE banner**: 오케스트레이터가 status.json 완료 처리 + 레지스트리 해제를 수행한 후, DONE 배너를 호출하여 워크플로우 최종 종료를 사용자에게 알립니다.
>
> **DONE Banner Call Order**: REPORT 완료 배너 -> 오케스트레이터가 status.json 완료 처리 -> usage-finalize -> 오케스트레이터가 레지스트리 해제 -> DONE 배너 호출 -> **즉시 종료 (추가 텍스트 출력 절대 금지)**
> ```bash
> Workflow <registryKey> DONE done
> ```

### DONE 배너 이후 절대 금지 규칙 (Post-DONE Silence)

**DONE 배너 호출 후 오케스트레이터는 어떤 텍스트도 출력하지 않고 즉시 종료해야 합니다.**

다음 문구는 DONE 배너 이후 절대 출력 금지입니다:

- "Workflow already completed."
- "Workflow already completed. All tasks finished and DONE banner was issued."
- "All tasks finished"
- "DONE banner was issued"
- 워크플로우 상태를 설명하는 모든 문장
- 완료를 재확인하는 모든 문장

**위반 시 사용자에게 불필요한 노이즈가 발생합니다. DONE 배너가 워크플로우의 마지막 출력이어야 합니다.**

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
- reporter가 보고서 작성 + summary.txt 생성
- **Output:** 보고서 경로

## Step 4: END (end Agent)

reporter 완료 후, **end 에이전트**가 마무리 처리를 수행합니다.

```
Task(subagent_type="end", model="haiku", prompt="
registryKey: <registryKey>
workDir: <workDir>
command: <command>
title: <title>
reportPath: <reporter 반환 보고서 경로>
status: <reporter 반환 상태>
")
```

end 에이전트가 수행하는 작업:

### 1. history.md 갱신 (summary.txt 활용)

- `{workDir}/summary.txt`를 읽어 history.md에 이력 행 추가
- `.prompt/history.md` 테이블에 새 행 삽입

### 2. status.json 완료 처리

reporter가 성공적으로 반환된 경우:
```bash
wf-state status <registryKey> REPORT COMPLETED
```

reporter가 실패로 반환된 경우:
```bash
wf-state status <registryKey> REPORT FAILED
```

### 3. 사용량 확정

reporter가 성공적으로 반환된 경우, status 갱신 후 usage를 확정합니다:
```bash
wf-state usage-finalize <registryKey>
```

> 실패 시 경고만 출력하고 워크플로우를 블로킹하지 않습니다 (비차단 원칙).

### 4. 레지스트리 해제

status.json 완료 처리 후, 전역 레지스트리에서 워크플로우를 해제합니다:
```bash
wf-state unregister <registryKey>
```

### 5. DONE 배너

```bash
Workflow <registryKey> DONE done
```

> **책임 분리 원칙**: reporter는 보고서 생성 + summary.txt에 집중하고, 워크플로우 상태 관리(history.md, status.json, 레지스트리, DONE 배너)는 end 에이전트가 담당합니다. 이는 SRP(단일 책임 원칙)에 따른 설계입니다.

## DONE 배너 이후 절대 금지 규칙 (Post-DONE Silence)

**end 에이전트가 DONE 배너를 호출한 후, 오케스트레이터는 어떤 텍스트도 출력하지 않고 즉시 종료해야 합니다.**

다음 문구는 DONE 배너 이후 절대 출력 금지입니다:

- "Workflow already completed."
- "Workflow already completed. All tasks finished and DONE banner was issued."
- "All tasks finished"
- "DONE banner was issued"
- 워크플로우 상태를 설명하는 모든 문장
- 완료를 재확인하는 모든 문장

**위반 시 사용자에게 불필요한 노이즈가 발생합니다. DONE 배너가 워크플로우의 마지막 출력이어야 합니다.**

# Step 1: INIT (init Agent)

> **Agent-Skill Binding**
> - Agent: `init` (model: haiku, maxTurns: 15)
> - Skill: `workflow-init`
> - Task prompt: `command: <command>, mode: <mode>`

> cc:* 명령어 수신 시 사용자 입력 유무와 관계없이 MUST call init. 입력이 없는 경우의 처리(시나리오 분기)는 init 에이전트가 자체 수행한다.

## INIT Banner (Before init Agent Call)

```bash
Workflow INIT none <command>
```

## Agent Call

```
Task(subagent_type="init", prompt="
command: <command>
mode: <mode>
")
```

> `mode` parameter is optional. Default is `full`. Values: `full`, `no-plan`, `prompt`.
> For prompt command, always pass `mode: prompt`.
> For commands with `-np` flag, pass `mode: no-plan`.

## Return Values

`request`, `workDir`, `workId`, `registryKey`, `date`, `title`, `workName`, `근거`

- init이 전처리(prompt.txt 읽기, 작업 디렉토리 생성, user_prompt.txt 복사, prompt.txt 클리어)를 수행
- **registryKey**: init이 반환하는 `YYYYMMDD-HHMMSS` 형식 식별자. 후속 모든 `Workflow` 배너 및 `wf-state` 호출에 사용
- **status.json**: init이 `<workDir>/status.json` 생성 완료 (phase: "INIT"). 좀비 정리도 이 단계에서 수행
- **workDir format**: `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>` (중첩 구조)

## Orchestrator Post-INIT Rules (CRITICAL)

> **init이 에러 없이 반환하면, 오케스트레이터는 반환값을 있는 그대로 수용하고 즉시 Mode Branching으로 진행한다. 어떠한 판단도 개입하지 않는다.**

### 절대 금지 (오케스트레이터)

| 금지 행위 | 위반 사례 |
|-----------|----------|
| init 반환값의 품질/완전성/정확성 평가 | "request가 불완전해 보인다" → AskUserQuestion |
| init 반환 후 AskUserQuestion 호출 | "무엇을 구현하시겠습니까?" 질문 |
| init 반환값 재해석/보정/보완 | request 필드를 다른 값으로 교체 |
| init 반환 후 추가 정보 수집 시도 | prompt.txt를 직접 다시 읽기 |

### 유일한 분기 조건

- init이 `에러:` 접두사로 반환 → 워크플로우 중단
- 그 외 모든 경우 → **무조건** Mode Branching 진행

> **근거:** prompt.txt가 비어있는 경우의 사용자 확인은 init 에이전트가 자체 처리한다 (시나리오 1/2). init이 정상 반환했다는 것은 사용자 요청이 확보되었다는 의미이다. 오케스트레이터가 이를 재검증하는 것은 역할 침범이다.

---

## Return Value Retention Rules (REQUIRED)

init 반환값(request, workDir, workId, registryKey, date, title, workName, 근거)을 모두 보관하고, 후속 단계에 필요한 파라미터를 전달한다:

| Parameter | Used In | Purpose |
|-----------|---------|---------|
| `request` | PLAN (Step 2) | user_prompt.txt의 첫 50자 |
| `workDir` | PLAN (Step 2), REPORT (Step 4) | 작업 디렉토리 경로 |
| `workId` | PLAN (Step 2), WORK (Step 3), REPORT (Step 4) | 작업 식별자 |
| `registryKey` | PLAN (Step 2), WORK (Step 3), REPORT (Step 4) | Workflow/wf-state 호출의 식별자. date + "-" + workId 형식 |
| `date`, `title`, `workName` | REPORT (Step 4), Prompt mode (history) | 경로 구성 시 사용 |
| `근거` | Logging only | 로깅용 |

### usage.json 초기화

- **usage.json**: register 시점에 `<workDir>/usage.json` 빈 구조 자동 생성 (usage-tracker.sh가 서브에이전트별 토큰을 기록)

## Prompt Mode (Tier 3) Post-INIT Flow

When command is `prompt`, the orchestrator skips PLAN and proceeds directly to WORK (main agent direct work) -> REPORT -> DONE:

1. `wf-state both <registryKey> worker INIT WORK`
2. `Workflow <registryKey> WORK` (WORK start banner)
3. Read `<workDir>/user_prompt.txt` for user request
4. Main agent performs direct work (file changes allowed)
5. `mkdir -p <workDir>/work` (ensure work directory exists for reporter)
6. `Workflow <registryKey> WORK done` (WORK completion banner)
7. `wf-state both <registryKey> reporter WORK REPORT`
8. `Workflow <registryKey> REPORT` (REPORT start banner)
9. Reporter call: `Task(subagent_type="reporter", prompt="command: prompt, workId: <workId>, workDir: <workDir>, workPath: <workDir>/work/")`
10. `Workflow <registryKey> REPORT done` (REPORT completion banner)
11. `Workflow <registryKey> DONE` (DONE start banner)
12. Done agent call: `Task(subagent_type="done", prompt="registryKey: <registryKey>, workDir: <workDir>, command: prompt, title: <title>, reportPath: <reportPath>, status: <status>")`
13. `Workflow <registryKey> DONE done` (DONE completion banner)
14. Terminate

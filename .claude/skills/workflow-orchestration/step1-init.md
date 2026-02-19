# Step 1: INIT (init Agent)

> **Agent-Skill Binding**
> - Agent: `init` (model: haiku, maxTurns: 15)
> - Skill: `workflow-init`
> - Task prompt: `command: <command>, mode: <mode>`

> cc:* 명령어 수신 시 사용자 입력 유무와 관계없이 MUST call init. 입력이 없는 경우의 처리(시나리오 분기)는 init 에이전트가 자체 수행한다.

## INIT Banner (Before init Agent Call)

```bash
step-start INIT none <command>
```

## Agent Call

```
Task(subagent_type="init", prompt="
command: <command>
mode: <mode>
")
```

> `mode` parameter is optional. Default is `full`. Values: `full`, `strategy`, `prompt`.
> 오케스트레이터가 "Mode Auto-Determination Rule" (SKILL.md)에 따라 결정한 값을 전달한다.

## Return Values

`request`, `workDir`, `workId`, `registryKey`, `date`, `title`, `workName`, `근거`

- init이 전처리(prompt.txt 읽기, 작업 디렉터리 생성, user_prompt.txt 복사, prompt.txt 클리어)를 수행
- **registryKey**: init이 반환하는 `YYYYMMDD-HHMMSS` 형식 식별자. 후속 모든 `step-start`/`step-end` 배너 및 `update_state.py` 호출에 사용
- **status.json**: init이 `<workDir>/status.json` 생성 완료 (phase: "INIT"). 좀비 정리도 이 단계에서 수행
- **workDir format**: `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>` (중첩 구조)

## INIT Completion Banner

init 에이전트가 정상 반환(에러 없음)한 후, Mode Branching 전에 INIT 완료 배너를 호출한다.

```bash
step-end <registryKey> INIT
```

**호출 타이밍:**
1. init 에이전트 정상 반환 확인
2. 반환값(request, workDir, workId, registryKey 등) 추출/보관
3. `step-end <registryKey> INIT` 호출
4. Mode Branching 진행 (full -> PLAN, strategy -> STRATEGY, prompt -> WORK)

> init이 `에러:` 접두사로 반환한 경우에는 step-end를 호출하지 않고 재시도 로직으로 진행한다.

## Error Handling

INIT 에이전트 호출 실패 시 최대 3회 재시도합니다.

```
retry_count = 0
MAX_RETRIES = 3

while retry_count < MAX_RETRIES:
    result = Task(subagent_type="init", prompt="command: <command>, mode: <mode>")
    if result does not start with "에러:":
        break  # 성공 → Mode Branching 진행
    retry_count += 1
    log("[WARN] INIT 실패 (시도 {retry_count}/{MAX_RETRIES}): {result}")

if retry_count >= MAX_RETRIES:
    AskUserQuestion("INIT 에이전트가 3회 연속 실패했습니다. 워크플로우를 재시도하거나 중단할 수 있습니다.")
```

| 상황 | 처리 |
|------|------|
| init 반환값이 `에러:` 접두사 | 재시도 (최대 3회) |
| 3회 모두 실패 | AskUserQuestion으로 사용자에게 상황 보고 |
| 재시도 중 성공 | 경고 로그만 남기고 정상 진행 |

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
| `workDir` | PLAN (Step 2), REPORT (Step 4) | 작업 디렉터리 경로 |
| `workId` | PLAN (Step 2), WORK (Step 3), REPORT (Step 4) | 작업 식별자 |
| `registryKey` | PLAN (Step 2), WORK (Step 3), REPORT (Step 4) | step-start/step-end/update_state.py 호출의 식별자. date + "-" + workId 형식 |
| `date`, `title`, `workName` | REPORT (Step 4), Prompt mode (history) | 경로 구성 시 사용 |
| `근거` | Logging only | 로깅용 |

### usage.json 초기화

- **usage.json**: register 시점에 `<workDir>/usage.json` 빈 구조 자동 생성 (usage_tracker.py가 서브에이전트별 토큰을 기록)

## Prompt Mode (Tier 3) Post-INIT Flow

When command is `prompt`, the orchestrator skips PLAN and proceeds directly to WORK (main agent direct work) -> REPORT -> DONE.

### Prompt Mode Direct Write/Edit Scope

> **허용 범위**: 1-2개 파일 즉석 수정, 질의응답 텍스트 답변
> **권장하지 않음**: 3개 이상 파일 수정, 새 기능 구현 -> `cc:implement` 사용 권장
> **근거**: prompt 모드의 핵심 가치는 Worker 없이 오케스트레이터가 직접 처리하는 경량성. 복잡한 작업은 Worker 위임(full 모드)이 적합

### Flow

1. `python3 .claude/scripts/workflow/update_state.py both <registryKey> worker INIT WORK`
2. `step-start <registryKey> WORK` (WORK start banner)
3. Read `<workDir>/user_prompt.txt` for user request (1회만, 반복 읽기 금지)
4. Main agent performs direct work (file changes allowed, scope: 1-2 files)
5. `mkdir -p <workDir>/work` (ensure work directory exists for reporter)
6. `step-end <registryKey> WORK` (WORK completion)
7. `python3 .claude/scripts/workflow/update_state.py both <registryKey> reporter WORK REPORT`
8. `step-start <registryKey> REPORT` (REPORT start banner)
9. Reporter call: `Task(subagent_type="reporter", prompt="command: prompt, workId: <workId>, workDir: <workDir>, workPath: <workDir>/work/")`
10. `step-end <registryKey> REPORT` (REPORT completion)
11. `step-start <registryKey> DONE` (DONE start banner)
12. Done agent call: `Task(subagent_type="done", prompt="registryKey: <registryKey>, workDir: <workDir>, command: prompt, title: <title>, reportPath: <reportPath>, status: <status>")`
13. `step-end <registryKey> DONE done` (DONE completion)
14. Terminate

## Strategy Mode Post-INIT Flow

When command is `strategy`, the orchestrator skips PLAN, WORK, REPORT and dispatches the strategy sub-agent for STRATEGY phase -> DONE.

### Flow

1. `python3 .claude/scripts/workflow/update_state.py both <registryKey> strategy INIT STRATEGY`
2. `step-status <registryKey>`
3. `step-start <registryKey> STRATEGY` (STRATEGY start banner)
4. `Task(subagent_type="strategy", prompt="command: strategy, workId: <workId>, request: <request>, workDir: <workDir>")`
5. Extract first 3 lines from strategy return (discard from line 4)
6. `step-end <registryKey> STRATEGY` (STRATEGY completion)
7. `step-start <registryKey> DONE` (DONE start banner)
8. Done agent call: `Task(subagent_type="done", prompt="registryKey: <registryKey>, workDir: <workDir>, command: strategy, title: <title>, reportPath: <reportPath>, status: <status>")`
9. `step-end <registryKey> DONE done` (DONE completion)
10. Terminate

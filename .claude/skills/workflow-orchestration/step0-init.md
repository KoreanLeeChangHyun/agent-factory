# Step 0: INIT (init Agent)

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

`request`, `workDir`, `workId`, `date`, `title`, `workName`, `근거`

- init이 전처리(prompt.txt 읽기, 작업 디렉토리 생성, user_prompt.txt 복사, prompt.txt 클리어)를 수행
- **status.json**: init이 `<workDir>/status.json` 생성 완료 (phase: "INIT"). 좀비 정리도 이 단계에서 수행
- **workDir format**: `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>` (중첩 구조)

## Return Value Retention Rules (REQUIRED)

init 반환값(request, workDir, workId, date, title, workName, 근거)을 모두 보관하고, 후속 단계에 필요한 파라미터를 전달한다:

| Parameter | Used In | Purpose |
|-----------|---------|---------|
| `request` | PLAN (Step 1) | user_prompt.txt의 첫 50자 |
| `workDir` | PLAN (Step 1), REPORT (Step 3) | 작업 디렉토리 경로 |
| `workId` | PLAN (Step 1), WORK (Step 2), REPORT (Step 3) | 작업 식별자 |
| `date`, `title`, `workName` | REPORT (Step 3), Prompt mode (history) | 경로 구성 시 사용 |
| `근거` | Logging only | 로깅용 |

## Prompt Mode (Tier 3) Post-INIT Flow

When command is `prompt`, the orchestrator does NOT proceed to PLAN/WORK/REPORT. Instead:

1. Read `<workDir>/user_prompt.txt` for user request
2. Main agent performs direct work (file changes allowed)
3. Append 1 row to `.workflow/history.md`
4. `wf-state status <registryKey> INIT COMPLETED`
5. `wf-state unregister <registryKey>`
6. `Workflow <registryKey> DONE done`
7. Terminate

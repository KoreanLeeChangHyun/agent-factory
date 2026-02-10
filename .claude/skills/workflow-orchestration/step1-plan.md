# Step 1: PLAN (planner Agent)

## No-Plan Mode Skip Condition

> **no-plan 모드(`-np` 플래그)에서는 PLAN 단계 전체를 건너뛰고 WORK로 직행합니다.**
>
> 판별: status.json의 `mode` 필드가 `no-plan`이면 아래 모든 절차(1a~1b)를 스킵합니다.
> - planner 에이전트 호출 없음
> - AskUserQuestion 승인 절차 없음
> - PLAN 배너 출력 없음
> - 오케스트레이터는 즉시 Step 2: WORK로 진행

---

## Step 1a: PLAN - planner Call

> **State Update** before PLAN start:
> ```bash
> wf-state both <registryKey> planner INIT PLAN
> ```

**Detailed Guide:** workflow-plan skill 참조

```
Task(subagent_type="planner", prompt="
command: <command>
workId: <workId>
request: <request>
workDir: <workDir>
")
```

- planner가 요구사항 완전 명확화 + 계획서 저장 후 `작성완료` 반환
- **Output:** 계획서 경로

## Step 1b: PLAN - Orchestrator User Approval

> planner가 `작성완료`를 반환하면, **오케스트레이터(메인 에이전트)가 직접** AskUserQuestion으로 사용자 최종 승인을 수행합니다.
> 서브에이전트(planner)는 AskUserQuestion을 호출할 수 없으므로(플랫폼 제약), 승인 절차는 반드시 오케스트레이터가 담당합니다.

### 1b-1. .context.json Check/Update

> **.context.json은 INIT 단계에서 이미 저장되어 있습니다.** PLAN 단계에서는 내용 변경이 필요한 경우(제목 변경, 작업 이름 수정 등)에만 업데이트합니다. 변경이 없으면 이 단계를 건너뜁니다.

**Update가 필요한 경우:**
- agent 필드가 "planner"로 설정되어 있지 않은 경우

> **Note:** `update-workflow-state.sh context` 모드는 `agent` 필드만 갱신할 수 있습니다. title, workName 등 다른 필드를 변경해야 하는 경우, planner가 `.context.json`에 직접 쓰기를 수행하세요.

**Local .context.json Schema:**

`<workDir>/.context.json` (INIT 단계에서 생성, 이력 보존용):
```json
{
  "title": "<작업 제목>",
  "workId": "<workId>",
  "workName": "<작업 이름>",
  "command": "<command>",
  "agent": "planner",
  "created_at": "<KST ISO 타임스탬프>"
}
```

> - `workId`는 HHMMSS 6자리 형식 (예: "170327"). `<YYYYMMDD>-<workId>` 형식은 레지스트리 키에서 사용.
> - `workName`은 INIT 단계에서 title 인자를 기반으로 .context.json에 저장.

**Update Method (agent field, 1 Tool Call):**
```bash
Bash("wf-state context <registryKey> <agent>")
```

> **Note:**
> - `update-workflow-state.sh context` 모드의 3번째 인자는 에이전트 이름 문자열 (예: "planner", "worker", "reporter"). JSON 문자열을 인자로 받지 않음.
> - 이 모드는 로컬 `<workDir>/.context.json`의 `agent` 필드만 업데이트. 전역 `.workflow/registry.json`은 활성 워크플로우 레지스트리로 사용되며, `register`/`unregister` 모드로만 접근. 직접 쓰기 금지.

### 1b-2. Slack Notification (Automatic)

AskUserQuestion 호출 시 `PreToolUse` Hook이 자동으로 Slack 알림을 전송합니다.

- Hook script: `.claude/hooks/event/pre-tool-use/slack-ask.sh`
- Hook이 활성 워크플로우 레지스트리(`.workflow/registry.json`)에서 해당 워크플로우의 로컬 .context.json을 읽어 통일 포맷으로 Slack 전송
- 레지스트리 또는 로컬 .context.json이 없으면 폴백 포맷 사용

**Slack Notification Format (slack-ask.sh):**
```
<작업 제목>
- 작업ID: <YYYYMMDD>-<workId>
- 작업이름: <작업 이름>
- 명령어: <명령어>
- 상태: 사용자 입력 대기 중
```

### 1b-3. AskUserQuestion으로 사용자 승인

> **Sequential Execution REQUIRED (Critical):**
> PLAN 완료 배너(`Workflow <registryKey> PLAN done`)의 Bash 호출이 **완료된 후에만** AskUserQuestion을 호출해야 합니다.
> - PLAN 완료 배너와 AskUserQuestion을 **동일 응답에서 병렬로 호출하는 것은 MUST NOT**.
> - 반드시 **(1) PLAN 완료 배너 Bash 호출 -> 응답 수신 확인 -> (2) AskUserQuestion 호출** 순서로 2회의 별도 도구 호출 턴에서 실행.
> - 위반 시 사용자가 계획서 링크를 확인하지 못한 채 승인을 요청받는 UX 결함 발생.

planner가 계획서를 작성 완료하고 `작성완료` 상태를 반환하면, 오케스트레이터가 계획서 파일 경로를 터미널에 출력한 후 AskUserQuestion 도구로 승인/거부 선택지를 제시합니다. 계획 요약은 터미널에 직접 출력하지 않습니다 (사용자가 계획서 파일을 직접 확인).

```markdown
AskUserQuestion(
  questions: [{
    question: "위 계획대로 진행하시겠습니까?",
    header: "승인 요청",
    options: [
      { label: "승인 (Recommended)", description: "WORK 단계로 진행합니다" },
      { label: "수정 (prompt.txt)", description: "prompt.txt에 피드백을 작성한 후 선택합니다" },
      { label: "중지", description: "워크플로우를 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

> **AskUserQuestion Options Strictly Fixed (REQUIRED):**
> - 위 3개 옵션(승인/수정/중지)만 허용. 옵션 추가/변경/제거 MUST NOT.
> - `freeformLabel`, `freeformPlaceholder` 등 자유 입력 필드 사용 MUST NOT.
> - `"Type something"`, `"입력"` 등 자유 텍스트 입력 옵션 추가 MUST NOT.
> - `multiSelect: false` MUST maintain.
> - 옵션의 label, description 텍스트를 임의로 변경하지 않음.

### 1b-4. Approval Result Processing

| Selection | Action |
|-----------|--------|
| **승인** | WORK 단계로 진행 (status.json phase 업데이트는 오케스트레이터가 WORK 전이 시 수행) |
| **수정 (prompt.txt)** | 사용자가 prompt.txt에 피드백을 작성한 후 선택. planner를 재호출하여 피드백 반영 후 계획 재수립, 다시 Step 1b 수행 |
| **중지** | status.json phase="CANCELLED" 업데이트 후 워크플로우 중단 |

> **"수정 (prompt.txt)" selection handling:**
> 사용자가 `.prompt/prompt.txt`에 피드백을 작성한 후 "수정 (prompt.txt)"을 선택합니다. 오케스트레이터는 다음 절차를 순서대로 수행합니다:
>
> 1. **prompt.txt read**: `.prompt/prompt.txt`의 내용을 읽어 피드백 내용을 확보
> 2. **prompt.txt clear (REQUIRED)**: 읽기 직후 MUST clear prompt.txt
>    ```bash
>    > .prompt/prompt.txt
>    ```
>    클리어 실패 시 재시도:
>    ```bash
>    : > .prompt/prompt.txt
>    ```
> 3. **planner re-call**: 확보한 피드백 내용을 prompt에 `mode: revise` 및 피드백 내용으로 추가하여 계획 재수립
> 4. **Step 1b repeat**: 재수립된 계획에 대해 다시 사용자 승인 요청
>
> **Note:** prompt.txt 클리어를 생략하면 이전 피드백 내용이 잔존하여 후속 작업에서 중복/오염이 발생. INIT 단계의 init-workflow.sh Step 4와 동일한 패턴.

### CANCELLED Processing

사용자가 "중지"를 선택하면 오케스트레이터가 `update-workflow-state.sh`를 호출하여 CANCELLED 상태를 기록합니다.

**Update Method (1 Tool Call):**
```bash
Bash("wf-state status <registryKey> PLAN CANCELLED")
```

**Example:**
```bash
Bash("wf-state status 20260205-213000 PLAN CANCELLED")
```

**Script behavior:**
- `<workDir>/status.json`의 `phase`를 `"CANCELLED"`로 변경
- `transitions` 배열에 `{"from": "PLAN", "to": "CANCELLED", "at": "<현재시간ISO>"}` 추가
- `updated_at`을 현재 시간(ISO 8601, KST)으로 갱신

**Result example:**
```json
{
  "phase": "CANCELLED",
  "updated_at": "2026-02-05T21:30:00+09:00",
  "transitions": [
    {"from": "INIT", "to": "PLAN", "at": "..."},
    {"from": "PLAN", "to": "CANCELLED", "at": "2026-02-05T21:30:00+09:00"}
  ]
}
```

**Failure handling:** 스크립트 실패 시 `[WARN]` 경고만 출력하고 exit 0으로 종료. 워크플로우를 정상 진행(중단). status.json은 보조 상태 관리이므로 실패가 워크플로우를 차단하지 않음.

## Binding Contract Rule (REQUIRED)

> **PLAN 승인 후 계획 변경 불가 원칙**
>
> 사용자가 "승인"을 선택한 시점에서 계획서는 Binding Contract가 됩니다.
> 오케스트레이터는 승인된 계획서의 태스크를 변경, 추가, 제거하지 않습니다.
> 계획 변경이 필요하면 사용자가 "수정 (prompt.txt)" 선택지를 통해 재계획을 요청해야 합니다.
>
> **MUST NOT:**
> - 오케스트레이터가 독자적으로 태스크를 추가/삭제/변경
> - Worker 반환값을 근거로 계획을 임의 수정
> - "맥락 보강"을 이유로 계획에 없는 작업 수행

# PLAN (planner Agent)

> **Agent-Skill Binding**
> - Agent: `planner` (model: inherit, maxTurns: 30)
> - Skill: `workflow-plan`
> - Task prompt: `command: <command>, workId: <workId>, request: <request>, workDir: <workDir>`

## Strategy Mode Skip Condition

> **strategy 모드에서는 PLAN 단계 전체를 건너뛰고 STRATEGY Phase로 직행합니다.**
>
> 판별: 오케스트레이터가 INIT 전 "Mode Auto-Determination Rule"로 결정한 `mode` 변수가 `strategy`이면 아래 모든 절차(2a~2b)를 스킵합니다. (status.json Read 불필요)
> - planner 에이전트 호출 없음
> - AskUserQuestion 승인 절차 없음
> - PLAN 배너 출력 없음
> - 오케스트레이터는 즉시 Strategy Mode Post-INIT Flow (step-init.md 참조)로 진행

## Noplan Mode Skip Condition

> **noplan 모드에서는 PLAN 단계 전체를 건너뛰고 WORK Phase로 직행합니다.**
>
> 판별: 오케스트레이터가 INIT 전 "Mode Auto-Determination Rule"로 결정한 `mode` 변수가 `noplan`이면 아래 모든 절차(2a~2b)를 스킵합니다. (status.json Read 불필요)
> - planner 에이전트 호출 없음
> - AskUserQuestion 승인 절차 없음
> - PLAN 배너 출력 없음
> - 오케스트레이터는 즉시 Noplan Mode Post-INIT Flow (step-init.md 참조)로 진행

---

## Step 2a: PLAN - planner Call

> **State Update** before PLAN start:
> ```bash
> python3 .claude/scripts/state/update_state.py both <registryKey> planner INIT PLAN
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

### 2a-Post: planner 반환 후 오케스트레이터 호출 순서 (REQUIRED)

> planner가 `작성완료`를 반환한 직후, 오케스트레이터는 아래 순서를 **정확히 1회씩** 실행합니다.

1. `step-end <registryKey> PLAN` — PLAN 완료 배너 출력 (**1회만 호출, 재호출 MUST NOT**)
2. `step-end` Bash 호출의 응답 수신을 확인
3. **즉시** Step 2b의 AskUserQuestion으로 진행

> **MUST NOT:**
> - `step-end <registryKey> PLAN`을 2회 이상 호출
> - Step 2b 진입 시 `step-end`를 "보장을 위해" 재호출
> - `step-end`와 AskUserQuestion을 동일 응답에서 병렬 호출

## Step 2b: PLAN - Orchestrator User Approval

> planner가 `작성완료`를 반환하면, **오케스트레이터가 직접** AskUserQuestion으로 사용자 최종 승인을 수행합니다.
> 서브에이전트(planner)는 AskUserQuestion을 호출할 수 없으므로(플랫폼 제약), 승인 절차는 반드시 오케스트레이터가 담당합니다.

### 2b-1. .context.json Check/Update

> **.context.json은 INIT 단계에서 이미 저장되어 있습니다.** PLAN 단계에서는 내용 변경이 필요한 경우(제목 변경, 작업 이름 수정 등)에만 업데이트합니다. 변경이 없으면 이 단계를 건너뜁니다.

**Update가 필요한 경우:**
- agent 필드가 "planner"로 설정되어 있지 않은 경우

> **Note:** `update_state.py context` 모드는 `agent` 필드만 갱신할 수 있습니다. title, workName 등 다른 필드를 변경해야 하는 경우, planner가 `.context.json`에 직접 쓰기를 수행하세요.

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
Bash("python3 .claude/scripts/state/update_state.py context <registryKey> <agent>")
```

> **Note:**
> - `update_state.py context` 모드의 3번째 인자는 에이전트 이름 문자열 (예: "planner", "worker", "reporter"). JSON 문자열을 인자로 받지 않음.
> - 이 모드는 로컬 `<workDir>/.context.json`의 `agent` 필드만 업데이트. 전역 `.workflow/registry.json`은 활성 워크플로우 레지스트리로 사용되며, `register`/`unregister` 모드로만 접근. 직접 쓰기 금지.

### 2b-2. Slack Notification (Automatic)

AskUserQuestion 호출 시 `PreToolUse` Hook이 자동으로 Slack 알림을 전송합니다.

- Hook script: `.claude/hooks/pre-tool-use/slack-ask.py` (thin wrapper -> `.claude/scripts/slack/slack_ask.py`)
- Hook이 활성 워크플로우 레지스트리(`.workflow/registry.json`)에서 해당 워크플로우의 로컬 .context.json을 읽어 통일 포맷으로 Slack 전송
- 레지스트리 또는 로컬 .context.json이 없으면 폴백 포맷 사용

**Slack Notification Format (slack-ask.py):**
```
<작업 제목>
- 작업ID: <YYYYMMDD>-<workId>
- 작업이름: <작업 이름>
- 명령어: <명령어>
- 상태: 사용자 입력 대기 중
```

### 2b-3. AskUserQuestion으로 사용자 승인

> **Sequential Execution REQUIRED (Critical):**
> PLAN 완료 배너(`step-end <registryKey> PLAN`)의 Bash 호출이 **완료된 후에만** AskUserQuestion을 호출해야 합니다.
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
      { label: "승인", description: "WORK 단계로 진행합니다" },
      { label: "수정 요청", description: "계획서 수정 후 재검토합니다" },
      { label: "중지", description: "워크플로우를 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

> **AskUserQuestion Options Strictly Fixed (REQUIRED):**
> - 위 3개 옵션(승인/수정 요청/중지)만 허용. 옵션 추가/변경/제거 MUST NOT.
> - `freeformLabel`, `freeformPlaceholder` 등 자유 입력 필드 사용 MUST NOT.
> - `multiSelect: false` MUST maintain.
> - 옵션의 label, description 텍스트를 임의로 변경하지 않음.

### 2b-4. Approval Result Processing

| Selection | Action |
|-----------|--------|
| **승인** | WORK 단계로 진행 (status.json phase 업데이트는 오케스트레이터가 WORK 전이 시 수행). **MUST NOT:** `.prompt/prompt.txt` 읽기, `reload_prompt.py` 호출, `user_prompt.txt` 갱신 |
| **수정 요청** | 사용자가 `.prompt/prompt.txt`에 피드백을 작성한 후 선택. 오케스트레이터가 `reload_prompt.py`를 호출하여 피드백을 `user_prompt.txt`에 반영한 뒤 planner를 재호출하여 계획 재수립, 다시 Step 2b 수행 |
| **중지** | → [CANCELLED Processing](#cancelled-processing) 섹션으로 이동하여 처리. **MUST NOT:** `.prompt/prompt.txt` 읽기, `reload_prompt.py` 호출, `user_prompt.txt` 갱신, **done 에이전트 호출**, **DONE 배너(`step-start DONE`) 호출** |

> **prompt.txt Isolation Rule (CRITICAL):**
> `.prompt/prompt.txt` 읽기 및 `reload_prompt.py` 호출은 **오직 "수정 요청" 선택 시에만** 허용됩니다.
> "승인" 또는 "중지" 선택 후 `.prompt/prompt.txt`를 읽으면, 사용자가 다른 워크플로우를 위해 작성한 내용이 현재 워크플로우에 혼입되어 질의 충돌이 발생합니다.
> - "승인" 시: prompt.txt 무시, WORK 단계로 즉시 진행
> - "중지" 시: prompt.txt 무시, CANCELLED 처리만 수행
> - "수정 요청" 시: reload_prompt.py 1회 호출 (유일한 prompt.txt 접근 경로)

> **Error Handling:** planner 에이전트 호출이 실패(에러 반환 또는 비정상 종료)한 경우, 최대 3회 재시도합니다. 3회 모두 실패하면 AskUserQuestion으로 사용자에게 상황을 보고하고, 재시도 또는 워크플로우 중단을 선택하도록 요청합니다. 재시도 시 이전 호출과 동일한 파라미터를 사용합니다.

> **"수정 요청" selection handling:**
> **Precondition:** 아래 3단계 절차는 사용자가 "수정 요청"을 선택한 경우에만 실행합니다. "승인" 또는 "중지" 선택 시 이 절차를 실행하는 것은 MUST NOT입니다.
>
> 사용자가 `.prompt/prompt.txt`에 피드백을 작성한 후 "수정 요청"을 선택합니다. 오케스트레이터는 다음 3단계 절차를 순서대로 수행합니다:
>
> **1단계. reload_prompt.py 호출** — 피드백 수신
>
> 오케스트레이터가 스크립트를 1회 호출하여 사용자 피드백을 수신합니다.
>
> ```bash
> # 오케스트레이터 실행 코드
> feedback=$(Bash("python3 .claude/scripts/init/reload_prompt.py <workDir>"))
> ```
>
> - 스크립트가 prompt.txt 읽기, user_prompt.txt append, .uploads/ 복사/클리어, prompt.txt 클리어, querys.txt 기록을 일괄 수행
> - stdout으로 피드백 전문을 출력
> - 종료코드 0: 정상 완료 → stdout 내용을 `feedback` 변수에 저장
> - 종료코드 1: 실패 → 에러 메시지를 사용자에게 알림 후 재시도 또는 중단 선택 요청
> - stdout에 `[WARN] prompt.txt is empty`가 포함된 경우: prompt.txt가 비어있는 상태. 피드백 없이 planner를 재호출하여 자체 판단으로 계획 개선 (feedback 변수를 빈 문자열로 처리)
>
> **2단계. planner re-call** — 피드백 포함 계획 재수립
>
> stdout으로 수신한 피드백 내용을 `mode: revise` 프롬프트에 포함하여 planner를 재호출합니다.
>
> ```
> Task(subagent_type="planner", prompt="
> command: <command>
> workId: <workId>
> request: <request>
> workDir: <workDir>
> mode: revise
> feedback: <reload_prompt.py stdout>
> ")
> ```
>
> - `feedback` 값이 빈 문자열인 경우(`[WARN] prompt.txt is empty` 케이스): `feedback` 필드를 생략하거나 빈 값으로 전달. planner가 기존 계획서를 자체 판단으로 개선
> - planner는 기존 계획서를 기반으로 피드백을 반영한 수정 계획서를 작성하여 `작성완료` 반환
>
> **3단계. Step 2b repeat** — 재승인 요청
>
> 재수립된 계획에 대해 다시 Step 2b(사용자 승인 요청)를 반복합니다. 사용자가 "승인"을 선택할 때까지 1~3단계를 반복할 수 있습니다.
>
> **Note:** `.uploads/` 복사/클리어, `user_prompt.txt` append, `prompt.txt` 클리어, `querys.txt` 기록은 모두 스크립트가 처리하므로 오케스트레이터에서 별도 인라인 절차가 불필요합니다.

### CANCELLED Processing

> **CRITICAL WARNING: 중지 선택 시 DONE 단계를 거치지 않는다.**
>
> "중지" 선택 시 done 에이전트 호출, DONE 배너(`step-start DONE`, `step-end DONE`) 호출을 **절대 수행하지 않는다**.
> 오케스트레이터가 직접 status 전이(`PLAN` → `CANCELLED`) + `unregister`만 수행한 후 워크플로우를 **즉시 종료**한다.
> DONE 단계는 정상 완료(승인 → WORK → REPORT → DONE) 경로에서만 진입하는 단계이다.

사용자가 "중지"를 선택하면 오케스트레이터가 `update_state.py`를 호출하여 CANCELLED 상태를 기록합니다.

**Update Method (2 Tool Calls, sequential):**
```bash
# 1. CANCELLED 상태로 전이
Bash("python3 .claude/scripts/state/update_state.py status <registryKey> PLAN CANCELLED")
# 2. 레지스트리에서 해제 (MUST: 누락 시 잔류 엔트리 발생)
Bash("python3 .claude/scripts/state/update_state.py unregister <registryKey>")
```

> **REQUIRED:** `unregister` 호출을 생략하면 CANCELLED 상태의 엔트리가 레지스트리에 잔류합니다. status 전이와 unregister는 반드시 순차 실행하세요.

**Script behavior:**
- `<workDir>/status.json`의 `phase`를 `"CANCELLED"`로 변경
- `transitions` 배열에 `{"from": "PLAN", "to": "CANCELLED", "at": "<현재시간ISO>"}` 추가
- `updated_at`을 현재 시간(ISO 8601, KST)으로 갱신
- 전역 레지스트리(`.workflow/registry.json`)에서 해당 워크플로우 엔트리 제거

**Failure handling:** 스크립트 실패 시 `[WARN]` 경고만 출력하고 exit 0으로 종료. 워크플로우를 정상 진행(중단). status.json은 보조 상태 관리이므로 실패가 워크플로우를 차단하지 않음.

**CANCELLED 후 오케스트레이터 종료 방법 (REQUIRED):**

> status 전이(`update_state.py status`) + unregister(`update_state.py unregister`) 호출이 완료되면,
> 오케스트레이터는 **추가 배너 호출(`step-start`, `step-end`), 에이전트 호출(`done`, `reporter`, `worker` 등)을 일체 수행하지 않고** 현재 turn을 즉시 종료합니다.
> CANCELLED 처리 후 남은 행위는 없습니다.

## Binding Contract Rule (REQUIRED)

> **PLAN 승인 후 계획 변경 불가 원칙**
>
> 사용자가 "승인"을 선택한 시점에서 계획서는 Binding Contract가 됩니다.
> 오케스트레이터는 승인된 계획서의 태스크를 변경, 추가, 제거하지 않습니다.
> 계획 변경이 필요하면 사용자가 "수정 요청" 선택지를 통해 재계획을 요청해야 합니다.
>
> **MUST NOT:**
> - 오케스트레이터가 독자적으로 태스크를 추가/삭제/변경
> - Worker 반환값을 근거로 계획을 임의 수정
> - "맥락 보강"을 이유로 계획에 없는 작업 수행

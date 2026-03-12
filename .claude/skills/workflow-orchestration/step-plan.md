# PLAN (planner Agent)

> **Agent-Skill Binding**
> - Agent: `planner` (model: opus, maxTurns: 100)
> - Skill: `workflow-agent-planner`
> - Task prompt: `command: <command>, workId: <workId>, request: <request>, workDir: <workDir>`

PLAN Step은 모든 워크플로우에서 필수로 실행됩니다.

---

## Step 2-pre: Prompt Quality Check

> **하위 호환 보장**: `init-result.json`에 `prompt_quality` 필드가 없으면 이 단계 전체를 스킵하고 Step 2a로 진행합니다.

initialization.py가 `init-result.json`에 기록한 `prompt_quality.quality_score`를 확인하여 사용자에게 피드백을 제공합니다.

**실행 조건:**

- `init-result.json`에 `prompt_quality` 필드가 존재하는 경우에만 실행
- 필드가 없으면 즉시 Step 2a로 진행

**처리 분기:**

| `quality_score` | 동작 |
|-----------------|------|
| 필드 없음 | 스킵 → Step 2a로 진행 |
| `>= 0.6` | 정상 진행 → Step 2a로 진행 |
| `< 0.6` | 역방향 피드백 표시 후 AskUserQuestion 제시 |

**score < 0.6 시 피드백 표시 및 선택지 제시:**

`prompt_quality.feedback` 목록을 사용자에게 표시한 후 AskUserQuestion을 호출합니다.

```markdown
AskUserQuestion(
  questions: [{
    question: "티켓 파일 품질 점수가 낮습니다 (score: {quality_score:.2f}).\n\n개선이 필요한 항목:\n{feedback_lines}\n\n계속 진행하시겠습니까?",
    header: "Prompt 품질 확인",
    options: [
      { label: "계속 진행", description: "현재 티켓 파일로 planner를 호출합니다" },
      { label: "prompt 보강 후 재실행", description: "/wf -o로 티켓 파일을 보강한 뒤 커맨드를 다시 실행합니다" }
    ],
    multiSelect: false
  }]
)
```

> `{feedback_lines}`: `prompt_quality.feedback` 목록의 각 항목을 `\n- ` 형식으로 결합한 문자열
> `{quality_score:.2f}`: `prompt_quality.quality_score`를 소수 2자리로 표시

**선택 결과 처리:**

| 선택 | 동작 |
|------|------|
| **계속 진행** | Step 2a로 진행 |
| **prompt 보강 후 재실행** | 오케스트레이터 현재 turn 즉시 종료 (FSM 상태 전이 없음) |

> "prompt 보강 후 재실행" 선택 시: PLAN 이전 단계이므로 FSM 상태 전이를 수행하지 않습니다. 사용자가 `/wf -o`로 티켓 파일을 보강한 뒤 커맨드를 직접 재실행하도록 안내합니다.

---

## Step 2a: PLAN - planner Call

> **State Update** before PLAN Step start:
> ```bash
> flow-update both <registryKey> planner PLAN
> ```

**Detailed Guide:** workflow-agent-planner skill 참조

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

1. **plan_validator.py 자동 실행** — 계획서 구조 검증 (상세: [2a-Post-Validator](#2a-post-validator-plan_validatorpy-자동-실행) 참조)
2. `flow-step end <registryKey> planSubmit` — PLAN Step 완료 배너 + plan.md 링크 + [OK] 출력 (**1회만 호출**)
3. **즉시** Step 2c(스킬 매핑 검증 루프)로 진행

> **MUST NOT:**
> - `flow-step end`를 2회 이상 호출
> - Step 2c 진입 시 `flow-step end`를 "보장을 위해" 재호출

### 2a-Post-Validator: plan_validator.py 자동 실행

> planner가 `작성완료`를 반환한 후, `flow-step end` 호출 **전에** 오케스트레이터가 plan_validator.py를 실행한다.

**실행 명령:**
```bash
validator_output=$(flow-validate <workDir>/plan.md 2>&1) || validator_output=""
```

- `"검증 통과"` 출력 → 경고 없음
- 그 외 출력 → `[WARN]` 로그로 출력 (비차단, 흐름을 중단하지 않음)
- 실행 실패 시 → 빈 문자열로 폴백 (검증은 advisory이므로 blocking하지 않음)

## Step 2c: PLAN - Skill Mapping Validation Loop

> planner가 `작성완료`를 반환하고 2a-Post가 완료되면, 오케스트레이터는 skill_mapper.py의 스킬 매핑 유효성을 검증합니다.
> 검증 실패 시 planner를 revise 모드로 재호출하여 스킬 매핑을 수정합니다 (최대 3회).

### 2c-1. skill_mapper.py 실행 및 검증

**실행 명령:**
```bash
skill_mapper_output=$(flow-skill-map <workDir>/plan.md 2>&1)
skill_mapper_exit=$?
```

**Exit code 분기:**

| Exit Code | 의미 | 동작 |
|-----------|------|------|
| `0` | 성공 (스킬 매핑 유효) | WORK 단계로 즉시 진행 |
| `2` | 검증 실패 (스킬 매핑 무효) | 재시도 루프 진입 (2c-2) |
| `1` | 스크립트 오류 | `[WARN]` 로그 출력 후 WORK 단계로 강제 진행 (비차단) |

### 2c-2. 재시도 루프 (최대 3회)

검증 실패(exit code 2) 시 오케스트레이터는 다음 절차를 반복합니다:

**반복 조건:** `retry_count < 3` AND `skill_mapper_exit == 2`

**각 반복에서 수행하는 절차:**

1. `retry_count` 증가
2. `[WARN] skill_mapper 검증 실패 (시도 {retry_count}/3): {skill_mapper_output의 stderr}` 로그 출력
3. planner를 revise 모드로 재호출하여 스킬 매핑 수정 요청:

```
Task(subagent_type="planner", prompt="
command: <command>
workId: <workId>
request: <request>
workDir: <workDir>
mode: revise
feedback: 스킬 매핑 검증 실패. 사유: {skill_mapper_stderr}. 계획서의 스킬 매핑을 수정해주세요.
")
```

4. planner 반환 후 2a-Post(plan_validator + flow-step end) 재실행
5. skill_mapper.py 재실행하여 검증 결과 확인

**3회 초과 시:**

```
[WARN] skill_mapper 검증 3회 실패. 현재 스킬 매핑으로 강제 진행합니다.
```

경고 로그를 출력하고 WORK 단계로 강제 진행합니다.

### 2c-3. WORK 단계 진행

검증 통과 또는 강제 진행 후, 오케스트레이터는 사용자 입력 없이 즉시 WORK 단계로 진행합니다.

> **MUST NOT:**
> - 스킬 매핑 검증 후 AskUserQuestion 호출
> - 사용자 승인 대기
> - 검증 결과와 무관하게 WORK 진행을 차단

## Binding Contract Rule (REQUIRED)

> **PLAN 승인 후 계획 변경 불가 원칙**
>
> planner가 계획서를 작성 완료한 시점(스킬 검증 통과 포함)에서 계획서는 Binding Contract가 됩니다.
> 오케스트레이터는 확정된 계획서의 태스크를 변경, 추가, 제거하지 않습니다.
>
> **MUST NOT:**
> - 오케스트레이터가 독자적으로 태스크를 추가/삭제/변경
> - Worker 반환값을 근거로 계획을 임의 수정
> - "맥락 보강"을 이유로 계획에 없는 작업 수행

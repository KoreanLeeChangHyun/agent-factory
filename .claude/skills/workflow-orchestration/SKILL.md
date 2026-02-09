---
name: workflow-orchestration
description: "워크플로우 오케스트레이션 스킬. INIT -> PLAN -> WORK -> REPORT 워크플로우를 관리합니다. cc:implement, cc:refactor, cc:review, cc:build, cc:analyze, cc:architect, cc:framework, cc:research 등의 커맨드에서 호출됩니다."
disable-model-invocation: true
---

## 워크플로우 준수 의무

**모든 cc:* 명령어는 다음 워크플로우를 절대 생략 없이 순서대로 수행해야 합니다:**

```
INIT -> PLAN -> WORK -> REPORT
(필수)  (필수)  (필수)  (필수)
```

**준수 규칙:**
1. 모든 단계 **절대 생략 불가**, 반드시 **순서대로** 수행
2. PLAN에서 사용자 승인이 없으면 WORK 진행 금지
3. **위반 시:** 작업 중단 및 에러 보고

---

# Orchestrator

메인 에이전트가 워크플로우 순서 제어와 에이전트 호출만 담당합니다. 각 단계의 상세 가이드는 해당 스킬을 참조하세요.

## 워크플로우 구조

```
메인 에이전트 (오케스트레이터)
    |
    +-- 0. INIT: init 에이전트 호출
    |       +-- request, workDir, workId, date, title, workName, 근거 반환
    |
    +-- 서브에이전트 호출 (상세: 각 스킬 참조)
            +-- 1. PLAN   -> planner 에이전트 (workflow-plan 로드)
            +-- 2. WORK   -> worker 에이전트 (workflow-work 로드)
            +-- 3. REPORT -> reporter 에이전트 (workflow-report 로드)
```

**핵심 원칙:**
- 모든 단계는 서브에이전트를 통해 실행
- 서브에이전트는 다른 서브에이전트를 호출할 수 없음. 메인이 직접 체이닝.
- Git 커밋은 워크플로우 완료 후 `/git:commit`으로 별도 실행

## 지원 명령어

| 명령어 | 설명 |
|--------|------|
| implement | 기능 구현 |
| refactor | 코드 리팩토링 |
| review | 코드 리뷰 |
| build | 빌드 스크립트 생성 |
| analyze | 요구사항 분석 |
| architect | 아키텍처 설계 및 다이어그램 생성 |
| framework | 프레임워크 프로젝트 초기화 |
| research | 연구/조사 |

모든 명령어는 동일한 **INIT -> PLAN -> WORK -> REPORT** 워크플로우를 따릅니다.

## 입력 파라미터

- `command`: 실행 명령어 (implement, refactor, review 등)

> **주의**: cc:* 명령어는 `$ARGUMENTS`를 사용하지 않는다. 사용자 요청은 `.prompt/prompt.txt`를 통해 init 에이전트가 처리하므로, 오케스트레이터는 `$ARGUMENTS`의 유무로 입력을 판단하지 않는다.

---

## 터미널 출력 프로토콜

> **핵심 원칙: 사용자는 단계별 작업 결과만 보고 싶다. 내부 분석/사고 과정은 출력하지 않는다.**

### 단계 배너 호출

각 단계 시작/완료 시 배너 스크립트를 Bash로 호출하여 시각적 구분을 제공합니다:

```bash
# 단계 시작 배너
Workflow <registryKey> <phase>

# 단계 완료 배너 (상태 포함, path 자동 추론)
Workflow <registryKey> <phase> <status>
```

> **Bash description 파라미터**: 배너 호출 시 `description` 파라미터를 활용하면 Bash 괄호 안 표시가 간결해집니다.
> ```
> Bash(command="Workflow <registryKey> PLAN", description="PLAN 시작 배너")
> Bash(command="Workflow <registryKey> PLAN done", description="PLAN 완료 배너")
> ```

**`<registryKey>`**: `YYYYMMDD-HHMMSS` 형식의 워크플로우 식별자. 전체 workDir 경로(`.workflow/...`)도 하위 호환됨.
**`[path]`**: (선택) 해당 단계에서 생성된 문서 경로. 미전달 시 phase별 기본 경로 자동 추론 (PLAN→plan.md, WORK→work/, REPORT→report.md). 명시적 전달 시 자동 추론보다 우선 적용.

**호출 시점:**
- INIT 시작 전: `Workflow INIT none <command>` (레거시 방식, workDir 미확보 상태)
- PLAN 시작 전: `Workflow <registryKey> PLAN`
- PLAN 완료 후: `Workflow <registryKey> PLAN done` (path 자동 추론: plan.md) **-- AskUserQuestion 이전에 반드시 호출 완료 (병렬 호출 금지)**
- WORK 시작 전: `Workflow <registryKey> WORK`
- WORK 완료 후: `Workflow <registryKey> WORK done` (path 자동 추론: work/)
- REPORT 시작 전: `Workflow <registryKey> REPORT`
- REPORT 완료 후: `Workflow <registryKey> REPORT done` (path 자동 추론: report.md)
- DONE (최종 완료): `Workflow <registryKey> DONE done`

> **path 자동 추론**: 완료 배너에서 path 인자를 생략하면 phase별 기본 경로를 자동 표시합니다 (PLAN→plan.md, WORK→work/, REPORT→report.md). 커스텀 경로가 필요한 경우에만 명시적으로 전달하세요.
> **DONE 배너**: REPORT 완료 배너 후, status.json 완료 처리 및 레지스트리 해제가 끝난 뒤 호출합니다. 워크플로우의 최종 종료를 사용자에게 시각적으로 알리며, **Slack 완료 알림도 자동 전송**합니다. registryKey를 1번째 인자로 전달하면 registry.json에서 workDir을 해석하고 `<workDir>/.context.json`에서 메시지 구성에 필요한 정보를 읽어 Slack 알림을 비동기로 전송합니다.

### 출력 허용 목록

| 허용 항목 | 예시 |
|----------|------|
| 단계 배너 | `workflow-banner.sh` 출력 (INIT/PLAN/WORK/REPORT/DONE) |
| 단계별 보고서 링크 | 완료 배너의 `  -> <경로>` (phase별 자동 추론 또는 명시적 path) |
| 파일 경로 | `계획서: .workflow/20260208-133900/plan.md` |
| 승인 요청 | AskUserQuestion 호출 |
| 에러 메시지 | `에러: 파일을 찾을 수 없습니다` |
| 상태 반환값 | `상태: 성공` (규격 반환 형식) |

### 출력 금지 목록

| 금지 항목 | 예시 |
|----------|------|
| 분석 과정 | "파일을 분석해보겠습니다", "구조를 살펴보면..." |
| 판단 근거 | "이 방식이 더 적합한 이유는...", "비교해보면..." |
| 코드 리뷰 상세 | "이 함수는 ~하고 있으며...", "변경 사항을 보면..." |
| 비교 검토 | "A 방식 vs B 방식을 비교하면..." |
| 내부 사고 | "~를 살펴보겠습니다", "~를 확인해보겠습니다" |
| 작업 계획 설명 | "먼저 ~하고, 다음에 ~하겠습니다" |
| 중간 진행 보고 | "~를 완료했습니다. 다음으로..." |
| 워크플로우 완료 자유 텍스트 안내 | "워크플로우가 완료되었습니다. 보고서는 ...에서 확인할 수 있습니다." (DONE 배너는 허용) |
| 서브에이전트 반환값 해석/요약 | 서브에이전트(Task) 반환값을 터미널에 그대로 출력하거나 해석/요약하여 출력 금지 |
| 서브에이전트 호출 안내 | "~를 호출합니다", "~에이전트를 실행합니다", "~가 완료되었습니다" |
| DONE 배너 이후 텍스트 | DONE 배너 호출 후 어떠한 텍스트도 출력 금지. 즉시 종료 |

### 서브에이전트 출력 규칙

- **에이전트 (init, planner, worker, reporter)**: 규격 반환 형식만 출력. 분석/설명 텍스트 금지.
- **스킬 참조 시**: 스킬 내용을 터미널에 인용/설명하지 않음. 지시에 따라 행동만 수행.

### 서브에이전트 반환 후 오케스트레이터 침묵 규칙

> **핵심: 서브에이전트(Task) 반환 후 오케스트레이터가 수행할 동작은 화이트리스트에 명시된 것만 허용된다. 자유 텍스트 출력은 일체 금지.**

각 Step 완료 시점에서 오케스트레이터의 **허용 동작 화이트리스트**:

| Step 완료 | 허용 동작 | 금지 동작 |
|----------|----------|----------|
| Step 0 (INIT) 시작 전 | (1) INIT 시작 배너 호출 (`Workflow INIT none <command>`), (2) init 에이전트 호출 | 반환값 요약, 진행 안내, 분석 텍스트 |
| Step 0 (INIT) 완료 | (1) 반환값에서 파라미터 추출/보관, (2) PLAN 시작 배너 호출, (3) 상태 업데이트 스크립트 호출, (4) planner 에이전트 호출 | 반환값 요약, 진행 안내, 분석 텍스트 |
| Step 1a (PLAN) 완료 | (1) PLAN 완료 배너 호출 **(Bash 완료 대기 필수)**, (2) AskUserQuestion 호출 (Step 1b) -- **(1)과 (2)는 반드시 순차 실행. 병렬 호출 금지** | 계획 요약, 반환값 해석, 진행 안내, **(1)과 (2)의 병렬 호출** |
| Step 1b (승인) 완료 | (1) 승인 결과에 따른 분기 처리 (WORK 진행 / planner 재호출 / CANCELLED 처리), (2) WORK 시작 배너 호출, (3) 상태 업데이트 스크립트 호출 | 승인 결과 설명, 진행 안내 |
| Step 2 (WORK) 진행 중 | (1) 다음 worker 호출, (2) 병렬 worker 동시 호출, (3) 종속성 확인 후 순차 worker 호출 | planner 재호출, status.json 롤백, phase 변경, 자의적 맥락 보강 판단, 계획 수정 |
| Step 2 (WORK) 완료 | (1) WORK 완료 배너 호출, (2) 반환값에서 첫 3줄 추출, (3) REPORT 시작 배너 호출, (4) 상태 업데이트 스크립트 호출, (5) reporter 에이전트 호출 | 작업 결과 요약, 변경 파일 나열, 진행 안내 |
| Step 3 (REPORT) 완료 | (1) REPORT 완료 배너 호출, (2) DONE 배너 호출, (3) **즉시 종료** | 보고서 요약, 완료 안내, DONE 배너 이후 어떤 텍스트든 출력 |

---

## Step 0: INIT (init 에이전트)

> **무조건 호출**: cc:* 명령어 수신 시 사용자 입력 유무와 관계없이 반드시 init을 호출한다. 입력이 없는 경우의 처리(시나리오 분기)는 init 에이전트가 자체 수행한다.

**INIT 시작 배너 호출 (init 에이전트 호출 직전):**
```bash
Workflow INIT none <command>
```

```
Task(subagent_type="init", prompt="
command: <command>
")
```

**반환값:** `request`, `workDir`, `workId`, `date`, `title`, `workName`, `근거`

> init이 전처리(prompt.txt 읽기, 작업 디렉토리 생성, user_prompt.txt 복사, prompt.txt 클리어)를 수행합니다.
> **status.json**: init이 `<workDir>/status.json` 생성 완료 (phase: "INIT"). 좀비 정리도 이 단계에서 수행.
> **workDir 형식**: `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>` (중첩 구조)

**반환값 보관 규칙 (필수):**
init 반환값(request, workDir, workId, date, title, workName, 근거)을 모두 보관하고, 후속 단계에 필요한 파라미터를 전달한다:
- `request`: user_prompt.txt의 첫 50자. PLAN(Step 1)에 전달
- `workDir`: PLAN(Step 1), REPORT(Step 3)에 전달
- `workId`: PLAN(Step 1), WORK(Step 2), REPORT(Step 3)에 전달
- `date`, `title`, `workName`: REPORT(Step 3)에서 경로 구성 시 사용
- `근거`: 로깅용으로만 사용

---

## 서브에이전트 호출

각 단계는 서브에이전트를 호출하여 수행합니다. 각 단계의 상세 가이드는 해당 스킬을 참조하세요.

### Step 1a: PLAN - planner 호출

> **상태 업데이트**: PLAN 시작 전:
> ```bash
> wf-state both <registryKey> planner INIT PLAN
> ```

**상세 가이드:** workflow-plan 스킬 참조

```
Task(subagent_type="planner", prompt="
command: <command>
workId: <workId>
request: <request>
workDir: <workDir>
")
```

- planner가 요구사항 완전 명확화 + 계획서 저장 후 `작성완료` 반환
- **출력:** 계획서 경로

### Step 1b: PLAN - 오케스트레이터 사용자 승인

> planner가 `작성완료`를 반환하면, **오케스트레이터(메인 에이전트)가 직접** AskUserQuestion으로 사용자 최종 승인을 수행합니다.
> 서브에이전트(planner)는 AskUserQuestion을 호출할 수 없으므로(플랫폼 제약), 승인 절차는 반드시 오케스트레이터가 담당합니다.

#### 1b-1. .context.json 확인/업데이트

> **.context.json은 INIT 단계에서 이미 저장되어 있습니다.** PLAN 단계에서는 내용 변경이 필요한 경우(제목 변경, 작업 이름 수정 등)에만 업데이트합니다. 변경이 없으면 이 단계를 건너뜁니다.

**업데이트가 필요한 경우:**
- agent 필드가 "planner"로 설정되어 있지 않은 경우

> **참고:** `update-workflow-state.sh context` 모드는 `agent` 필드만 갱신할 수 있습니다. title, workName 등 다른 필드를 변경해야 하는 경우, planner가 `.context.json`에 직접 쓰기를 수행하세요.

**로컬 .context.json 스키마 참조:**

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

> - `workId`는 HHMMSS 6자리 형식입니다 (예: "170327"). `<YYYYMMDD>-<workId>` 형식은 레지스트리 키에서 사용됩니다.
> - `workName`은 INIT 단계에서 title 인자를 기반으로 .context.json에 저장됩니다.

**업데이트 방법 (agent 필드 갱신, 1 Tool Call):**
```bash
Bash("wf-state context <registryKey> <agent>")
```

> **주의:**
> - `update-workflow-state.sh context` 모드의 3번째 인자는 에이전트 이름 문자열입니다 (예: "planner", "worker", "reporter"). JSON 문자열을 인자로 받지 않습니다.
> - 이 모드는 로컬 `<workDir>/.context.json`의 `agent` 필드만 업데이트합니다. 전역 `.workflow/registry.json`은 활성 워크플로우 레지스트리로 사용되며, `register`/`unregister` 모드로만 접근합니다. 직접 쓰기는 금지됩니다.

#### 1b-2. Slack 알림 (자동)

AskUserQuestion 호출 시 `PreToolUse` Hook이 자동으로 Slack 알림을 전송합니다.

- Hook 스크립트: `.claude/hooks/event/pre-tool-use/slack-ask.sh`
- Hook이 활성 워크플로우 레지스트리(`.workflow/registry.json`)에서 해당 워크플로우의 로컬 .context.json을 읽어 통일 포맷으로 Slack 전송
- 레지스트리 또는 로컬 .context.json이 없으면 폴백 포맷 사용

**Slack 알림 포맷 (slack-ask.sh):**
```
<작업 제목>
- 작업ID: <YYYYMMDD>-<workId>
- 작업이름: <작업 이름>
- 명령어: <명령어>
- 상태: 사용자 입력 대기 중
```

#### 1b-3. AskUserQuestion으로 사용자 승인

> **순차 실행 강제 (Critical):**
> PLAN 완료 배너(`Workflow <registryKey> PLAN done`)의 Bash 호출이 **완료된 후에만** AskUserQuestion을 호출해야 합니다.
> - PLAN 완료 배너와 AskUserQuestion을 **동일 응답에서 병렬로 호출하는 것은 절대 금지**합니다.
> - 반드시 **(1) PLAN 완료 배너 Bash 호출 → 응답 수신 확인 → (2) AskUserQuestion 호출** 순서로 2회의 별도 도구 호출 턴에서 실행합니다.
> - 이를 위반하면 사용자가 계획서 링크를 확인하지 못한 채 승인을 요청받는 UX 결함이 발생합니다.

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

> **AskUserQuestion 옵션 엄격 고정 (필수):**
> - 위 3개 옵션(승인/수정/중지)만 허용. 옵션 추가/변경/제거 절대 금지.
> - `freeformLabel`, `freeformPlaceholder` 등 자유 입력 필드 사용 금지.
> - `"Type something"`, `"입력"` 등 자유 텍스트 입력 옵션 추가 금지.
> - `multiSelect: false` 반드시 유지.
> - 옵션의 label, description 텍스트를 임의로 변경하지 않음.

#### 1b-4. 승인 결과 처리

| 선택 | 처리 |
|------|------|
| **승인** | WORK 단계로 진행 (status.json phase 업데이트는 오케스트레이터가 WORK 전이 시 수행) |
| **수정 (prompt.txt)** | 사용자가 prompt.txt에 피드백을 작성한 후 선택. planner를 재호출하여 피드백 반영 후 계획 재수립, 다시 Step 1b 수행 |
| **중지** | status.json phase="CANCELLED" 업데이트 후 워크플로우 중단 |

> **"수정 (prompt.txt)" 선택 시 오케스트레이터 동작:**
> 사용자가 `.prompt/prompt.txt`에 피드백을 작성한 후 "수정 (prompt.txt)"을 선택합니다. 오케스트레이터는 다음 절차를 순서대로 수행합니다:
>
> 1. **prompt.txt 읽기**: `.prompt/prompt.txt`의 내용을 읽어 피드백 내용을 확보
> 2. **prompt.txt 클리어 (필수)**: 읽기 직후 반드시 prompt.txt를 클리어하여 다음 작업에 대비
>    ```bash
>    > .prompt/prompt.txt
>    ```
>    클리어 실패 시 재시도:
>    ```bash
>    : > .prompt/prompt.txt
>    ```
> 3. **planner 재호출**: 확보한 피드백 내용을 prompt에 `mode: revise` 및 피드백 내용으로 추가하여 계획 재수립
> 4. **Step 1b 반복**: 재수립된 계획에 대해 다시 사용자 승인 요청
>
> **주의:** prompt.txt 클리어를 생략하면 이전 피드백 내용이 잔존하여 후속 작업에서 중복/오염이 발생합니다. INIT 단계의 init-workflow.sh Step 4와 동일한 패턴을 따릅니다.

#### 중지 시 status.json CANCELLED 처리

사용자가 "중지"를 선택하면 오케스트레이터가 `update-workflow-state.sh`를 호출하여 CANCELLED 상태를 기록합니다.

**업데이트 방법 (1 Tool Call):**
```bash
Bash("wf-state status <registryKey> PLAN CANCELLED")
```

**예시:**
```bash
Bash("wf-state status 20260205-213000 PLAN CANCELLED")
```

**스크립트 동작:**
- `<workDir>/status.json`의 `phase`를 `"CANCELLED"`로 변경
- `transitions` 배열에 `{"from": "PLAN", "to": "CANCELLED", "at": "<현재시간ISO>"}` 추가
- `updated_at`을 현재 시간(ISO 8601, KST)으로 갱신

**결과 예시:**
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

**실패 시 대응:** 스크립트 실패 시 `[WARN]` 경고만 출력하고 exit 0으로 종료합니다. 워크플로우를 정상 진행(중단)합니다. status.json은 보조 상태 관리이므로 실패가 워크플로우를 차단하지 않습니다.

### Binding Contract 규칙 (필수)

> **PLAN 승인 후 계획 변경 불가 원칙**
>
> 사용자가 "승인"을 선택한 시점에서 계획서는 Binding Contract가 됩니다.
> 오케스트레이터는 승인된 계획서의 태스크를 변경, 추가, 제거하지 않습니다.
> 계획 변경이 필요하면 사용자가 "수정 (prompt.txt)" 선택지를 통해 재계획을 요청해야 합니다.
>
> **금지 사항:**
> - 오케스트레이터가 독자적으로 태스크를 추가/삭제/변경
> - Worker 반환값을 근거로 계획을 임의 수정
> - "맥락 보강"을 이유로 계획에 없는 작업 수행

### Step 2: WORK (worker 에이전트)

> **상태 업데이트**: WORK 시작 전:
> ```bash
> wf-state both <registryKey> worker PLAN WORK
> ```

> **WORK phase 규칙 (필수 준수)**
>
> | 구분 | 규칙 |
> |------|------|
> | **허용 호출** | worker, reporter 에이전트만 호출 가능 |
> | **재호출 금지** | planner, init 에이전트 재호출 절대 금지 |
> | **역방향 전이 금지** | WORK→PLAN, WORK→INIT 등 역방향 phase 변경 금지 |
> | **자의적 판단 금지** | 오케스트레이터가 독자적으로 맥락 보강, 계획 수정, 태스크 추가/삭제/변경을 판단하지 않음 |
> | **계획서 태스크만 실행** | 계획서에 명시된 태스크만 순서대로 실행. 계획서에 없는 작업은 수행하지 않음 |
>
> 위반 시 워크플로우 무결성이 훼손됩니다. WORK phase에서 문제가 발생하면 worker 반환값의 "실패" 상태로 처리하고, 오케스트레이터가 임의로 PLAN으로 회귀하지 않습니다.

**상세 가이드:** workflow-work 스킬 참조

> **Worker 내부 처리 절차 (4단계):** 각 worker는 호출 후 내부적으로 `계획서 확인 → 스킬 로드 → 작업 진행 → 실행 내역 작성`의 4단계를 수행합니다. 상세는 workflow-work 스킬 및 worker.md 참조.

#### Phase 0: 준비 단계 (필수, 순차 1개 worker)

Phase 1~N 실행 전에 반드시 Phase 0을 먼저 수행합니다. Phase 0은 1개 worker가 순차로 실행합니다.

```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: phase0, planPath: <planPath>, workDir: <workDir>, mode: phase0")
```

Phase 0 기능: (1) `<workDir>/work/` 디렉터리 생성, (2) 계획서 태스크와 스킬을 매핑하여 `<workDir>/work/skill-map.md` 생성.

Phase 0 완료 후 skill-map.md를 참고하여 후속 worker 호출 시 skills 파라미터를 전달합니다.

#### Phase 1~N: 작업 실행

계획서의 Phase 순서대로 실행합니다:

**독립 작업 (병렬):**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, planPath: <planPath>, workDir: <workDir>, skills: <스킬명>")
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W02, planPath: <planPath>, workDir: <workDir>")
```

**종속 작업 (순차):**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W04, planPath: <planPath>, workDir: <workDir>")
```

> **skills 파라미터**: Phase 0에서 생성된 skill-map.md의 추천 스킬 또는 계획서에 명시된 스킬을 전달. 미명시 태스크는 worker가 자동 결정.

#### Explore 서브에이전트 활용

계획서에서 `서브에이전트: Explore`로 지정된 태스크는 Explore(Haiku) 서브에이전트를 사용합니다.

**Explore 호출 패턴:**
```
Task(subagent_type="explore", prompt="
다음 파일들을 분석하고 각 파일의 주요 기능과 구조를 요약하세요:
- <파일 경로 목록>

출력 형식: 파일별 1-3줄 요약
")
```

**Explore 사용 규칙:**
- **읽기 전용 태스크만**: 파일 수정이 필요 없는 대량 분석 태스크에만 사용
- **병렬 호출 가능**: 여러 Explore 에이전트를 동시에 호출하여 파일 분배
- **Worker와 조합**: Explore(읽기) 결과를 수집한 후 Worker(쓰기)에 전달하는 파이프라인 구성 가능
- **계획서 준수**: 계획서에 `서브에이전트: Explore`로 명시된 태스크만 Explore로 호출. 명시되지 않은 태스크는 Worker 사용

#### Worker 반환값 처리 (필수)

> **경고: Worker 반환값이 3줄을 초과하면 메인 컨텍스트가 폭증하여 시스템 장애가 발생합니다.**

Task(worker) 호출 후 반환값 처리 규칙:
1. 반환값에서 **첫 3줄만** 추출하여 컨텍스트에 보관 (4줄째부터는 반드시 폐기)
2. 나머지는 무시 (상세 내용은 .workflow/ 파일에 이미 저장됨)
3. 3줄 형식이 아닌 반환값이라도 첫 3줄만 사용, 초과분은 절대 보관 금지

**정상 반환값 (3줄):**
```
상태: 성공 | 부분성공 | 실패
작업 내역: <파일 경로>
변경 파일: N개
```

- **출력:** 작업 내역 경로

### Step 3: REPORT (reporter 에이전트)

> **상태 업데이트**: REPORT 시작 전:
> ```bash
> wf-state both <registryKey> reporter WORK REPORT
> ```

**상세 가이드:** workflow-report 스킬 참조

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
- **출력:** 보고서 경로, CLAUDE.md 갱신 완료

> **REPORT 완료 후 DONE 배너**: REPORT 완료 배너 호출 후, 오케스트레이터는 자유 텍스트 완료 메시지를 출력하지 않는다. 대신 DONE 배너를 호출하여 워크플로우 최종 종료를 사용자에게 알린다. DONE 배너 호출 후 즉시 종료한다.
>
> **DONE 배너 호출 순서**: REPORT 완료 배너 → (reporter가 status.json 완료 처리 + 레지스트리 해제 수행) → DONE 배너 호출 → 종료
> ```bash
> Workflow <registryKey> DONE done
> ```
>
> **참고**: `status.json 완료 처리`(REPORT→COMPLETED)와 `레지스트리 해제`(unregister)는 reporter 에이전트가 전담 수행한다. 오케스트레이터는 이를 중복 호출하지 않는다.

---

## 서브에이전트 반환 형식 (필수)

> **경고: 반환값이 규격 줄 수를 초과하면 메인 에이전트 컨텍스트가 폭증하여 시스템 장애가 발생합니다.**
>
> 1. 모든 작업 결과는 `.workflow/` 파일에 기록 완료 후 반환
> 2. 반환값은 오직 상태 + 파일 경로만 포함
> 3. 코드, 목록, 테이블, 요약, 마크다운 헤더는 반환에 절대 포함 금지
> 4. 규격 외 내용 1줄이라도 추가 시 시스템 장애 발생

### 공통 규칙

| 규칙 | 설명 |
|------|------|
| 작업 상세는 .workflow에 저장 | 서브에이전트는 모든 작업 상세를 파일로 기록 |
| 메인에 최소 반환 | 아래 에이전트별 형식만 반환 (추가 정보 금지) |
| 대량 내역 절대 금지 | 코드 변경 내용, 상세 로그, 파일 목록 테이블 등 반환 금지 |

### init 반환 형식 (7줄)

```
request: <user_prompt.txt의 첫 50자>
workDir: .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>
workId: <workId>
date: <YYYYMMDD>
title: <제목>
workName: <작업이름>
근거: [1줄 요약]
```

**금지**: 요청 전문, 다음 단계 안내, 상세 설명, 마크다운 헤더, 판단 근거 상세, 변경 파일 목록, 예상 작업 시간 등 추가 정보

### planner 반환 형식 (3줄)

```
상태: 작성완료
계획서: <계획서 파일 경로>
태스크 수: N개
```

**금지**: 계획 요약, 태스크 목록, 다음 단계 안내 등

### worker 반환 형식 (3줄)

```
상태: 성공 | 부분성공 | 실패
작업 내역: <작업 내역 파일 경로>
변경 파일: N개
```

**금지**: 변경 파일 목록 테이블, 코드 스니펫, 작업 요약, 다음 단계 안내 등

### reporter 반환 형식 (3줄)

```
상태: 완료 | 실패
보고서: <보고서 파일 경로>
CLAUDE.md: 갱신완료 | 스킵 | 실패
```

**금지**: 요약, 태스크 수, 변경 파일 수, 다음 단계 등 추가 정보 일체

---

## 호출 방식 규칙

| 대상 유형 | 호출 방식 | 예시 |
|----------|----------|------|
| 에이전트 (4개) | Task | `Task(subagent_type="init", prompt="...")` |
| 스킬 (5개) | Skill | `Skill(skill="workflow-report")` |

**에이전트:** init, planner, worker, reporter
**스킬:** workflow-orchestration, workflow-init, workflow-plan, workflow-work, workflow-report

> 에이전트별 색상 정보는 각 에이전트 정의 파일(`.claude/agents/*.md`)의 frontmatter 참조.

### 상태 업데이트 방법

단계 전환 시 `both` 모드로 로컬 .context.json(agent)과 status.json(phase)을 동시 업데이트합니다. 각 단계별 `both` 호출은 서브에이전트 호출 섹션에 기재되어 있습니다.

```bash
# 로컬 .context.json의 agent 필드만 업데이트
wf-state context <registryKey> <agent>
# 로컬 status.json의 phase 변경
wf-state status <registryKey> <fromPhase> <toPhase>
# 로컬 context + status 동시 업데이트 (권장)
wf-state both <registryKey> <agent> <fromPhase> <toPhase>
# 전역 레지스트리에 워크플로우 등록 (INIT 완료 시)
wf-state register <registryKey>
# 전역 레지스트리에서 워크플로우 해제 (REPORT 완료 시)
wf-state unregister <registryKey>
# status.json의 linked_sessions 배열에 세션 ID 추가 (worker/reporter가 자체 호출)
wf-state link-session <registryKey> <sessionId>
```

> **주의**: `context` 모드와 `both` 모드는 로컬 `<workDir>/.context.json`의 `agent` 필드만 업데이트합니다. 전역 `.workflow/registry.json`은 레지스트리 전용이며, `register`/`unregister` 모드로만 접근합니다.
> **registryKey 형식**: `YYYYMMDD-HHMMSS` 형식의 워크플로우 식별자. 스크립트 내부에서 registry.json을 조회하여 전체 workDir 경로를 자동 해석합니다. 전체 workDir 경로(`.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>`)도 하위 호환됩니다.

agent 값: INIT=`init`, PLAN=`planner`, WORK=`worker`, REPORT=`reporter`. 실패 시 경고만 출력, 워크플로우 정상 진행.

---

## 상태 관리 (status.json)

각 워크플로우 작업은 `status.json`으로 현재 단계와 전이 이력을 추적합니다.

> status.json 스키마(9개 필드)와 저장 위치는 workflow-init 스킬 참조. 저장 경로: `<workDir>/status.json` (workDir = `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>`)

### status.json `linked_sessions` 필드

`linked_sessions`는 워크플로우에 참여한 세션 ID의 배열입니다. init이 초기 세션 ID로 배열을 생성하고, 이후 worker/reporter가 자신의 세션 ID를 `link-session` 모드로 추가합니다. 세션 재시작 시에도 새 세션 ID가 자동 병합됩니다.

- 용도: 워크플로우에 참여한 세션 ID 추적 (디버깅/감사 목적)
- 갱신: `wf-state link-session <registryKey> <sessionId>` (중복 자동 방지, 비차단)
- 오케스트레이터는 link-session을 직접 호출하지 않음 (worker/reporter가 자체 등록)

### FSM 전이 규칙

`INIT -> PLAN -> WORK -> REPORT -> COMPLETED` (정상 흐름). 분기: PLAN->CANCELLED, WORK/REPORT->FAILED, TTL만료->STALE. 불법 전이 시 시스템 가드가 차단. update-workflow-state.sh는 전이 미수행(no-op), PreToolUse Hook은 도구 호출 deny. 비상 시 WORKFLOW_SKIP_GUARD=1로 우회 가능.

> 업데이트 방법은 "상태 업데이트 방법" 섹션 참조. 비차단 원칙: 실패 시 경고만 출력, 워크플로우 정상 진행.

---

## 에러 처리

| 상황 | 처리 방식 |
|------|----------|
| INIT 에러 | 최대 3회 재시도 (경고 로그 출력) |
| 단계 에러 (PLAN/WORK/REPORT) | 최대 3회 재시도 후 에러 보고 |
| 독립 태스크 실패 | 다른 독립 태스크는 계속 진행 |
| 종속 태스크 블로커 실패 | 해당 종속 체인 중단, 다른 체인 계속 |
| 전체 실패율 50% 초과 | 워크플로우 중단 및 AskUserQuestion으로 사용자 확인 |

## 주의사항

1. **INIT 우선**: 반드시 INIT 먼저 수행하여 request, workDir 확보
2. **입력 검증 금지 및 무조건 INIT 호출**: cc:* 명령어 수신 시, 오케스트레이터는 사용자 입력의 유무를 판단하지 않는다. `$ARGUMENTS`가 비어 있어도, prompt.txt의 존재/내용을 확인하지 않고, **어떤 경우에도 즉시 init 에이전트를 호출한다**. 사용자 요청은 `.prompt/prompt.txt`에 저장되어 있으며, 이를 읽고 처리하는 것은 init 에이전트의 전담 책임이다. 입력이 없는 경우의 시나리오 분기(이전 워크플로우 기반 후속 제안 또는 중지)도 init이 자체 처리한다.
3. **순서 준수**: INIT -> PLAN -> WORK -> REPORT 엄수
3. **PLAN 완전 명확화**: WORK에서는 질문 불가, PLAN에서 100% 명확화
4. **PLAN 최종 컨펌**: planner `작성완료` 반환 후 오케스트레이터가 AskUserQuestion으로 직접 사용자 승인을 수행. 승인 후에만 WORK 진행
5. **병렬/순차**: 독립 작업만 병렬, 종속 작업은 순차
6. **문서화 필수**: 모든 단계에서 문서 저장
7. **REPORT에서 CLAUDE.md 갱신 필수**
8. **Slack 실패해도 워크플로우는 정상 완료 처리**
9. **Git 분리**: 커밋은 `/git:commit`으로 별도 실행

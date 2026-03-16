# INIT (Orchestrator-driven)

> **INIT은 서브에이전트 없이 오케스트레이터가 직접 수행합니다.**
> 오케스트레이터가 command를 파싱하고, initialization.py를 호출하여 워크플로우 디렉터리 생성 + 메타데이터 기록을 완료합니다.
> LLM 별도 호출 없음 (순수 IO).

---

## INIT 실행 흐름

`/wf` 슬래시 커맨드 실행 시 오케스트레이터가 아래 5단계를 순차 실행합니다.

### Step 1: Command 및 플래그 파싱

사용자 입력에서 command와 플래그를 파싱합니다.

```
/wf -s implement           → command=implement, autoApprove=true
/wf -s implement -n        → command=implement, autoApprove=false
/wf -s review              → command=review, autoApprove=true
/wf -s research            → command=research, autoApprove=true
/wf -s research>implement  → command=research>implement, autoApprove=true
```

> **체인 command**: `wf-submit.md`의 체인 파싱 후 전달받은 전체 문자열(예: `research>implement`)을 그대로 `command` 변수에 보관합니다. initialization.py에는 이 전체 문자열을 그대로 전달합니다.

**`-n` 플래그 파싱:**

- `$ARGUMENTS`에 `-n` 문자열이 포함되어 있으면 `autoApprove=false`
- 포함되어 있지 않으면 `autoApprove=true` (기본값)
- (하위 호환) `-y` 플래그가 포함된 경우: 무시하고 기본값 `autoApprove=true` 적용. 단, deprecated 경고를 터미널에 출력: `[WARN] -y 플래그는 더 이상 사용되지 않습니다. autoApprove가 기본값(true)으로 변경되었습니다. 강제 승인 요청이 필요하면 -n을 사용하세요.`

### Step 2: 시작 배너 출력

```bash
flow-claude start <command>
```

### Step 3: 제목 생성

티켓 파일(`.kanban/T-NNN.xml`)을 읽어 20자 이내 한글 제목을 생성합니다.

- 오케스트레이터가 직접 생성 (LLM 별도 호출 없음)
- 티켓 파일 내용을 기반으로 작업 의도를 요약

### Step 4: initialization.py 실행

```bash
python3 .claude/scripts/flow/initialization.py <command> "<title>" #N
```

`#N`은 `/wf -s N`에서 파싱한 티켓 번호입니다 (예: `#5`). 티켓 번호를 반드시 전달하여 정확한 티켓을 초기화합니다.

> **체인 command 전달 규칙**: `<command>` 인자에 체인 command인 경우 **전체 문자열**(예: `research>implement`)을 그대로 전달해야 합니다. 첫 번째 세그먼트만 전달하면 안 됩니다. initialization.py가 `>` 구분자를 감지하여 첫 세그먼트를 실제 실행 command(`effective_command`)로 사용하고, 전체 문자열을 `.context.json`의 `command` 필드에 기록합니다. 이 전체 문자열이 없으면 finalization.py가 체인 후속 스테이지를 발사할 수 없습니다.

**스크립트 수행 내역:**

| 순서 | 작업 | 생성 파일 |
|------|------|----------|
| 1 | 티켓 파일(`.kanban/T-NNN.xml`) 읽기 (XML 전체 내용을 문자열로 읽기. 내부 구조: `<metadata>` / `<submit>` / `<history>` 3래퍼 요소. `<metadata>` 내부에 number/title/datetime/status/current 포함. `<subnumber>` 내부에 `<prompt>` 래퍼가 있으며, `<result>` 내부에 workdir/plan/work/report 하위 요소 포함) | - |
| 2 | 워크플로우 디렉터리 생성 | `<workDir>/` |
| 3 | 사용자 원문 요청 보존 (티켓 파일 전체 XML을 그대로 복사) | `<workDir>/user_prompt.txt` |
| 4 | 티켓 XML의 `<metadata>/<status>`를 In Progress로 갱신 (`<metadata>` 래퍼의 `<status>` 필드만 사용) | - |
| 5 | 작업 메타데이터 생성 | `<workDir>/.context.json` |
| 6 | FSM 상태 초기화 | `<workDir>/status.json` (step: NONE) |
| 7 | 좀비 워크플로우 정리 | - |
| 8 | KEEP_COUNT 초과 시 아카이빙 | - |

**stdout:** 배너만 출력 (파싱 불필요). 실패 시 `FAIL` + 비정상 종료 코드.

**종료 코드:**

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 티켓 파일 비어있음 |
| 2 | 인자 오류 |
| 4 | 워크플로우 초기화 실패 |

### Step 5: init-result.json에서 workDir 파싱

종료 코드 0이면 `<workDir>/init-result.json`을 Read하여 값을 도출합니다.

단, workDir 경로 자체는 init-result.json 안에 있으므로, 최신 `.workflow/` 디렉터리를 찾아 읽습니다:

```bash
ls -td .workflow/*/  | head -1
```

해당 디렉터리 하위에서 `init-result.json`을 Read합니다.

| 값 | init-result.json 키 |
|---|---|
| `workDir` | `workDir` |
| `registryKey` | `registryKey` |
| `workId` | `workId` |
| `date` | `date` |
| `workName` | `workName` |
| `command` | `command` |
| `title` | `title` |
| `ticketNumber` | `ticketNumber` |

---

## Return Value Retention (REQUIRED)

init-result.json에서 읽은 workDir 경로와 도출 값을 보관하고, 후속 단계에 전달합니다.

| Parameter | Used In | Purpose |
|-----------|---------|---------|
| `workDir` | PLAN, WORK, REPORT, DONE | 작업 디렉터리 경로 |
| `registryKey` | PLAN, WORK, REPORT, DONE | 배너 호출 및 update_state.py 호출의 식별자 |
| `workId` | PLAN, WORK, REPORT, DONE | 작업 식별자 (HHMMSS 6자리) |
| `title` | DONE | 작업 제목 (Step 3에서 보유) |
| `command` | PLAN, WORK, REPORT, DONE | 실행 명령어 (Step 1에서 보유) |
| `autoApprove` | PLAN | -n 플래그 미지정 시 true (기본), -n 지정 시 false |
| `ticketNumber` | DONE | flow-finish --ticket-number 인자로 전달 |

---

## Post-INIT Flow

INIT 완료 후, 오케스트레이터는 즉시 PLAN Step으로 진행합니다.

```
INIT 완료 → PLAN Step 진행
```

> **MUST NOT:**
> - INIT 결과를 사용자에게 요약/출력
> - AskUserQuestion으로 확인 요청
> - echo로 OK/workDir를 stdout에 출력 (initialization.py가 배너를 직접 출력함)
> - 티켓 파일을 직접 다시 읽기 (initialization.py가 이미 처리 완료)

---

## Error Handling

| 상황 | 종료 코드 | 처리 |
|------|----------|------|
| 티켓 파일 비어있음 | 1 | 사용자에게 `.kanban/T-NNN.xml` 티켓 작성을 안내하고 워크플로우 종료 |
| 인자 오류 (잘못된 command) | 2 | 에러 메시지 출력 후 워크플로우 종료 |
| 워크플로우 초기화 실패 | 4 | 에러 메시지 출력 후 워크플로우 종료 |
| Bash stdout 파싱 실패 | - | AskUserQuestion으로 사용자에게 상황 보고, 재시도 또는 중단 선택 요청 |

> **비재시도 설계:** initialization.py는 순수 IO 스크립트(LLM 호출 없음)이므로 동일 입력에 대해 항상 동일 결과를 반환합니다. 실패 시 재시도보다 원인 파악이 우선입니다.

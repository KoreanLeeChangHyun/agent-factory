# INIT (Orchestrator-driven)

> **INIT은 서브에이전트 없이 오케스트레이터가 직접 수행합니다.**
> 오케스트레이터가 command를 파싱하고, initialization.py를 호출하여 워크플로우 디렉터리 생성 + 메타데이터 기록을 완료합니다.
> LLM 별도 호출 없음 (순수 IO).

---

## INIT 실행 흐름

cc:* 슬래시 커맨드 실행 시 오케스트레이터가 아래 5단계를 순차 실행합니다.

### Step 1: Command 및 플래그 파싱

사용자 입력에서 command와 플래그를 파싱합니다.

```
/cc:implement      → command=implement, autoApprove=false
/cc:implement -y   → command=implement, autoApprove=true
/cc:review         → command=review, autoApprove=false
/cc:research       → command=research, autoApprove=false
```

**`-y` 플래그 파싱:**

- `$ARGUMENTS`에 `-y` 문자열이 포함되어 있으면 `autoApprove=true`
- 포함되어 있지 않으면 `autoApprove=false`
- `cc:prompt`의 `-p/-q` 파싱과 동일한 패턴

### Step 2: 시작 배너 출력

```bash
flow-claude start <command>
```

### Step 3: 제목 생성

prompt.txt를 읽어 20자 이내 한글 제목을 생성합니다.

- 오케스트레이터가 직접 생성 (LLM 별도 호출 없음)
- prompt.txt 내용을 기반으로 작업 의도를 요약

### Step 4: initialization.py 실행

```bash
python3 .claude/scripts/flow/initialization.py <command> "<title>"
```

**스크립트 수행 내역:**

| 순서 | 작업 | 생성 파일 |
|------|------|----------|
| 1 | prompt.txt 읽기 | - |
| 2 | 워크플로우 디렉터리 생성 | `<workDir>/` |
| 3 | 사용자 원문 요청 보존 | `<workDir>/user_prompt.txt` |
| 4 | .uploads/ → files/ 복사 + 클리어 | `<workDir>/files/` (첨부 있을 경우) |
| 5 | prompt.txt 클리어 | - |
| 6 | 작업 메타데이터 생성 | `<workDir>/.context.json` |
| 7 | FSM 상태 초기화 | `<workDir>/status.json` (step: NONE) |
| 8 | 좀비 워크플로우 정리 | - |
| 9 | KEEP_COUNT 초과 시 아카이빙 | - |

**stdout:** 배너만 출력 (파싱 불필요). 실패 시 `FAIL` + 비정상 종료 코드.

**종료 코드:**

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | prompt.txt 비어있음 |
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
| `autoApprove` | PLAN | -y 플래그에 의한 자동승인 모드 (true/false) |

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
> - prompt.txt를 직접 다시 읽기 (initialization.py가 이미 처리 완료)

---

## Error Handling

| 상황 | 종료 코드 | 처리 |
|------|----------|------|
| prompt.txt 비어있음 | 1 | 사용자에게 prompt.txt 작성을 안내하고 워크플로우 종료 |
| 인자 오류 (잘못된 command) | 2 | 에러 메시지 출력 후 워크플로우 종료 |
| 워크플로우 초기화 실패 | 4 | 에러 메시지 출력 후 워크플로우 종료 |
| Bash stdout 파싱 실패 | - | AskUserQuestion으로 사용자에게 상황 보고, 재시도 또는 중단 선택 요청 |

> **비재시도 설계:** initialization.py는 순수 IO 스크립트(LLM 호출 없음)이므로 동일 입력에 대해 항상 동일 결과를 반환합니다. 실패 시 재시도보다 원인 파악이 우선입니다.

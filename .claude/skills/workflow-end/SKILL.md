---
name: workflow-end
description: "Internal skill for workflow END stage. Performs workflow finalization after reporter completion. Use for workflow finalization: history.md update (using summary.txt), status.json completion, usage finalization, registry release, workflow archiving (keeping latest 10) in a 5-step procedure. Internally invoked by orchestrator; not intended for direct user invocation."
disable-model-invocation: true
license: "Apache-2.0"
---

# Done

reporter 완료 후 워크플로우의 마무리 처리를 수행하는 스킬.

> 이 스킬은 workflow-orchestration 스킬이 관리하는 워크플로우의 한 단계입니다. 전체 워크플로우 구조는 workflow-orchestration 스킬을 참조하세요.

**workflow-end 스킬의 책임:**
- history.md 최종 확인 갱신 (phase 전이 시 자동 갱신 안전망)
- status.json 완료 처리 (REPORT -> COMPLETED / FAILED)
- 사용량 확정 (usage-finalize)
- 레지스트리 해제 (unregister)
- 워크플로우 아카이빙 (최신 10개 유지, 나머지 .history 이동)
- .kanbanboard 갱신 (strategy 프로젝트 연동, 선택적)

> **책임 경계**: 보고서 작성과 summary.txt 생성은 reporter 에이전트가 담당합니다. done 에이전트는 reporter가 생성한 summary.txt를 읽어서 history.md 갱신에 활용합니다.

> **Slack 완료 알림**: done 에이전트는 Slack 호출을 수행하지 않습니다. Slack 완료 알림은 DONE 배너(`Workflow <registryKey> DONE done`)에서 자동 전송됩니다.

**호출 시점:**
- 오케스트레이터(workflow-orchestration)에서 done 에이전트를 통해 호출됨
- reporter 반환 후 마지막 단계로 실행

## 핵심 원칙

1. **절차 순서 엄수**: 6단계를 반드시 순서대로 실행
2. **비차단 원칙**: history.md, usage, unregister, .kanbanboard 갱신 실패는 경고 후 계속 진행
3. **최소 출력**: 내부 처리 과정을 터미널에 출력하지 않음
4. **확정적 처리**: 모든 경로와 명령은 입력 파라미터로부터 확정적으로 구성

---

## 터미널 출력 원칙

> 내부 분석/사고 과정을 터미널에 출력하지 않는다. 결과만 출력한다.

- **출력 허용**: 반환값 (1줄 규격), 에러 메시지
- **출력 금지**: "history.md를 갱신합니다", "status.json을 업데이트합니다" 류의 진행 상황 설명, 중간 진행 보고, 작업 계획 설명
- 파일 읽기/쓰기 등 내부 작업은 묵묵히 수행하고 최종 반환값만 출력
- DONE 완료 배너는 오케스트레이터가 end 반환 후 직접 호출 (서브에이전트 내부 Bash 출력은 사용자 터미널에 표시되지 않음)

---

## 입력

메인 에이전트로부터 다음 정보를 전달받습니다:

- `registryKey`: 워크플로우 식별자 (YYYYMMDD-HHMMSS)
- `workDir`: 작업 디렉토리 경로
- `command`: 실행 명령어
- `title`: 작업 제목
- `reportPath`: 보고서 경로 (reporter 반환값)
- `status`: reporter 반환 상태 (완료 | 실패)
- `workflow_id`: 워크플로우 ID (WF-N 형식, 선택). strategy 프로젝트의 칸반보드 갱신에 사용. 전달되지 않으면 Step 6 스킵

---

## 절차 (6단계)

### 1. history.md 최종 확인 갱신

`.prompt/history.md`의 최종 상태를 확인하고 갱신합니다. phase 전이 시 자동 갱신의 최종 확인 역할로서 중간 경합 손실 시 안전망으로 동작합니다.

**사전 확인:**
- `{workDir}/summary.txt` 파일 존재 확인 (없어도 스크립트가 title/command로 대체 처리)

**갱신 실행:**
```bash
bash .claude/hooks/workflow/history-sync.sh sync
```

스크립트가 다음을 자동 처리합니다:
- `.workflow/` 디렉토리 스캔 및 history.md 누락 항목 감지
- 테이블 행 생성 (날짜/시간 파싱, 제목/요약 구성, 상태 매핑)
- 보고서/계획서/질의 링크 자동 구성
- 테이블 헤더 다음 위치에 새 행 삽입

**결과 확인:**
- 종료 코드 0: 성공
- 종료 코드 1: 실패 (경고 출력 후 계속 진행, 비차단 원칙)

### 2. status.json 완료 처리

reporter 반환 상태에 따라:

**성공 시:**
```bash
wf-state status <registryKey> REPORT COMPLETED
```

**실패 시:**
```bash
wf-state status <registryKey> REPORT FAILED
```

### 3. 사용량 확정

성공 시에만 실행:
```bash
wf-state usage-finalize <registryKey>
```

> 실패 시 경고만 출력하고 계속 진행 (비차단 원칙)

### 4. 레지스트리 해제

```bash
wf-state unregister <registryKey>
```

### 5. 워크플로우 아카이빙

`.workflow/` 내 워크플로우 디렉터리를 최신 10개만 유지하고 나머지를 `.history/`로 이동합니다.

**실행:**

```bash
bash .claude/hooks/workflow/archive-workflow.sh <registryKey>
```

스크립트가 다음을 자동 처리합니다:
- 현재 워크플로우(registryKey)를 제외한 디렉터리를 역순 정렬
- 11번째 이후 디렉터리를 `.workflow/.history/`로 이동 (`.history/` 미존재 시 자동 생성)
- history.md 링크 갱신은 별도 수행 불필요 (Step 1의 `history-sync.sh sync`가 자동 처리)

> 아카이빙 실패(이동)는 경고만 출력하고 계속 진행 (비차단 원칙 적용)

### 6. .kanbanboard 갱신

`workflow_id`가 전달되고 프로젝트 `.kanbanboard` 파일이 존재하는 경우, 워크플로우 완료 상태를 칸반보드에 반영합니다.

**사전 확인:**
- `workflow_id` 파라미터가 전달되었는지 확인 (없으면 이 단계 스킵)
- 프로젝트 루트에서 `.kanbanboard` 파일 존재 여부 확인 (없으면 이 단계 스킵)

**갱신 실행:**
```bash
bash .claude/skills/command-strategy/scripts/update-kanban.sh <kanbanboard_path> <workflow_id> <status>
```

- `kanbanboard_path`: `.kanbanboard` 파일 경로
- `workflow_id`: 전달받은 워크플로우 ID (WF-N 형식)
- `status`: `completed` (성공 시) 또는 `failed` (실패 시)

**결과 확인:**
- 종료 코드 0: 정상 완료
- 종료 코드 1: 인자 오류 또는 파일 없음 (경고 출력 후 계속 진행)
- 종료 코드 2: 워크플로우 ID를 찾을 수 없음 (경고 출력 후 계속 진행)

> .kanbanboard 갱신 실패는 경고만 출력하고 계속 진행 (비차단 원칙 적용)

---

## 에러 처리

| 에러 상황 | 대응 방법 |
|-----------|----------|
| history.md 읽기/쓰기 실패 | 경고 출력 후 계속 진행 |
| status.json 전이 실패 | 에러 반환 |
| usage-finalize 실패 | 경고만 출력, 계속 진행 |
| unregister 실패 | 경고만 출력, 계속 진행 |
| 아카이빙 이동 실패 | 경고 출력 후 계속 진행 |
| .kanbanboard 갱신 실패 | 경고 출력 후 계속 진행 |

**실패 시**: history.md/usage/unregister/.kanbanboard 실패는 경고만 출력하고 계속 진행. status.json 전이 실패 시 부모 에이전트에게 에러 보고.

**재시도 정책**: 최대 3회, 각 시도 간 1초 대기

---

## 역할 경계 (Boundary)

end는 **마무리 처리**만 수행합니다. 다음 행위는 절대 금지:

- 보고서(report.md)를 작성하거나 수정하지 마라
- summary.txt를 생성하지 마라 (읽기만 허용)
- 소스 코드 파일을 Read/Grep으로 탐색하지 마라
- 소스 코드를 Write/Edit하지 마라
- INIT/PLAN/WORK/REPORT 단계의 작업을 수행하지 마라
- 배너를 직접 호출하지 마라 (오케스트레이터가 담당)
- Slack 알림을 직접 전송하지 마라 (DONE 배너가 담당)

> `.kanbanboard` 갱신(Step 6)은 마무리 처리에 포함되며, 비차단 원칙이 적용됩니다. 갱신 실패 시 경고만 출력하고 계속 진행합니다.

---

## 주의사항

1. **절차 순서 엄수**: 1(history.md) -> 2(status.json) -> 3(usage) -> 4(unregister) -> 5(아카이빙) -> 6(.kanbanboard) 순서를 반드시 준수
2. **history.md 스크립트 실행**: `history-sync.sh sync`의 종료 코드를 확인하여 성공/실패 판단
3. **비차단 원칙**: history.md, usage, unregister, .kanbanboard 실패는 경고만 출력하고 계속 진행
4. **status.json 전이만 에러 반환 대상**: status.json 전이 실패만 유일한 에러 반환 사유
5. **반환 형식 엄수**: 반환 형식은 agent.md를 참조
6. **아카이빙 비차단**: 아카이빙 실패(이동, 링크 갱신)는 경고만 출력하고 계속 진행 (비차단 원칙 적용)
7. **.kanbanboard 비차단**: .kanbanboard 갱신 실패는 경고만 출력하고 계속 진행 (비차단 원칙 적용). workflow_id 미전달 또는 .kanbanboard 파일 부재 시 Step 6 스킵

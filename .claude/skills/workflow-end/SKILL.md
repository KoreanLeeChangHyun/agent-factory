---
name: workflow-end
description: "워크플로우 END 단계 전용 내부 스킬. reporter 완료 후 워크플로우 마무리 처리를 수행한다. Use for workflow finalization: history.md 갱신(summary.txt 활용), status.json 완료 처리, 사용량 확정, 레지스트리 해제를 4단계 절차로 수행한다. 오케스트레이터가 내부적으로 호출하며 사용자 직접 호출 대상이 아님."
disable-model-invocation: true
---

# End

reporter 완료 후 워크플로우의 마무리 처리를 수행하는 스킬.

> 이 스킬은 workflow-orchestration 스킬이 관리하는 워크플로우의 한 단계입니다. 전체 워크플로우 구조는 workflow-orchestration 스킬을 참조하세요.

**workflow-end 스킬의 책임:**
- history.md 갱신 (summary.txt 활용)
- status.json 완료 처리 (REPORT -> COMPLETED / FAILED)
- 사용량 확정 (usage-finalize)
- 레지스트리 해제 (unregister)

> **책임 경계**: 보고서 작성과 summary.txt 생성은 reporter 에이전트가 담당합니다. end 에이전트는 reporter가 생성한 summary.txt를 읽어서 history.md 갱신에 활용합니다.

> **Slack 완료 알림**: end 에이전트는 Slack 호출을 수행하지 않습니다. Slack 완료 알림은 DONE 배너(`Workflow <registryKey> DONE done`)에서 자동 전송됩니다.

**호출 시점:**
- 오케스트레이터(workflow-orchestration)에서 end 에이전트를 통해 호출됨
- reporter 반환 후 마지막 단계로 실행

## 핵심 원칙

1. **절차 순서 엄수**: 4단계를 반드시 순서대로 실행
2. **비차단 원칙**: history.md, usage, unregister 실패는 경고 후 계속 진행
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

---

## 절차 (4단계)

### 1. history.md 갱신

`.prompt/history.md`에 작업 이력 행을 추가합니다.

**summary.txt 활용:**
- `{workDir}/summary.txt` 파일이 있으면 읽어서 내용 요약에 활용
- 없으면 title과 command만으로 구성

**행 형식:**
```
| YYYY-MM-DD<br><sub>HH:MM</sub> | YYYYMMDD-HHMMSS | 제목<br><sub>요약</sub> | command | 상태 | 계획서 | 질의 | 이미지 | 보고서 |
```

**갱신 절차:**
1. `.prompt/history.md`를 Read로 읽기 (offset/limit 사용, 상단 7줄만)
2. 테이블 헤더 행 바로 다음에 새 행 삽입 (Edit 사용)
3. 보고서 링크: `[보고서](../<workDir>/report.md)` (보고서 없으면 `-`)
4. 계획서 링크: plan.md 존재 시 `[계획서](../<workDir>/plan.md)` (없으면 `-`)
5. 질의 링크: `[질의](../<workDir>/user_prompt.txt)` (prompt 모드는 `../<workDir>/user_prompt.txt`)
6. 날짜/시간은 registryKey에서 파싱 (YYYYMMDD -> YYYY-MM-DD, HHMMSS -> HH:MM)

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

---

## 에러 처리

| 에러 상황 | 대응 방법 |
|-----------|----------|
| history.md 읽기/쓰기 실패 | 경고 출력 후 계속 진행 |
| status.json 전이 실패 | 에러 반환 |
| usage-finalize 실패 | 경고만 출력, 계속 진행 |
| unregister 실패 | 경고만 출력, 계속 진행 |

**실패 시**: history.md/usage/unregister 실패는 경고만 출력하고 계속 진행. status.json 전이 실패 시 부모 에이전트에게 에러 보고.

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

---

## 주의사항

1. **절차 순서 엄수**: 1(history.md) -> 2(status.json) -> 3(usage) -> 4(unregister) 순서를 반드시 준수
2. **history.md 형식 준수**: 테이블 행 형식을 정확히 따르며, 날짜/시간은 registryKey에서 파싱
3. **비차단 원칙**: history.md, usage, unregister 실패는 경고만 출력하고 계속 진행
4. **status.json 전이만 에러 반환 대상**: status.json 전이 실패만 유일한 에러 반환 사유
5. **반환 형식 엄수**: 반환 형식은 agent.md를 참조

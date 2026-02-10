# Common Reference

## Sub-agent Return Formats (REQUIRED)

> **WARNING: 반환값이 규격 줄 수를 초과하면 메인 에이전트 컨텍스트가 폭증하여 시스템 장애가 발생합니다.**
>
> 1. 모든 작업 결과는 `.workflow/` 파일에 기록 완료 후 반환
> 2. 반환값은 오직 상태 + 파일 경로만 포함
> 3. 코드, 목록, 테이블, 요약, 마크다운 헤더는 반환에 MUST NOT include
> 4. 규격 외 내용 1줄이라도 추가 시 시스템 장애 발생

### Common Rules

| Rule | Description |
|------|-------------|
| 작업 상세는 .workflow에 저장 | 서브에이전트는 모든 작업 상세를 파일로 기록 |
| 메인에 최소 반환 | 아래 에이전트별 형식만 반환 (추가 정보 MUST NOT) |
| 대량 내역 MUST NOT | 코드 변경 내용, 상세 로그, 파일 목록 테이블 등 반환 MUST NOT |

### init Return Format (7 lines)

```
request: <user_prompt.txt의 첫 50자>
workDir: .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>
workId: <workId>
date: <YYYYMMDD>
title: <제목>
workName: <작업이름>
근거: [1줄 요약]
```

**MUST NOT**: 요청 전문, 다음 단계 안내, 상세 설명, 마크다운 헤더, 판단 근거 상세, 변경 파일 목록, 예상 작업 시간 등 추가 정보

### planner Return Format (3 lines)

```
상태: 작성완료
계획서: <계획서 파일 경로>
태스크 수: N개
```

**MUST NOT**: 계획 요약, 태스크 목록, 다음 단계 안내 등

### worker Return Format (3 lines)

```
상태: 성공 | 부분성공 | 실패
작업 내역: <작업 내역 파일 경로>
변경 파일: N개
```

**MUST NOT**: 변경 파일 목록 테이블, 코드 스니펫, 작업 요약, 다음 단계 안내 등

### reporter Return Format (3 lines)

```
상태: 완료 | 실패
보고서: <보고서 파일 경로>
CLAUDE.md: 갱신완료 | 스킵 | 실패
```

**MUST NOT**: 요약, 태스크 수, 변경 파일 수, 다음 단계 등 추가 정보 일체

## Call Method Rules

| Target Type | Method | Example |
|-------------|--------|---------|
| Agent (4개) | Task | `Task(subagent_type="init", prompt="...")` |
| Skill (5개) | Skill | `Skill(skill="workflow-report")` |

**Agents:** init, planner, worker, reporter
**Skills:** workflow-orchestration, workflow-init, workflow-plan, workflow-work, workflow-report

> 에이전트별 색상 정보는 각 에이전트 정의 파일(`.claude/agents/*.md`)의 frontmatter 참조.

## State Update Methods

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

> **Note**: `context` 모드와 `both` 모드는 로컬 `<workDir>/.context.json`의 `agent` 필드만 업데이트. 전역 `.workflow/registry.json`은 레지스트리 전용이며, `register`/`unregister` 모드로만 접근.
> **registryKey format**: `YYYYMMDD-HHMMSS` 형식의 워크플로우 식별자. 스크립트 내부에서 registry.json을 조회하여 전체 workDir 경로를 자동 해석. 전체 workDir 경로(`.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>`)도 하위 호환.

agent 값: INIT=`init`, PLAN=`planner`, WORK=`worker`, REPORT=`reporter`. 실패 시 경고만 출력, 워크플로우 정상 진행.

## State Management (status.json)

각 워크플로우 작업은 `status.json`으로 현재 단계와 전이 이력을 추적합니다.

> status.json 스키마(9개 필드)와 저장 위치는 workflow-init skill 참조. 저장 경로: `<workDir>/status.json` (workDir = `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>`)

### status.json `linked_sessions` Field

`linked_sessions`는 워크플로우에 참여한 세션 ID의 배열입니다. init이 초기 세션 ID로 배열을 생성하고, 이후 worker/reporter가 자신의 세션 ID를 `link-session` 모드로 추가합니다. 세션 재시작 시에도 새 세션 ID가 자동 병합됩니다.

- 용도: 워크플로우에 참여한 세션 ID 추적 (디버깅/감사 목적)
- 갱신: `wf-state link-session <registryKey> <sessionId>` (중복 자동 방지, 비차단)
- 오케스트레이터는 link-session을 직접 호출하지 않음 (worker/reporter가 자체 등록)

### FSM Transition Rules

`INIT -> PLAN -> WORK -> REPORT -> COMPLETED` (정상 흐름). 분기: PLAN->CANCELLED, WORK/REPORT->FAILED, TTL만료->STALE. 불법 전이 시 시스템 가드가 차단. update-workflow-state.sh는 전이 미수행(no-op), PreToolUse Hook은 도구 호출 deny. 비상 시 WORKFLOW_SKIP_GUARD=1로 우회 가능.

> 업데이트 방법은 "State Update Methods" 섹션 참조. 비차단 원칙: 실패 시 경고만 출력, 워크플로우 정상 진행.

## Error Handling

| Situation | Action |
|-----------|--------|
| INIT error | 최대 3회 재시도 (경고 로그 출력) |
| Step error (PLAN/WORK/REPORT) | 최대 3회 재시도 후 에러 보고 |
| Independent task failure | 다른 독립 태스크는 계속 진행 |
| Dependent task blocker failure | 해당 종속 체인 중단, 다른 체인 계속 |
| Total failure rate > 50% | 워크플로우 중단 및 AskUserQuestion으로 사용자 확인 |

# 워크플로우 엔진 v2 명세 (SPEC)

> **단일 진실 공급원 (SSOT)**. 본 문서는 v2 의 모든 책임 분담·인터페이스·캐논을 박제한다.
> 본 문서와 다른 문서(skills/SKILL.md, rules/workflow/workflow.md, agents/*.md) 가 충돌하면 본 문서가 우선이며 다른 문서를 갱신한다.
> 작성: 2026-05-14 (T-489, Phase 1). 명세 버전: v2.0.0

---

## 0. 한 줄 요약

> v2 = **driver script 1 프로세스 (룰베이스, LLM 호출 X) + claude -p subprocess N개 (Step 마다 1개)**.
> 모든 상태 변경·결정·제어 흐름은 driver. claude -p 는 산출물 파일만 작성한다.

### 0.1 책임 분담 캐논 (사용자 명시 2026-05-15, T-503 확장 2026-05-18)

> **driver = 14+룰 평가 + 코드 결정론 검증 (pytest/lint) + git commit + kanban 전이 + FSM** (전부 결정론)
> **LLM = 산출물 .md 본문 작성** (plan/work/validate 자연어 평가/report 의 **자연어 부분만**)

14+룰 평가·코드 결정론 검증 (pytest -q / ruff / mypy)·verdict 산출·git commit·kanban 전이·FSM 전이를 LLM 에게 위임하는 모든 prompt 영역은 **룰 위반**. driver 결정론 영역으로 회복한다.

### 0.1.1 검증 2축 분리 (T-503)

> v2 의 검증은 **2 축**으로 명확히 분리된다. 동일 'VALIDATE' 라는 어휘 안에 자연어 평가와 결정론 검증이 섞이는 v1·v2 초기 회귀를 차단한다.

| 축 | 주체 | 산출물 | 형식 | 본문 |
|----|------|--------|------|------|
| **자연어 보고서 평가 (LLM)** | claude -p (VALIDATE Step) | `validate/report.md` | Markdown | phase 분해 적정성 / deliverable 완성도 / deps 흐름 / 종합 평가 |
| **결정론 룰 평가 (driver)** | driver `_validate.py` | `validate/rules.json` | JSON | 14+룰 PASS/WARN/FAIL/SKIP 박제 + violation count + hard_fail |
| **결정론 코드 검증 (driver, implement 한정)** | driver `_verify_code.py` | `validate/code.json` | JSON | pytest -q + ruff check + mypy 의 status/counts/head_diagnostics |

LLM 은 코드 검증·룰 평가·verdict 산출 책임 X. driver 는 자연어 평가 책임 X. 양 축은 같은 `validate/` 디렉터리 산하에 분리 박제.

### 0.1.2 TDD 강제 (implement 한정)

> implement command 한정 — PLAN 단계의 acceptance_criteria 의무 + WORK 단계의 Red→Green→Refactor 사이클 prompt 강제. driver 측 R-CODE-1/2 룰로 후행 검증.

- **PLAN**: `plan.md` frontmatter 의 각 phase 에 `acceptance_criteria` 키 (list[str]) 명시 (criteria 충족 여부가 결정론 검증 가능한 형태 — pytest assertion / 파일 존재 / 명령 종료코드 등).
- **WORK**: acceptance_criteria 1 항목당 (1) 실패하는 테스트 작성 (Red) → (2) 통과하도록 구현 (Green) → (3) 정리 (Refactor) 순으로 처리.
- **검증**: driver `_verify_code.py` 가 worktree 안에서 pytest -q 호출 → `validate/code.json` 산출 → `_validate.py` 의 R-CODE-1 (pytest 통과 hard-fail) / R-CODE-2 (lint clean advisory) 평가.

research / review command 에서는 TDD 미적용 (코드 변경 동반 X). `_verify_code.py` 자체 SKIP.

---

## 1. 왜 v2 인가 (Why)

### 1.1 v1 의 본질적 결함

v1 은 메인 세션 클로드(LLM) 가 오케스트레이터 역할을 했다. 이는 세 가지 회귀를 누적시켰다:

1. **결정의 비결정성**: LLM 이 "다음 Step 진입 여부 / 재시도 prompt / phase 분해 / worker 할당" 같은 결정을 매 사이클마다 다르게 내림. 같은 입력에서 같은 출력이 보장 안 됨.
2. **hook 흡수 mechanism 의 fragile함**: PreToolUse Hook 으로 Task subagent 호출을 결정론 wrapper 로 변환하려 시도. ZodError schema 회귀, SDK cap (SKILL.md 10KB), Anthropic hardcoded 가드 등 다중 한계.
3. **메인 세션 컨텍스트 오염**: 워크플로우 진행이 메인 세션의 토큰 예산을 잠식. 사용자가 워크플로우 외 작업을 할 수 없음.

### 1.2 v2 의 해결 방향

- **오케스트레이션 = 룰베이스 코드**: LLM 의 결정 영역 → driver 의 함수로 흡수. 입력 → 같은 출력 보장.
- **claude -p subprocess 격리**: 각 Step 의 LLM 작업은 별도 subprocess 로 분리. 메인 세션 컨텍스트 0 영향.
- **file-based pipeline**: Step 간 통신은 파일만. 메모리 상태·세션 상태·hook 메시지 의존 X.
- **통째 주입 (요약 X)**: plan.md / work/ / validate-report.md 는 다음 Step 의 prompt 에 통째 inject. LLM lossy 압축 회피.

### 1.3 사용자 통찰 시퀀스 (2026-05-14)

> 오케스트레이터 폐지 → claude -p 모델 → 단계별 격리 → file-based pipeline → 산출물 통째 전파 (요약 X) → 재시도는 claude -p --resume 룰베이스

---

## 2. 어휘 정정 (Step vs Phase 반전)

v1 어휘는 동음이의어로 LLM/사람 모두 혼동을 일으켰다. v2 는 정정한다.

| 계층 | v1 (혼동) | **v2 정정** | 비고 |
|------|----------|------------|------|
| 워크플로우 6단계 | phase (`workflow_phase`) | **Step** (`workflow_step`) | INIT / PLAN / WORK / VALIDATE / REPORT / DONE |
| WORK 내부 sub-단계 | step (`work_step`) | **Phase** (`work_phase`) | Phase 1, Phase 2, ... |

### 2.1 영어 식별자 통일 (LLM 처리 정확도)

- `workflow_step`: 6 Step FSM (NONE / INIT / PLAN / WORK / VALIDATE / REPORT / DONE / FAILED)
- `work_phase`: WORK 내부 Phase 식별자 (P1, P2, ...)
- 옛 `workflow_phase` 키는 v2 base 에서 사라지고 `workflow_step` 으로 통째 교체

### 2.2 마이그레이션 코드 불필요

v2 는 b69645a base 에서 새로 시작하므로 옛 `workflow_phase` 키와 공존할 필요 없음. 새 코드는 처음부터 `workflow_step`.

---

## 3. 6 Step FSM 명세

### 3.1 Step 흐름

```
NONE → INIT → PLAN → WORK → VALIDATE → REPORT → DONE
                                                   ↓
                                                FAILED (재시도 N회 초과 시)
```

### 3.2 Step 별 책임 (T-503 산출물 6 영역 캐논)

| Step | 주체 | LLM 호출 | 산출물 | 핵심 책임 |
|------|------|---------|--------|----------|
| INIT | driver (in-process) | X | `metadata.json` (초기) / `workflow.log` (append 시작) | 티켓 prompt 파싱, work_dir 생성, kanban Open→In Progress |
| PLAN | driver → claude -p | 1 spawn | `plan.md` (YAML frontmatter + body) | 작업 분해, Phase·worker·deps·acceptance_criteria 명세 |
| WORK | driver → claude -p | 1 spawn (Phase loop 내부) | `work/<phase_id>/W<n>.md` × N (디렉터리 nesting) | Phase 별 산출물 작성, 종속 그래프 따라 진행, TDD Red→Green→Refactor (implement) |
| VALIDATE | driver → claude -p + driver | 1 spawn (LLM) + driver in-process | `validate/report.md` (LLM) + `validate/rules.json` (driver) + `validate/code.json` (driver, implement 한정) | **Quality 평가 자연어만 (LLM)** — phase 분해 적정성 / deliverable 완성도. **14+룰 평가·코드 결정론 검증 (driver)** — pytest/ruff/mypy + R-CODE-1/2 (§0.1.1 캐논) |
| REPORT | driver → claude -p | 1 spawn | `report.md` | plan + work + validate 통째 종합 |
| DONE | driver (in-process) | X | `metadata.json` (finalize 흡수 — summary/usage/finalized_at) | kanban In Progress→Review, 회귀 metric emit |
| FAILED | driver (in-process) | X | `metadata.json` (failure 필드 흡수) | 재시도 N회 초과 또는 hard-fail 룰 위반 시 fail-fast |

#### 3.2.1 산출물 6 영역 캐논 (T-503 도달 목표)

| # | 산출물 | 작성 주체 | 형식 |
|---|--------|----------|------|
| 1 | `metadata.json` | driver | JSON (옛 `.context.json` + `status.json` + `summary.txt` + `failure.md` 흡수) |
| 2 | `workflow.log` | driver | 텍스트 누적 로그 |
| 3 | `plan.md` | PLAN LLM | YAML frontmatter + Markdown body |
| 4 | `work/<phase>/W<n>.md` | WORK LLM | Markdown (디렉터리 nesting — 모든 phase 일관) |
| 5 | `report.md` | REPORT LLM | Markdown |
| 6 | `validate/` 디렉터리 | driver + VALIDATE LLM | `rules.json` (driver 14+룰) + `report.md` (LLM 자연어 보고서 검증) + `code.json` (driver pytest/lint, implement 한정) |

#### 3.2.2 폐기 산출물 (T-503 마이그레이션)

| 파일 | 사유 | 흡수처 |
|------|------|--------|
| `user_prompt.txt` | 티켓 prompt 가 SSOT | (티켓 본문) |
| `summary.txt` | report.md 가 자연어 보고서 SSOT | `report.md` |
| `.context.json` + `status.json` | 산출물 통합 정합 | `metadata.json` |
| `failure.md` | 단일 JSON 필드로 충분 | `metadata.json.failure` |
| `validate-report.md` (flat) | `validate/` 디렉터리 nesting | `validate/report.md` |
| `validate-rules.json` (flat) | `validate/` 디렉터리 nesting | `validate/rules.json` |

> **마이그레이션 순서 (T-503)**: 신규 cycle 만 새 경로 적용. 소급 변환은 별 트랙. driver path helper 는 양쪽 경로 (flat + nested) 둘 다 resolveable 하게 hold 후 cycle 안정 시 flat 폐기.

### 3.3 Step 전이 게이트

각 Step 종료 시 driver 가 룰베이스 검증 → 다음 Step 진입 또는 재시도 또는 FAILED.

```
Step N 종료
  ↓
산출물 정합 검증 (룰베이스 — file exist, size > 0, frontmatter schema, regex)
  ↓
PASS → Step N+1 진입
FAIL (재시도 < N_max) → claude -p --resume + 룰베이스 재시도 prompt → Step N 재실행
FAIL (재시도 = N_max) → Step FAILED → 사이클 종결
```

### 3.4 Step 별 재시도 한도 (기본값)

| Step | N_max | 비고 |
|------|-------|------|
| INIT | 0 | driver in-process, 재시도 의미 없음 |
| PLAN | 2 | 산출물 단순 (plan.md 1 파일), 단순 보정 가능 |
| WORK | 3 | Phase 단위 재시도 (Phase 별로 독립) |
| VALIDATE | 1 | advisory 평가, 재시도 가치 낮음 |
| REPORT | 2 | 종합 작성 (입력은 통째 보존, 재작성만) |
| DONE | 0 | driver in-process |

---

## 4. 산출물 모델 (file-based pipeline)

### 4.1 디렉터리 구조

```
.claude-organic/runs/<registryKey>/
├── .context.json          # 사이클 메타 (driver write)
├── status.json            # workflow_step 전이 로그 (driver write)
├── metrics.jsonl          # event stream (driver append, NDJSON)
├── user_prompt.txt        # INIT 단계 티켓 prompt 인용
├── plan.md                # PLAN 산출
├── work/
│   ├── P1.md              # WORK Phase 1 산출
│   ├── P2.md              # WORK Phase 2 산출
│   └── ...
├── validate-report.md     # VALIDATE 산출
├── report.md              # REPORT 산출
├── summary.txt            # DONE 산출
├── usage.json             # DONE 산출 (token usage 집계)
└── workflow.log           # driver stdout/stderr append
```

### 4.2 다음 Step 의 prompt 주입 매트릭스

| Step | prompt 본문에 통째 inject 되는 파일 |
|------|----------------------------------|
| INIT | (없음 — driver in-process) |
| PLAN | `.context.json` + 티켓 prompt (XML 5필드) |
| WORK | `.context.json` + `plan.md` (통째) + 종속 work/`<deps>`.md (선택) |
| VALIDATE | `.context.json` + `plan.md` (통째) + `work/*.md` (모두 통째) |
| REPORT | `.context.json` + `plan.md` + `work/*.md` + `validate-report.md` (모두 통째) |
| DONE | (없음 — driver in-process) |

### 4.3 통째 주입 vs 요약 (LLM lossy 압축 회피)

v1 의 회귀 패턴: PLAN 산출을 worker 에게 "요약본" 으로 전달 → worker 가 plan 의 디테일 누락 → 잘못된 구현. v2 는 **통째 inject**. context window 부담은 claude -p subprocess 격리로 메인 세션과 무관.

context window 한도 (200K tokens) 가까이 가면? → Phase 분할로 work/ 디렉터리 N 분할 + 종속 그래프 따라 선택 주입 (모두 통째 inject 는 REPORT 만 적용).

---

## 5. plan.md 구조화 명세

### 5.1 형식 (YAML frontmatter + markdown body, T-503 확장)

```yaml
---
schema_version: 2                # T-503 — acceptance_criteria/workers 필드 도입
ticket: T-NNN
command: implement
mode: multi          # single | multi
phases:
  - id: P1
    title: "core/_common 신설"
    deps: []
    deliverable: work/P1/W1.md   # T-503 — 디렉터리 nesting (모든 phase 일관)
    spawn_mode: in_place         # default — claude -p subprocess 1개 안에서 순차 처리
    workers: 1                   # T-503 — 본 phase 안에서 spawn 할 worker 수 (default 1)
    acceptance_criteria:         # T-503 — implement 한정 의무, 결정론 검증 가능 형태
      - "engine/v2/_common.py 신설 + import 가능"
      - "WorkflowContext dataclass 안에 work_dir/registry_key/command 필드 존재"
      - "pytest engine/v2/tests/test_common.py 통과"
  - id: P2
    title: "core/_emitter 신설"
    deps: [P1]
    deliverable: work/P2/W1.md
    spawn_mode: in_place
    workers: 1
    acceptance_criteria:
      - "engine/v2/_emitter.py 신설 + emit(ctx, event, **kwargs) 시그니처"
      - "pytest engine/v2/tests/test_emitter.py 통과"
  - id: P3
    title: "격리 필요 worker (DB write 등)"
    deps: [P1, P2]
    deliverable: work/P3/W1.md
    spawn_mode: subprocess       # 예외 격리 — 별도 claude -p subprocess
    workers: 1
    acceptance_criteria:
      - "DB 마이그레이션 스크립트 신설 + dry-run 통과"
---

# Plan 본문 (LLM 자유 산문 — driver 파싱 영역 X)

## 배경
...

## 접근
...

## Phase 별 상세
...
```

### 5.2 driver 의 frontmatter 파싱

- `phases` 필수, list 비어있으면 PLAN 재시도 trigger
- `deps` 의 ID 가 phases list 안에 존재해야 함 (룰베이스 validation)
- topological sort 로 실행 순서 결정 (circular dep 발견 시 PLAN 재시도)
- `spawn_mode` 기본값 `in_place`
- **`acceptance_criteria` 필수 (command=implement 한정, T-503)**: list[str], 1+ 항목. 누락 시 PLAN 재시도 trigger. research/review 는 미적용.
- `workers` 기본값 `1` (T-503). 2+ 면 본 phase 안에서 driver 가 N 개 subprocess 병렬 spawn (별 트랙 — 본 cycle 미구현, schema 만 박제).
- `deliverable` 권장 형식: `work/<id>/W1.md` (T-503 디렉터리 nesting). `work/<id>.md` flat 형식도 backward compat 으로 일정 기간 허용.

### 5.3 spawn_mode 의미

| 값 | 의미 | 효과 |
|----|------|------|
| `in_place` (default) | WORK Step 의 claude -p 1 subprocess 안에서 Phase 순차 처리 | spawn overhead 절감, plan.md + 전체 deps 메모리 보존 |
| `subprocess` (예외) | 해당 Phase 만 별도 claude -p subprocess spawn | 격리 필요한 작업 (DB write, network call, 대용량 context 등) |

WORK 의 in_place 인지는 plan.md 가 결정 (LLM 이 phase 작성 시 명시). driver 는 결정 X, 그저 plan.md 명세 그대로 spawn.

---

## 6. 재시도 정책

### 6.1 trigger

각 Step 종료 후 driver 의 룰베이스 검증 함수 실패 시.

검증 함수 예시 (PLAN):
- `verify_plan_md()`: file exist + size > 0 + frontmatter YAML parse + `phases` 비어있지 않음 + deps DAG 검증

### 6.2 재시도 prompt 템플릿 (룰베이스)

driver 가 검증 실패 항목을 list 로 수집 → 템플릿 fill:

```text
직전 산출물 검증 실패. 누락/오류 항목:
{missing_items}

위 항목만 채워서 다시 작성. 다른 영역 수정 금지.
산출물 경로: {artifact_path}
```

LLM 이 재시도 prompt 를 만들지 않는다. driver 의 `_render_retry_prompt(missing_items, artifact_path)` 함수가 결정론적으로 fill.

### 6.3 claude -p --resume

- 직전 claude -p subprocess 의 session_id 보존 (driver state)
- 재시도 시 `claude -p --resume <session_id> <retry_prompt>` 으로 같은 세션 이어가기
- 이전 컨텍스트 (plan.md / 작성 시도) 보존하면서 누락 항목만 추가

### 6.4 N_max 초과 시

`Step FAILED` 마커 status.json 에 write → `failure.md` 작성 (driver template) → 사이클 종결 → kanban 카드는 In Progress 유지 (사용자 결정 대기, 자동 회귀 X).

---

## 7. driver.py 책임 분담 (v1 오케스트레이터 → v2 driver 매핑)

### 7.1 매핑 표

| v1 책임 (메인 세션 LLM) | v2 driver 룰베이스 구현 |
|---|---|
| `/wf -s N` 트리거 → INIT 진입 | argparse + `.context.json` template fill |
| 티켓 prompt 필드 읽기 | xml parser + dict access |
| command 분기 (implement/research/review/test) | str match → command 별 prompt template |
| mode 분기 (single/multi) | auto_router 8 signal → threshold rule (LLM 호출 X) |
| PLAN 단계 진입 + planner subagent 호출 | `subprocess.run(["claude","-p",...])` |
| plan.md 검수 | file exist + size + frontmatter schema |
| **plan.md 분해 (Phase·worker·deps)** | **frontmatter YAML parser → Phase list 추출** |
| **종속 그래프 결정** | frontmatter `deps` → topological sort |
| WORK Step worker N개 호출 | `for phase in sorted_phases: spawn claude -p` |
| worker 결과 검수 | `verify_artifact("work/{phase.id}.md")` |
| **worker 산출물 git commit** (Stage 3-E 신설) | **driver `auto_commit(ctx)`** — WORK 종료 직후 결정론 `git -C <worktree> add -A` + `git commit -m "<template>"`. 변경 0건 skip. LLM 위임 금지 (§0.1) |
| **재시도 prompt 생성** | **template fill: "누락 = {missing}, 다시 작성"** |
| 재시도 결정 | `retry_count < N and verify_fail` → resume |
| VALIDATE LLM Quality 평가 | claude -p — `validate/report.md` 자연어 산출 (phase 분해 적정성 / deliverable 완성도 / deps 흐름). **14+룰 평가·코드 검증·verdict 산출 책임 X (§0.1)** |
| **14+룰 평가 + verdict 산출** | **driver `evaluate_rules` + `save_verdict_report` (validate/rules.json)** — DONE 단계 finalize 안에서 호출 (REPORT 완료 + step.end DONE 기록 후가 정합 시점, T-490 회귀 정정 §9.2). **LLM 위임 0건 (§0.1)** |
| **코드 결정론 검증 (pytest/ruff/mypy)** | **driver `_verify_code.py` (T-503)** — `validate/code.json` 산출. implement 한정 (research/review SKIP). 도구 미설치 / 설정 부재 → graceful SKIP. |
| **R-CODE-1 + R-CODE-2 평가** | **driver `_validate.py` (T-503)** — `validate/code.json` 의 `tool: pytest` / `tool: ruff` 결과를 룰베이스 평가. R-CODE-1 = pytest 통과 hard-fail / R-CODE-2 = lint clean advisory. |
| REPORT reporter subagent | `subprocess.run(["claude","-p",...])` |
| report.md 종합 | verify + size match (통째 inject 검증) |
| finalize (summary + usage) | `summary.txt` template + `usage.json` aggregate |
| kanban 전이 (In Progress → Review) | kanban CLI subprocess |
| 회귀 처리 | conditional + `metrics.jsonl` emit |
| 사용자 진행 보고 | driver stdout + SSE event emit |
| PreToolUse hook 흡수 | **hook 자체 폐기** — driver deterministic 진행 |
| Task subagent 호출 | **SDK Task 통째 폐기** → claude -p subprocess |
| `.claude/agents/*.md` 정의 | **통째 폐기** — claude -p prompt template 으로 대체 |

### 7.2 driver.py 의사 코드

```python
def main(ticket_no: str) -> int:
    # 1. INIT (driver in-process, LLM 호출 X)
    ctx = init_step(ticket_no)
    kanban_move(ticket_no, "in_progress")
    update_status(ctx, "INIT", "PLAN")

    # 2. PLAN
    plan_md = spawn_with_retry(
        step="PLAN",
        prompt=render_plan_prompt(ctx),
        artifact="plan.md",
        verify=verify_plan_md,
        n_max=2,
    )
    plan = parse_plan_frontmatter(plan_md)
    update_status(ctx, "PLAN", "WORK")

    # 3. WORK (Phase loop, in_place 또는 subprocess)
    if any(p.spawn_mode == "subprocess" for p in plan.phases):
        # 격리 모드 — Phase 마다 별도 spawn
        for phase in topo_sort(plan.phases):
            work_md = spawn_with_retry(
                step="WORK",
                phase=phase,
                prompt=render_work_prompt(ctx, plan, phase, load_deps(phase)),
                artifact=f"work/{phase.id}.md",
                verify=verify_work_md,
                n_max=3,
            )
    else:
        # default — claude -p 1 subprocess 안에서 순차 처리
        work_outputs = spawn_with_retry(
            step="WORK",
            prompt=render_work_prompt(ctx, plan, all_phases=plan.phases),
            artifact_set=[f"work/{p.id}.md" for p in plan.phases],
            verify=verify_work_set,
            n_max=3,
        )
    auto_commit(ctx)  # Stage 3-E §0.1 — worker 산출물 결정론 commit (변경 0건 skip)
    update_status(ctx, "WORK", "VALIDATE")

    # 4. VALIDATE — LLM 은 Quality 평가 자연어만 (§0.1, 12룰 평가 0건)
    validate_md = spawn_with_retry(
        step="VALIDATE",
        prompt=render_validate_prompt(ctx, plan, load_all_work()),
        artifact="validate-report.md",
        verify=verify_validate_md,
        n_max=1,
    )
    update_status(ctx, "VALIDATE", "REPORT")

    # 5. REPORT — LLM 은 plan+work+validate(Quality) 통째 inject 받아 자연어 종합
    report_md = spawn_with_retry(
        step="REPORT",
        prompt=render_report_prompt(ctx, plan, load_all_work(), validate_md),
        artifact="report.md",
        verify=verify_report_md,
        n_max=2,
    )
    update_status(ctx, "REPORT", "DONE")

    # 6. DONE (driver in-process) — 12룰 평가 + verdict 산출 (§0.1)
    verdict = evaluate_12_rules(ctx)
    save_verdict_report(ctx, verdict)  # validate-rules.json — SSOT
    finalize(ctx)
    kanban_move(ticket_no, "review")
    return 0
```

---

## 8. claude -p subprocess 인터페이스

### 8.1 spawn 호출 패턴

```python
result = subprocess.run(
    [
        "claude", "-p",
        "--session-id", session_id,           # Step 마다 고유 (재시도 시 재사용)
        "--append-system-prompt", system_prompt,  # v2 SKILL.md 의 핵심만 (10KB cap 이하)
        prompt_body,                          # plan.md / work/* / validate-report.md 통째 inject
    ],
    cwd=ctx.work_dir,
    timeout=ctx.step_timeout,  # Step 별 (PLAN 5min, WORK 30min, VALIDATE 3min, REPORT 10min)
    capture_output=True,
)
```

### 8.2 session_id 관리

- driver 가 Step + Phase 별로 session_id 생성: `wf-T489-PLAN`, `wf-T489-WORK-P1`, `wf-T489-WORK-P2`, ...
- 재시도 시 `--resume <session_id>` 으로 같은 session 이어가기
- session 저장 위치: Claude CLI 기본 (`~/.claude/projects/...`) — driver 가 path 관리 X

### 8.3 system prompt 전달

v1 의 SKILL.md (15KB) 가 SDK cap (10KB) 으로 잘리던 문제 → v2 는 **각 Step 의 system prompt 가 별도** + 10KB 이하 정합.

- `engine/v2/prompts/plan.txt` (PLAN system prompt, target 5KB)
- `engine/v2/prompts/work.txt`
- `engine/v2/prompts/validate.txt`
- `engine/v2/prompts/report.txt`

driver 가 `--append-system-prompt` 로 전달. SDK cap 회피 확실.

### 8.4 산출물 작성 위치

claude -p subprocess 의 `cwd` = `ctx.work_dir` (= `.claude-organic/runs/<key>/`). prompt 가 "산출물 경로 = `plan.md`" 또는 "`work/P1.md`" 식으로 명시. claude -p 가 Write/Edit 도구로 직접 write.

---

## 9. VALIDATE 14+룰 캐논 (rule-based, T-503 확장)

T-463 12룰 (이미 v1 에서 박제) + T-503 신설 R-CODE-1/2. 단 일부 룰 명칭은 `workflow_step` 어휘로 정정.

| 카테고리 | ID | 룰 | hard-fail? | command 분기 |
|---------|----|----|----------|-------------|
| R-EXIST | R-EXIST-1 | report.md 존재 | YES | 전체 |
| R-EXIST | R-EXIST-2 | plan.md 존재 (research SKIP) | NO | research SKIP |
| R-EXIST | R-EXIST-3 | status.json 존재 + `workflow_step` 키 | NO | 전체 |
| R-EXIST | R-EXIST-4 | metrics.jsonl 존재 ≥ 1 줄 | NO | 전체 |
| R-METRIC | R-METRIC-2 | 마지막 step.end{step=DONE}.outcome == "ok" | YES | 전체 |
| R-METRIC | R-METRIC-3 | tool.deny 0건 | NO | 전체 |
| R-GUARD | R-GUARD-1 | worktree 모드 활성 | NO | research/review SKIP |
| R-GUARD | R-GUARD-2 | feature branch 존재 | NO | feature_branch 없으면 SKIP |
| R-GUARD | R-GUARD-3 | regression.pattern 0건 | NO | 전체 |
| R-PATH | R-PATH-1 | report.md → plan.md 링크 매칭 (research 외) | NO | research SKIP |
| R-FSM | R-FSM-1 | status.json `workflow_step` ∈ {DONE, FAILED} | NO | 전체 |
| R-WT | R-WT-1 | commits ahead ≥ 1 (command=implement) 또는 SKIP | YES (implement 한정) | research/review SKIP |
| **R-CODE** | **R-CODE-1** | **pytest 통과 (`validate/code.json` 의 tool=pytest, status ∈ {ok, skip})** | **YES (implement 한정)** | **research/review SKIP** |
| **R-CODE** | **R-CODE-2** | **lint clean (`validate/code.json` 의 tool=ruff, status ∈ {ok, skip} 또는 counts==0)** | **NO (advisory FAIL)** | **research/review SKIP** |

### 9.1 verdict 판정 (advisory only, T-503 임계 재계산)

- PASS: 14+ 룰 위반 0건
- WARN: 1~2 룰 위반 (hard-fail 0건)
- FAIL: 3+ 룰 위반 또는 hard-fail 1건 이상
- SKIP: `workflow_step` ∉ {DONE, FAILED}

> **임계 재계산 (T-503)**: 12룰 → 14+룰 확장 후에도 WARN 1~2 / FAIL 3+ 임계는 동일. hard-fail rules = `R-EXIST-1` + `R-METRIC-2` + `R-WT-1` + `R-CODE-1` 4 종.

verdict FAIL 이어도 Review→Done DnD 강행 가능 (advisory only). 자동 가드·자동 회귀 0건.

### 9.1.1 worktree 정책 (command 별 분기, T-489 Stage 3-D)

사용자 명시 정책 (2026-05-15): **워크플로우가 코드 변경을 동반하는 티켓은 worktree 격리 필수, 연구·리뷰 티켓은 worktree-less 허용**.

| command | worktree 분기 | feature_branch | R-WT-1 평가 |
|---------|--------------|---------------|------------|
| `implement` | `git worktree add` + feature_branch 생성 (driver init_step) | `feat/T-NNN-<title>` | **hard-fail** (commits ahead ≥ 1 의무) |
| `research` | 워크트리 생성 X (develop 직접) | `null` | SKIP (`research` mark) |
| `review` | 워크트리 생성 X (develop 직접) | `null` | SKIP (`review` mark) |

driver `init_step` 안에서 `worktree_manager.create_worktree(ticket_no, title, command=...)` 를 호출하고 `command != "implement"` 인 경우 None 반환 → ctx.feature_branch=null + work_dir 은 메인 `.claude-organic/runs/<key>/`. `command == "implement"` 인 경우 ctx.feature_branch + work_dir 은 `<worktree_path>/.claude-organic/runs/<key>/` 안.

### 9.2 평가 시기 (DONE 단계)

driver 룰베이스 `evaluate_rules` (T-503 — 옛 `evaluate_12_rules`) 호출은 **DONE Step 안**에서 수행 (`done_step` 함수 내부, `step_end DONE outcome=ok` 기록 후 + `update_step(_, "DONE")` 후 + `kanban_move review` 전).

이유:
- R-EXIST-1 (`report.md` 존재) — REPORT 단계 완료 후에야 정합
- R-METRIC-2 (`step.end DONE outcome=ok`) — DONE step.end 기록 후에야 정합
- R-FSM-1 (`workflow_step ∈ {DONE, FAILED}`) — `update_step("DONE")` 후에야 정합
- R-CODE-1/2 — `validate/code.json` 산출 후 (VALIDATE Step 안에서 driver 가 `_verify_code.py` 호출 → DONE 단계에서 R-CODE 룰 평가)

VALIDATE Step 의 `validate_step` 함수는 (1) `claude -p (advisory)` 1 spawn 으로 `validate/report.md` 자유 산문 작성 + (2) driver 가 `_verify_code.run(ctx)` 호출 → `validate/code.json` 산출 (implement 한정). driver 14+룰 평가는 본 단계 미수행 — DONE 단계로 지연.

### 9.3 산출물 분리 캐논 (T-503 — 3 형식 분리)

> 사용자 명시 (2026-05-18): 산출물 형식은 **3 영역으로 분리**되며 각 영역은 단일 책임을 갖는다.

| 형식 | 영역 | 책임 |
|------|------|------|
| **JSON** | `metadata.json` / `validate/rules.json` / `validate/code.json` / `usage.json` | driver 결정론 평가·메타데이터·코드 검증 결과. 기계 가독 우선. |
| **Markdown (자연어)** | `plan.md` / `work/<phase>/W<n>.md` / `validate/report.md` / `report.md` | LLM 자연어 산출. 사람 가독 + LLM 다음 Step inject 가독. |
| **HTML 렌더 (viewer 책임)** | T-502 board UI viewer | JSON 과 Markdown 을 합성해 사용자 가독 카드/탭 렌더. 본 트랙 비범위 — 별 트랙. |

위 3 영역 외 형식 (예: CSV / YAML / 옛 `summary.txt` / 옛 `failure.md` / 옛 `validate/code.md`) 은 도입 금지. 사람 가독은 board UI viewer 책임으로 명확히 분리.

산출물별 매핑:
- `validate/report.md` = claude -p (LLM) 의 advisory 자연어 평가 (VALIDATE 단계, T-503 디렉터리 nesting)
- `validate/rules.json` = driver 의 룰베이스 결정론 평가 (DONE 단계, T-503 디렉터리 nesting)
- `validate/code.json` = driver `_verify_code.py` 의 결정론 코드 검증 (VALIDATE 단계 안 driver 호출, T-503 신설)

---

## 10. 회귀 5종 차단 검증

T-489 prototype 검증 criteria. 1 사이클 finalize 시 자동 차단 확인.

| 회귀 패턴 | 차단 메커니즘 |
|----------|-------------|
| `worker_false_success` | driver 의 `verify_artifact` 룰베이스 검증 (file size > 0, regex match) |
| `hook_deny` | hook 자체 폐기 (v2 는 hook 의존 X) |
| `empty_bash_card` | claude -p 가 산출물 파일에 직접 write, Board UI 의 bash card 의존 X |
| `stage_header_leak` | driver 가 stdout 제어, Step 헤더 형식 driver template fill |
| `worktree_commit_missing` | R-WT-1 hard-fail 승격 (commits ahead ≥ 1 의무) |

---

## 11. 사라지는 인프라 (v1 → v2 통째 폐기)

revert (b69645a base) 후에도 v1 의 잔재가 살아있다면 추가 폐기:

### 11.1 통째 삭제 대상

- `.claude/agents/*.md` 9 파일 (서브에이전트 정의)
- `engine/workflow_hooks/` (revert 후 살아있으면 다시 폐기)
- `engine/banners/` (Step 헤더 출력 스크립트 — driver template 으로 흡수)
- `engine/hooks/dispatcher.py` 의 Task subagent 분기
- SDK Task 호출 전체
- `system-prompt-wf.xml` (이미 폐기, 다시 살리지 않음)
- `flow-init` / `flow-update` / `flow-phase` / `flow-step` / `flow-finish` / `flow-launcher` 6 wrapper (driver 안으로 통합)

### 11.2 신설 wrapper

- `flow-wf` 단일 entrypoint (`.claude-organic/bin/flow-wf`)
- 호출: `flow-wf submit T-NNN` → `python3 -m engine.v2.driver T-NNN`
- 기존 `/wf` 슬래시 명령은 보존 (사용자 인터페이스), 내부적으로 `flow-wf submit` 호출

### 11.3 보존 대상

- `engine/core/` — v1 core 모듈 일부는 driver 안에서 재사용 가능 (`_common.py` 의 path helper 등). 단 v2 driver 가 명세 위반 코드만 사용
- `engine/guards/` — finalize 가드 (R-WT-1 등) 는 driver 가 호출
- `engine/flow/` — kanban CLI / kanban data model 보존
- `engine/git/` — git 헬퍼 보존
- `engine/sync/` — history sync 보존
- `engine/memory_gc/` — 메모리 GC 보존
- VALIDATE 12룰 평가 코드 (T-463 본체) 보존

---

## 12. 인터페이스

### 12.1 CLI

```bash
# 사용자 진입
flow-wf submit T-NNN              # Step 0~6 통째 실행 (driver spawn)
flow-wf submit T-NNN --step PLAN  # 특정 Step 만 실행 (디버그)
flow-wf status T-NNN              # 진행 상태 조회 (status.json read)
flow-wf abort T-NNN               # 사이클 중단 (claude -p subprocess kill + status FAILED)
```

### 12.2 슬래시 명령

`/wf -s N` → `.claude-organic/bin/flow-wf submit T-N` 호출. 메인 세션은 trigger 만, 진행은 driver.

### 12.3 SSE event (Board UI)

driver 가 stdout 으로 NDJSON emit → Board 서버가 SSE 로 클라이언트 전송:

```json
{"event":"step.start","step":"PLAN","ticket":"T-489","ts":"2026-05-14T..."}
{"event":"step.end","step":"PLAN","outcome":"ok","retry_count":0,"ts":"..."}
{"event":"phase.start","step":"WORK","phase":"P1","ts":"..."}
{"event":"phase.end","step":"WORK","phase":"P1","outcome":"ok","ts":"..."}
{"event":"workflow.finish","outcome":"ok","verdict":"PASS","ts":"..."}
```

Board UI 의 workflow-bar / kanban verdict 배지 모두 본 stream 으로 갱신.

### 12.4 kanban 전이

- INIT 진입 시: `kanban move T-NNN in_progress` (driver)
- DONE 종결 시: `kanban move T-NNN review` (driver)
- FAILED 종결 시: kanban 자동 회귀 X (In Progress 유지, 사용자 결정)

---

## 13. 디렉터리 구조 (신설)

```
.claude-organic/engine/v2/
├── SPEC.md                    # 본 문서 (SSOT)
├── driver.py                  # 진입점 + 6 Step orchestration
├── _common.py                 # path helper, kanban CLI wrapper, status I/O
├── _emitter.py                # SSE event NDJSON emit
├── _verify.py                 # 룰베이스 산출물 검증 함수 모음
├── _retry.py                  # 재시도 prompt 템플릿 + claude -p --resume
├── _spawn.py                  # claude -p subprocess.run wrapper
├── steps/
│   ├── init.py
│   ├── plan.py
│   ├── work.py
│   ├── validate.py
│   ├── report.py
│   └── done.py
├── prompts/                   # claude -p 의 system prompt (각 Step 별 10KB 이하)
│   ├── plan.txt
│   ├── work.txt
│   ├── validate.txt
│   └── report.txt
├── templates/                 # driver 가 fill 하는 출력 template
│   ├── retry_prompt.txt
│   ├── summary.txt
│   └── failure.md
└── tests/
    ├── test_driver.py
    ├── test_spawn.py
    ├── test_verify.py
    └── test_retry.py
```

---

## 14. 마일스톤 (Phase 0~3)

### Phase 0 — revert base 확보 (완료)

- T-489 To Do → Open
- develop reset --hard b69645a (39 commit revert, 사용자 명시 예외)
- T-488 삭제 (검증 대상 T-486 사라짐)
- working tree clean, push 보류

### Phase 1 — v2 명세 박제 (진행 중)

- `engine/v2/SPEC.md` 신설 (본 문서)
- `.claude/rules/workflow/workflow.md` 갱신 (오케스트레이터 섹션 → driver, Step/Phase 어휘 정정)
- 메모리 `project_workflow_v2_orchestrator_to_driver_canon.md` 신설

### Phase 2 — driver prototype 구현

- `driver.py` + `_common.py` + `_emitter.py` + `_verify.py` + `_retry.py` + `_spawn.py`
- `steps/init.py` + `steps/plan.py` + `steps/work.py` + `steps/validate.py` + `steps/report.py` + `steps/done.py`
- `prompts/*.txt` (각 Step system prompt)
- `templates/*` (driver fill 출력)
- `tests/test_*.py` (단위 테스트)
- `.claude-organic/bin/flow-wf` wrapper

### Phase 3 — 1 사이클 finalize 검증

- 검증용 신규 티켓 1건 생성 (T-490 후보, 간단한 implement)
- `flow-wf submit T-490` 실행 → driver 가 6 Step 통째 진행
- 산출물 5종 정합성 검증: plan.md / work/*.md / validate-report.md / report.md / .context.json
- 회귀 5종 차단 검증 (R-WT-1 + worker_false_success 등)
- token usage 측정 (v1 SDK Task 모델 1 사이클 대비)
- v1 대비 token 사용량 / 결정론성 / context 격리 보고서 작성

### 후속 마일스톤

- Phase 4 — 멀티 Phase 격리 모드 (`spawn_mode: subprocess`) 검증
- Phase 5 — 멀티 사이클 동시 제출 race 차단 (registryKey 충돌 회귀 차단)
- Phase 6 — Board UI workflow-bar v2 적용 (SSE event 매핑)
- Phase 7 — single 모드 (멀티 폐기 vs 보존 결정)

---

## 15. 본 문서의 정합성 규칙

### 15.1 SSOT 우선

본 문서와 다른 문서 충돌 시 본 문서 우선. 다른 문서를 갱신한다.

### 15.2 변경 절차

- v2 명세 변경 = 본 문서 갱신 + 사용자 합의
- 합의 없는 자율 갱신 금지 (general.md "추측 금지" 룰 적용)
- 변경 시 `## 변경 이력` 섹션에 날짜·항목·근거 기록

### 15.3 v1 유산 참조

본 문서 안에서 v1 회귀 사례를 참조할 때는 commit 해시 또는 메모리 파일 이름을 인용. 추측 인용 금지.

### 15.4 Stage 3-E 검증 절차

Stage 3-E (§0.1 책임 분담 캐논 박제) 의 작동은 본 T-494 같은 단순 산출물 티켓 1 사이클을 finalize 하여 검증한다. driver 측에서 12룰 평가·verdict 산출·git commit (auto_commit)·kanban 전이·FSM 전이가 모두 결정론으로 수행되고, 동시에 claude -p subprocess (PLAN/WORK/REPORT) 는 산출물 .md 본문의 자연어 부분만 작성하여 driver 책임을 침범하지 않으면 통과. T-493 smoke 에서 발견된 LLM verdict 와 driver verdict 충돌 (validate.txt 가 LLM 에게 12룰을 평가시킨 룰 위반 + work.txt 의 git commit 누락) 같은 회귀가 사라졌는지 확인하는 것이 본 절차의 핵심이며, 상세 책임 분담은 §0.1 / §3.2 (Step 별 책임) / §7.1 (driver.py 매핑) 을 참조한다.

---

## 변경 이력

| 날짜 | 항목 | 근거 |
|------|------|------|
| 2026-05-14 | v2.0.0 초안 작성 (T-489 Phase 1) | 사용자 통찰 시퀀스 (오케스트레이터 폐지 → claude -p 모델 → file-based pipeline → 통째 주입 → 룰베이스 재시도) |
| 2026-05-15 | §7.1 + §9.2 — driver 룰베이스 12룰 재검증 시기를 VALIDATE → DONE 단계로 정정 | T-490 Phase 3 검증 회귀 발견 (VALIDATE 시점에 evaluate 호출 시 report.md / step.end DONE 미생성으로 거짓 FAIL 3건 = R-EXIST-1 / R-METRIC-2 / R-PATH-1) |
| 2026-05-15 | §9.1.1 — command 별 worktree 분기 정책 도입 (Stage 3-D) | T-489 Stage 3-D — implement 의무 / research·review worktree-less / R-WT-1 SKIP 정합 (commit e73dfc1 + 79bf36d) |
| 2026-05-15 | §0.1 책임 분담 캐논 신설 (Stage 3-E) — driver=12룰+commit+kanban+FSM 결정론 / LLM=자연어 산출만. §3.2 / §7.1 / §7.2 정합 | T-493 smoke 에서 LLM verdict (WARN) ≡ driver verdict (FAIL) 충돌 발견. validate.txt 가 LLM 에게 12룰 평가시키고 verdict 산출시킨 룰 위반 + work.txt 의 git commit 누락. 사용자 명시 캐논 박제 (commit ? + ?) |
| 2026-05-18 | T-503 — §0.1 / §0.1.1 / §0.1.2 / §3.2 / §3.2.1 / §3.2.2 / §5.1 / §5.2 / §7.1 / §9 / §9.2 / §9.3 갱신 — 12룰 → 14+룰 (R-CODE-1/2), 산출물 6 영역 + 폐기 5 파일, 검증 2축 분리 (자연어 보고서 LLM / 결정론 코드 driver), TDD 강제 (acceptance_criteria + Red→Green→Refactor) | 사용자 명시 캐논 확장 (산출물 정합화 + 검증 2축 분리 + TDD prompt 강제). 본 cycle 자체는 옛 driver 처리 — R-CODE 는 다음 cycle 적용. |

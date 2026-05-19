# 워크플로우 시스템 상세 규칙

> **v2 명세 SSOT**: `.claude-organic/engine/v2/SPEC.md`. 본 문서와 충돌 시 SPEC.md 우선.
> v2 = **driver script 1 프로세스 (룰베이스, LLM 호출 X) + claude -p subprocess N개 (Step 마다 1개)**. 메인 세션은 오케스트레이터 아님 — 사용자 대화 전용.
> 어휘: `workflow_step` (6단계 FSM), `work_phase` (WORK 내부 sub-단계). `workflow_phase` 는 v1 옛 키 — 사용 금지.

## 칸반 상태 흐름

### 5단계 FSM

> 이 5단계는 `kanban_status` 도메인이며 워크플로우 8상태(`workflow_step`: NONE/INIT/PLAN/WORK/VALIDATE/REPORT/DONE/FAILED) 와 분리됨.

```
To Do → Open → In Progress → Review → Done
```

- **To Do**: 미래에 할 백로그·아이디어 저장소 (티켓 생성 공간). 지금 당장 집중하지 않는 작업.
- **Open**: 지금 집중해야 하는 임박 작업. 워크플로우 실행(`/wf -s N`) 대상.
- **In Progress**: 워크플로우 실행 중인 상태.
- **Review**: 워크플로우 완료 후 보고서 검토 + 카드 4행 토글로 feature 브랜치 활성화 → 사용자 직접 테스트 + 사용자 리뷰. (토글 ON: feature 브랜치로 git switch, OFF: develop 복귀)
- **Done**: 머지 + 사용자 직접 테스트 통과 후의 진짜 종결. 작업 흐름(코드 머지) + 사용자 검증(직접 테스트) 양쪽이 끝난 상태만 Done으로 처리한다.

### 전이 규칙

| 전이 | 방법 | 비고 |
|------|------|------|
| To Do → Open | `flow-kanban move T-NNN open` | 승격 |
| Open → To Do | `flow-kanban move T-NNN todo` | 강등 |
| Open → In Progress | `/wf -s N` | 워크플로우 실행 |
| In Progress → Review | 워크플로우 자동 전이 | driver finalize |
| Review → Done | `/wf -d N` | |
| Review → Open | `/wf -e N` | 재작업 |

### 티켓 생성 규칙

티켓은 **무조건 To Do 상태로 생성**한다 (MUST). 사용자가 즉시 집중하려면 칸반 DnD (To Do → Open) 한 번으로 충분하므로 생성 시점 상태 결정·메뉴 질의는 불필요한 낭비.

```bash
flow-kanban create "제목" --command implement --status todo
```

### 번호 영역 정책

티켓 번호는 단일 영역 (T-001 ~ T-NNN). 자동 채번은 `max(전체) + 1`, 또는 `--number` 로 명시. 동일 번호 충돌 시 에러.

## DO
- 코드 수정은 기본적으로 `/wf -e` 로 티켓 생성/편집 후 `/wf -s N` 으로 실행
- 사용자가 직접 수정을 명시 요청한 경우에만 메인 세션에서 직접 수정
- 메인 세션은 기본적으로 티켓 관리·상태 확인·결과 리뷰 등 조율 역할 담당
- 자연어 요청도 워크플로우 명령으로 변환하여 처리 (아래 자연어 매핑 참조)
- 티켓 생성 시 대화 맥락에서 관련 티켓이 있으면 `flow-kanban link` 로 관계를 자동 연결한다 (SHOULD)
  - 기존 티켓 실행 중 발견된 버그/이슈 → `--derived-from` (파생)
  - 선행 작업이 필요한 경우 → `--depends-on` (의존)
  - 후속 작업을 차단하는 경우 → `--blocks` (차단)
- 티켓 생성 시 상태 메뉴 질의 금지 (MUST NOT). 무조건 `--status todo` 로 생성한다. Open 승격은 사용자가 칸반 DnD 로 직접 수행
- 티켓 생성 전 사용자 요구사항이 모호하면 **인터뷰 식**으로 자연어 질문한다 (MUST). 메뉴 (1=A/2=B) 형태 질의 금지. 한 번에 1~2개씩만 묻고 답을 받아 다음 질문으로 진행
  - **호출 강제 (MUST)**: 아래 트리거 감지 시 description match 에 의존하지 말고 **즉시 Skill 도구로 `grill-me` 명시 호출**. 본 룰이 호출 강제의 단일 진실 공급원
  - **트리거 키워드**: `티켓 만들어줘`, `/wf -o`, `티켓 생성해줘`, `grill me`, `캐물어줘`, `제대로 물어봐`, `인터뷰해줘`, 또는 **작업 범위·산출물 형태·제약·우선순위** 중 하나라도 모호한 신규 요청 발화
  - 묻는 대상: 작업 범위 / 산출물 형태 / 제약 / 우선순위 등 연구·구현 방향에 결정적인 모호 포인트
  - 묻지 않는 대상: 티켓 상태 (자동 To Do), 기본 생성 옵션 (기본값 사용)
  - 상세 호출 절차 / 예시: `.claude/skills/grill-me/SKILL.md` (인터뷰), `.claude/skills/brainstorming/SKILL.md` (컨셉 정리). 룰 정의는 본 문서가 단일 진실 공급원
- 사용자가 설계·아키텍처·워크플로우·구조 제안을 공유하면 **사용자가 "어때요?" 명시 요청하기 전에 즉시 약점을 짚는다** (MUST). 시각화·옵션 질의만 하고 약점 분석을 미루는 것 금지 (MUST NOT). 점검 7축:
  1. **재시도/실패 처리 의미론**: 실패 사유 피드백 루프 / 재시도 범위 / MAX 도달 시 후속 처리
  2. **컴포넌트 간 책임 중복**: 같은 일을 두 곳에서 하지 않는가 / 책임이 비어있는 영역은 없는가
  3. **기존 인프라와의 매핑**: 신설 vs 흡수 vs 폐지 결정점 / 기존 가드·규약과의 충돌
  4. **FSM 경계 명시**: 새 `workflow_step` 이 기존 칸반 FSM(`kanban_status`) 의 어느 단계 안에 있는지 / 회귀 가능성
  5. **비용 vs 가치**: LLM 호출 추가 시 cost / skip 조건 정의 가능성
  6. **다른 모드와의 양립성**: 명령(research/implement/review) 분기와 일관성
  7. **명명 모호성**: 동음이의어 회피 — 동의어 페어마다 영어 식별자 분리
- `flow-kanban create` 호출 시 `--status todo` 명시 (MUST)
- 메인 클로드가 develop 브랜치에 직접 commit 하지 않는다 (MUST NOT) — 워크플로우 회귀 진단·복구 등 즉각 차단 케이스라도 `fix/...` 또는 `hotfix/...` 별도 브랜치 경유를 권장 (SHOULD). 머지 시 `--no-ff` 권장. 즉흥 브랜치 OK — 티켓 채번 없이 `fix/short-desc` 형태 브랜치 바로 생성 가능

## DO NOT
- PreToolUse Hook 활성 시 직접 수정 시도하지 않는다 — 차단되므로 토큰 낭비
- 서브에이전트(Agent 도구)를 통해 조사·수정을 직접 시도하지 않는다 — 티켓 생성 후 워크플로우로 처리
- `flow-kanban` 호출 시 bin 레퍼런스에 나열되지 않은 서브커맨드를 사용하지 않는다
- `/clear` 후 시스템 프롬프트가 소실되었다고 가정하지 않는다 — SessionStart hook 이 자동 재주입
- 사용자 발화에 명시되지 않은 행위를 추론하여 수행하지 않는다 — "추가해주세요"는 추가만 의미
- `python3 .claude-organic/engine/...` 형태로 스크립트를 직접 호출하지 않는다 — `.claude-organic/bin/flow-*` wrapper 사용
- derived-from 파생 티켓이 미완료(Done 아닌 상태)면 원본 티켓을 Done 처리하지 않는다 — Hook 이 차단

## bin wrapper 레퍼런스

`.claude-organic/bin/flow-*` 실행 파일을 직접 호출 (alias 아님). 대화형 zsh 셸은 PATH 등록되어 있을 수 있으나, 비대화형 Bash tool 환경에서는 절대/상대 경로로 호출한다 (MUST).

### flow-kanban 서브커맨드 (이 외 사용 금지)
create, move, done, delete, update-title, update, update-prompt, update-result, set-editing, link, unlink, list, board, show

예시:
- `.claude-organic/bin/flow-kanban create "제목" --command implement --status todo`
- `.claude-organic/bin/flow-kanban update-prompt T-001 --goal "목표" --target "대상"`
- `.claude-organic/bin/flow-kanban update-result T-001 --registrykey "20260329-180635" --workdir "경로"`
- `.claude-organic/bin/flow-kanban link T-001 --derived-from T-000`
- `.claude-organic/bin/flow-kanban move T-001 progress`
- `.claude-organic/bin/flow-kanban done T-001`

### XML 필드 개행 컨벤션
복수 항목 필드(goal, target, constraints, criteria, context)에 여러 항목을 입력할 때는 반드시 `\n` 개행을 삽입한다 (MUST).

- 단일 문장: `--constraints "조건1"` (개행 불필요)
- 복수 항목: `--constraints "조건1\n조건2\n조건3"` (MUST)
- 대상 필드: goal, target, constraints, criteria, context 전체

> `\n` 이 누락되면 XML 래핑이 실패하여 태그 직후에 텍스트가 붙는 형식 오류가 발생한다.

### 기타 bin wrapper (실제 존재 항목)

| wrapper | 용도 |
|---------|------|
| `flow-wf` | **v2 워크플로우 driver 진입점** (`submit T-NNN [--step STEP]`) |
| `flow-launcher` | 워크플로우 spawn (board UI 측 진입 — driver 호출 wrap) |
| `flow-kanban` | 칸반 티켓 라이프사이클 (위 서브커맨드 참조) |
| `flow-claude` | 세션 라이프사이클 (`start`, `end`) |
| `flow-claude-edit` | `.claude/` 파일 편집 (`open`, `save`, `new`) — 직접 Edit/Write 차단 영역 우회 |
| `flow-merge` | 워크트리 → develop 머지 (`--force` 시 워커 commit 누락도 자동 commit + merge) |
| `flow-undo-done` | Done 처리 롤백 |
| `flow-review-verdict` | 14룰 advisory verdict 단발 평가 |
| `flow-validate` | plan.md 단계 검증 (rule-based) |
| `flow-validate-p` | 티켓 XML prompt 필드 완성도 검수 |
| `flow-skill` | 스킬 archive/activate/list |
| `flow-skillmap` | 스킬맵 생성 |
| `flow-catalog` | 스킬 카탈로그 갱신 (`--dry-run`) |
| `flow-history` | runs/ 히스토리 동기화 (`sync`, `status`, `archive`) |
| `flow-metrics` | metrics.jsonl 조회/집계 |
| `flow-memory-gc` | auto-memory 인덱스 갱신 (`run`) |
| `flow-migrate-runs` | runs/ 디렉터리 마이그레이션 도구 |
| `flow-gc` | 좀비/임시 디렉터리 GC |
| `flow-gitconfig` | git 사용자 설정 자동 적용 (`--global`/`--local`) |
| `flow-detect` | 프로젝트 자동 탐지 (`--generate`) |

> 스크립트 호출 시 반드시 위 bin wrapper 를 사용 (MUST). `python3` 직접 경로 호출 금지 (MUST NOT).

## 워크플로우 요약
- entry-point: `/wf` 명령어 (단일 진입점). 내부적으로 `flow-wf submit T-NNN` 호출
- lifecycle: 위 "칸반 상태 흐름" 5단계 FSM 참조
- commands:
  - `/wf -o`: 새 티켓 생성 (채번+용도선택만)
  - `/wf -o N`: 기존 티켓 열람
  - `/wf -e`: 새 티켓 생성 + 프롬프트 편집
  - `/wf -e N`: 기존 티켓 편집
  - `/wf -oe` / `/wf -oe N`: `-o -e` 단축 별칭
  - `/wf -s N`: 티켓 제출 및 워크플로우 실행
  - `/wf -d N`: 티켓 종료 (Done)
  - `/wf -c N`: 티켓 삭제
- 상세 참조: `.claude/commands/wf.md`, `.claude/skills/workflow-wf/`

## 자연어 매핑

| 자연어 | 워크플로우 명령 | 비고 |
|--------|---------------|------|
| "이거 수정해줘" / "코드 고쳐줘" | `/wf -e` → `/wf -s N` | - |
| "분석해줘" / "조사해줘" | `/wf -e` (research) → `/wf -s N` | - |
| "티켓 만들어" | `/wf -o` | - |
| "리뷰해줘" | `/wf -e` (review) → `/wf -s N` | - |
| "종료해줘" | `/wf -d N` | - |
| "티켓 편집해줘" | `/wf -e N` | - |
| "티켓 생성해줘" / "나중에" / "언젠가" / "백로그" | `/wf -o` | To Do 자동 |
| "지금 집중" / "바로 해야 함" / "이번에 하자" | `/wf -o` → DnD | To Do 생성 후 사용자가 칸반 DnD 로 Open 승격 |
| "데브루프 고정" / "데브루프에 올려" / "데브루프 동기화" / "올리자" | develop ff merge + origin push | "데브루프" = develop branch. 현재 작업 브랜치 → develop ff → `origin develop` push. non-FF 면 사용자 옵션 묻기. main 머지는 별도 release 결정 |

## Review 단계 1차 룰베이스 자동 검증 (advisory)

> Review 컬럼 진입 직후 driver `_validate.py` 가 룰베이스 1차 자동 검증을 수행하여 advisory verdict (PASS / WARN / FAIL / SKIP) 를 카드 배지로 표시. **자동 강제 전이 / 강제 회귀 / 강제 차단 0건**. 사용자는 verdict FAIL 이어도 Review→Done DnD 강행 가능.

### 검증 룰 카탈로그 (14 룰 / 7 카테고리)

SSOT = `.claude-organic/engine/v2/_validate.py`. 본 표는 요약.

#### R-EXIST (산출물 존재, 4룰)

| ID | 룰 | 검사 대상 | 통과 조건 |
|----|----|---------|----------|
| R-EXIST-1 | report.md 존재 (**hard-fail**) | `<work_dir>/report.md` | 파일 존재 + size > 0 |
| R-EXIST-2 | plan.md 존재 | `<work_dir>/plan.md` | 파일 존재 + size > 0 (research 명령 SKIP) |
| R-EXIST-3 | status.json 존재 | `<work_dir>/status.json` | 파일 존재 + JSON parse + `workflow_step` 키 |
| R-EXIST-4 | metrics.jsonl 존재 | `<work_dir>/metrics.jsonl` | 파일 존재 + 줄 수 ≥ 1 |

#### R-METRIC (metrics.jsonl event_type 발화, 2룰)

| ID | 룰 | 통과 조건 |
|----|----|----------|
| R-METRIC-2 | step.end DONE outcome (**hard-fail**) | 마지막 step.end{step=DONE}.outcome == "ok" |
| R-METRIC-3 | tool.deny 0건 | tool.deny event 0건 |

#### R-GUARD (가드 정합, 3룰)

| ID | 룰 | 통과 조건 |
|----|----|----------|
| R-GUARD-1 | worktree 모드 활성 | `.context.json: worktree.enabled == true` |
| R-GUARD-2 | feature branch 존재 | `.context.json: worktree.featureBranch` 가 `git branch --list` 매칭 |
| R-GUARD-3 | regression.pattern 0건 | `metrics.jsonl` 의 regression.pattern 0건 |

#### R-PATH (산출물 path 정합, 1룰)

| ID | 룰 | 통과 조건 |
|----|----|----------|
| R-PATH-1 | report.md → plan.md 링크 매칭 | report.md 본문 plan.md 토큰 + 실제 plan.md 위치 매칭 (research 외) |

#### R-FSM (FSM 종착점, 1룰)

| ID | 룰 | 통과 조건 |
|----|----|----------|
| R-FSM-1 | status.json workflow_step | `workflow_step ∈ {DONE, FAILED}` |

#### R-WT (워크트리 변경, 1룰)

| ID | 룰 | 통과 조건 |
|----|----|----------|
| R-WT-1 | commits ahead ≥ 1 (**hard-fail**) | `git rev-list --count develop..HEAD` ≥ 1 (research/review 명령 SKIP) |

#### R-CODE (TDD 코드 결정론 검증, implement 한정, 2룰)

| ID | 룰 | 통과 조건 |
|----|----|----------|
| R-CODE-1 | pytest 통과 (**hard-fail**) | worktree 안 `pytest -q` 종료코드 0 (research/review SKIP) |
| R-CODE-2 | lint clean (advisory) | `ruff check` + `mypy` 둘 다 clean (advisory FAIL — hard-fail 아님) |

### Verdict 임계 (advisory only)

- **PASS**: 14 룰 위반 0건
- **WARN**: 1~2 룰 위반 (hard-fail 0건)
- **FAIL**: 3+ 룰 위반 또는 hard-fail 룰 1건 이상 (R-EXIST-1 / R-METRIC-2 / R-WT-1 / R-CODE-1)
- **SKIP**: `workflow_step != DONE/FAILED` (워크플로우 미종료 시점)

### advisory 보장

- `review_verdict.py` — kanban move / status 전이 / sentinel 호출 0건
- driver finalize 직후 — try/except 흡수 비차단
- Board API endpoint — GET only
- UI 배지 — tooltip only (클릭 자동 액션 0건)
- DnD 핸들러 — verdict 결과로 차단 분기 0건
- metrics.jsonl emit — regression.pattern 재사용 (신규 event_type 0건)

### 사용자 안내

- verdict FAIL 이어도 Review→Done DnD 강행 가능 — advisory 권고일 뿐 차단 아님
- 배지 색: PASS=청록 / WARN=앰버 / FAIL=주홍 / SKIP/UNKNOWN=숨김
- 배지 hover 시 violations 목록 tooltip 표시

### 후속 트랙 (3-tier AI 리뷰 구조)

| Tier | 검증 방식 | 트리거 |
|------|---------|------|
| 1차 | 룰베이스 자동 (본 섹션) | driver finalize 자동 |
| 2차 | LLM 자동 | driver finalize 자동 (별도 트랙) |
| 3차 | 사용자 트리거 외부 cross-review | DnD 또는 명령 |

## 워크플로우 데이터 정합성 룰 (MUST)

워크플로우 1건은 다음 두 조건을 모두 만족해야 한다 (MUST):

### (1) 티켓 연결 필수
- `.context.json` 의 `ticketNumber` 필드가 비어있지 않고 칸반에 실존해야 한다
- 워크플로우 제목(title) = 티켓 제목과 동일

### (2) v2 산출물 6 영역 (SPEC.md §3 캐논)

각 워크플로우 디렉터리(`runs/<key>/`) 직속에 다음이 존재해야 한다:

| 종류 | 경로 | 생성 단계 |
|------|------|----------|
| 질의 | `user_prompt.txt` + `.context.json` | INIT |
| 계획 | `plan.md` | PLAN |
| 작업 | `work/P{n}/W{m}.md` | WORK |
| 검증 | `validate/report.md` (LLM) + `validate/rules.json` (driver) + `validate/code.json` (implement 한정) | VALIDATE |
| 보고 | `report.md` | REPORT |
| 종결 | `status.json` + `metrics.jsonl` + `workflow.log` | 전체 |

> 상세 명세는 SPEC.md §3 (T-503 6 영역 캐논) 우선.

### How to apply
- 정합성 검증·`flow-history sync` 도구는 위 두 조건을 검증 항목으로 포함
- 옛 워크플로우 cleanup 시 룰 위반 케이스 (티켓 미연결 + 산출물 누락) 는 자동 폐기가 아니라 **사용자 결정 받기**
- 룰 위반은 advisory only — 자동 강제 차단·status 강제 전이 도입 금지 (general.md "추측 금지" 참조)

## Research 워크플로우 품질 룰 (MUST)

Research 워크플로우 (`/wf -s N` command=research) 산출물 품질은 **메인 세션이 직접 조사했을 때 이상**이어야 한다. 미달 시 워크플로우 자체가 무의미.

### Why
- 워크플로우의 본질 = 메인 세션 컨텍스트를 분리해 더 깊은 조사 + 토큰 절약
- 결과 품질이 메인 이하 → 컨텍스트 분리의 비용 정당화 불가
- 메인 세션을 능가하지 못하면 사용자가 직접 메인에서 묻는 게 더 빠르고 정확 → 워크플로우 사용 의미 자체가 사라짐

### How to apply
- research workflow 결과 (report.md) 를 받으면 "메인 세션이 직접 조사했을 가상 결과" 와 비교 평가
- 미달 신호 발견 시 즉시 보완 후보로 분류:
  - **출력 깊이**: 메인이라면 더 깊이 본 곳을 얕게 끝냄 (코드 인용 부족, 사례 1~2건만)
  - **도구 사용 누락**: 메인이 grep+read+glob 조합으로 잡을 패턴을 놓침
  - **컨텍스트 누락**: 메모리/CLAUDE.md/관련 메모를 충분히 인지 못함
  - **결과 정형성 부족**: table/우선순위/근거 인용 없이 산문만
  - **메타 인지 부재**: "더 봐야 할 곳" / "확신도" 등 자가 평가 없음
- 평가 시 구체 비교 항목: 깊이 / 정확성 / 도구 활용 / 컨텍스트 인지 / 결과 정형성 / 메타 인지

## Hook 가드 derived-from 우회 경로 (MUST)

`flow-kanban done T-NNN` 호출 시 Hook 가드가 평가하는 derived-from 자식 상태는 **그 호출 시점의 칸반 상태**다. Done 처리 후 추가로 link 한 자식은 가드 대상이 아니다.

### Why
- 룰: derived-from 파생 티켓 미완료 시 원본 Done 차단 (DO NOT 섹션의 derived-from 룰)
- 가드는 unlink 가능. unlink → done → relink 시퀀스로 정상 우회 가능 (관계 추적성 유지)

### How to apply
- **권장 순서 (research → implement)**: research 티켓 Review 진입 → 사용자 검토 → research Done **먼저** → 후속 implement 티켓 등록 + `--derived-from research` link
- **이미 link 된 후 Done 차단 시 우회 시퀀스**:
  1. `flow-kanban unlink T-자식 --derived-from T-부모` (자식 모두 반복)
  2. `flow-kanban done T-부모`
  3. `flow-kanban link T-자식 --derived-from T-부모` (관계 복원)
- Done 후 link 는 부모의 Relations 에 `blocks T-자식` 형태로 표시 (양방향 reverse)
- **가드 우회를 위해 derived-from 을 영구 제거하지 말 것** — 관계 추적성 손실

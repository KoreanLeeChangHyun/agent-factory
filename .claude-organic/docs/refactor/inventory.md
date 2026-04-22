# .claude-organic 리네이밍 인벤토리 — 2026-04-22

본 문서는 `.claude.workflow` → `.claude-organic` 전면 리네이밍 작업의 인벤토리 및 확정 매핑이다. Phase 1~4 작업 중 참조 기준이 된다.

## 대상 규모 (Phase 0 스캔)

| 대상 | 건수 |
|---|---|
| `.claude.workflow` 리터럴 참조 | 480건 |
| `.claude.workflow` 참조 파일 | 약 60 파일 |
| `bin/` alias wrapper (flow-*) | 22개 |
| `.claude/settings.json` hook/permission 참조 | 12건 |
| `.claude.workflow/.settings` 주석 참조 | ~10건 |
| auto memory 참조 (`~/.claude/projects/.../memory/`) | 26건 |
| Python 내부 `from data.constants` import | ~5건 |
| Python `sys.path.insert(..., _scripts_dir)` 패턴 | 7건 |

## 최종 rename map (확정)

### 루트 및 최상위 디렉터리
| 현재 | 변경 | 비고 |
|---|---|---|
| `.claude.workflow/` | `.claude-organic/` | 확정 (사용자 결정) |
| `scripts/` | `engine/` | 설계안 원안 유지 |
| `kanban/` | `tickets/` | 설계안 원안 |
| `workflow/` | `runs/` | 설계안 원안, 런타임 산출물 96M |
| `dashboard/` | `board/data/` | board/ 하위로 흡수 |
| `prompt/` | `prompts/` | 복수형 |
| `init/` | `build-assets/` | build.sh 리소스 |
| `edit/` | `staging/` | flow-claude-edit 작업 영역 |
| `notes/` | `memo/` | 사용자 메모 |
| `.sessions/` | `.terminal-sessions/` | runs/ 와 구분 |
| `bin/`, `hooks/`, `docs/`, `board/`, `.settings`, `.board.url`, `.last-session-id`, `.version`, `build.sh`, `build.url` | 유지 | 이미 명확 |

### `scripts/` 하위 세부 매핑 (설계안 대비 단순화)
| 현재 | 변경 | 근거 |
|---|---|---|
| `scripts/data/constants.py` | `engine/constants.py` | **디렉터리 제거 — flat 단순화**. data/ 내 constants.py 하나만 있어 중간 디렉터리 불필요. `from data.constants` → `from constants`로 import 정합 |
| `scripts/data/colors.sh` | `engine/banners/colors.sh` | banner 관련 sh와 통합 (sh만 있으므로) |
| `scripts/banner/` | `engine/banners/` | 복수형 |
| `scripts/session_start/ensure_bin_path.sh` | `engine/hook-handlers/ensure_bin_path.sh` | 루트 `hooks/`와 충돌 회피 |
| `scripts/flow/` | `engine/flow/` | **유지 — 설계안 매핑 미정 항목 확정**. 워크플로우 엔진 본체라 역할 명확 |
| `scripts/sync/` | `engine/sync/` | 유지 — 역할 명확 |
| `scripts/guards/` | `engine/guards/` | 유지 — 역할 명확 |
| `scripts/slack/` | `engine/slack/` | **`integrations/` 그룹화 포기**. import 변경 최소화 (`from slack.*` 유지 가능) |
| `scripts/git/` | `engine/git/` | 동일 근거 |
| `scripts/common.py` | `engine/common.py` | `lib/` 제거, flat 유지 |
| `scripts/statusline.py` | `engine/statusline.py` | 동일 |
| `scripts/claude_edit.py` | `engine/claude_edit.py` | 동일 |

### 설계안과의 차이 (판단 근거)
1. **`engine/lib/` 제거**: lib 하위에 3개 파일만 두는 것이 과도한 계층. flat 유지가 Claude 이해도에도 더 나음.
2. **`engine/integrations/` 제거**: slack/git을 integrations/ 하위로 2단 중첩하면 `from slack.slack_common` → `from integrations.slack.slack_common`이 되어 import 이름이 길어짐. 그룹화 가치보다 import 단순성 우선.
3. **`engine/constants/` 제거**: constants.py 단일 파일을 디렉터리로 만들지 않고 `engine/constants.py`로 flat. 단, Python import는 `from data.constants` → `from constants`로 변경 필요.

## Python import 전략

### 기본 원칙
- **sys.path 기반 flat namespace 유지** (정식 package 구조 전환은 스코프 외)
- `sys.path.insert(0, _engine_dir)` 로 `engine/`을 path에 추가 (변수명 `_scripts_dir` → `_engine_dir` 일괄 치환)

### 변경 대상 import
| 현재 | 변경 | 영향 파일 |
|---|---|---|
| `from data.constants import ...` | `from constants import ...` | statusline.py, sync/usage_sync.py, flow/stuck_detector.py, sync/history_sync.py, flow/initialization.py |
| `from slack.slack_common import ...` | **유지** | slack_ask.py, slack_notify.py |
| `from flow.xxx import ...` | **유지** | flow/ 내 다수 |
| `from sync.xxx import ...` | **유지** | - |
| `from guards.xxx import ...` | **유지** | - |

## 영향 파일 카탈로그

### `.claude/` (hook으로 직접 수정 차단됨 → `flow-claude-edit` 경유 또는 hook 일시 우회)
- `.claude/settings.json` (12건)
- `.claude/rules/workflow/general.md`, `workflow.md`
- `.claude/skills/*/SKILL.md` 및 reference/*.md (~10파일)
- `.claude/commands/{wf,sync/*,git/*}.md`
- `.claude/agents/*.md` (~8 파일)

### `.claude.workflow/` 내부 (직접 수정 가능)
- `build.sh`
- `bin/flow-*` (22개 wrapper)
- `scripts/**/*.py` (~50 파일, `.claude.workflow` 리터럴 포함 파일 ~20건)
- `hooks/*.py` (5개)
- `prompt/messages.py`
- `board/**` (Python + JS + CSS)

### `init-claude-workflow.sh` (루트)
- 프로젝트 초기화 스크립트 — `.claude.workflow` 생성 경로 포함

### `~/.claude/projects/-home-deus-workspace-claude/memory/*` (auto memory)
- 26건 참조 — Phase 4에서 일괄 치환

## Phase별 실행 순서 (확정)

| Phase | 범위 | 원자 커밋 |
|---|---|---|
| **P0 (본 문서)** | 인벤토리 + rename map 박제 | 1 |
| **P1** | 루트 `.claude.workflow/` → `.claude-organic/` **git mv만** + `.claude/settings.json` + `init-claude-workflow.sh` + `.claude/rules/*`에 포함된 리터럴 치환. 내부 디렉터리 구조는 미변경 | 1 |
| **P2** | 내부 디렉터리 rename (scripts→engine, kanban→tickets 등) + bin/* wrapper 경로 갱신 + Python import 치환 (`from data.constants` → `from constants`, `_scripts_dir` → `_engine_dir`) | 2 (디렉터리 rename / import 치환) |
| **P3** | 스모크 — bin/flow-* 22개, Board 기동, 세션, hook 4개. 회귀 시 보정 | 1 |
| **P4** | 문서/메모리 동기화 — CLAUDE.md 하위 참조, auto memory 26건, `.claude.workflow/.settings` 주석 | 1 |

## 리스크 및 대응

### R1. `.claude/` 수정 차단 hook
- 정책: `flow-claude-edit open/save` 경유가 원칙 (`.claude/rules/workflow/general.md`)
- 수정 대상 수십 파일 → claude_edit 스테이징 경유 비효율
- **대응**: Phase 1 시작 전 `hooks_self_guard.py` 또는 관련 PreToolUse 블록을 임시 우회. Phase 1/4 종료 후 hook 복원. hook 자체가 rename 대상(`scripts/` 경로 포함)이므로 Phase 2에서 차단 해제 없이도 자연스럽게 갱신됨.

### R2. 진행 중 도구 자기 수정
- `flow-claude-edit` 자체가 `.claude.workflow/scripts/claude_edit.py` → rename 대상
- Phase 1에서 루트만 rename하면 `.claude-organic/scripts/claude_edit.py`로 살아남음. Phase 2에서 내부도 rename되면서 `.claude-organic/engine/claude_edit.py`로 최종 이동.
- 각 Phase 커밋 직후 bin/* wrapper 경로도 같이 갱신되어 alias 기능 유지.

### R3. 런타임 산출물 경로
- `.board.url`, `.last-session-id`, `.sessions/*` — 루트 rename만으로 위치 자동 변경. 내부 참조 코드는 `scripts/common.py`의 `resolve_project_root`가 `$CLAUDE_PROJECT_DIR/.claude.workflow`를 하드코딩한 곳이면 치환 필요. → Phase 1 literal 치환으로 커버.

### R4. Git history
- 모든 rename은 `git mv`로 수행. `git log --follow`로 이력 추적 유지.

## 선행 조건 상태 (Phase 0 완료 시점)

- [x] origin/develop push 완료 (15b5e28 포함)
- [x] 신규 브랜치 `refactor/claude-organic-rename` 생성
- [x] 본 인벤토리 문서 작성
- [ ] Phase 1 착수

## 참고 커밋
- `6178aad docs: T-379 Board 전면 리팩토링 플랜 박제` — Phase 분할 전략 참고
- `d6b6ac6 refactor(T-379): Phase 0-1 static/ 구조 생성` — git mv 패턴 참고

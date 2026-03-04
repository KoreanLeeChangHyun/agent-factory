---
name: workflow-system-script-convention
description: "Script naming, placement, and alias registration conventions for the Claude Code workflow system. Covers flow-* alias registration rules, Bash chaining prohibition, naming conventions (flow-* prefix), and script directory placement. Use when creating new scripts, modifying existing scripts, or adding new aliases. Triggers: 'scripts', '스크립트', 'alias', 'aliases', '알리아스', 'flow-', 'flow-*', '배너', 'banner', 'init-claude-workflow', '컨벤션', 'convention'."
license: "Apache-2.0"
---

# 스크립트 컨벤션 가이드

## 설명

오케스트레이터 및 워크플로우 시스템에서 사용하는 스크립트의 신규 생성, 수정, alias 추가 시 준수해야 할 컨벤션입니다.

## 사용 시기

- 새로운 스크립트를 신규 생성할 때
- 기존 스크립트를 수정하거나 이동할 때
- 오케스트레이터에서 호출할 alias를 추가할 때

---

## 규칙 체크리스트

### 1. alias 등록 필수

- [ ] 오케스트레이터(Bash 도구)에서 직접 호출하는 스크립트는 `init-claude-workflow.sh`의 `setup_shell_aliases()` 함수에 `flow-*` alias로 반드시 등록한다
- [ ] alias 미등록 스크립트는 오케스트레이터에서 직접 호출할 수 없다 (절대 경로 호출은 컨벤션 위반)
- [ ] alias 추가 후 `$HOME/.claude.aliases`에 정상 반영되는지 확인한다

### 2. 체이닝 금지

- [ ] 오케스트레이터의 Bash 도구 호출 시 `&&` 또는 `;` 체이닝을 사용하지 않는다
- [ ] 두 스크립트를 연속 실행해야 할 경우, 단일 모드로 통합한 새 핸들러를 추가한다
- [ ] 예외: Hook 스크립트 내부 로직은 체이닝 가능하나, 오케스트레이터 호출 레이어에서는 단일 명령 원칙 준수

**허용 예시:**
```bash
flow-update task-start <registryKey> W01 W02
```

**금지 예시:**
```bash
flow-update task-status <registryKey> running W01 W02 && flow-update usage-pending <registryKey> W01 W02
```

### 3. 네이밍 컨벤션

- [ ] 오케스트레이터용 alias는 `flow-` 접두사를 사용한다
- [ ] 배너 스크립트: `flow-claude`, `flow-step`, `flow-phase` 형태
- [ ] 플로우 제어 스크립트: `flow-init`, `flow-finish`, `flow-reload`, `flow-update` 형태
- [ ] 유틸리티 스크립트: `flow-gc`, `flow-skillmap`, `flow-validate` 형태
- [ ] 스크립트 파일명은 snake_case 사용 (예: `flow_claude_banner.sh`, `initialization.py`)

### 4. 위치 규칙

- [ ] 배너 출력 스크립트는 `.claude/scripts/banner/`에 위치한다
- [ ] 워크플로우 흐름 제어 스크립트는 `.claude/scripts/flow/`에 위치한다
- [ ] 가드/보안 스크립트는 `.claude/scripts/guards/`에 위치한다
- [ ] 동기화 스크립트는 `.claude/scripts/sync/`에 위치한다
- [ ] Hook 디스패처는 `.claude/hooks/`에 위치한다 (실제 로직은 `scripts/`에 분리)

---

## 현재 등록된 alias 목록

| alias | 스크립트 경로 | 용도 |
|-------|-------------|------|
| `flow-claude` | `.claude/scripts/banner/flow_claude_banner.sh` | 워크플로우 시작/종료 배너 |
| `flow-step` | `.claude/scripts/banner/flow_step_banner.sh` | 스텝 시작/종료 배너 |
| `flow-phase` | `.claude/scripts/banner/flow_phase_banner.sh` | WORK 페이즈 배너 |
| `flow-init` | `python3 .claude/scripts/flow/initialization.py` | 워크플로우 초기화 |
| `flow-finish` | `python3 .claude/scripts/flow/finalization.py` | 워크플로우 마무리 처리 |
| `flow-reload` | `python3 .claude/scripts/flow/reload_prompt.py` | 프롬프트 리로드 |
| `flow-update` | `python3 .claude/scripts/flow/update_state.py` | 워크플로우 상태 관리 |
| `flow-skillmap` | `python3 .claude/scripts/flow/skill_mapper.py` | 태스크별 스킬 매핑 생성 |
| `flow-validate` | `python3 .claude/scripts/flow/plan_validator.py` | 계획서 유효성 검증 |
| `flow-validate-p` | `python3 .claude/scripts/flow/prompt_validator.py` | 프롬프트 유효성 검증 |
| `flow-recommend` | `python3 .claude/scripts/flow/skill_recommender.py` | 스킬 자동 추천 |
| `flow-gc` | `python3 .claude/scripts/flow/garbage_collect.py` | 좀비 워크플로우 정리 |

> alias 추가 시 `init-claude-workflow.sh`의 `setup_shell_aliases()` 함수 내 `.claude.aliases` heredoc에 항목을 추가한다.

---

## 참고

- `init-claude-workflow.sh` — alias 등록 위치 (`setup_shell_aliases()` 함수)
- `.claude/scripts/` — 실제 로직 스크립트 디렉터리
- workflow-system-hooks-guide 스킬 — Hook 이벤트와 스크립트 연동 방법

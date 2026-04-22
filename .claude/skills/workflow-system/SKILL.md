---
name: workflow-system
description: "Claude Code workflow system infrastructure skills: hooks system management, report output generation, script naming conventions, CLI status line configuration, and verification before completion. Triggers: 'hook', '훅', 'PreToolUse', 'PostToolUse', 'Hook 설정', 'rm -rf', 'git reset --hard', 'git push --force', '위험 명령어', 'dangerous command', 'changelog', 'release notes', '변경 이력', '릴리스 노트', 'PR', 'pull request', 'PR 요약', 'scripts', '스크립트', 'alias', 'flow-', 'statusline 설정', '상태줄 설정', 'Done', 'Complete', '완료', '끝', 'PASS', '통과'."
license: "Apache-2.0"
---

# Workflow System

Claude Code 워크플로우 시스템의 인프라 스킬 모음. Hooks, Report Output, Script Convention, StatusLine, Verification 5개 시스템 스킬을 통합한다.

## 구성

| 스킬 | 용도 | 상세 |
|------|------|------|
| Hooks Guide | Hook 이벤트, 설정, 위험 명령어 차단 | [reference/hooks-guide.md](reference/hooks-guide.md) |
| Report Output | CHANGELOG, 릴리스 노트, PR 요약 생성 | [reference/report-output.md](reference/report-output.md) |
| Script Convention | alias 등록, 네이밍, 위치 규칙 | 아래 섹션 직접 포함 |
| StatusLine | CLI 하단 상태줄 설정 | 아래 섹션 직접 포함 |
| Verification | 완료 선언 전 검증 원칙 | [reference/verification.md](reference/verification.md) |

---

## 스크립트 컨벤션 가이드

오케스트레이터 및 워크플로우 시스템에서 사용하는 스크립트의 신규 생성, 수정, alias 추가 시 준수해야 할 컨벤션.

**사용 시기**: 새로운 스크립트 신규 생성, 기존 스크립트 수정/이동, 오케스트레이터에서 호출할 alias 추가

### 규칙 체크리스트

#### 1. alias 등록 필수

- [ ] 오케스트레이터(Bash 도구)에서 직접 호출하는 스크립트는 `build.sh`의 `setup_shell_aliases()` 함수에 `flow-*` alias로 반드시 등록
- [ ] alias 미등록 스크립트는 오케스트레이터에서 직접 호출 불가 (절대 경로 호출은 컨벤션 위반)
- [ ] alias 추가 후 `$HOME/.claude.aliases`에 정상 반영되는지 확인

#### 2. 체이닝 금지

- [ ] 오케스트레이터의 Bash 도구 호출 시 `&&` 또는 `;` 체이닝 사용 금지
- [ ] 두 스크립트를 연속 실행해야 할 경우, 단일 모드로 통합한 새 핸들러 추가
- [ ] 예외: Hook 스크립트 내부 로직은 체이닝 가능하나, 오케스트레이터 호출 레이어에서는 단일 명령 원칙 준수

**허용 예시:**
```bash
flow-update task-start <registryKey> W01 W02
```

**금지 예시:**
```bash
flow-update task-status <registryKey> running W01 W02 && flow-update usage-pending <registryKey> W01 W02
```

#### 3. 네이밍 컨벤션

- [ ] 오케스트레이터용 alias는 `flow-` 접두사 사용
- [ ] 배너 스크립트: `flow-claude`, `flow-step`, `flow-phase` 형태
- [ ] 플로우 제어 스크립트: `flow-init`, `flow-finish`, `flow-reload`, `flow-update` 형태
- [ ] 유틸리티 스크립트: `flow-gc`, `flow-skillmap`, `flow-validate` 형태
- [ ] 스크립트 파일명은 snake_case 사용 (예: `flow_claude_banner.sh`, `initialization.py`)

#### 4. 위치 규칙

- [ ] 배너 출력 스크립트: `.claude-organic/engine/banners/`
- [ ] 워크플로우 흐름 제어 스크립트: `.claude-organic/engine/flow/`
- [ ] 가드/보안 스크립트: `.claude-organic/engine/guards/`
- [ ] 동기화 스크립트: `.claude-organic/engine/sync/`
- [ ] Hook 디스패처: `.claude-organic/hooks/` (실제 로직은 `scripts/`에 분리)

### 현재 등록된 alias 목록

| alias | 스크립트 경로 | 용도 |
|-------|-------------|------|
| `flow-claude` | `.claude-organic/engine/banners/flow_claude_banner.sh` | 워크플로우 시작/종료 배너 |
| `flow-step` | `.claude-organic/engine/banners/flow_step_banner.sh` | 스텝 시작/종료 배너 |
| `flow-phase` | `.claude-organic/engine/banners/flow_phase_banner.sh` | WORK 페이즈 배너 |
| `flow-init` | `python3 .claude-organic/engine/flow/initialization.py` | 워크플로우 초기화 |
| `flow-finish` | `python3 .claude-organic/engine/flow/finalization.py` | 워크플로우 마무리 처리 |
| `flow-reload` | `python3 .claude-organic/engine/flow/reload_prompt.py` | 프롬프트 리로드 |
| `flow-update` | `python3 .claude-organic/engine/flow/update_state.py` | 워크플로우 상태 관리 |
| `flow-skillmap` | `python3 .claude-organic/engine/flow/skill_mapper.py` | 태스크별 스킬 매핑 생성 |
| `flow-validate` | `python3 .claude-organic/engine/flow/plan_validator.py` | 계획서 유효성 검증 |
| `flow-validate-p` | `python3 .claude-organic/engine/flow/prompt_validator.py` | 프롬프트 유효성 검증 |
| `flow-recommend` | `python3 .claude-organic/engine/flow/skill_recommender.py` | 스킬 자동 추천 |
| `flow-gc` | `python3 .claude-organic/engine/flow/garbage_collect.py` | 좀비 워크플로우 정리 |
| `flow-kanban` | `python3 .claude-organic/engine/flow/kanban.py` | 칸반 보드 관리 |
| `flow-merge` | `python3 .claude-organic/engine/flow/merge_pipeline.py` | PR 기반 머지 파이프라인 |
| `flow-launcher` | `.claude-organic/bin/flow-launcher` | HTTP API 기반 워크플로우 세션 실행 |
| `flow-history` | `python3 .claude-organic/engine/sync/history_sync.py` | 히스토리 동기화 |
| `flow-catalog` | `python3 .claude-organic/engine/sync/catalog_sync.py` | 스킬 카탈로그 재생성 |
| `flow-gitconfig` | `python3 .claude-organic/engine/git/git_config.py` | Git config 설정 |
| `flow-detect` | `python3 .claude-organic/engine/flow/project_skill_detector.py` | 프로젝트 스킬 감지 |

> alias 추가 시 `build.sh`의 `setup_shell_aliases()` 함수 내 `.claude.aliases` heredoc에 항목을 추가한다.

**참고**: `build.sh` (alias 등록 위치), `.claude-organic/engine/` (실제 로직 스크립트 디렉터리), [reference/hooks-guide.md](reference/hooks-guide.md) (Hook 이벤트와 스크립트 연동 방법)

---

## StatusLine Setup

Claude Code CLI의 하단 상태줄(StatusLine)을 설정한다.

**사용 시기**: StatusLine settings.json 등록, statusline.sh 스크립트 작성/수정, 상태줄 표시 내용 커스터마이징

### 구조

1. **설정** (`~/.claude/settings.json`): StatusLine 활성화 및 스크립트 경로 지정
2. **스크립트** (`~/.claude/statusline.sh`): 실제 표시 내용을 출력하는 Python/Bash 스크립트

### settings.json 등록

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 0
  }
}
```

### 입력 JSON 구조

스크립트는 **stdin으로 JSON 데이터**를 받아 **stdout으로 표시할 문자열**을 출력한다.

```json
{
  "model": { "display_name": "Opus 4.5" },
  "cost": { "total_lines_added": 42, "total_lines_removed": 10 },
  "context_window": {
    "context_window_size": 200000,
    "current_usage": {
      "input_tokens": 50000,
      "cache_creation_input_tokens": 10000,
      "cache_read_input_tokens": 5000
    }
  },
  "workspace": { "current_dir": "/path/to/project" }
}
```

### ANSI 색상 코드

| 코드 | 색상 |
|------|------|
| `\033[31m` | 빨강 |
| `\033[32m` | 초록 |
| `\033[33m` | 노랑 |
| `\033[34m` | 파랑 |
| `\033[35m` | 보라 |
| `\033[36m` | 시안 |
| `\033[90m` | 회색 |
| `\033[0m` | 리셋 |

### 워크플로우 세션 필터링

StatusLine은 **현재 터미널 세션에 연결된 워크플로우만** 표시한다.

**필터링 흐름:**
1. 환경변수 `CLAUDE_SESSION_ID`에서 현재 세션 ID 획득
2. `.workflow/` 디렉터리 스캔으로 활성 워크플로우 탐색
3. 각 워크플로우의 `status.json`에서 세션 소유권 확인:
   - `session_id` 필드: 오케스트레이터(메인) 세션 ID
   - `linked_sessions` 배열: 워커/리포터 등 하위 세션 ID 목록
4. 현재 세션 ID가 `session_id` 또는 `linked_sessions`에 포함된 워크플로우를 표시

**폴백**: `CLAUDE_SESSION_ID` 미설정 또는 매칭 워크플로우 없으면 워크플로우 표시 생략

### Step별 색상 코드

| Step | 색상 | ANSI 코드 |
|------|------|-----------|
| INIT | 빨강(Red) | `\033[31m` |
| PLAN | 파랑(Blue) | `\033[34m` |
| WORK | 초록(Green) | `\033[32m` |
| REPORT | 보라(Magenta) | `\033[35m` |

제목이 30자를 초과하면 30자로 잘라내고 "..."을 붙인다.

### 기본 템플릿 (Python)

```python
#!/usr/bin/env python3
import json, sys, subprocess, os

data = json.load(sys.stdin)

model = data.get("model", {}).get("display_name", "?")
added = data.get("cost", {}).get("total_lines_added", 0)
removed = data.get("cost", {}).get("total_lines_removed", 0)
ctx_size = data.get("context_window", {}).get("context_window_size", 0)
usage = data.get("context_window", {}).get("current_usage")
cwd = data.get("workspace", {}).get("current_dir", "")

pct = 0
if usage and ctx_size:
    tokens = (usage.get("input_tokens", 0)
              + usage.get("cache_creation_input_tokens", 0)
              + usage.get("cache_read_input_tokens", 0))
    pct = tokens * 100 // ctx_size

branch = ""
try:
    b = subprocess.check_output(
        ["git", "-C", cwd, "branch", "--show-current"],
        stderr=subprocess.DEVNULL, timeout=2
    ).decode().strip()
    if b:
        branch = f" \033[33m{b}\033[0m"
except Exception:
    pass

STEP_COLORS = {
    "INIT":     "\033[31m",
    "PLAN":     "\033[34m",
    "WORK":     "\033[32m",
    "REPORT":   "\033[35m",
}
RESET = "\033[0m"

workflow_display = ""
current_session = os.environ.get("CLAUDE_SESSION_ID", "")
if cwd and current_session:
    workflow_dir = os.path.join(cwd, ".claude-organic", "workflow")
    try:
        for date_dir in sorted(os.listdir(workflow_dir), reverse=True):
            date_path = os.path.join(workflow_dir, date_dir)
            if not os.path.isdir(date_path) or date_dir.startswith("."):
                continue
            for name_dir in os.listdir(date_path):
                name_path = os.path.join(date_path, name_dir)
                if not os.path.isdir(name_path):
                    continue
                for cmd_dir in os.listdir(name_path):
                    work_dir = os.path.join(".claude-organic", "workflow", date_dir, name_dir, cmd_dir)
                    status_path = os.path.join(cwd, work_dir, "status.json")
                    try:
                        with open(status_path, "r") as sf:
                            wf_status = json.load(sf)
                    except Exception:
                        continue
                    orch_sid = wf_status.get("session_id", "")
                    linked = wf_status.get("linked_sessions", [])
                    if current_session != orch_sid and current_session not in linked:
                        continue
                    title = wf_status.get("title", "")
                    step = wf_status.get("step", "") or wf_status.get("phase", "")
                    if len(title) > 30:
                        title = title[:30] + "..."
                    step_color = STEP_COLORS.get(step, "\033[90m")
                    if step:
                        workflow_display = f" {step_color}[{step}]{RESET} {title}"
                    elif title:
                        workflow_display = f" \033[90m{title}{RESET}"
                    break
    except Exception:
        pass

print(f"\033[36m{model}\033[0m{workflow_display}{branch} \033[35mctx:{pct}%\033[0m \033[32m+{added}\033[0m/\033[31m-{removed}\033[0m")
```

### 설정 절차

1. `~/.claude/settings.json` 읽기
2. `statusLine` 항목 존재 확인
3. 없으면 추가, 있으면 현재 설정 표시
4. `~/.claude/statusline.sh` 존재 확인
5. 없으면 기본 템플릿으로 생성, 있으면 현재 내용 표시
6. 스크립트에 실행 권한 부여: `chmod +x ~/.claude/statusline.sh`

**커스터마이징 옵션**: 모델명, 에이전트 표시, Git 브랜치, 컨텍스트 사용률, 추가/삭제 라인 수, 비용 정보, 색상/레이블 변경

---

## 참고

- **Hooks 시스템 상세**: [reference/hooks-guide.md](reference/hooks-guide.md)
- **Report Output 생성**: [reference/report-output.md](reference/report-output.md)
- **Verification 원칙**: [reference/verification.md](reference/verification.md)

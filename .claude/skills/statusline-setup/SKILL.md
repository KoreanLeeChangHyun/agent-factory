---
name: statusline-setup
description: "Claude Code CLI 하단 상태줄(StatusLine) 설정 스킬. Use for StatusLine configuration tasks: (1) settings.json에 StatusLine 등록, (2) statusline.sh 스크립트 작성/수정, (3) 상태줄 표시 내용 커스터마이징. 트리거: 'statusline 설정', '상태줄 설정', 'statusline 수정', 'status line 변경', 'init:statusLine'."
---

# StatusLine Setup

Claude Code CLI의 하단 상태줄(StatusLine)을 설정합니다.

## 구조

StatusLine은 두 가지로 구성됩니다:

1. **설정** (`~/.claude/settings.json`): StatusLine 활성화 및 스크립트 경로 지정
2. **스크립트** (`~/.claude/statusline.sh`): 실제 표시 내용을 출력하는 Python/Bash 스크립트

## 설정 방법

### 1. settings.json에 StatusLine 등록

`~/.claude/settings.json`에 아래 항목 추가:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 0
  }
}
```

### 2. StatusLine 스크립트 작성

스크립트는 **stdin으로 JSON 데이터**를 받아 **stdout으로 표시할 문자열**을 출력합니다.

#### 입력 JSON 구조

```json
{
  "model": { "display_name": "Opus 4.5" },
  "cost": {
    "total_lines_added": 42,
    "total_lines_removed": 10
  },
  "context_window": {
    "context_window_size": 200000,
    "current_usage": {
      "input_tokens": 50000,
      "cache_creation_input_tokens": 10000,
      "cache_read_input_tokens": 5000
    }
  },
  "workspace": {
    "current_dir": "/path/to/project"
  }
}
```

#### 사용 가능한 ANSI 색상 코드

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

#### 워크플로우 세션 필터링

StatusLine은 **현재 터미널 세션에 연결된 워크플로우만** 표시합니다. 여러 터미널에서 각각 다른 워크플로우를 실행할 때, 각 터미널은 자신의 워크플로우만 상태줄에 표시합니다.

**필터링 흐름:**

1. 환경변수 `CLAUDE_SESSION_ID`에서 현재 세션 ID를 획득
2. `.workflow/registry.json`의 각 워크플로우 엔트리를 순회
3. 각 워크플로우의 `status.json`에서 세션 소유권을 확인:
   - `session_id` 필드: 오케스트레이터(메인) 세션 ID
   - `linked_sessions` 배열: 워커/리포터 등 하위 세션 ID 목록
4. 현재 세션 ID가 `session_id` 또는 `linked_sessions`에 포함된 워크플로우를 표시

**폴백 동작:**

- `CLAUDE_SESSION_ID`가 설정되지 않은 경우: 워크플로우 표시 생략
- 매칭되는 워크플로우가 없는 경우: 워크플로우 표시 생략
- `status.json` 읽기 실패: 해당 워크플로우를 건너뛰고 다음 엔트리 검사

#### 워크플로우 Phase별 색상 코드

StatusLine은 세션 필터링을 통해 매칭된 워크플로우의 **Phase(단계)**와 **제목(title)**을 `[PHASE] 제목` 또는 `[PHASE:agent] 제목` 형식으로 표시합니다. Phase별 색상은 `banner.sh`의 색상 체계와 일치합니다.

| Phase | 색상 | ANSI 코드 | 의미 |
|-------|------|-----------|------|
| INIT | 빨강(Red) | `\033[31m` | 초기화 |
| PLAN | 파랑(Blue) | `\033[34m` | 계획 |
| WORK | 초록(Green) | `\033[32m` | 실행 |
| REPORT | 보라(Magenta) | `\033[35m` | 보고 |

워크플로우가 비활성이거나 현재 세션에 매칭되는 워크플로우가 없으면 Phase/제목 표시를 생략하고 기존 포맷을 유지합니다.
제목이 30자를 초과하면 30자로 잘라내고 "..."을 붙입니다.

#### 기본 템플릿 (Python)

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

# Phase color mapping (ANSI codes)
PHASE_COLORS = {
    "INIT":     "\033[31m",   # Red
    "PLAN":     "\033[34m",   # Blue
    "WORK":     "\033[32m",   # Green
    "REPORT":   "\033[35m",   # Magenta
}
RESET = "\033[0m"

# Read workflow info filtered by current session
# Uses CLAUDE_SESSION_ID to match against status.json's
# session_id (orchestrator) and linked_sessions (workers)
workflow_display = ""
current_session = os.environ.get("CLAUDE_SESSION_ID", "")
if cwd and current_session:
    registry_path = os.path.join(cwd, ".workflow", "registry.json")
    try:
        with open(registry_path, "r") as f:
            registry = json.load(f)
        if registry and isinstance(registry, dict):
            for key, entry in registry.items():
                work_dir = entry.get("workDir", "")
                if not work_dir:
                    continue
                # Check session ownership via status.json
                status_path = os.path.join(cwd, work_dir, "status.json")
                try:
                    with open(status_path, "r") as sf:
                        status = json.load(sf)
                except Exception:
                    continue
                orch_sid = status.get("session_id", "")
                linked = status.get("linked_sessions", [])
                if current_session != orch_sid and current_session not in linked:
                    continue
                title = entry.get("title", "")
                phase = entry.get("phase", "")
                if len(title) > 30:
                    title = title[:30] + "..."
                phase_color = PHASE_COLORS.get(phase, "\033[90m")
                if phase:
                    workflow_display = f" {phase_color}[{phase}]{RESET} {title}"
                elif title:
                    workflow_display = f" \033[90m{title}{RESET}"
                break  # 매칭된 첫 번째 워크플로우만 사용
    except Exception:
        pass

print(f"\033[36m{model}\033[0m{workflow_display}{branch} \033[35mctx:{pct}%\033[0m \033[32m+{added}\033[0m/\033[31m-{removed}\033[0m")
```

## 설정 절차

1. `~/.claude/settings.json` 읽기
2. `statusLine` 항목 존재 확인
3. 없으면 추가, 있으면 현재 설정 표시
4. `~/.claude/statusline.sh` 존재 확인
5. 없으면 기본 템플릿으로 생성, 있으면 현재 내용 표시
6. 스크립트에 실행 권한 부여: `chmod +x ~/.claude/statusline.sh`

## 커스터마이징 옵션

사용자 요청에 따라 아래 항목을 추가/제거 가능:

- **모델명**: `data["model"]["display_name"]`
- **에이전트 표시**: `.workflow/registry.json` -> `status.json`의 세션 매칭 -> `.context.json`의 `agent` 필드 (에이전트별 고유 색상)
- **Git 브랜치**: `git branch --show-current`
- **컨텍스트 사용률**: 입력 토큰 / 컨텍스트 윈도우 크기
- **추가/삭제 라인 수**: `total_lines_added`, `total_lines_removed`
- **비용 정보**: `data["cost"]` (API 비용)
- **색상 변경**: ANSI 코드 수정
- **레이블 변경**: 한글/영어 등

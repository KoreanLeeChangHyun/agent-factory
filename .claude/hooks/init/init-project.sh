#!/bin/bash
# init-project.sh - 프로젝트 분석 및 초기화 스크립트
# 사용법: ./init-project.sh <subcommand> [options]
#
# 서브커맨드:
#   analyze                프로젝트 분석 (JSON 결과 stdout 출력)
#   generate-claude-md     CLAUDE.md 생성 (stdin으로 analyze JSON 수신)
#   generate-empty-template CLAUDE.md 빈 템플릿 생성 (analyze 없이 프로젝트명만)
#   setup-dirs             디렉토리 + 파일 생성
#   setup-gitignore        .gitignore 업데이트 (중복 체크)
#   setup-wf-alias         워크플로우 alias 설정 (~/.zshrc + ~/.local/bin wrapper)
#   verify                 전체 검증

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ---------- 유틸리티 ----------

json_escape() {
  # JSON 문자열 이스케이프 (개행, 탭, 백슬래시, 따옴표)
  printf '%s' "$1" | python3 -c '
import json, sys
print(json.dumps(sys.stdin.read()), end="")
'
}

err() {
  echo "[ERROR] $*" >&2
  exit 1
}

warn() {
  echo "[WARN] $*" >&2
}

# ---------- analyze ----------

cmd_analyze() {
  cd "$PROJECT_ROOT"

  # --- 프로젝트 이름 ---
  local project_name
  project_name="$(basename "$PROJECT_ROOT")"

  # --- 프로젝트 설명 ---
  local project_description=""
  if [ -f package.json ]; then
    project_description=$(python3 -c '
import json, sys
try:
    d = json.load(open("package.json"))
    print(d.get("description",""), end="")
except Exception:
    pass
' 2>/dev/null || true)
  fi

  # --- 언어 감지 ---
  local languages=()

  if [ -f tsconfig.json ]; then
    languages+=("TypeScript")
  fi
  if [ -f package.json ]; then
    languages+=("JavaScript")
  fi
  if [ -f requirements.txt ] || [ -f pyproject.toml ] || [ -f Pipfile ] || [ -f setup.py ]; then
    languages+=("Python")
  fi
  if [ -f go.mod ]; then
    languages+=("Go")
  fi
  if [ -f Cargo.toml ]; then
    languages+=("Rust")
  fi
  if [ -f Gemfile ]; then
    languages+=("Ruby")
  fi
  if [ -f pom.xml ] || [ -f build.gradle ] || [ -f build.gradle.kts ]; then
    languages+=("Java/Kotlin")
  fi
  if compgen -G "*.csproj" >/dev/null 2>&1 || compgen -G "*.sln" >/dev/null 2>&1; then
    languages+=("C#")
  fi
  if [ -f composer.json ]; then
    languages+=("PHP")
  fi
  # 언어를 감지 못한 경우 Markdown/Shell 검사
  if [ ${#languages[@]} -eq 0 ]; then
    if compgen -G "*.md" >/dev/null 2>&1 || compgen -G "*.sh" >/dev/null 2>&1; then
      languages+=("Markdown" "Shell")
    else
      languages+=("Unknown")
    fi
  fi

  local detected_languages
  detected_languages=$(printf '%s\n' "${languages[@]}" | sort -u | paste -sd ',' - | sed 's/,/, /g')

  # --- 프레임워크 감지 ---
  local frameworks=()

  # JavaScript/TypeScript 프레임워크
  if [ -f package.json ]; then
    local pkg_content
    pkg_content=$(cat package.json 2>/dev/null || echo '{}')
    local fw_keywords=("react:React" "next:Next.js" "vue:Vue.js" "nuxt:Nuxt.js" "angular:Angular" "express:Express" "fastify:Fastify" "@nestjs:NestJS" "electron:Electron")
    for entry in "${fw_keywords[@]}"; do
      local keyword="${entry%%:*}"
      local name="${entry#*:}"
      if echo "$pkg_content" | grep -q "\"$keyword\""; then
        frameworks+=("$name")
      fi
    done
  fi

  # Python 프레임워크
  local py_deps=""
  if [ -f requirements.txt ]; then
    py_deps=$(cat requirements.txt 2>/dev/null || true)
  fi
  if [ -f pyproject.toml ]; then
    py_deps="$py_deps $(cat pyproject.toml 2>/dev/null || true)"
  fi
  if [ -n "$py_deps" ]; then
    local py_keywords=("fastapi:FastAPI" "django:Django" "flask:Flask" "streamlit:Streamlit" "torch:PyTorch" "pytorch:PyTorch" "tensorflow:TensorFlow")
    for entry in "${py_keywords[@]}"; do
      local keyword="${entry%%:*}"
      local name="${entry#*:}"
      if echo "$py_deps" | grep -qi "$keyword"; then
        frameworks+=("$name")
      fi
    done
  fi

  # Go 프레임워크
  if [ -f go.mod ]; then
    local go_content
    go_content=$(cat go.mod 2>/dev/null || true)
    local go_keywords=("gin-gonic/gin:Gin" "labstack/echo:Echo" "gofiber/fiber:Fiber")
    for entry in "${go_keywords[@]}"; do
      local keyword="${entry%%:*}"
      local name="${entry#*:}"
      if echo "$go_content" | grep -q "$keyword"; then
        frameworks+=("$name")
      fi
    done
  fi

  local detected_frameworks="None"
  if [ ${#frameworks[@]} -gt 0 ]; then
    detected_frameworks=$(printf '%s\n' "${frameworks[@]}" | sort -u | paste -sd ',' - | sed 's/,/, /g')
  fi

  # --- 주요 의존성 추출 (상위 10개) ---
  local key_dependencies="None"
  if [ -f package.json ]; then
    key_dependencies=$(python3 -c '
import json, sys
try:
    d = json.load(open("package.json"))
    deps = list(d.get("dependencies", {}).keys())[:10]
    if deps:
        print(", ".join(deps), end="")
    else:
        print("None", end="")
except Exception:
    print("None", end="")
' 2>/dev/null || echo "None")
  elif [ -f requirements.txt ]; then
    key_dependencies=$(head -10 requirements.txt 2>/dev/null | sed 's/[>=<].*//' | paste -sd ',' - | sed 's/,/, /g')
    [ -z "$key_dependencies" ] && key_dependencies="None"
  elif [ -f pyproject.toml ]; then
    key_dependencies=$(python3 -c '
import sys, re
content = open("pyproject.toml").read()
m = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
if m:
    deps = re.findall(r"\"([^\">=<\[]+)", m.group(1))[:10]
    print(", ".join(deps), end="") if deps else print("None", end="")
else:
    print("None", end="")
' 2>/dev/null || echo "None")
  fi

  # --- 패키지 매니저 감지 ---
  local package_manager="None"
  if [ -f pnpm-lock.yaml ]; then
    package_manager="pnpm"
  elif [ -f yarn.lock ]; then
    package_manager="yarn"
  elif [ -f bun.lockb ]; then
    package_manager="bun"
  elif [ -f package-lock.json ]; then
    package_manager="npm"
  elif [ -f poetry.lock ]; then
    package_manager="poetry"
  elif [ -f Pipfile.lock ]; then
    package_manager="pipenv"
  fi

  # --- 런타임 감지 ---
  local runtime="None"
  if [ -f .nvmrc ]; then
    runtime="Node.js $(cat .nvmrc 2>/dev/null | tr -d '[:space:]')"
  elif [ -f .node-version ]; then
    runtime="Node.js $(cat .node-version 2>/dev/null | tr -d '[:space:]')"
  elif [ -f .python-version ]; then
    runtime="Python $(cat .python-version 2>/dev/null | tr -d '[:space:]')"
  elif [ -f .ruby-version ]; then
    runtime="Ruby $(cat .ruby-version 2>/dev/null | tr -d '[:space:]')"
  elif [ -f .tool-versions ]; then
    runtime=$(cat .tool-versions 2>/dev/null | head -3 | paste -sd ',' - | sed 's/,/, /g')
  fi

  # --- 디렉토리 구조 분석 ---
  local known_dirs=("src" "lib" "app" "pages" "components" "api" "routes" "controllers" "tests" "test" "__tests__" "docs" "scripts" "packages" "apps" ".claude" ".github" "public" "static" "assets" "cli")
  local existing_dirs=()
  for d in "${known_dirs[@]}"; do
    if [ -d "$d" ]; then
      existing_dirs+=("$d")
    fi
  done

  local existing_directories="None"
  if [ ${#existing_dirs[@]} -gt 0 ]; then
    existing_directories=$(printf '%s\n' "${existing_dirs[@]}" | paste -sd ',' - | sed 's/,/, /g')
  fi

  # --- 프로젝트 유형 판단 ---
  local project_type="Unknown"

  # 모노레포 체크
  if [ -d packages ] || [ -d apps ] || [ -f lerna.json ] || [ -f pnpm-workspace.yaml ] || [ -f turbo.json ]; then
    project_type="Monorepo"
  # 라이브러리 체크
  elif [ -d lib ] && [ -f package.json ]; then
    local has_exports
    has_exports=$(python3 -c '
import json
d = json.load(open("package.json"))
if d.get("main") or d.get("module") or d.get("exports"):
    print("yes", end="")
else:
    print("no", end="")
' 2>/dev/null || echo "no")
    if [ "$has_exports" = "yes" ]; then
      project_type="Library"
    fi
  fi

  # Frontend / Backend / Full-stack
  if [ "$project_type" = "Unknown" ]; then
    local has_fe=false has_be=false
    for d in pages components public static assets; do
      [ -d "$d" ] && has_fe=true && break
    done
    for d in api routes controllers; do
      [ -d "$d" ] && has_be=true && break
    done

    if $has_fe && $has_be; then
      project_type="Full-stack Application"
    elif $has_fe; then
      project_type="Frontend Application"
    elif $has_be; then
      project_type="Backend Application"
    fi
  fi

  # CLI Tool 체크
  if [ "$project_type" = "Unknown" ] && [ -f package.json ]; then
    local has_bin
    has_bin=$(python3 -c '
import json
d = json.load(open("package.json"))
print("yes" if d.get("bin") else "no", end="")
' 2>/dev/null || echo "no")
    if [ "$has_bin" = "yes" ] || [ -d cli ]; then
      project_type="CLI Tool"
    fi
  fi

  # Configuration 체크
  if [ "$project_type" = "Unknown" ]; then
    if [ -d .claude ] || [ -d .github ]; then
      # 소스 디렉토리가 없으면 Configuration
      local has_src=false
      for d in src lib app pages components api routes controllers; do
        [ -d "$d" ] && has_src=true && break
      done
      if ! $has_src; then
        project_type="Configuration"
      fi
    fi
  fi

  # --- Git 상태 파악 ---
  local git_initialized="false"
  local git_repository="local"
  local git_current_branch=""
  local git_main_branch="main"
  local git_branch_strategy="Unknown"

  if [ -d .git ]; then
    git_initialized="true"

    git_current_branch=$(git branch --show-current 2>/dev/null || echo "")

    local detected_main
    detected_main=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || true)
    if [ -z "$detected_main" ]; then
      detected_main=$(git branch -l main master 2>/dev/null | head -1 | tr -d '* ' || true)
    fi
    [ -n "$detected_main" ] && git_main_branch="$detected_main"

    git_repository=$(git remote get-url origin 2>/dev/null || echo "local")

    # 브랜치 전략 추정
    local remote_branches
    remote_branches=$(git branch -r 2>/dev/null | tr -d ' ' || true)
    if echo "$remote_branches" | grep -qE '(develop|development)$'; then
      git_branch_strategy="Git Flow"
    elif echo "$remote_branches" | grep -qE 'release/'; then
      git_branch_strategy="Git Flow"
    elif echo "$remote_branches" | grep -qE '(feature/|bugfix/|hotfix/)'; then
      git_branch_strategy="Git Flow"
    elif [ -n "$remote_branches" ]; then
      local branch_count
      branch_count=$(echo "$remote_branches" | grep -c '.' || echo "0")
      if [ "$branch_count" -le 2 ]; then
        git_branch_strategy="Trunk-based"
      else
        git_branch_strategy="GitHub Flow"
      fi
    fi
  fi

  # --- JSON 출력 ---
  python3 -c '
import json, sys

data = {
    "project_name": sys.argv[1],
    "project_description": sys.argv[2],
    "project_type": sys.argv[3],
    "detected_languages": sys.argv[4],
    "detected_frameworks": sys.argv[5],
    "runtime": sys.argv[6],
    "package_manager": sys.argv[7],
    "key_dependencies": sys.argv[8],
    "existing_directories": sys.argv[9],
    "git_initialized": sys.argv[10] == "true",
    "git_repository": sys.argv[11],
    "git_current_branch": sys.argv[12],
    "git_main_branch": sys.argv[13],
    "git_branch_strategy": sys.argv[14]
}

print(json.dumps(data, ensure_ascii=False, indent=2))
' \
    "$project_name" \
    "$project_description" \
    "$project_type" \
    "$detected_languages" \
    "$detected_frameworks" \
    "$runtime" \
    "$package_manager" \
    "$key_dependencies" \
    "$existing_directories" \
    "$git_initialized" \
    "$git_repository" \
    "$git_current_branch" \
    "$git_main_branch" \
    "$git_branch_strategy"
}

# ---------- generate-claude-md ----------

cmd_generate_claude_md() {
  cd "$PROJECT_ROOT"

  # stdin에서 JSON 읽기
  local json_input
  json_input=$(cat)

  if [ -z "$json_input" ]; then
    err "stdin으로 analyze JSON이 필요합니다. 사용법: ./init-project.sh analyze | ./init-project.sh generate-claude-md"
  fi

  # 기존 CLAUDE.md에서 보존할 섹션 추출
  local recent_changes="없음"
  local known_issues="없음"
  local next_steps=""

  if [ -f CLAUDE.md ]; then
    # python3으로 섹션 추출
    local preserved
    preserved=$(python3 -c '
import re, sys, json

content = open("CLAUDE.md").read()

def extract_section(title):
    """## Title 부터 다음 ## 까지 내용 추출"""
    pattern = r"## " + re.escape(title) + r"\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, content, re.DOTALL)
    if m:
        text = m.group(1).strip()
        # > 로 시작하는 가이드 주석 제거
        lines = []
        in_blockquote = False
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(">"):
                in_blockquote = True
                continue
            if in_blockquote and stripped == "":
                in_blockquote = False
                continue
            in_blockquote = False
            lines.append(line)
        cleaned = "\n".join(lines).strip()
        return cleaned if cleaned else None
    return None

result = {
    "recent_changes": extract_section("Recent Changes") or "",
    "known_issues": extract_section("Known Issues") or "",
    "next_steps": extract_section("Next Steps") or ""
}
print(json.dumps(result, ensure_ascii=False))
' 2>/dev/null || echo '{}')

    if [ -n "$preserved" ] && [ "$preserved" != '{}' ]; then
      local rc ki ns
      rc=$(echo "$preserved" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("recent_changes",""), end="")')
      ki=$(echo "$preserved" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("known_issues",""), end="")')
      ns=$(echo "$preserved" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("next_steps",""), end="")')
      [ -n "$rc" ] && recent_changes="$rc"
      [ -n "$ki" ] && known_issues="$ki"
      [ -n "$ns" ] && next_steps="$ns"
    fi
  fi

  # JSON에서 값 추출 후 CLAUDE.md 생성
  python3 -c '
import json, sys

data = json.loads(sys.argv[1])
recent_changes = sys.argv[2]
known_issues = sys.argv[3]
next_steps = sys.argv[4]

# 디렉토리 트리 생성
dirs = data["existing_directories"]
if dirs and dirs != "None":
    dir_list = [d.strip() for d in dirs.split(",")]
else:
    dir_list = []

tree_lines = ["."]
for d in dir_list:
    tree_lines.append(f"├── {d}/")
tree = "\n".join(tree_lines)

# 디렉토리 설명 테이블
dir_descriptions_map = {
    "src": "소스 코드",
    "lib": "라이브러리 코드",
    "app": "애플리케이션 코드",
    "pages": "페이지 컴포넌트",
    "components": "UI 컴포넌트",
    "api": "API 엔드포인트",
    "routes": "라우트 정의",
    "controllers": "컨트롤러",
    "tests": "테스트 파일",
    "test": "테스트 파일",
    "__tests__": "테스트 파일",
    "docs": "문서",
    "scripts": "스크립트",
    "packages": "모노레포 패키지",
    "apps": "모노레포 앱",
    ".claude": "Claude Code 설정",
    ".github": "GitHub 설정",
    "public": "정적 파일",
    "static": "정적 파일",
    "assets": "에셋 파일",
    "cli": "CLI 코드",
}

dir_desc_rows = []
for d in dir_list:
    desc = dir_descriptions_map.get(d, "")
    if desc:
        dir_desc_rows.append(f"| `{d}/` | {desc} |")

dir_descriptions = "\n".join(dir_desc_rows) if dir_desc_rows else "| - | - |"

# 의존성 목록 형식
deps = data["key_dependencies"]
if deps and deps != "None":
    dep_list = [d.strip() for d in deps.split(",")]
    key_deps_text = "\n".join(f"- {d}" for d in dep_list)
else:
    key_deps_text = "없음"

template = f"""# {data["project_name"]}

## Project Overview

| 항목 | 값 |
|------|-----|
| **Name** | {data["project_name"]} |
| **Description** | {data["project_description"] or ""} |
| **Type** | {data["project_type"]} |

## Tech Stack

| 항목 | 값 |
|------|-----|
| **Language** | {data["detected_languages"]} |
| **Framework** | {data["detected_frameworks"]} |
| **Runtime** | {data["runtime"]} |
| **Package Manager** | {data["package_manager"]} |

### Key Dependencies

{key_deps_text}

## Project Structure

```
{tree}
```

### 주요 디렉토리 설명

| 디렉토리 | 설명 |
|----------|------|
{dir_descriptions}

## Git Information

| 항목 | 값 |
|------|-----|
| **Repository** | {data["git_repository"]} |
| **Current Branch** | {data["git_current_branch"] or "없음"} |
| **Main Branch** | {data["git_main_branch"]} |
| **Branch Strategy** | {data["git_branch_strategy"]} |

## Recent Changes

{recent_changes}

## Known Issues

{known_issues}

## Next Steps

{next_steps}
"""

with open("CLAUDE.md", "w") as f:
    f.write(template.rstrip() + "\n")

print("CLAUDE.md 생성 완료", file=sys.stderr)
' "$json_input" "$recent_changes" "$known_issues" "$next_steps"
}

# ---------- generate-empty-template ----------

cmd_generate_empty_template() {
  cd "$PROJECT_ROOT"

  # CLAUDE.md가 이미 존재하면 스킵
  if [ -f CLAUDE.md ]; then
    echo '{"status":"skipped","reason":"already_exists"}'
    return 0
  fi

  # 프로젝트명 추출
  local project_name
  project_name="$(basename "$PROJECT_ROOT")"

  # 빈 템플릿 생성
  cat > CLAUDE.md << TMPL
# ${project_name}

## Project Overview

| 항목 | 값 |
|------|-----|
| **Name** | ${project_name} |
| **Description** | |
| **Type** | |

## Tech Stack

| 항목 | 값 |
|------|-----|
| **Language** | |
| **Framework** | |
| **Runtime** | |
| **Package Manager** | |

### Key Dependencies

없음

## Project Structure

\`\`\`
.
\`\`\`

## Git Information

| 항목 | 값 |
|------|-----|
| **Repository** | |
| **Current Branch** | |
| **Main Branch** | |
| **Branch Strategy** | |

## Known Issues

없음

## Next Steps

없음
TMPL

  echo '{"status":"created","file":"CLAUDE.md"}'
}

# ---------- setup-dirs ----------

cmd_setup_dirs() {
  cd "$PROJECT_ROOT"

  local dirs=(".workflow" ".prompt")
  local files=(".prompt/prompt.txt" ".prompt/memo.txt" ".prompt/querys.txt" ".claude.env")
  local created_dirs=()
  local created_files=()

  # 디렉토리 생성
  for d in "${dirs[@]}"; do
    if [ ! -d "$d" ]; then
      mkdir -p "$d"
      created_dirs+=("$d")
    fi
  done

  # 파일 생성 (이미 존재하면 건너뜀)
  for f in "${files[@]}"; do
    if [ ! -f "$f" ]; then
      touch "$f"
      created_files+=("$f")
    fi
  done

  # .prompt/history.md 초기 템플릿 생성
  if [ ! -f ".prompt/history.md" ]; then
    cat > ".prompt/history.md" << 'HISTORY_TMPL'
# 워크플로우 실행 이력

<!-- 새 항목은 이 줄 아래에 추가됩니다 -->

| 날짜 | 작업ID | 제목 & 내용 | 명령어 | 상태 | 계획서 | 질의 | 이미지 | 보고서 |
|------|--------|------------|--------|------|--------|------|--------|--------|
HISTORY_TMPL
    created_files+=(".prompt/history.md")
  fi

  # .workflow/registry.json 초기값 생성
  if [ ! -f ".workflow/registry.json" ]; then
    echo '{}' > ".workflow/registry.json"
    created_files+=(".workflow/registry.json")
  fi

  # JSON 결과 출력
  local all_dirs=(".workflow" ".prompt")
  local all_files=(".prompt/prompt.txt" ".prompt/memo.txt" ".prompt/querys.txt" ".claude.env" ".prompt/history.md" ".workflow/registry.json")

  python3 -c '
import json, sys
result = {
    "created_dirs": json.loads(sys.argv[1]),
    "created_files": json.loads(sys.argv[2]),
    "all_dirs_exist": True,
    "all_files_exist": True
}
# 검증
import os
all_dirs = json.loads(sys.argv[3])
all_files = json.loads(sys.argv[4])
for d in all_dirs:
    if not os.path.isdir(d):
        result["all_dirs_exist"] = False
for f in all_files:
    if not os.path.isfile(f):
        result["all_files_exist"] = False
print(json.dumps(result, ensure_ascii=False, indent=2))
' \
    "$(printf '%s\n' "${created_dirs[@]:-}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')" \
    "$(printf '%s\n' "${created_files[@]:-}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')" \
    "$(printf '%s\n' "${all_dirs[@]}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')" \
    "$(printf '%s\n' "${all_files[@]}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')"
}

# ---------- setup-gitignore ----------

cmd_setup_gitignore() {
  cd "$PROJECT_ROOT"

  local gitignore_file=".gitignore"

  # .gitignore 없으면 생성
  if [ ! -f "$gitignore_file" ]; then
    touch "$gitignore_file"
  fi

  local content
  content=$(cat "$gitignore_file")

  # 추가할 패턴 정의 (그룹별)
  local -a patterns_workflow=(".workflow/")
  local -a patterns_env=(".claude.env" ".claude.env*")
  local -a patterns_prompt=(".prompt/")
  local added=()
  local skipped=()
  local append_block=""

  # 워크플로우 패턴
  local need_workflow_header=false
  for p in "${patterns_workflow[@]}"; do
    if echo "$content" | grep -qF "$p"; then
      skipped+=("$p")
    else
      need_workflow_header=true
      added+=("$p")
    fi
  done
  if $need_workflow_header; then
    append_block+="\n# Workflow documents"
    for p in "${patterns_workflow[@]}"; do
      if [[ " ${added[*]} " == *" $p "* ]]; then
        append_block+="\n$p"
      fi
    done
  fi

  # 환경변수 패턴
  local need_env_header=false
  for p in "${patterns_env[@]}"; do
    if echo "$content" | grep -qF "$p"; then
      skipped+=("$p")
    else
      need_env_header=true
      added+=("$p")
    fi
  done
  if $need_env_header; then
    append_block+="\n\n# Claude Code environment (secrets only)"
    for p in "${patterns_env[@]}"; do
      if [[ " ${added[*]} " == *" $p "* ]]; then
        append_block+="\n$p"
      fi
    done
  fi

  # 프롬프트/임시 패턴
  local need_prompt_header=false
  for p in "${patterns_prompt[@]}"; do
    if echo "$content" | grep -qF "$p"; then
      skipped+=("$p")
    else
      need_prompt_header=true
      added+=("$p")
    fi
  done
  if $need_prompt_header; then
    append_block+="\n\n# Prompts and temps"
    for p in "${patterns_prompt[@]}"; do
      if [[ " ${added[*]} " == *" $p "* ]]; then
        append_block+="\n$p"
      fi
    done
  fi

  # 추가할 패턴이 있으면 파일 끝에 append
  if [ ${#added[@]} -gt 0 ]; then
    # 파일 끝에 개행 확인 후 추가
    if [ -s "$gitignore_file" ]; then
      local last_char
      last_char=$(tail -c 1 "$gitignore_file" | xxd -p)
      if [ "$last_char" != "0a" ]; then
        echo "" >> "$gitignore_file"
      fi
    fi
    printf "$append_block\n" >> "$gitignore_file"
  fi

  # JSON 결과 출력
  python3 -c '
import json, sys
result = {
    "added": json.loads(sys.argv[1]),
    "skipped": json.loads(sys.argv[2])
}
print(json.dumps(result, ensure_ascii=False, indent=2))
' \
    "$(printf '%s\n' "${added[@]:-}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')" \
    "$(printf '%s\n' "${skipped[@]:-}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')"
}

# ---------- setup-wf-alias ----------

cmd_setup_wf_alias() {
  local zshrc="$HOME/.zshrc"

  # ~/.zshrc 없으면 생성
  if [ ! -f "$zshrc" ]; then
    touch "$zshrc"
  fi

  local content
  content=$(cat "$zshrc")

  # 대상 alias 정의 (bash 3.2 호환: 연관 배열 대신 일반 배열 사용)
  local alias_names=("Workflow" "wf-state" "wf-init" "wf-claude" "wf-project" "wf-clear" "wf-registry" "wf-sync" "wf-git-config" "wf-slack" "wf-info" "wf-commands" "wf-history")
  local alias_cmds=(
    "bash .claude/hooks/workflow/banner.sh"
    "bash .claude/hooks/workflow/update-state.sh"
    "bash .claude/hooks/init/init-workflow.sh"
    "bash .claude/hooks/init/init-claude.sh"
    "bash .claude/hooks/init/init-project.sh"
    "bash .claude/hooks/init/init-clear.sh"
    "bash .claude/hooks/workflow/registry.sh"
    "bash .claude/hooks/init/init-sync.sh"
    "bash .claude/hooks/init/git-config.sh"
    "bash .claude/hooks/slack/slack.sh"
    "bash .claude/hooks/workflow/info.sh"
    "bash .claude/hooks/workflow/commands.sh"
    "bash .claude/hooks/workflow/history-sync.sh"
  )

  local added=()
  local skipped=()

  for (( i=0; i<${#alias_names[@]}; i++ )); do
    local name="${alias_names[$i]}"
    if echo "$content" | grep -q "^alias ${name}="; then
      skipped+=("$name")
    else
      added+=("$i")
    fi
  done

  # 추가할 alias가 있으면 append
  if [ ${#added[@]} -gt 0 ]; then
    # 헤더 주석이 없으면 추가
    if ! echo "$content" | grep -qF "# Workflow shortcut aliases"; then
      {
        echo ""
        echo "# Workflow shortcut aliases (for Claude Code Bash tool)"
      } >> "$zshrc"
    fi

    for idx in "${added[@]}"; do
      local name="${alias_names[$idx]}"
      local cmd="${alias_cmds[$idx]}"
      echo "alias ${name}='${cmd}'" >> "$zshrc"
    done
  fi

  # --- ~/.local/bin/ wrapper 스크립트 생성 ---
  # alias는 non-interactive bash에서 동작하지 않으므로
  # PATH 기반 실행 파일로도 노출 (Claude Code Bash 도구 호환)
  local bin_dir="$HOME/.local/bin"
  mkdir -p "$bin_dir"

  local wrapper_added=()
  local wrapper_skipped=()

  for (( i=0; i<${#alias_names[@]}; i++ )); do
    local name="${alias_names[$i]}"
    local cmd="${alias_cmds[$i]}"
    local wrapper_path="${bin_dir}/${name}"

    # 항상 덮어쓰기 (idempotent) - 내용이 최신인지 보장
    cat > "$wrapper_path" << WRAPPER_EOF
#!/bin/bash
# Auto-generated by init-project.sh (setup-wf-alias)
# Wrapper script for non-interactive bash environments (e.g. Claude Code Bash tool)
# Equivalent to: alias ${name}='${cmd}'
exec ${cmd} "\$@"
WRAPPER_EOF
    chmod +x "$wrapper_path"
    wrapper_added+=("$name")
  done

  # added 인덱스를 이름으로 변환
  local added_names=()
  for idx in "${added[@]:-}"; do
    [ -n "$idx" ] && added_names+=("${alias_names[$idx]}")
  done

  # JSON 결과 출력
  python3 -c '
import json, sys
result = {
    "status": "ok",
    "zshrc_added": json.loads(sys.argv[1]),
    "zshrc_skipped": json.loads(sys.argv[2]),
    "wrapper_added": json.loads(sys.argv[3])
}
print(json.dumps(result, ensure_ascii=False))
' \
    "$(printf '%s\n' "${added_names[@]:-}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')" \
    "$(printf '%s\n' "${skipped[@]:-}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')" \
    "$(printf '%s\n' "${wrapper_added[@]:-}" | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')"
}

# ---------- verify ----------

cmd_verify() {
  cd "$PROJECT_ROOT"

  local checks=()
  local all_pass=true

  # CLAUDE.md 확인
  if [ -f CLAUDE.md ]; then
    checks+=('{"item":"CLAUDE.md","status":"PASS","detail":"파일 존재"}')
  else
    checks+=('{"item":"CLAUDE.md","status":"FAIL","detail":"파일 없음"}')
    all_pass=false
  fi

  # 디렉토리 확인
  for d in .workflow .prompt; do
    if [ -d "$d" ]; then
      checks+=("{\"item\":\"$d/\",\"status\":\"PASS\",\"detail\":\"디렉토리 존재\"}")
    else
      checks+=("{\"item\":\"$d/\",\"status\":\"FAIL\",\"detail\":\"디렉토리 없음\"}")
      all_pass=false
    fi
  done

  # 파일 확인
  for f in .prompt/prompt.txt .prompt/memo.txt .prompt/querys.txt .prompt/history.md .claude.env; do
    if [ -f "$f" ]; then
      checks+=("{\"item\":\"$f\",\"status\":\"PASS\",\"detail\":\"파일 존재\"}")
    else
      checks+=("{\"item\":\"$f\",\"status\":\"FAIL\",\"detail\":\"파일 없음\"}")
      all_pass=false
    fi
  done

  # .workflow 파일 확인
  for f in .workflow/registry.json; do
    if [ -f "$f" ]; then
      checks+=("{\"item\":\"$f\",\"status\":\"PASS\",\"detail\":\"파일 존재\"}")
    else
      checks+=("{\"item\":\"$f\",\"status\":\"FAIL\",\"detail\":\"파일 없음\"}")
      all_pass=false
    fi
  done

  # 워크플로우 alias 확인 (~/.zshrc)
  if [ -f "$HOME/.zshrc" ]; then
    local zshrc_content
    zshrc_content=$(cat "$HOME/.zshrc")
    for alias_name in Workflow wf-state wf-init wf-claude wf-project wf-clear wf-sync wf-git-config wf-slack wf-info wf-commands wf-history wf-registry; do
      if echo "$zshrc_content" | grep -q "^alias ${alias_name}="; then
        checks+=("{\"item\":\"~/.zshrc(${alias_name})\",\"status\":\"PASS\",\"detail\":\"alias 존재\"}")
      else
        checks+=("{\"item\":\"~/.zshrc(${alias_name})\",\"status\":\"FAIL\",\"detail\":\"alias 누락\"}")
        all_pass=false
      fi
    done
  else
    checks+=('{"item":"~/.zshrc","status":"FAIL","detail":"파일 없음 (워크플로우 alias 미설정)"}')
    all_pass=false
  fi

  # 워크플로우 wrapper 스크립트 확인 (~/.local/bin/)
  local bin_dir="$HOME/.local/bin"
  for cmd_name in Workflow wf-state wf-init wf-claude wf-project wf-clear wf-sync wf-git-config wf-slack wf-info wf-commands wf-history wf-registry; do
    local wrapper_path="${bin_dir}/${cmd_name}"
    if [ -x "$wrapper_path" ]; then
      checks+=("{\"item\":\"~/.local/bin/${cmd_name}\",\"status\":\"PASS\",\"detail\":\"wrapper 스크립트 존재 (실행 가능)\"}")
    elif [ -f "$wrapper_path" ]; then
      checks+=("{\"item\":\"~/.local/bin/${cmd_name}\",\"status\":\"FAIL\",\"detail\":\"wrapper 스크립트 존재하나 실행 권한 없음\"}")
      all_pass=false
    else
      checks+=("{\"item\":\"~/.local/bin/${cmd_name}\",\"status\":\"FAIL\",\"detail\":\"wrapper 스크립트 없음\"}")
      all_pass=false
    fi
  done

  # .gitignore 패턴 확인
  if [ -f .gitignore ]; then
    local gi_content
    gi_content=$(cat .gitignore)
    for p in ".workflow/" ".claude.env" ".prompt/"; do
      if echo "$gi_content" | grep -qF "$p"; then
        checks+=("{\"item\":\".gitignore($p)\",\"status\":\"PASS\",\"detail\":\"패턴 존재\"}")
      else
        checks+=("{\"item\":\".gitignore($p)\",\"status\":\"FAIL\",\"detail\":\"패턴 누락\"}")
        all_pass=false
      fi
    done
  else
    checks+=('{"item":".gitignore","status":"FAIL","detail":"파일 없음"}')
    all_pass=false
  fi

  # JSON 결과 출력
  local checks_json
  checks_json=$(printf '%s\n' "${checks[@]}" | python3 -c '
import json, sys
items = [json.loads(line) for line in sys.stdin if line.strip()]
print(json.dumps(items, ensure_ascii=False))
')

  python3 -c '
import json, sys
result = {
    "all_pass": sys.argv[1] == "true",
    "checks": json.loads(sys.argv[2])
}
print(json.dumps(result, ensure_ascii=False, indent=2))
' "$all_pass" "$checks_json"
}

# ---------- 메인 디스패치 ----------

case "${1:-}" in
  analyze)
    cmd_analyze
    ;;
  generate-claude-md)
    cmd_generate_claude_md
    ;;
  generate-empty-template)
    cmd_generate_empty_template
    ;;
  setup-dirs)
    cmd_setup_dirs
    ;;
  setup-gitignore)
    cmd_setup_gitignore
    ;;
  setup-wf-alias)
    cmd_setup_wf_alias
    ;;
  verify)
    cmd_verify
    ;;
  *)
    echo "사용법: $0 <subcommand>"
    echo ""
    echo "서브커맨드:"
    echo "  analyze                프로젝트 분석 (JSON 출력)"
    echo "  generate-claude-md     CLAUDE.md 생성 (stdin으로 analyze JSON 수신)"
    echo "  generate-empty-template CLAUDE.md 빈 템플릿 생성 (analyze 없이)"
    echo "  setup-dirs             디렉토리 + 파일 생성"
    echo "  setup-gitignore        .gitignore 업데이트"
    echo "  setup-wf-alias         워크플로우 alias 설정 (~/.zshrc + ~/.local/bin wrapper)"
    echo "  verify                 전체 검증"
    echo ""
    echo "예시:"
    echo "  $0 analyze"
    echo "  $0 analyze | $0 generate-claude-md"
    echo "  $0 generate-empty-template"
    echo "  $0 setup-dirs"
    echo "  $0 setup-gitignore"
    echo "  $0 setup-wf-alias"
    echo "  $0 verify"
    exit 1
    ;;
esac

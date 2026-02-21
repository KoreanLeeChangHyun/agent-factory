#!/usr/bin/env -S python3 -u
"""
init_project.py - 프로젝트 분석 및 초기화 스크립트

사용법: python3 init_project.py <subcommand> [options]

서브커맨드:
  analyze                프로젝트 분석 (JSON 결과 stdout 출력)
  generate-claude-md     CLAUDE.md 생성 (stdin으로 analyze JSON 수신)
  generate-empty-template CLAUDE.md 빈 템플릿 생성 (analyze 없이 프로젝트명만)
  setup-dirs             디렉토리 + 파일 생성
  setup-gitignore        .gitignore 업데이트 (중복 체크)
  setup-wf-alias         워크플로우 alias 설정 (~/.zshrc + ~/.local/bin wrapper)
  verify                 전체 검증
"""

import glob
import json
import os
import re
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))


def _err(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def _warn(msg):
    print(f"[WARN] {msg}", file=sys.stderr)


# ---------- analyze ----------

def cmd_analyze():
    os.chdir(_PROJECT_ROOT)

    # --- 프로젝트 이름 ---
    project_name = os.path.basename(_PROJECT_ROOT)

    # --- 프로젝트 설명 ---
    project_description = ""
    if os.path.isfile("package.json"):
        try:
            with open("package.json", "r", encoding="utf-8") as f:
                d = json.load(f)
            project_description = d.get("description", "")
        except Exception:
            pass

    # --- 언어 감지 ---
    languages = []

    if os.path.isfile("tsconfig.json"):
        languages.append("TypeScript")
    if os.path.isfile("package.json"):
        languages.append("JavaScript")
    if any(os.path.isfile(f) for f in ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]):
        languages.append("Python")
    if os.path.isfile("go.mod"):
        languages.append("Go")
    if os.path.isfile("Cargo.toml"):
        languages.append("Rust")
    if os.path.isfile("Gemfile"):
        languages.append("Ruby")
    if any(os.path.isfile(f) for f in ["pom.xml", "build.gradle", "build.gradle.kts"]):
        languages.append("Java/Kotlin")
    if glob.glob("*.csproj") or glob.glob("*.sln"):
        languages.append("C#")
    if os.path.isfile("composer.json"):
        languages.append("PHP")

    if not languages:
        if glob.glob("*.md") or glob.glob("*.sh"):
            languages.extend(["Markdown", "Shell"])
        else:
            languages.append("Unknown")

    detected_languages = ", ".join(sorted(set(languages)))

    # --- 프레임워크 감지 ---
    frameworks = []

    # JavaScript/TypeScript 프레임워크
    if os.path.isfile("package.json"):
        try:
            pkg_content = open("package.json", "r", encoding="utf-8").read()
        except Exception:
            pkg_content = "{}"
        fw_keywords = [
            ("react", "React"), ("next", "Next.js"), ("vue", "Vue.js"),
            ("nuxt", "Nuxt.js"), ("angular", "Angular"), ("express", "Express"),
            ("fastify", "Fastify"), ("@nestjs", "NestJS"), ("electron", "Electron"),
        ]
        for keyword, name in fw_keywords:
            if f'"{keyword}"' in pkg_content:
                frameworks.append(name)

    # Python 프레임워크
    py_deps = ""
    if os.path.isfile("requirements.txt"):
        try:
            py_deps = open("requirements.txt", "r", encoding="utf-8").read()
        except Exception:
            pass
    if os.path.isfile("pyproject.toml"):
        try:
            py_deps += " " + open("pyproject.toml", "r", encoding="utf-8").read()
        except Exception:
            pass
    if py_deps:
        py_keywords = [
            ("fastapi", "FastAPI"), ("django", "Django"), ("flask", "Flask"),
            ("streamlit", "Streamlit"), ("torch", "PyTorch"), ("pytorch", "PyTorch"),
            ("tensorflow", "TensorFlow"),
        ]
        for keyword, name in py_keywords:
            if keyword.lower() in py_deps.lower():
                frameworks.append(name)

    # Go 프레임워크
    if os.path.isfile("go.mod"):
        try:
            go_content = open("go.mod", "r", encoding="utf-8").read()
        except Exception:
            go_content = ""
        go_keywords = [
            ("gin-gonic/gin", "Gin"), ("labstack/echo", "Echo"), ("gofiber/fiber", "Fiber"),
        ]
        for keyword, name in go_keywords:
            if keyword in go_content:
                frameworks.append(name)

    detected_frameworks = "None"
    if frameworks:
        detected_frameworks = ", ".join(sorted(set(frameworks)))

    # --- 주요 의존성 추출 (상위 10개) ---
    key_dependencies = "None"
    if os.path.isfile("package.json"):
        try:
            d = json.load(open("package.json", "r", encoding="utf-8"))
            deps = list(d.get("dependencies", {}).keys())[:10]
            if deps:
                key_dependencies = ", ".join(deps)
        except Exception:
            pass
    elif os.path.isfile("requirements.txt"):
        try:
            lines = open("requirements.txt", "r", encoding="utf-8").readlines()[:10]
            deps = [re.split(r"[>=<\[]", line.strip())[0] for line in lines if line.strip() and not line.startswith("#")]
            if deps:
                key_dependencies = ", ".join(deps)
        except Exception:
            pass
    elif os.path.isfile("pyproject.toml"):
        try:
            content = open("pyproject.toml", "r", encoding="utf-8").read()
            m = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
            if m:
                deps = re.findall(r'"([^">=<\[]+)', m.group(1))[:10]
                if deps:
                    key_dependencies = ", ".join(deps)
        except Exception:
            pass

    # --- 패키지 매니저 감지 ---
    package_manager = "None"
    if os.path.isfile("pnpm-lock.yaml"):
        package_manager = "pnpm"
    elif os.path.isfile("yarn.lock"):
        package_manager = "yarn"
    elif os.path.isfile("bun.lockb"):
        package_manager = "bun"
    elif os.path.isfile("package-lock.json"):
        package_manager = "npm"
    elif os.path.isfile("poetry.lock"):
        package_manager = "poetry"
    elif os.path.isfile("Pipfile.lock"):
        package_manager = "pipenv"

    # --- 런타임 감지 ---
    runtime = "None"
    if os.path.isfile(".nvmrc"):
        try:
            v = open(".nvmrc", "r").read().strip()
            runtime = f"Node.js {v}"
        except Exception:
            pass
    elif os.path.isfile(".node-version"):
        try:
            v = open(".node-version", "r").read().strip()
            runtime = f"Node.js {v}"
        except Exception:
            pass
    elif os.path.isfile(".python-version"):
        try:
            v = open(".python-version", "r").read().strip()
            runtime = f"Python {v}"
        except Exception:
            pass
    elif os.path.isfile(".ruby-version"):
        try:
            v = open(".ruby-version", "r").read().strip()
            runtime = f"Ruby {v}"
        except Exception:
            pass
    elif os.path.isfile(".tool-versions"):
        try:
            lines = open(".tool-versions", "r").readlines()[:3]
            runtime = ", ".join(line.strip() for line in lines if line.strip())
        except Exception:
            pass

    # --- 디렉토리 구조 분석 ---
    known_dirs = [
        "src", "lib", "app", "pages", "components", "api", "routes",
        "controllers", "tests", "test", "__tests__", "docs", "scripts",
        "packages", "apps", ".claude", ".github", "public", "static", "assets", "cli",
    ]
    existing_dirs = [d for d in known_dirs if os.path.isdir(d)]
    existing_directories = ", ".join(existing_dirs) if existing_dirs else "None"

    # --- 프로젝트 유형 판단 ---
    project_type = "Unknown"

    # 모노레포 체크
    if any(os.path.isdir(d) for d in ["packages", "apps"]) or \
       any(os.path.isfile(f) for f in ["lerna.json", "pnpm-workspace.yaml", "turbo.json"]):
        project_type = "Monorepo"
    # 라이브러리 체크
    elif os.path.isdir("lib") and os.path.isfile("package.json"):
        try:
            d = json.load(open("package.json", "r", encoding="utf-8"))
            if d.get("main") or d.get("module") or d.get("exports"):
                project_type = "Library"
        except Exception:
            pass

    # Frontend / Backend / Full-stack
    if project_type == "Unknown":
        has_fe = any(os.path.isdir(d) for d in ["pages", "components", "public", "static", "assets"])
        has_be = any(os.path.isdir(d) for d in ["api", "routes", "controllers"])
        if has_fe and has_be:
            project_type = "Full-stack Application"
        elif has_fe:
            project_type = "Frontend Application"
        elif has_be:
            project_type = "Backend Application"

    # CLI Tool 체크
    if project_type == "Unknown" and os.path.isfile("package.json"):
        try:
            d = json.load(open("package.json", "r", encoding="utf-8"))
            if d.get("bin") or os.path.isdir("cli"):
                project_type = "CLI Tool"
        except Exception:
            pass

    # Configuration 체크
    if project_type == "Unknown":
        if os.path.isdir(".claude") or os.path.isdir(".github"):
            has_src = any(os.path.isdir(d) for d in [
                "src", "lib", "app", "pages", "components", "api", "routes", "controllers",
            ])
            if not has_src:
                project_type = "Configuration"

    # --- Git 상태 파악 ---
    git_initialized = False
    git_repository = "local"
    git_current_branch = ""
    git_main_branch = "main"
    git_branch_strategy = "Unknown"

    if os.path.isdir(".git"):
        git_initialized = True

        try:
            git_current_branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode().strip()
        except Exception:
            git_current_branch = ""

        detected_main = ""
        try:
            detected_main = subprocess.check_output(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode().strip().replace("refs/remotes/origin/", "")
        except Exception:
            pass
        if not detected_main:
            try:
                result = subprocess.check_output(
                    ["git", "branch", "-l", "main", "master"],
                    stderr=subprocess.DEVNULL, timeout=5
                ).decode().strip()
                if result:
                    detected_main = result.split("\n")[0].strip("* ").strip()
            except Exception:
                pass
        if detected_main:
            git_main_branch = detected_main

        try:
            git_repository = subprocess.check_output(
                ["git", "remote", "get-url", "origin"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode().strip()
        except Exception:
            git_repository = "local"

        # 브랜치 전략 추정
        try:
            remote_branches = subprocess.check_output(
                ["git", "branch", "-r"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode().strip()
            if remote_branches:
                if re.search(r"(develop|development)$", remote_branches, re.MULTILINE):
                    git_branch_strategy = "Git Flow"
                elif re.search(r"release/", remote_branches):
                    git_branch_strategy = "Git Flow"
                elif re.search(r"(feature/|bugfix/|hotfix/)", remote_branches):
                    git_branch_strategy = "Git Flow"
                else:
                    branch_count = len([b for b in remote_branches.split("\n") if b.strip()])
                    if branch_count <= 2:
                        git_branch_strategy = "Trunk-based"
                    else:
                        git_branch_strategy = "GitHub Flow"
        except Exception:
            pass

    # --- JSON 출력 ---
    data = {
        "project_name": project_name,
        "project_description": project_description,
        "project_type": project_type,
        "detected_languages": detected_languages,
        "detected_frameworks": detected_frameworks,
        "runtime": runtime,
        "package_manager": package_manager,
        "key_dependencies": key_dependencies,
        "existing_directories": existing_directories,
        "git_initialized": git_initialized,
        "git_repository": git_repository,
        "git_current_branch": git_current_branch,
        "git_main_branch": git_main_branch,
        "git_branch_strategy": git_branch_strategy,
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ---------- generate-claude-md ----------

def cmd_generate_claude_md():
    os.chdir(_PROJECT_ROOT)

    # stdin에서 JSON 읽기
    json_input = sys.stdin.read().strip()
    if not json_input:
        _err("stdin으로 analyze JSON이 필요합니다. 사용법: python3 init_project.py analyze | python3 init_project.py generate-claude-md")

    data = json.loads(json_input)

    # 기존 CLAUDE.md에서 보존할 섹션 추출
    recent_changes = "없음"
    known_issues = "없음"
    next_steps = ""

    if os.path.isfile("CLAUDE.md"):
        try:
            content = open("CLAUDE.md", "r", encoding="utf-8").read()

            def extract_section(title):
                pattern = r"## " + re.escape(title) + r"\s*\n(.*?)(?=\n## |\Z)"
                m = re.search(pattern, content, re.DOTALL)
                if m:
                    text = m.group(1).strip()
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

            rc = extract_section("Recent Changes")
            ki = extract_section("Known Issues")
            ns = extract_section("Next Steps")
            if rc:
                recent_changes = rc
            if ki:
                known_issues = ki
            if ns:
                next_steps = ns
        except Exception:
            pass

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
        "src": "소스 코드", "lib": "라이브러리 코드", "app": "애플리케이션 코드",
        "pages": "페이지 컴포넌트", "components": "UI 컴포넌트", "api": "API 엔드포인트",
        "routes": "라우트 정의", "controllers": "컨트롤러", "tests": "테스트 파일",
        "test": "테스트 파일", "__tests__": "테스트 파일", "docs": "문서",
        "scripts": "스크립트", "packages": "모노레포 패키지", "apps": "모노레포 앱",
        ".claude": "Claude Code 설정", ".github": "GitHub 설정", "public": "정적 파일",
        "static": "정적 파일", "assets": "에셋 파일", "cli": "CLI 코드",
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

    with open("CLAUDE.md", "w", encoding="utf-8") as f:
        f.write(template.rstrip() + "\n")

    print("CLAUDE.md 생성 완료", file=sys.stderr)


# ---------- generate-empty-template ----------

def cmd_generate_empty_template():
    os.chdir(_PROJECT_ROOT)

    if os.path.isfile("CLAUDE.md"):
        print('{"status":"skipped","reason":"already_exists"}')
        return

    project_name = os.path.basename(_PROJECT_ROOT)

    template = f"""# {project_name}

## Project Overview

| 항목 | 값 |
|------|-----|
| **Name** | {project_name} |
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

```
.
```

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
"""

    with open("CLAUDE.md", "w", encoding="utf-8") as f:
        f.write(template.rstrip() + "\n")

    print('{"status":"created","file":"CLAUDE.md"}')


# ---------- setup-dirs ----------

def cmd_setup_dirs():
    os.chdir(_PROJECT_ROOT)

    dirs = [".workflow", ".prompt"]
    files = [".prompt/prompt.txt", ".prompt/memo.txt", ".prompt/querys.txt", ".claude.env"]
    created_dirs = []
    created_files = []

    # 디렉토리 생성
    for d in dirs:
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            created_dirs.append(d)

    # 파일 생성 (이미 존재하면 건너뜀)
    for f in files:
        if not os.path.isfile(f):
            parent = os.path.dirname(f)
            if parent:
                os.makedirs(parent, exist_ok=True)
            open(f, "a").close()
            created_files.append(f)

    # .prompt/history.md 초기 템플릿 생성
    if not os.path.isfile(".prompt/history.md"):
        with open(".prompt/history.md", "w", encoding="utf-8") as f:
            f.write(
                "# 워크플로우 실행 이력\n"
                "\n"
                "| 날짜 | 작업ID | 제목 & 내용 | 명령어 | 상태 | 계획서 | 질의 | 이미지 | 보고서 |\n"
                "|------|--------|------------|--------|------|--------|------|--------|--------|\n"
            )
        created_files.append(".prompt/history.md")

    # .workflow/registry.json 초기값 생성
    if not os.path.isfile(".workflow/registry.json"):
        with open(".workflow/registry.json", "w", encoding="utf-8") as f:
            f.write("{}\n")
        created_files.append(".workflow/registry.json")

    # 검증
    all_dirs = [".workflow", ".prompt"]
    all_files = [".prompt/prompt.txt", ".prompt/memo.txt", ".prompt/querys.txt",
                 ".claude.env", ".prompt/history.md", ".workflow/registry.json"]

    all_dirs_exist = all(os.path.isdir(d) for d in all_dirs)
    all_files_exist = all(os.path.isfile(f) for f in all_files)

    result = {
        "created_dirs": created_dirs,
        "created_files": created_files,
        "all_dirs_exist": all_dirs_exist,
        "all_files_exist": all_files_exist,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------- setup-gitignore ----------

def cmd_setup_gitignore():
    os.chdir(_PROJECT_ROOT)

    gitignore_file = ".gitignore"
    if not os.path.isfile(gitignore_file):
        open(gitignore_file, "a").close()

    content = open(gitignore_file, "r", encoding="utf-8").read()

    # 추가할 패턴 정의 (그룹별)
    groups = [
        ("# Workflow documents", [".workflow/"]),
        ("# Claude Code environment (secrets only)", [".claude.env", ".claude.env*"]),
        ("# Prompts and temps", [".prompt/"]),
    ]

    added = []
    skipped = []
    append_block = ""

    for header, patterns in groups:
        need_header = False
        group_added = []
        for p in patterns:
            if p in content:
                skipped.append(p)
            else:
                need_header = True
                added.append(p)
                group_added.append(p)

        if need_header:
            if append_block:
                append_block += "\n"
            append_block += f"\n{header}\n"
            for p in group_added:
                append_block += f"{p}\n"

    # 추가할 패턴이 있으면 파일 끝에 append
    if added:
        # 파일 끝에 개행 확인
        if content and not content.endswith("\n"):
            append_block = "\n" + append_block

        with open(gitignore_file, "a", encoding="utf-8") as f:
            f.write(append_block)

    result = {
        "added": added,
        "skipped": skipped,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------- setup-wf-alias ----------

def cmd_setup_wf_alias():
    zshrc = os.path.join(os.environ.get("HOME", ""), ".zshrc")
    if not os.path.isfile(zshrc):
        open(zshrc, "a").close()

    content = open(zshrc, "r", encoding="utf-8").read()

    # --- 구 alias 정리 (wf-*, Workflow 등 슬래시 커맨드로 대체된 항목) ---
    deprecated_aliases = [
        "Workflow", "wf-state", "wf-init", "wf-claude", "wf-project",
        "wf-clear", "wf-sync", "wf-git-config", "wf-slack", "wf-info",
        "wf-commands", "wf-registry", "wf-history",
    ]
    lines = content.splitlines(True)
    cleaned_lines = []
    removed_names = []
    for line in lines:
        stripped = line.strip()
        # "# Workflow shortcut aliases" 헤더도 제거
        if stripped == "# Workflow shortcut aliases (for Claude Code Bash tool)":
            removed_names.append("(header)")
            continue
        matched = False
        for dep_name in deprecated_aliases:
            if stripped.startswith(f"alias {dep_name}="):
                removed_names.append(dep_name)
                matched = True
                break
        if not matched:
            cleaned_lines.append(line)

    if removed_names:
        content = "".join(cleaned_lines)
        # 연속 빈 줄 정리 (3줄 이상 → 2줄)
        while "\n\n\n" in content:
            content = content.replace("\n\n\n", "\n\n")
        with open(zshrc, "w", encoding="utf-8") as f:
            f.write(content)

    # --- 구 wrapper 스크립트 정리 (~/.local/bin/) ---
    bin_dir = os.path.join(os.environ.get("HOME", ""), ".local", "bin")
    removed_wrappers = []
    for dep_name in deprecated_aliases:
        wrapper_path = os.path.join(bin_dir, dep_name)
        if os.path.isfile(wrapper_path):
            os.remove(wrapper_path)
            removed_wrappers.append(dep_name)

    # --- 현행 alias 정의 (step-start, step-change, step-end) ---
    alias_defs = [
        ("step-start", "bash .claude/scripts/workflow/banner/step_start_banner.sh"),
        ("step-change", "bash .claude/scripts/workflow/banner/step_change_banner.sh"),
        ("step-end", "bash .claude/scripts/workflow/banner/step_end_banner.sh"),
    ]

    added_indices = []
    skipped_names = []

    for i, (name, _cmd) in enumerate(alias_defs):
        if f"alias {name}=" in content:
            skipped_names.append(name)
        else:
            added_indices.append(i)

    # 추가할 alias가 있으면 append
    if added_indices:
        with open(zshrc, "a", encoding="utf-8") as f:
            for idx in added_indices:
                name, cmd = alias_defs[idx]
                f.write(f"alias {name}='{cmd}'\n")

    # --- ~/.local/bin/ wrapper 스크립트 생성 ---
    bin_dir = os.path.join(os.environ.get("HOME", ""), ".local", "bin")
    os.makedirs(bin_dir, exist_ok=True)

    wrapper_added = []
    for name, cmd in alias_defs:
        wrapper_path = os.path.join(bin_dir, name)
        wrapper_content = (
            f"#!/bin/bash\n"
            f"# Auto-generated by init_project.py (setup-wf-alias)\n"
            f"# Wrapper script for non-interactive bash environments (e.g. Claude Code Bash tool)\n"
            f"# Equivalent to: alias {name}='{cmd}'\n"
            f'exec {cmd} "$@"\n'
        )
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(wrapper_content)
        os.chmod(wrapper_path, 0o755)
        wrapper_added.append(name)

    added_names = [alias_defs[idx][0] for idx in added_indices]

    result = {
        "status": "ok",
        "zshrc_added": added_names,
        "zshrc_skipped": skipped_names,
        "wrapper_added": wrapper_added,
    }
    print(json.dumps(result, ensure_ascii=False))


# ---------- verify ----------

def cmd_verify():
    os.chdir(_PROJECT_ROOT)

    checks = []
    all_pass = True

    # CLAUDE.md 확인
    if os.path.isfile("CLAUDE.md"):
        checks.append({"item": "CLAUDE.md", "status": "PASS", "detail": "파일 존재"})
    else:
        checks.append({"item": "CLAUDE.md", "status": "FAIL", "detail": "파일 없음"})
        all_pass = False

    # 디렉토리 확인
    for d in [".workflow", ".prompt"]:
        if os.path.isdir(d):
            checks.append({"item": f"{d}/", "status": "PASS", "detail": "디렉토리 존재"})
        else:
            checks.append({"item": f"{d}/", "status": "FAIL", "detail": "디렉토리 없음"})
            all_pass = False

    # 파일 확인
    for f in [".prompt/prompt.txt", ".prompt/memo.txt", ".prompt/querys.txt", ".prompt/history.md", ".claude.env"]:
        if os.path.isfile(f):
            checks.append({"item": f, "status": "PASS", "detail": "파일 존재"})
        else:
            checks.append({"item": f, "status": "FAIL", "detail": "파일 없음"})
            all_pass = False

    # .workflow 파일 확인
    if os.path.isfile(".workflow/registry.json"):
        checks.append({"item": ".workflow/registry.json", "status": "PASS", "detail": "파일 존재"})
    else:
        checks.append({"item": ".workflow/registry.json", "status": "FAIL", "detail": "파일 없음"})
        all_pass = False

    # 워크플로우 alias 확인 (~/.zshrc)
    zshrc = os.path.join(os.environ.get("HOME", ""), ".zshrc")
    alias_names = [
        "step-start", "step-change", "step-end",
    ]
    if os.path.isfile(zshrc):
        zshrc_content = open(zshrc, "r", encoding="utf-8").read()
        for alias_name in alias_names:
            if f"alias {alias_name}=" in zshrc_content:
                checks.append({"item": f"~/.zshrc({alias_name})", "status": "PASS", "detail": "alias 존재"})
            else:
                checks.append({"item": f"~/.zshrc({alias_name})", "status": "FAIL", "detail": "alias 누락"})
                all_pass = False
    else:
        checks.append({"item": "~/.zshrc", "status": "FAIL", "detail": "파일 없음 (워크플로우 alias 미설정)"})
        all_pass = False

    # 워크플로우 wrapper 스크립트 확인 (~/.local/bin/)
    bin_dir = os.path.join(os.environ.get("HOME", ""), ".local", "bin")
    for cmd_name in alias_names:
        wrapper_path = os.path.join(bin_dir, cmd_name)
        if os.path.isfile(wrapper_path) and os.access(wrapper_path, os.X_OK):
            checks.append({"item": f"~/.local/bin/{cmd_name}", "status": "PASS", "detail": "wrapper 스크립트 존재 (실행 가능)"})
        elif os.path.isfile(wrapper_path):
            checks.append({"item": f"~/.local/bin/{cmd_name}", "status": "FAIL", "detail": "wrapper 스크립트 존재하나 실행 권한 없음"})
            all_pass = False
        else:
            checks.append({"item": f"~/.local/bin/{cmd_name}", "status": "FAIL", "detail": "wrapper 스크립트 없음"})
            all_pass = False

    # .gitignore 패턴 확인
    if os.path.isfile(".gitignore"):
        gi_content = open(".gitignore", "r", encoding="utf-8").read()
        for p in [".workflow/", ".claude.env", ".prompt/"]:
            if p in gi_content:
                checks.append({"item": f".gitignore({p})", "status": "PASS", "detail": "패턴 존재"})
            else:
                checks.append({"item": f".gitignore({p})", "status": "FAIL", "detail": "패턴 누락"})
                all_pass = False
    else:
        checks.append({"item": ".gitignore", "status": "FAIL", "detail": "파일 없음"})
        all_pass = False

    result = {
        "all_pass": all_pass,
        "checks": checks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------- 메인 디스패치 ----------

def main():
    if len(sys.argv) < 2:
        print(f"사용법: {sys.argv[0]} <subcommand>")
        print()
        print("서브커맨드:")
        print("  analyze                프로젝트 분석 (JSON 출력)")
        print("  generate-claude-md     CLAUDE.md 생성 (stdin으로 analyze JSON 수신)")
        print("  generate-empty-template CLAUDE.md 빈 템플릿 생성 (analyze 없이)")
        print("  setup-dirs             디렉토리 + 파일 생성")
        print("  setup-gitignore        .gitignore 업데이트")
        print("  setup-wf-alias         워크플로우 alias 설정 (~/.zshrc + ~/.local/bin wrapper)")
        print("  verify                 전체 검증")
        print()
        print("예시:")
        print(f"  {sys.argv[0]} analyze")
        print(f"  {sys.argv[0]} analyze | {sys.argv[0]} generate-claude-md")
        print(f"  {sys.argv[0]} generate-empty-template")
        print(f"  {sys.argv[0]} setup-dirs")
        print(f"  {sys.argv[0]} setup-gitignore")
        print(f"  {sys.argv[0]} setup-wf-alias")
        print(f"  {sys.argv[0]} verify")
        sys.exit(1)

    subcmd = sys.argv[1]
    dispatch = {
        "analyze": cmd_analyze,
        "generate-claude-md": cmd_generate_claude_md,
        "generate-empty-template": cmd_generate_empty_template,
        "setup-dirs": cmd_setup_dirs,
        "setup-gitignore": cmd_setup_gitignore,
        "setup-wf-alias": cmd_setup_wf_alias,
        "verify": cmd_verify,
    }

    if subcmd in dispatch:
        dispatch[subcmd]()
    else:
        print(f"사용법: {sys.argv[0]} <subcommand>")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env -S python3 -u
"""
project_skill_detector.py - 코드베이스 분석 기반 프로젝트 스킬 자동 감지

프로젝트 루트의 매니페스트 파일(package.json, pyproject.toml, go.mod 등)을
분석하여 기술 스택을 식별하고, scope: project 스킬 초안(SKILL.md)을 자동 생성한다.

사용법:
  python3 project_skill_detector.py [프로젝트루트]
  python3 project_skill_detector.py [프로젝트루트] --generate
  python3 project_skill_detector.py --help

출력:
  (기본) 감지 결과를 stdout으로 출력
  (--generate) .claude/skills/project-<도메인명>/SKILL.md 파일 생성
"""

import json
import os
import re
import sys
from datetime import datetime

# 프로젝트 루트 결정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import resolve_project_root

# ─── 스택 감지 규칙 ───────────────────────────────────────────────────────────

# 각 규칙: (파일/디렉터리 패턴, 감지기 함수 또는 None, 기본 스택 태그)
# 감지기 함수는 파일 내용을 파싱하여 세부 스택 태그를 반환한다.


def _detect_node_stack(project_root):
    """package.json에서 Node.js 기술 스택을 감지한다."""
    tags = ["Node.js"]
    pkg_path = os.path.join(project_root, "package.json")

    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return tags

    all_deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        if isinstance(pkg.get(key), dict):
            all_deps.update(pkg[key])

    dep_names = set(all_deps.keys())

    # 프레임워크 감지
    if "next" in dep_names:
        tags.append("Next.js")
    if "react" in dep_names:
        tags.append("React")
    if "vue" in dep_names:
        tags.append("Vue.js")
    if "svelte" in dep_names or "@sveltejs/kit" in dep_names:
        tags.append("Svelte")
    if "express" in dep_names:
        tags.append("Express")
    if "fastify" in dep_names:
        tags.append("Fastify")
    if "nestjs" in dep_names or "@nestjs/core" in dep_names:
        tags.append("NestJS")

    # 상태 관리
    if "zustand" in dep_names:
        tags.append("Zustand")
    if "redux" in dep_names or "@reduxjs/toolkit" in dep_names:
        tags.append("Redux")

    # 테스트
    if "jest" in dep_names:
        tags.append("Jest")
    if "vitest" in dep_names:
        tags.append("Vitest")
    if "playwright" in dep_names or "@playwright/test" in dep_names:
        tags.append("Playwright")

    # 빌드 도구
    if "vite" in dep_names:
        tags.append("Vite")
    if "webpack" in dep_names:
        tags.append("Webpack")
    if "turbo" in dep_names:
        tags.append("Turborepo")

    # ORM / DB
    if "prisma" in dep_names or "@prisma/client" in dep_names:
        tags.append("Prisma")
    if "typeorm" in dep_names:
        tags.append("TypeORM")
    if "drizzle-orm" in dep_names:
        tags.append("Drizzle")

    # TypeScript
    if "typescript" in dep_names:
        tags.append("TypeScript")

    return tags


def _detect_python_stack(project_root):
    """pyproject.toml 또는 requirements.txt에서 Python 기술 스택을 감지한다."""
    tags = ["Python"]

    # pyproject.toml 파싱 (간이 TOML 파서 - dependencies 섹션만)
    pyproject_path = os.path.join(project_root, "pyproject.toml")
    req_path = os.path.join(project_root, "requirements.txt")

    dep_text = ""

    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 의존성 섹션만 추출하여 파싱 범위 최소화
            dep_sections = re.findall(
                r'\[(?:project\.(?:optional-)?dependencies|tool\.poetry\.(?:dev-)?dependencies)\](.*?)(?=\n\[|\Z)',
                content,
                re.DOTALL,
            )
            if dep_sections:
                dep_text = "\n".join(dep_sections)
            else:
                # 의존성 섹션 패턴 매칭 실패 시 전체 내용으로 폴백
                dep_text = content
        except (IOError, OSError):
            pass

    if os.path.isfile(req_path):
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                dep_text += "\n" + f.read()
        except (IOError, OSError):
            pass

    dep_lower = dep_text.lower()

    # 프레임워크 감지
    if "fastapi" in dep_lower:
        tags.append("FastAPI")
    if "django" in dep_lower:
        tags.append("Django")
    if "flask" in dep_lower:
        tags.append("Flask")
    if "starlette" in dep_lower:
        tags.append("Starlette")

    # ORM / DB
    if "sqlalchemy" in dep_lower:
        tags.append("SQLAlchemy")
    if "alembic" in dep_lower:
        tags.append("Alembic")
    if "tortoise" in dep_lower:
        tags.append("Tortoise ORM")
    if "sqlmodel" in dep_lower:
        tags.append("SQLModel")

    # 테스트
    if "pytest" in dep_lower:
        tags.append("pytest")
    if "hypothesis" in dep_lower:
        tags.append("Hypothesis")

    # ML / Data
    if "pandas" in dep_lower:
        tags.append("pandas")
    if "numpy" in dep_lower:
        tags.append("NumPy")
    if "torch" in dep_lower or "pytorch" in dep_lower:
        tags.append("PyTorch")
    if "tensorflow" in dep_lower:
        tags.append("TensorFlow")

    # 비동기
    if "uvicorn" in dep_lower:
        tags.append("Uvicorn")
    if "celery" in dep_lower:
        tags.append("Celery")

    # 타입
    if "pydantic" in dep_lower:
        tags.append("Pydantic")
    if "mypy" in dep_lower:
        tags.append("mypy")

    return tags


def _detect_go_stack(project_root):
    """go.mod에서 Go 기술 스택을 감지한다."""
    tags = ["Go"]
    gomod_path = os.path.join(project_root, "go.mod")

    try:
        with open(gomod_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return tags

    content_lower = content.lower()

    if "gin-gonic" in content_lower:
        tags.append("Gin")
    if "echo" in content_lower and "labstack" in content_lower:
        tags.append("Echo")
    if "fiber" in content_lower and "gofiber" in content_lower:
        tags.append("Fiber")
    if "gorm" in content_lower:
        tags.append("GORM")
    if "grpc" in content_lower:
        tags.append("gRPC")

    return tags


def _detect_rust_stack(project_root):
    """Cargo.toml에서 Rust 기술 스택을 감지한다."""
    tags = ["Rust"]
    cargo_path = os.path.join(project_root, "Cargo.toml")

    try:
        with open(cargo_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return tags

    content_lower = content.lower()

    if "actix" in content_lower:
        tags.append("Actix")
    if "axum" in content_lower:
        tags.append("Axum")
    if "tokio" in content_lower:
        tags.append("Tokio")
    if "serde" in content_lower:
        tags.append("Serde")
    if "diesel" in content_lower:
        tags.append("Diesel")
    if "sqlx" in content_lower:
        tags.append("SQLx")

    return tags


def detect_project_stack(project_root):
    """프로젝트 루트에서 기술 스택을 식별한다.

    매니페스트 파일 존재 여부를 확인하고, 존재하는 경우
    파일 내용을 파싱하여 세부 기술 스택을 감지한다.

    Args:
        project_root: 프로젝트 루트 절대 경로

    Returns:
        dict: {
            "stacks": [스택 태그 목록],
            "infra": [인프라 태그 목록],
            "domain_name": 프로젝트 도메인명 (스킬 디렉터리명에 사용),
            "project_name": 프로젝트 디렉터리명,
        }
    """
    stacks = []
    infra = []

    # 1. 언어/프레임워크 감지
    if os.path.isfile(os.path.join(project_root, "package.json")):
        stacks.extend(_detect_node_stack(project_root))

    if os.path.isfile(os.path.join(project_root, "pyproject.toml")) or \
       os.path.isfile(os.path.join(project_root, "requirements.txt")):
        stacks.extend(_detect_python_stack(project_root))

    if os.path.isfile(os.path.join(project_root, "go.mod")):
        stacks.extend(_detect_go_stack(project_root))

    if os.path.isfile(os.path.join(project_root, "Cargo.toml")):
        stacks.extend(_detect_rust_stack(project_root))

    # 2. 인프라 감지
    if os.path.isfile(os.path.join(project_root, "docker-compose.yml")) or \
       os.path.isfile(os.path.join(project_root, "docker-compose.yaml")) or \
       os.path.isfile(os.path.join(project_root, "compose.yml")) or \
       os.path.isfile(os.path.join(project_root, "compose.yaml")):
        infra.append("Docker Compose")

    if os.path.isfile(os.path.join(project_root, "Dockerfile")):
        infra.append("Docker")

    if os.path.isdir(os.path.join(project_root, ".github", "workflows")):
        infra.append("GitHub Actions CI/CD")

    if os.path.isfile(os.path.join(project_root, ".gitlab-ci.yml")):
        infra.append("GitLab CI")

    if os.path.isfile(os.path.join(project_root, "Jenkinsfile")):
        infra.append("Jenkins")

    if os.path.isfile(os.path.join(project_root, "terraform.tf")) or \
       os.path.isdir(os.path.join(project_root, "terraform")):
        infra.append("Terraform")

    if os.path.isfile(os.path.join(project_root, "serverless.yml")):
        infra.append("Serverless Framework")

    if os.path.isdir(os.path.join(project_root, "k8s")) or \
       os.path.isdir(os.path.join(project_root, "kubernetes")):
        infra.append("Kubernetes")

    # 3. 모노레포 감지
    if os.path.isfile(os.path.join(project_root, "pnpm-workspace.yaml")) or \
       os.path.isfile(os.path.join(project_root, "lerna.json")):
        infra.append("Monorepo")

    # 4. 도메인명 결정
    project_name = os.path.basename(os.path.abspath(project_root))
    # 도메인명은 프로젝트 디렉터리명을 소문자+하이픈으로 정규화
    domain_name = re.sub(r"[^a-z0-9-]", "-", project_name.lower())
    domain_name = re.sub(r"-+", "-", domain_name).strip("-")
    if not domain_name:
        domain_name = "unknown"

    # 5. 디렉터리 구조 요약
    dir_summary = _summarize_directory_structure(project_root)

    return {
        "stacks": stacks,
        "infra": infra,
        "domain_name": domain_name,
        "project_name": project_name,
        "dir_summary": dir_summary,
    }


def _summarize_directory_structure(project_root, max_depth=2):
    """프로젝트 루트의 최상위 디렉터리 구조를 요약한다.

    .git, node_modules, __pycache__, .claude 등 무관한 디렉터리는 제외한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        max_depth: 최대 탐색 깊이

    Returns:
        list[str]: 디렉터리 경로 목록 (상대 경로)
    """
    exclude = {
        ".git", "node_modules", "__pycache__", ".claude", ".workflow",
        ".venv", "venv", ".env", "dist", "build", ".next", ".cache",
        "coverage", ".mypy_cache", ".pytest_cache", "target",
    }

    dirs = []

    def _walk(path, depth, prefix):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(path))
        except (PermissionError, OSError):
            return

        for entry in entries:
            if entry.startswith(".") and entry in exclude:
                continue
            if entry in exclude:
                continue
            full = os.path.join(path, entry)
            if os.path.islink(full):
                continue
            if os.path.isdir(full):
                rel = os.path.relpath(full, project_root)
                dirs.append(rel)
                _walk(full, depth + 1, prefix + "  ")

    _walk(project_root, 0, "")
    return dirs[:50]  # 최대 50개까지만


def generate_project_skill(detection_result, project_root):
    """감지된 스택 정보를 기반으로 프로젝트 스킬 SKILL.md 초안을 생성한다.

    Args:
        detection_result: detect_project_stack()의 반환값
        project_root: 프로젝트 루트 절대 경로

    Returns:
        tuple: (skill_dir_path, skill_content) - 스킬 디렉터리 경로와 SKILL.md 내용
    """
    domain = detection_result["domain_name"]
    project_name = detection_result["project_name"]
    stacks = detection_result["stacks"]
    infra = detection_result["infra"]
    dir_summary = detection_result.get("dir_summary", [])

    skill_name = f"project-{domain}"
    skill_dir = os.path.join(project_root, ".claude", "skills", skill_name)

    # 스택 문자열
    stack_str = ", ".join(stacks) if stacks else "(감지된 스택 없음)"
    infra_str = ", ".join(infra) if infra else "(감지된 인프라 없음)"

    # 트리거 키워드 생성
    triggers = []
    for s in stacks[:5]:
        triggers.append(f"'{s}'")
    triggers.append(f"'{project_name}'")
    trigger_str = ", ".join(triggers)

    # 디렉터리 구조 요약 (상위 디렉터리만)
    top_dirs = [d for d in dir_summary if "/" not in d][:10]
    dir_lines = "\n".join(f"- `{d}/`" for d in top_dirs) if top_dirs else "- (디렉터리 구조 미감지)"

    # SKILL.md 생성
    today = datetime.now().strftime("%Y-%m-%d")
    content = f"""---
name: {skill_name}
scope: project
description: "Project-specific skill for {project_name}. Auto-detected stack: {stack_str}. Triggers: {trigger_str}."
license: "Apache-2.0"
---

# {project_name} 프로젝트 스킬

> 이 파일은 `project_skill_detector.py`에 의해 자동 생성되었습니다 ({today}).
> 프로젝트 고유 도메인 지식, 코딩 컨벤션, 금지 패턴 등을 추가하세요.

## 기술 스택

{stack_str}

## 인프라

{infra_str}

## 디렉터리 구조

{dir_lines}

## 코딩 컨벤션

> TODO: 프로젝트 고유 코딩 컨벤션을 기술하세요.

- 네이밍 규칙: (미설정)
- 파일 구조 규칙: (미설정)
- 커밋 메시지 규칙: (미설정)

## 도메인 용어집

> TODO: 프로젝트 고유 도메인 용어를 정의하세요.

| 용어 | 정의 |
|------|------|
| (예시) | (예시 정의) |

## 금지 패턴

> TODO: 프로젝트에서 금지하는 패턴을 기술하세요.

- (미설정)

## ADR 요약

> TODO: 주요 Architecture Decision Records를 요약하세요.

- (미설정)
"""

    return skill_dir, content


def format_detection_result(result):
    """감지 결과를 사람이 읽기 쉬운 형태로 포맷한다.

    Args:
        result: detect_project_stack()의 반환값

    Returns:
        str: 포맷된 감지 결과 문자열
    """
    lines = []
    lines.append(f"Project: {result['project_name']}")
    lines.append(f"Domain:  project-{result['domain_name']}")
    lines.append("")

    if result["stacks"]:
        lines.append("Stacks:")
        for s in result["stacks"]:
            lines.append(f"  - {s}")
    else:
        lines.append("Stacks: (none detected)")

    lines.append("")

    if result["infra"]:
        lines.append("Infrastructure:")
        for i in result["infra"]:
            lines.append(f"  - {i}")
    else:
        lines.append("Infrastructure: (none detected)")

    lines.append("")

    top_dirs = [d for d in result.get("dir_summary", []) if "/" not in d][:10]
    if top_dirs:
        lines.append("Top-level directories:")
        for d in top_dirs:
            lines.append(f"  - {d}/")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("사용법: python3 project_skill_detector.py <프로젝트루트> [--generate]", file=sys.stderr)
        print("", file=sys.stderr)
        print("옵션:", file=sys.stderr)
        print("  <프로젝트루트>  감지할 프로젝트의 루트 디렉터리 경로", file=sys.stderr)
        print("  --generate      감지 결과를 기반으로 SKILL.md 파일을 실제 생성", file=sys.stderr)
        print("", file=sys.stderr)
        print("예시:", file=sys.stderr)
        print("  python3 project_skill_detector.py .", file=sys.stderr)
        print("  python3 project_skill_detector.py /path/to/project --generate", file=sys.stderr)
        sys.exit(0 if sys.argv[1:] == ["--help"] else 1)

    project_root = os.path.abspath(sys.argv[1])
    generate = "--generate" in sys.argv

    if not os.path.isdir(project_root):
        print(f"[ERROR] 디렉터리를 찾을 수 없습니다: {project_root}", file=sys.stderr)
        sys.exit(1)

    # 스택 감지
    result = detect_project_stack(project_root)

    # 감지 결과 출력
    print(format_detection_result(result))

    # --generate 플래그 시 SKILL.md 파일 생성
    if generate:
        if not result["stacks"] and not result["infra"]:
            print("\n[WARN] 감지된 스택/인프라가 없어 SKILL.md 생성을 건너뜁니다.", file=sys.stderr)
            sys.exit(0)

        skill_dir, content = generate_project_skill(result, project_root)
        os.makedirs(skill_dir, exist_ok=True)
        skill_path = os.path.join(skill_dir, "SKILL.md")

        if os.path.isfile(skill_path):
            print(f"\n[WARN] 이미 존재하는 파일을 덮어씁니다: {skill_path}", file=sys.stderr)

        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"\nGenerated: {skill_path}")


if __name__ == "__main__":
    main()

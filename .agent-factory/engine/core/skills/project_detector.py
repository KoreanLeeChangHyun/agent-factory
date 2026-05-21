#!/usr/bin/env -S python3 -u
"""project_skill_detector.py - Automatic detection of project skills based on codebase analysis.

Manifest files (package.json, pyproject.toml, go.mod, etc.) in the project root.
Analysis identifies the technology stack and automatically creates a scope: project skill draft (SKILL.md).

Usage:
  flow-detect <project root>
  flow-detect <project root> --generate
  flow-detect --help

output of power:
  (Default) Output detection results to stdout
  (--generate) Generate .claude/skills/project-<domain name>/SKILL.md file
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime

_agent_factory_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)

from engine.common import resolve_project_root


def _build_common_epilog() -> str:
    """Return CLI help footer without depending on flow runtime modules."""
    return (
        "Workflow version: 2.1.25 \n"
        "Documentation: See .agent-factory/docs/ or .claude/rules/workflow.md \n"
        "Ticket management: flow-kanban <subcommand> --help"
    )

# ─── Stack detection rules ───────────────────────────────────────────────────────────────

# Each rule: (file/directory pattern, detector function or None, default stack tag)
# The detector function parses the file contents and returns detailed stack tags.


def _detect_node_stack(project_root: str) -> list[str]:
    """Detect Node.js technology stack in package.json.

    Args:
        project_root: absolute path to the project root

    Returns:
        List of detected stack tags. Contains at least ["Node.js"].
    """
    tags = ["Node.js"]
    pkg_path = os.path.join(project_root, "package.json")

    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return tags

    all_deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        if isinstance(pkg.get(key), dict):
            all_deps.update(pkg[key])

    dep_names = set(all_deps.keys())

    # Framework detection
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

    # State Management
    if "zustand" in dep_names:
        tags.append("Zustand")
    if "redux" in dep_names or "@reduxjs/toolkit" in dep_names:
        tags.append("Redux")

    # test
    if "jest" in dep_names:
        tags.append("Jest")
    if "vitest" in dep_names:
        tags.append("Vitest")
    if "playwright" in dep_names or "@playwright/test" in dep_names:
        tags.append("Playwright")

    # build tools
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


def _detect_python_stack(project_root: str) -> list[str]:
    """Detect your Python technology stack in pyproject.toml or requirements.txt.

    Args:
        project_root: absolute path to the project root

    Returns:
        List of detected stack tags. Contains at least ["Python"].
    """
    tags = ["Python"]

    # Parse pyproject.toml (simple TOML parser - dependencies section only)
    pyproject_path = os.path.join(project_root, "pyproject.toml")
    req_path = os.path.join(project_root, "requirements.txt")

    dep_text = ""

    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Minimize parsing scope by extracting only dependency sections
            dep_sections = re.findall(
                r'\[(?:project\.(?:optional-)?dependencies|tool\.poetry\.(?:dev-)?dependencies)\](.*?)(?=\n\[|\Z)',
                content,
                re.DOTALL,
            )
            if dep_sections:
                dep_text = "\n".join(dep_sections)
            else:
                # Fallback to full content when dependency section pattern matching fails
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

    # Framework detection
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

    # test
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

    # asynchronous
    if "uvicorn" in dep_lower:
        tags.append("Uvicorn")
    if "celery" in dep_lower:
        tags.append("Celery")

    # type
    if "pydantic" in dep_lower:
        tags.append("Pydantic")
    if "mypy" in dep_lower:
        tags.append("mypy")

    return tags


def _detect_go_stack(project_root: str) -> list[str]:
    """Detect the Go technology stack in go.mod.

    Args:
        project_root: absolute path to the project root

    Returns:
        List of detected stack tags. Contains at least ["Go"].
    """
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


def _detect_rust_stack(project_root: str) -> list[str]:
    """Detect Rust technology stack in Cargo.toml.

    Args:
        project_root: absolute path to the project root

    Returns:
        List of detected stack tags. Contains at least ["Rust"].
    """
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


def detect_project_stack(project_root: str) -> dict[str, object]:
    """Identify the technology stack at the project root.

    Check if the manifest file exists, if it exists
    Detect detailed technology stack by parsing file contents.

    Args:
        project_root: absolute path to the project root

    Returns:
        Detection result dictionary. Includes the following keys:
        - stacks (list[str]): List of detected technology stack tags
        - infra (list[str]): List of detected infrastructure tags
        - domain_name (str): Project domain name (used for skill directory name)
        - project_name (str): Project directory name
        - dir_summary (list[str]): Top-level directory structure summary (relative path)
    """
    stacks: list[str] = []
    infra: list[str] = []

    # 1. Language/framework detection
    if os.path.isfile(os.path.join(project_root, "package.json")):
        stacks.extend(_detect_node_stack(project_root))

    if os.path.isfile(os.path.join(project_root, "pyproject.toml")) or \
       os.path.isfile(os.path.join(project_root, "requirements.txt")):
        stacks.extend(_detect_python_stack(project_root))

    if os.path.isfile(os.path.join(project_root, "go.mod")):
        stacks.extend(_detect_go_stack(project_root))

    if os.path.isfile(os.path.join(project_root, "Cargo.toml")):
        stacks.extend(_detect_rust_stack(project_root))

    # 2. Infrastructure detection
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

    # 3. Monorepo detection
    if os.path.isfile(os.path.join(project_root, "pnpm-workspace.yaml")) or \
       os.path.isfile(os.path.join(project_root, "lerna.json")):
        infra.append("Monorepo")

    # 4. Decide on a domain name
    project_name = os.path.basename(os.path.abspath(project_root))
    # The domain name is normalized from the project directory name to lowercase letters + hyphens.
    domain_name = re.sub(r"[^a-z0-9-]", "-", project_name.lower())
    domain_name = re.sub(r"-+", "-", domain_name).strip("-")
    if not domain_name:
        domain_name = "unknown"

    # 5. Directory Structure Summary
    dir_summary = _summarize_directory_structure(project_root)

    return {
        "stacks": stacks,
        "infra": infra,
        "domain_name": domain_name,
        "project_name": project_name,
        "dir_summary": dir_summary,
    }


def _summarize_directory_structure(project_root: str, max_depth: int = 2) -> list[str]:
    """Summarizes the top-level directory structure of the project root.

    Exclude irrelevant directories such as .git, node_modules, __pycache__, and .claude.

    Args:
        project_root: absolute path to the project root
        max_depth: maximum search depth (default: 2)

    Returns:
        List of directory paths (relative paths). Up to 50 pieces.
    """
    exclude = {
        ".git", "node_modules", "__pycache__", ".claude", ".agent-factory",
        ".venv", "venv", ".env", "dist", "build", ".next", ".cache",
        "coverage", ".mypy_cache", ".pytest_cache", "target",
    }

    dirs: list[str] = []

    def _walk(path: str, depth: int, prefix: str) -> None:
        """Searches directories recursively."""
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
    return dirs[:50]  # Up to 50 items only


def generate_project_skill(
    detection_result: dict[str, object],
    project_root: str,
) -> tuple[str, str]:
    """Create a draft project skill SKILL.md based on the detected stack information.

    Args:
        detection_result: Return value of detect_project_stack()
        project_root: absolute path to the project root

    Returns:
        2-tuple (skill_dir_path, skill_content):
        - skill_dir_path: Absolute path to skill directory
        - skill_content: SKILL.md file content string
    """
    domain = detection_result["domain_name"]
    project_name = detection_result["project_name"]
    stacks: list[str] = detection_result["stacks"]  # type: ignore[assignment]
    infra: list[str] = detection_result["infra"]  # type: ignore[assignment]
    dir_summary: list[str] = detection_result.get("dir_summary", [])  # type: ignore[assignment]

    skill_name = f"project-{domain}"
    skill_dir = os.path.join(project_root, ".claude", "skills", skill_name)

    # stack string
    stack_str = ", ".join(stacks) if stacks else "(no stack detected)"
    infra_str = ", ".join(infra) if infra else "(No infrastructure detected)"

    # Create trigger keyword
    triggers: list[str] = []
    for s in stacks[:5]:
        triggers.append(f"'{s}'")
    triggers.append(f"'{project_name}'")
    trigger_str = ", ".join(triggers)

    # Directory structure summary (parent directory only)
    top_dirs = [d for d in dir_summary if "/" not in d][:10]
    dir_lines = "\n".join(f"- `{d}/`" for d in top_dirs) if top_dirs else "- (Directory structure not detected)"

    # Create SKILL.md
    today = datetime.now().strftime("%Y-%m-%d")
    content = f"""---
name: {skill_name}
scope: project
description: "Project-specific skill for {project_name}. Auto-detected stack: {stack_str}. Triggers: {trigger_str}."
license: "Apache-2.0"
---

# {project_name} project skill

> This file was automatically generated by `project_skill_detector.py` ({today}).
> Add project-specific domain knowledge, coding conventions, prohibited patterns, etc.

##Technology Stack

{stack_str}

## infrastructure

{infra_str}

## Directory structure

{dir_lines}

## Coding Convention

> TODO: Describe project-specific coding conventions.

- Naming rule: (not set)
- File structure rules: (not set)
- Commit message rule: (not set)

## Domain Glossary

> TODO: Define project-specific domain terms.

| Terminology | definition |
|------|------|
| (Example) | (example definition) |

## Prohibited pattern

> TODO: Describe patterns that are prohibited in your project.

- (Not set)

##ADRSummary

> TODO: Summarize key Architecture Decision Records.

- (Not set)
"""

    return skill_dir, content


def format_detection_result(result: dict[str, object]) -> str:
    """Format the detection results in a format that is easy for humans to read.

    Args:
        result: Return value of detect_project_stack()

    Returns:
        Formatted detection result string.
    """
    lines: list[str] = []
    lines.append(f"Project: {result['project_name']}")
    lines.append(f"Domain:  project-{result['domain_name']}")
    lines.append("")

    stacks: list[str] = result["stacks"]  # type: ignore[assignment]
    infra: list[str] = result["infra"]  # type: ignore[assignment]
    dir_summary: list[str] = result.get("dir_summary", [])  # type: ignore[assignment]

    if stacks:
        lines.append("Stacks:")
        for s in stacks:
            lines.append(f"  - {s}")
    else:
        lines.append("Stacks: (none detected)")

    lines.append("")

    if infra:
        lines.append("Infrastructure:")
        for i in infra:
            lines.append(f"  - {i}")
    else:
        lines.append("Infrastructure: (none detected)")

    lines.append("")

    top_dirs = [d for d in dir_summary if "/" not in d][:10]
    if top_dirs:
        lines.append("Top-level directories:")
        for d in top_dirs:
            lines.append(f"  - {d}/")

    return "\n".join(lines)


def main() -> None:
    """CLI entry point. Analyzes the project root and outputs technology stack detection results.

    If the --generate flag is present, the SKILL.md file is also created.

    Raises:
        SystemExit: Insufficient arguments (1), directory does not exist (1), normal completion (0).
    """
    parser = argparse.ArgumentParser(
        prog="flow-detect",
        description="Automatic detection of project skills based on code base analysis",
        epilog=_build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "project_root",
        metavar="project root",
        help="Root directory path of the project to be discovered",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        default=False,
        help="Actual creation of SKILL.md file based on detection results",
    )

    args = parser.parse_args()
    project_root = os.path.abspath(args.project_root)
    generate = args.generate

    if not os.path.isdir(project_root):
        print(f"[ERROR] Directory not found: {project_root}", file=sys.stderr)
        sys.exit(1)

    # stack detection
    result = detect_project_stack(project_root)
    stacks_detected: list[str] = result["stacks"]  # type: ignore[assignment]

    # Detection result output
    domain_name = result.get("domain_name", "unknown")
    print("[STATE] DETECT", flush=True)
    print(f">> domain=project-{domain_name}, stacks={len(stacks_detected)}", flush=True)
    print(format_detection_result(result))

    # Generate SKILL.md file with --generate flag
    if generate:
        stacks: list[str] = result["stacks"]  # type: ignore[assignment]
        infra: list[str] = result["infra"]  # type: ignore[assignment]
        if not stacks and not infra:
            print("\n [WARN] Skipping SKILL.md creation as no stack/infrastructure detected.", file=sys.stderr)
            sys.exit(0)

        skill_dir, content = generate_project_skill(result, project_root)
        os.makedirs(skill_dir, exist_ok=True)
        skill_path = os.path.join(skill_dir, "SKILL.md")

        if os.path.isfile(skill_path):
            print(f"\n [WARN] Overwrite already existing file: {skill_path}", file=sys.stderr)

        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"\nGenerated: {skill_path}")


if __name__ == "__main__":
    main()

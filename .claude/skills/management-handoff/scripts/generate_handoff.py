#!/usr/bin/env python3
"""
HANDOFF.md 자동 생성 스크립트

현재 작업 상태를 자동으로 감지하여 HANDOFF.md를 생성합니다.
이 스크립트는 Claude Code가 직접 실행하거나, Bash 훅에서 호출할 수 있습니다.

사용법:
    python3 generate_handoff.py [--workflow-dir <path>] [--output <path>]

Arguments:
    --workflow-dir  워크플로우 디렉토리 경로 (기본값: .workflow)
    --output        출력 파일 경로 (기본값: 자동 감지)
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """프로젝트 루트 디렉토리 추정."""
    # .git 디렉토리로 프로젝트 루트 찾기
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd()


def find_recent_workflow(workflow_dir: Path) -> Optional[Path]:
    """가장 최근 워크플로우 디렉토리 찾기."""
    if not workflow_dir.exists():
        return None

    recent = None
    recent_time = 0

    for command_dir in workflow_dir.iterdir():
        if not command_dir.is_dir():
            continue
        for work_dir in command_dir.iterdir():
            if not work_dir.is_dir():
                continue
            # YYYYMMDD-HHMMSS 패턴 매칭
            if re.match(r"^\d{8}-\d{6}-", work_dir.name):
                mtime = work_dir.stat().st_mtime
                if mtime > recent_time:
                    recent_time = mtime
                    recent = work_dir

    return recent


def extract_from_plan(plan_path: Path) -> dict:
    """계획서에서 정보 추출."""
    result = {
        "work_id": "",
        "command": "",
        "title": "",
        "tasks": [],
    }

    if not plan_path.exists():
        return result

    content = plan_path.read_text(encoding="utf-8")

    # 작업 ID 추출
    work_id_match = re.search(r"작업 ID:\s*(\d+)", content)
    if work_id_match:
        result["work_id"] = work_id_match.group(1)

    # 명령어 추출
    command_match = re.search(r"명령어:\s*(\w+)", content)
    if command_match:
        result["command"] = command_match.group(1)

    # 태스크 목록 추출 (테이블 형식)
    task_pattern = r"\|\s*(W\d+)\s*\|\s*([^|]+)\s*\|"
    for match in re.finditer(task_pattern, content):
        result["tasks"].append({
            "id": match.group(1).strip(),
            "name": match.group(2).strip(),
            "completed": False,
        })

    return result


def extract_from_work_files(work_dir: Path) -> list:
    """작업 내역 파일에서 완료된 태스크 추출."""
    completed = []

    # CASE1: work.md
    work_md = work_dir / "work.md"
    if work_md.exists():
        completed.append("CASE1 작업 완료")
        return completed

    # CASE2: work/ 디렉토리
    work_subdir = work_dir / "work"
    if work_subdir.exists() and work_subdir.is_dir():
        for f in work_subdir.iterdir():
            if f.suffix == ".md":
                # W01-task-name.md 형식에서 ID 추출
                match = re.match(r"(W\d+)", f.stem)
                if match:
                    completed.append(match.group(1))

    return completed


def extract_recent_changes(claude_md_path: Path) -> list:
    """CLAUDE.md에서 Recent Changes 추출."""
    changes = []

    if not claude_md_path.exists():
        return changes

    content = claude_md_path.read_text(encoding="utf-8")

    # Recent Changes 섹션 찾기
    changes_match = re.search(
        r"## Recent Changes\n(.*?)(?=\n##|\Z)",
        content,
        re.DOTALL
    )

    if changes_match:
        section = changes_match.group(1)
        # 각 변경 항목 추출 (- **날짜**: 내용 형식)
        for match in re.finditer(r"-\s+\*\*([^*]+)\*\*:\s*(.+?)(?=\n-|\n\n|\Z)", section, re.DOTALL):
            changes.append({
                "date": match.group(1).strip(),
                "content": match.group(2).strip().split("\n")[0],
            })

    return changes[:3]  # 최근 3개만


def get_modified_files(project_root: Path) -> list:
    """Git에서 수정된 파일 목록 가져오기."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                status = line[:2].strip()
                filepath = line[3:].strip()
                files.append({"status": status, "path": filepath})

        return files[:10]  # 최대 10개
    except Exception:
        return []


def generate_handoff(
    workflow_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> str:
    """HANDOFF.md 내용 생성."""
    project_root = get_project_root()

    if workflow_dir is None:
        workflow_dir = project_root / ".workflow"

    # 최근 워크플로우 찾기
    recent_work = find_recent_workflow(workflow_dir)

    # 정보 수집
    plan_info = {}
    completed_tasks = []

    if recent_work:
        plan_path = recent_work / "plan.md"
        plan_info = extract_from_plan(plan_path)
        completed_tasks = extract_from_work_files(recent_work)

    # CLAUDE.md에서 최근 변경 사항 추출
    claude_md = project_root / "CLAUDE.md"
    recent_changes = extract_recent_changes(claude_md)

    # 수정된 파일 목록
    modified_files = get_modified_files(project_root)

    # 출력 경로 결정
    if output_path is None:
        if recent_work:
            output_path = recent_work / "HANDOFF.md"
        else:
            prompt_dir = project_root / ".prompt"
            prompt_dir.mkdir(exist_ok=True)
            output_path = prompt_dir / "handoff.md"

    # HANDOFF.md 생성
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = f"""# Handoff Document

- 생성일: {now} (KST)
"""

    if plan_info.get("work_id"):
        content += f"- 작업 ID: {plan_info['work_id']}\n"
    if plan_info.get("command"):
        content += f"- 명령어: {plan_info['command']}\n"

    content += """
## 현재 상태 요약

[자동 생성됨 - 수동으로 상태 요약 작성 필요]

## 완료된 항목

"""

    if completed_tasks:
        for task in completed_tasks:
            content += f"- [x] {task}\n"
    else:
        content += "- [x] (완료 항목 없음 - 수동 작성 필요)\n"

    content += """
## 미완료 항목

"""

    if plan_info.get("tasks"):
        for task in plan_info["tasks"]:
            if task["id"] not in completed_tasks:
                content += f"- [ ] {task['id']}: {task['name']}\n"
    else:
        content += "- [ ] (미완료 항목 - 수동 작성 필요)\n"

    content += """
## 다음 단계

1. [즉시 수행해야 할 작업 - 수동 작성 필요]
2. [후속 작업]

## 핵심 결정 사항

| 결정 | 근거 | 영향 범위 |
|------|------|----------|
| - | - | - |

## 참조 파일

다음 세션에서 반드시 읽어야 할 파일:

| 파일 | 용도 |
|------|------|
"""

    if recent_work and (recent_work / "plan.md").exists():
        content += f"| `{recent_work.relative_to(project_root)}/plan.md` | 계획서 확인 |\n"

    if modified_files:
        for f in modified_files[:5]:
            content += f"| `{f['path']}` | 최근 수정 ({f['status']}) |\n"

    content += """
## 최근 변경 사항 (CLAUDE.md 기준)

"""

    if recent_changes:
        for change in recent_changes:
            content += f"- **{change['date']}**: {change['content']}\n"
    else:
        content += "- (최근 변경 사항 없음)\n"

    content += """
## 주의사항

- [다음 세션에서 알아야 할 중요 정보 - 수동 작성 필요]

## 이전 핸드오프 참조

이전 핸드오프 문서: 없음
"""

    return content


def main():
    parser = argparse.ArgumentParser(description="HANDOFF.md 자동 생성")
    parser.add_argument("--workflow-dir", type=Path, help="워크플로우 디렉토리 경로")
    parser.add_argument("--output", type=Path, help="출력 파일 경로")
    parser.add_argument("--dry-run", action="store_true", help="내용만 출력하고 파일 생성 안함")

    args = parser.parse_args()

    content = generate_handoff(
        workflow_dir=args.workflow_dir,
        output_path=args.output,
    )

    if args.dry_run:
        print(content)
    else:
        output = args.output
        if output is None:
            project_root = get_project_root()
            workflow_dir = args.workflow_dir or (project_root / ".workflow")
            recent_work = find_recent_workflow(workflow_dir)

            if recent_work:
                output = recent_work / "HANDOFF.md"
            else:
                prompt_dir = project_root / ".prompt"
                prompt_dir.mkdir(exist_ok=True)
                output = prompt_dir / "handoff.md"

        output.write_text(content, encoding="utf-8")
        print(f"HANDOFF.md 생성 완료: {output}")


if __name__ == "__main__":
    main()

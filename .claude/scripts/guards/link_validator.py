#!/usr/bin/env python3
"""마크다운 파일 링크 유효성 검사 스크립트.

.workflow/ 디렉터리 내 report.md, plan.md 파일에서 마크다운 링크를 추출하고,
각 링크 대상 파일의 존재 여부를 검증한다.

이 스크립트는 자동 hook에 연결되어 있지 않으며, 수동으로 실행하는 유틸리티입니다.
워크플로우 완료 후 또는 보고서 작성 후 링크 유효성을 점검할 때 사용합니다.

실행 예시:
    python3 .claude/scripts/guards/link_validator.py
    python3 .claude/scripts/guards/link_validator.py --active-only

주요 함수:
    main: 진입점, CLI 인자 파싱 후 검증 수행
    scan_markdown_files: 스캔 대상 마크다운 파일 목록 반환
    extract_links: 마크다운 텍스트에서 링크 추출
    validate_link: 단일 링크의 유효성 검사
    validate_all: 전체 파일 목록에 대한 링크 검증 실행
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


# 마크다운 링크 패턴: [text](path)
_MD_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# 외부 링크 접두사
_EXTERNAL_PREFIXES: tuple[str, ...] = ("http://", "https://")

# 플레이스홀더 패턴 (템플릿 링크 감지)
_PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"\{\{[^}]+\}\}")

# 프로젝트 루트 기준 경로 접두사
_PROJECT_ROOT_PREFIXES: tuple[str, ...] = (".workflow/", ".claude/")


def _find_project_root() -> Path:
    """프로젝트 루트 디렉터리를 찾아 반환한다.

    이 스크립트는 .claude/scripts/guards/ 하위에 위치하므로,
    3단계 상위 디렉터리가 프로젝트 루트이다.

    Returns:
        프로젝트 루트 Path 객체.
    """
    return Path(__file__).resolve().parent.parent.parent.parent


def scan_markdown_files(
    project_root: Path,
    active_only: bool = False,
) -> list[Path]:
    """검증 대상 마크다운 파일 목록을 반환한다.

    .workflow/ 디렉터리 하위의 report.md, plan.md 파일을 수집한다.
    active_only=True이면 .workflow/.history/는 제외한다.

    Args:
        project_root: 프로젝트 루트 디렉터리 경로.
        active_only: True이면 활성 워크플로우(.workflow/ 직접 하위)만 스캔.

    Returns:
        스캔 대상 마크다운 파일 경로 목록.
    """
    workflow_dir = project_root / ".workflow"
    if not workflow_dir.exists():
        return []

    target_filenames: set[str] = {"report.md", "plan.md"}
    result: list[Path] = []

    # 활성 워크플로우 스캔 (.workflow/ 직접 하위, .history/ 제외)
    for entry in workflow_dir.iterdir():
        if entry.name == ".history":
            continue
        if entry.is_dir():
            for md_file in entry.rglob("*.md"):
                if md_file.name in target_filenames:
                    result.append(md_file)

    # 히스토리 스캔 (active_only=False 일 때)
    if not active_only:
        history_dir = workflow_dir / ".history"
        if history_dir.exists():
            for md_file in history_dir.rglob("*.md"):
                if md_file.name in target_filenames:
                    result.append(md_file)

    return sorted(result)


def extract_links(content: str) -> list[str]:
    """마크다운 텍스트에서 링크 경로(href) 목록을 추출한다.

    Args:
        content: 마크다운 파일 텍스트 내용.

    Returns:
        추출된 링크 href 문자열 목록.
    """
    matches = _MD_LINK_PATTERN.findall(content)
    # (text, href) 튜플에서 href만 추출
    return [href for _text, href in matches]


def _is_skip_link(href: str) -> bool:
    """링크를 검증 대상에서 제외해야 하는지 판단한다.

    외부 링크(http/https)와 템플릿 플레이스홀더 링크는 스킵한다.

    Args:
        href: 링크 경로 문자열.

    Returns:
        스킵 대상이면 True, 검증 대상이면 False.
    """
    # 외부 링크 스킵
    for prefix in _EXTERNAL_PREFIXES:
        if href.startswith(prefix):
            return True

    # 플레이스홀더 포함 링크 스킵 (템플릿)
    if _PLACEHOLDER_PATTERN.search(href):
        return True

    return False


def validate_link(
    href: str,
    md_file: Path,
    project_root: Path,
) -> bool:
    """단일 링크 경로의 파일 존재 여부를 검증한다.

    프로젝트 루트 기준 경로(.workflow/, .claude/ 시작)는 project_root에서 해석하고,
    그 외 상대 경로는 md_file이 위치한 디렉터리 기준으로 해석한다.

    Args:
        href: 링크 경로 문자열.
        md_file: 링크가 포함된 마크다운 파일 경로.
        project_root: 프로젝트 루트 디렉터리 경로.

    Returns:
        파일이 존재하면 True, 존재하지 않으면 False.
    """
    # 프로젝트 루트 기준 경로
    for prefix in _PROJECT_ROOT_PREFIXES:
        if href.startswith(prefix):
            target = project_root / href
            return target.exists()

    # 상대 경로: 마크다운 파일 디렉터리 기준
    target = md_file.parent / href
    return target.exists()


def validate_all(
    md_files: list[Path],
    project_root: Path,
) -> tuple[int, int, list[tuple[Path, str]]]:
    """전체 마크다운 파일 목록에 대해 링크 유효성을 검사한다.

    Args:
        md_files: 검사할 마크다운 파일 경로 목록.
        project_root: 프로젝트 루트 디렉터리 경로.

    Returns:
        (유효한 링크 수, 무효한 링크 수, 무효 링크 목록) 튜플.
        무효 링크 목록의 각 항목은 (마크다운 파일 경로, href) 튜플.
    """
    valid_count: int = 0
    invalid_count: int = 0
    invalid_links: list[tuple[Path, str]] = []

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[WARN] 파일 읽기 실패: {md_file} ({exc})", file=sys.stderr)
            continue

        hrefs = extract_links(content)
        for href in hrefs:
            if _is_skip_link(href):
                continue

            if validate_link(href, md_file, project_root):
                valid_count += 1
            else:
                invalid_count += 1
                invalid_links.append((md_file, href))

    return valid_count, invalid_count, invalid_links


def _print_results(
    valid_count: int,
    invalid_count: int,
    invalid_links: list[tuple[Path, str]],
    project_root: Path,
) -> None:
    """검증 결과를 stdout에 출력한다.

    Args:
        valid_count: 유효한 링크 수.
        invalid_count: 무효한 링크 수.
        invalid_links: 무효 링크 목록 (마크다운 파일 경로, href) 튜플 리스트.
        project_root: 프로젝트 루트 경로 (상대 경로 표시용).
    """
    total_count = valid_count + invalid_count
    print(f"링크 검사 결과: 총 {total_count}개 (유효 {valid_count}개, 무효 {invalid_count}개)")

    if invalid_links:
        print("\n무효 링크 목록 (404 예상):")
        for md_file, href in invalid_links:
            # 프로젝트 루트 기준 상대 경로로 표시
            try:
                rel_md = md_file.relative_to(project_root)
            except ValueError:
                rel_md = md_file
            print(f"  파일: {rel_md}")
            print(f"  링크: {href}")
            print()
    else:
        print("\n모든 내부 링크가 유효합니다.")


def main() -> None:
    """링크 유효성 검사 스크립트의 진입점.

    CLI 인자를 파싱하고 검증을 수행한 뒤,
    무효 링크가 있으면 exitcode 1, 모두 유효하면 0으로 종료한다.
    """
    parser = argparse.ArgumentParser(
        description=".workflow/ 내 마크다운 파일의 링크 유효성을 검사합니다.",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        default=False,
        help="활성 워크플로우(.workflow/ 직접 하위)만 검사합니다. .workflow/.history/는 제외.",
    )
    args = parser.parse_args()

    project_root = _find_project_root()

    # 스캔 대상 파일 수집
    md_files = scan_markdown_files(project_root, active_only=args.active_only)

    scope_label = "활성 워크플로우" if args.active_only else "전체 워크플로우(활성+히스토리)"
    print(f"검사 범위: {scope_label}")
    print(f"검사 파일 수: {len(md_files)}개")
    print()

    if not md_files:
        print("검사할 파일이 없습니다.")
        sys.exit(0)

    valid_count, invalid_count, invalid_links = validate_all(md_files, project_root)
    _print_results(valid_count, invalid_count, invalid_links, project_root)

    # 무효 링크 존재 시 exitcode 1
    sys.exit(1 if invalid_count > 0 else 0)


if __name__ == "__main__":
    main()

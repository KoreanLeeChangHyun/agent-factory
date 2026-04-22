#!/usr/bin/env -S python3 -u
"""스킬 활성화/아카이브 상태 관리 CLI 모듈.

스킬의 활성(active)/아카이브(archived) 상태를 skill-state.json 파일로 관리한다.
CLI를 통해 스킬 아카이브, 활성화, 상태 목록 조회를 수행하며,
catalog_sync.py에서 import하여 아카이브된 스킬을 카탈로그에서 제외한다.

주요 함수:
    load_skill_state: skill-state.json 로드
    save_skill_state: skill-state.json 원자적 저장
    archive_skill: 스킬을 archived 상태로 전환
    activate_skill: 스킬을 active 상태로 전환
    list_skills: active/archived 상태 구분 출력
    is_archived: 아카이브 여부 판별 헬퍼

사용법:
    flow-skill archive <skill_name>
    flow-skill activate <skill_name>
    flow-skill list [--archived | --active]

종료 코드: 0 성공, 1 실패
"""

from __future__ import annotations

import argparse
import os
import sys

# ─── sys.path 설정 ────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ─── 공통 모듈 임포트 ─────────────────────────────────────────────────────────

from common import (  # noqa: E402
    C_BOLD,
    C_CYAN,
    C_DIM,
    C_GREEN,
    C_RED,
    C_RESET,
    C_YELLOW,
    atomic_write_json,
    load_json_file,
    resolve_project_root,
)
from flow.cli_utils import build_common_epilog  # noqa: E402

# ─── 상수 ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT: str = resolve_project_root()
SKILLS_DIR: str = os.path.join(PROJECT_ROOT, ".claude", "skills")
STATE_FILE: str = os.path.join(SKILLS_DIR, "skill-state.json")

_STATE_VERSION: int = 1


# ─── 핵심 함수 ────────────────────────────────────────────────────────────────


def load_skill_state(state_path: str | None = None) -> dict[str, str]:
    """skill-state.json에서 스킬 상태를 로드한다.

    파일이 존재하지 않으면 빈 딕셔너리를 반환하여 모든 스킬을 active로 간주한다.

    Args:
        state_path: skill-state.json 경로. None이면 기본 경로 사용.

    Returns:
        스킬명을 키, 상태("active" 또는 "archived")를 값으로 하는 딕셔너리.
        파일 미존재 또는 파싱 실패 시 빈 딕셔너리.
    """
    path = state_path or STATE_FILE
    data = load_json_file(path)
    if not isinstance(data, dict):
        return {}
    skills = data.get("skills")
    if not isinstance(skills, dict):
        return {}
    return skills


def save_skill_state(state: dict[str, str], state_path: str | None = None) -> None:
    """스킬 상태를 skill-state.json에 원자적으로 저장한다.

    Args:
        state: 스킬명-상태 딕셔너리.
        state_path: skill-state.json 경로. None이면 기본 경로 사용.
    """
    path = state_path or STATE_FILE
    data = {
        "version": _STATE_VERSION,
        "skills": state,
    }
    atomic_write_json(path, data)


def is_archived(name: str, state: dict[str, str]) -> bool:
    """스킬이 아카이브 상태인지 판별한다.

    state에 키가 없으면 active로 간주하여 False를 반환한다.

    Args:
        name: 스킬명.
        state: load_skill_state()가 반환한 상태 딕셔너리.

    Returns:
        archived이면 True, 그 외(active 또는 키 없음)이면 False.
    """
    return state.get(name) == "archived"


def _validate_skill_exists(name: str) -> bool:
    """스킬 디렉터리가 존재하는지 검증한다.

    Args:
        name: 스킬명.

    Returns:
        디렉터리 존재 시 True, 미존재 시 False.
    """
    skill_dir = os.path.join(SKILLS_DIR, name)
    return os.path.isdir(skill_dir)


def _get_all_skill_names() -> list[str]:
    """skills 디렉터리에서 전체 스킬명 목록을 스캔한다.

    Returns:
        정렬된 스킬명 목록. 디렉터리가 아닌 항목과 skill-state.json,
        skill-catalog.md 등 파일은 제외.
    """
    if not os.path.isdir(SKILLS_DIR):
        return []
    return sorted(
        entry
        for entry in os.listdir(SKILLS_DIR)
        if os.path.isdir(os.path.join(SKILLS_DIR, entry))
        and not entry.startswith(".")
    )


def archive_skill(name: str) -> None:
    """스킬을 archived 상태로 전환한다.

    스킬 디렉터리가 존재하지 않으면 에러 메시지를 출력하고 exit 1로 종료.
    이미 archived 상태이면 안내 메시지를 출력하고 정상 종료.

    Args:
        name: 아카이브할 스킬명.
    """
    if not _validate_skill_exists(name):
        print(
            f"{C_RED}[ERROR]{C_RESET} 스킬 '{name}'이(가) 존재하지 않습니다.",
            file=sys.stderr,
        )
        sys.exit(1)

    state = load_skill_state()

    if is_archived(name, state):
        print("[STATE] SKILL", flush=True)
        print(f">> [INFO] '{name}'은(는) 이미 archived 상태입니다.", flush=True)
        return

    state[name] = "archived"
    save_skill_state(state)
    print("[STATE] SKILL", flush=True)
    print(f">> [OK] '{name}' -> archived", flush=True)


def activate_skill(name: str) -> None:
    """스킬을 active 상태로 전환한다.

    active 전환 시 상태 딕셔너리에서 키를 삭제하여 기본값(active)으로 복원한다.
    스킬 디렉터리가 존재하지 않으면 에러 메시지를 출력하고 exit 1로 종료.
    이미 active 상태이면 안내 메시지를 출력하고 정상 종료.

    Args:
        name: 활성화할 스킬명.
    """
    if not _validate_skill_exists(name):
        print(
            f"{C_RED}[ERROR]{C_RESET} 스킬 '{name}'이(가) 존재하지 않습니다.",
            file=sys.stderr,
        )
        sys.exit(1)

    state = load_skill_state()

    if not is_archived(name, state):
        print("[STATE] SKILL", flush=True)
        print(f">> [INFO] '{name}'은(는) 이미 active 상태입니다.", flush=True)
        return

    # 키 삭제로 active 기본값 복원
    state.pop(name, None)
    save_skill_state(state)
    print("[STATE] SKILL", flush=True)
    print(f">> [OK] '{name}' -> active", flush=True)


def list_skills(filter_mode: str | None = None) -> None:
    """스킬 상태 목록을 출력한다.

    filter_mode에 따라 전체, archived만, active만 출력한다.

    Args:
        filter_mode: "archived"이면 archived만, "active"이면 active만, None이면 전체 출력.
    """
    all_names = _get_all_skill_names()
    if not all_names:
        print("[STATE] SKILL", flush=True)
        print(">> [INFO] 스킬이 없습니다.", flush=True)
        return

    state = load_skill_state()

    active_names: list[str] = []
    archived_names: list[str] = []

    for name in all_names:
        if is_archived(name, state):
            archived_names.append(name)
        else:
            active_names.append(name)

    print("[STATE] SKILL list", flush=True)
    print(f">> Total: {len(all_names)} skills (active: {len(active_names)}, archived: {len(archived_names)})", flush=True)

    if filter_mode == "archived":
        if not archived_names:
            return
        print(f"{C_BOLD}Archived ({len(archived_names)}){C_RESET}")
        for name in archived_names:
            print(f"  {C_DIM}{name}{C_RESET}")
    elif filter_mode == "active":
        if not active_names:
            return
        print(f"{C_BOLD}Active ({len(active_names)}){C_RESET}")
        for name in active_names:
            print(f"  {C_CYAN}{name}{C_RESET}")
    else:
        # 전체 출력: active 먼저, archived 나중
        print(f"{C_BOLD}Active ({len(active_names)}){C_RESET}")
        for name in active_names:
            print(f"  {C_CYAN}{name}{C_RESET}")
        if archived_names:
            print(f"\n{C_BOLD}Archived ({len(archived_names)}){C_RESET}")
            for name in archived_names:
                print(f"  {C_DIM}{name}{C_RESET}")


# ─── argparse 파서 구성 ──────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """argparse 기반 CLI 파서를 구성하여 반환한다.

    Returns:
        구성된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="flow-skill",
        description="스킬 활성(active)/아카이브(archived) 상태 관리 CLI",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # archive 서브커맨드
    archive_parser = subparsers.add_parser(
        "archive",
        help="스킬을 archived 상태로 전환한다",
    )
    archive_parser.add_argument("skill_name", help="아카이브할 스킬명")

    # activate 서브커맨드
    activate_parser = subparsers.add_parser(
        "activate",
        help="스킬을 active 상태로 전환한다",
    )
    activate_parser.add_argument("skill_name", help="활성화할 스킬명")

    # list 서브커맨드
    list_parser = subparsers.add_parser(
        "list",
        help="스킬 상태 목록을 조회한다",
    )
    list_filter_group = list_parser.add_mutually_exclusive_group()
    list_filter_group.add_argument(
        "--archived",
        action="store_true",
        default=False,
        help="archived 상태 스킬만 표시한다",
    )
    list_filter_group.add_argument(
        "--active",
        action="store_true",
        default=False,
        help="active 상태 스킬만 표시한다",
    )

    return parser


# ─── CLI 진입점 ───────────────────────────────────────────────────────────────


def main() -> None:
    """CLI 진입점. argparse subparsers로 서브커맨드를 파싱하여 해당 핸들러를 호출한다."""
    parser = build_parser()
    args = parser.parse_args()

    if args.subcommand == "archive":
        archive_skill(args.skill_name)

    elif args.subcommand == "activate":
        activate_skill(args.skill_name)

    elif args.subcommand == "list":
        filter_mode: str | None = None
        if args.archived:
            filter_mode = "archived"
        elif args.active:
            filter_mode = "active"
        list_skills(filter_mode)


if __name__ == "__main__":
    main()

#!/usr/bin/env -S python3 -u
"""
registry_sync.py - 워크플로우 레지스트리 관리 CLI (registry.sh -> registry_sync.py 1:1 포팅)

사용법:
  python3 .claude/scripts/sync/registry_sync.py list                    # 모든 엔트리 컬러 테이블 출력
  python3 .claude/scripts/sync/registry_sync.py clean                   # 정리 대상 엔트리 제거
  python3 .claude/scripts/sync/registry_sync.py clean --dry-run         # 정리 대상 미리보기만
  python3 .claude/scripts/sync/registry_sync.py clean --force           # 전체 registry 초기화 ({})
  python3 .claude/scripts/sync/registry_sync.py remove <key>            # 특정 키 단건 제거

종료 코드: 0 성공, 1 실패
"""

import json
import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta, timezone

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.common import (
    C_BOLD,
    C_CYAN,
    C_DIM,
    C_GRAY,
    C_GREEN,
    C_PURPLE,
    C_RED,
    C_RESET,
    C_YELLOW,
    C_BLUE,
    PHASE_COLORS,
    atomic_write_json,
    load_json_file,
    resolve_project_root,
)

PROJECT_ROOT = resolve_project_root()
REGISTRY_FILE = os.path.join(PROJECT_ROOT, ".workflow", "registry.json")


def check_registry():
    """registry.json 존재 확인."""
    if not os.path.isfile(REGISTRY_FILE):
        print(f"{C_YELLOW}[WARN] registry.json이 존재하지 않습니다: {REGISTRY_FILE}{C_RESET}")
        sys.exit(0)


def cmd_help():
    """도움말 출력."""
    print(f"{C_BOLD}registry_sync.py{C_RESET} - 워크플로우 레지스트리 관리")
    print()
    print(f"  {C_CYAN}list{C_RESET}                  모든 엔트리 조회 (컬러 테이블)")
    print(f"  {C_CYAN}clean{C_RESET}                 정리 대상 엔트리 제거")
    print(f"  {C_CYAN}clean --dry-run{C_RESET}       정리 대상 미리보기 (제거하지 않음)")
    print(f"  {C_CYAN}clean --force{C_RESET}         전체 레지스트리 초기화 ({{}})")
    print(f"  {C_CYAN}remove <key>{C_RESET}          특정 YYYYMMDD-HHMMSS 키 단건 제거")
    print(f"  {C_CYAN}help{C_RESET}                  이 도움말 표시")
    print()
    print(f"{C_BOLD}정리 대상 (clean):{C_RESET}")
    print("  - COMPLETED / FAILED / STALE / CANCELLED phase 엔트리")
    print("  - status.json이 없는 고아 엔트리")
    print("  - registry phase와 status.json phase가 불일치하는 엔트리")
    print("  - REPORT phase인데 1시간 이상 경과한 잔류 엔트리")
    print("  - INIT / PLAN phase인데 1시간 이상 경과한 잔류 엔트리 (중단된 워크플로우)")
    print()
    print(f"{C_DIM}참고: .workflow/ 하위 디렉토리 물리 파일 삭제는 python3 .claude/scripts/init/init_clear.py를 사용하세요{C_RESET}", flush=True)


def cmd_list():
    """모든 엔트리를 컬러 테이블로 출력."""
    check_registry()

    registry = load_json_file(REGISTRY_FILE)
    if not isinstance(registry, dict) or not registry:
        print(f"{C_YELLOW}레지스트리가 비어있습니다.{C_RESET}")
        sys.exit(0)

    entries = []
    max_key = len("KEY")
    max_title = len("TITLE")
    max_phase = len("PHASE")
    max_cmd = len("COMMAND")

    for key in sorted(registry.keys()):
        entry = registry[key]
        title = entry.get("title", "(없음)")
        phase = entry.get("phase", "(없음)")
        command = entry.get("command", "(없음)")
        entries.append((key, title, phase, command))
        max_key = max(max_key, len(key))
        max_title = max(max_title, len(title))
        max_phase = max(max_phase, len(phase))
        max_cmd = max(max_cmd, len(command))

    if max_title > 40:
        max_title = 40

    separator_width = max_key + max_title + max_phase + max_cmd + 13
    separator = "-" * separator_width

    print()
    print(f"  {C_BOLD}워크플로우 레지스트리{C_RESET}  {C_DIM}({len(entries)}개 엔트리){C_RESET}")
    print(f"  {C_DIM}{separator}{C_RESET}")
    print(f"  {C_BOLD}{C_CYAN}{'KEY':<{max_key}}{C_RESET}  {C_BOLD}{'TITLE':<{max_title}}{C_RESET}  {C_BOLD}{'PHASE':<{max_phase}}{C_RESET}  {C_BOLD}{'COMMAND':<{max_cmd}}{C_RESET}")
    print(f"  {C_DIM}{separator}{C_RESET}")

    for key, title, phase, command in entries:
        if len(title) > max_title:
            title = title[: max_title - 2] + ".."
        color = PHASE_COLORS.get(phase, "")
        reset = C_RESET if color else ""
        print(f"  {key:<{max_key}}  {title:<{max_title}}  {color}{phase:<{max_phase}}{reset}  {command:<{max_cmd}}")

    print(f"  {C_DIM}{separator}{C_RESET}")
    print(flush=True)


def cmd_clean(args):
    """정리 대상 엔트리 제거."""
    force = "--force" in args
    dry_run = "--dry-run" in args

    check_registry()

    if force:
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            f.write("{}\n")
        print(f"{C_GREEN}[OK]{C_RESET} 레지스트리를 초기화했습니다. ({{}})")
        return

    registry = load_json_file(REGISTRY_FILE)
    if not isinstance(registry, dict) or not registry:
        print(f"{C_YELLOW}레지스트리가 비어있습니다.{C_RESET}")
        sys.exit(0)

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    report_ttl_hours = 1

    remove_phases = {"STALE", "COMPLETED", "FAILED", "CANCELLED"}
    targets = []

    for key, entry in registry.items():
        work_dir = entry.get("workDir", "")
        registry_phase = entry.get("phase", "")

        if not work_dir:
            targets.append((key, "empty workDir"))
            continue

        abs_work_dir = work_dir if work_dir.startswith("/") else os.path.join(PROJECT_ROOT, work_dir)
        status_file = os.path.join(abs_work_dir, "status.json")

        if not os.path.isfile(status_file):
            targets.append((key, "orphan (no status.json)"))
            continue

        status_data = load_json_file(status_file)
        if not isinstance(status_data, dict):
            targets.append((key, "orphan (status.json unreadable)"))
            continue

        status_phase = status_data.get("phase", "")

        if status_phase in remove_phases:
            targets.append((key, f"status phase={status_phase}"))
            continue

        if registry_phase in remove_phases and status_phase not in remove_phases:
            targets.append((key, f"registry phase={registry_phase} (status={status_phase})"))
            continue

        if status_phase != registry_phase and status_phase in remove_phases:
            targets.append((key, f"phase mismatch: registry={registry_phase}, status={status_phase}"))
            continue

        # REPORT 잔류 1시간 초과
        if registry_phase == "REPORT" or status_phase == "REPORT":
            time_str = status_data.get("updated_at") or status_data.get("created_at", "")
            if time_str:
                try:
                    updated = datetime.fromisoformat(time_str)
                    elapsed = now - updated
                    if elapsed.total_seconds() > report_ttl_hours * 3600:
                        targets.append((key, f"REPORT stale ({elapsed.total_seconds()/3600:.1f}h)"))
                        continue
                except (ValueError, TypeError):
                    pass

        # INIT/PLAN 잔류 1시간 초과
        if status_phase in ("INIT", "PLAN"):
            time_str = status_data.get("updated_at") or status_data.get("created_at", "")
            if time_str:
                try:
                    updated = datetime.fromisoformat(time_str)
                    elapsed = now - updated
                    if elapsed.total_seconds() > report_ttl_hours * 3600:
                        targets.append((key, f"{status_phase} stale ({elapsed.total_seconds()/3600:.1f}h)"))
                        continue
                except (ValueError, TypeError):
                    pass

    if not targets:
        print(f"{C_GREEN}[OK]{C_RESET} 정리 대상 엔트리가 없습니다.")
        sys.exit(0)

    mode_label = f"{C_YELLOW}[DRY-RUN]{C_RESET}" if dry_run else f"{C_RED}[CLEAN]{C_RESET}"
    print()
    print(f"  {mode_label} 정리 대상: {len(targets)}개")
    print()
    max_key = max(len(k) for k, _ in targets)
    for key, reason in sorted(targets):
        print(f"  {C_RED}x{C_RESET} {key:<{max_key}}  {C_DIM}{reason}{C_RESET}")
    print()

    if dry_run:
        print(f"  {C_DIM}실제 삭제하려면: python3 .claude/scripts/sync/registry_sync.py clean{C_RESET}")
        print(flush=True)
        sys.exit(0)

    # 삭제 실행
    for key, _ in targets:
        del registry[key]

    try:
        atomic_write_json(REGISTRY_FILE, registry)
        print(f"  {C_GREEN}[OK]{C_RESET} {len(targets)}개 엔트리를 제거했습니다. (잔여: {len(registry)}개)")
        print(flush=True)
    except Exception as e:
        print(f"{C_RED}[ERROR] registry.json 쓰기 실패: {e}{C_RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_remove(args):
    """특정 키 단건 제거."""
    if not args or not args[0]:
        print(f"{C_RED}[ERROR] 사용법: python3 .claude/scripts/sync/registry_sync.py remove <YYYYMMDD-HHMMSS>{C_RESET}")
        sys.exit(1)

    target_key = args[0]
    check_registry()

    registry = load_json_file(REGISTRY_FILE)
    if not isinstance(registry, dict):
        print(f"{C_RED}[ERROR] registry.json 형식이 올바르지 않습니다.{C_RESET}", file=sys.stderr)
        sys.exit(1)

    if target_key not in registry:
        print(f"{C_YELLOW}[WARN] 키를 찾을 수 없습니다: {target_key}{C_RESET}")
        sys.exit(0)

    entry = registry[target_key]
    title = entry.get("title", "(없음)")
    phase = entry.get("phase", "(없음)")
    print(f"  제거: {target_key} ({title}, phase={phase})")

    del registry[target_key]

    try:
        atomic_write_json(REGISTRY_FILE, registry)
        print(f"{C_GREEN}[OK]{C_RESET} 키 {target_key}을 제거했습니다. (잔여: {len(registry)}개)", flush=True)
    except Exception as e:
        print(f"{C_RED}[ERROR] registry.json 쓰기 실패: {e}{C_RESET}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(1)

    subcmd = sys.argv[1]
    rest = sys.argv[2:]

    if subcmd == "list":
        cmd_list()
    elif subcmd == "clean":
        cmd_clean(rest)
    elif subcmd == "remove":
        cmd_remove(rest)
    elif subcmd in ("help", "--help", "-h"):
        cmd_help()
    else:
        print(f"{C_RED}[ERROR] 알 수 없는 서브커맨드: {subcmd}{C_RESET}")
        print(f"{C_DIM}사용법: python3 .claude/scripts/sync/registry_sync.py list | clean [--dry-run|--force] | remove <key> | help{C_RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()

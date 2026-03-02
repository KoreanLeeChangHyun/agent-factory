#!/usr/bin/env -S python3 -u
"""
워크플로우 마무리 처리 스크립트 (flow-finish)

오케스트레이터가 직접 호출하는 워크플로우 마무리 5단계 결정론적 스크립트.

사용법:
  flow-finish <registryKey> <status> <mode> [--workflow-id <id>]

인자:
  registryKey   워크플로우 식별자 (YYYYMMDD-HHMMSS)
  status        완료 | 실패
  mode          full (유일 지원 모드)
  --workflow-id WF-N 형식 (선택)

4단계:
  1. status.json 완료 처리   (update_state.py status, 실패 시 exit 1 — sync 포함)
  2. 사용량 확정             (update_state.py usage-finalize, 비차단)
  3. 아카이빙               (history_sync.py archive, 비차단)
  4. .kanbanboard 갱신       (update-kanban.sh, workflow_id 있을 때만, 비차단)

종료 코드:
  0  성공
  1  status.json 전이 실패
"""

import argparse
import glob
import json
import os
import subprocess
import sys

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import C_CLAUDE, C_DIM, C_RED, C_RESET, C_YELLOW, load_json_file, resolve_abs_work_dir, resolve_project_root

PROJECT_ROOT = resolve_project_root()

# 스크립트 경로
HISTORY_SYNC = os.path.join(PROJECT_ROOT, ".claude", "scripts", "sync", "history_sync.py")
UPDATE_STATE = os.path.join(PROJECT_ROOT, ".claude", "scripts", "flow", "update_state.py")
USAGE_SYNC = os.path.join(PROJECT_ROOT, ".claude", "scripts", "sync", "usage_sync.py")
UPDATE_KANBAN = os.path.join(PROJECT_ROOT, ".claude", "skills", "design-strategy", "scripts", "update-kanban.sh")


def run(cmd, label, critical=False, input_data=None):
    """subprocess 실행 래퍼.

    Args:
        cmd: 실행할 명령어 리스트
        label: 로그용 라벨
        critical: True이면 실패 시 exit 1
        input_data: stdin으로 전달할 문자열 (선택)

    Returns:
        int: 종료 코드
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, input=input_data)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if critical:
                print("FAIL", flush=True)
                print(f"[ERROR] {label}: exit {result.returncode}", file=sys.stderr)
                if stderr:
                    print(f"  {stderr}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"[WARN] {label}: exit {result.returncode}", file=sys.stderr)
                if stderr:
                    print(f"  {stderr}", file=sys.stderr)
        return result.returncode
    except subprocess.TimeoutExpired:
        if critical:
            print("FAIL", flush=True)
            print(f"[ERROR] {label}: timeout", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"[WARN] {label}: timeout", file=sys.stderr)
            return 1
    except Exception as e:
        if critical:
            print("FAIL", flush=True)
            print(f"[ERROR] {label}: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"[WARN] {label}: {e}", file=sys.stderr)
            return 1


def _find_transcript_path(registry_key):
    """registryKey로부터 subagents 디렉터리의 transcript 경로를 구성한다.

    status.json의 linked_sessions에서 세션 ID를 읽고,
    ~/.claude/projects/ 아래에서 subagents/ 디렉터리를 탐색한다.
    실제 agent-*.jsonl 파일이 존재하는 경우 첫 번째 파일 경로를 반환한다.
    """
    abs_work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
    if not abs_work_dir:
        return None

    status_file = os.path.join(abs_work_dir, "status.json")
    status_data = load_json_file(status_file)
    if not isinstance(status_data, dict):
        return None

    sessions = status_data.get("linked_sessions", [])
    if not sessions:
        return None

    project_slug = PROJECT_ROOT.replace("/", "-")

    for claude_base in [
        os.path.expanduser("~/.claude"),
        os.path.expanduser("~/.config/claude"),
    ]:
        projects_dir = os.path.join(claude_base, "projects", project_slug)
        if not os.path.isdir(projects_dir):
            continue
        for session_id in sessions:
            subagents_dir = os.path.join(projects_dir, session_id, "subagents")
            if os.path.isdir(subagents_dir):
                # subagents/ 디렉터리 내부의 실제 agent-*.jsonl 파일 탐색
                matches = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
                if matches:
                    return matches[0]

    return None


def find_kanbanboard():
    """프로젝트 루트에서 .kanbanboard 파일을 탐색."""
    pattern = os.path.join(PROJECT_ROOT, ".workflow", "**", ".kanbanboard")
    matches = sorted(glob.glob(pattern, recursive=True))
    if matches:
        return matches[0]
    # 프로젝트 루트 직접 확인
    root_kanban = os.path.join(PROJECT_ROOT, ".kanbanboard")
    if os.path.isfile(root_kanban):
        return root_kanban
    return None


def main():
    parser = argparse.ArgumentParser(
        description="워크플로우 마무리 처리 (flow-finish 5단계)",
    )
    parser.add_argument("registryKey", help="워크플로우 식별자 (YYYYMMDD-HHMMSS)")
    parser.add_argument("status", choices=["완료", "실패"], help="워크플로우 결과 상태")
    parser.add_argument("--workflow-id", default=None, help="WF-N 형식 워크플로우 ID (선택)")

    args = parser.parse_args()

    registry_key = args.registryKey
    status = args.status
    workflow_id = args.workflow_id

    # ── Step 1: status.json 완료 처리 (critical) ──
    to_step = "DONE" if status == "완료" else "FAILED"

    run(
        ["python3", UPDATE_STATE, "status", registry_key, to_step],
        "Step 1: status.json transition",
        critical=True,
    )

    # ── Step 2: 사용량 확정 (비차단, 성공 시만) ──
    if status == "완료":
        # Step 2a: JSONL 일괄 파싱 (usage_sync.py batch)
        transcript_path = _find_transcript_path(registry_key)
        print(f"[flow-finish] batch: transcript_path={transcript_path}", file=sys.stderr)
        if transcript_path:
            stdin_json = json.dumps({"agent_type": "orchestrator", "agent_transcript_path": transcript_path})
            run(
                ["python3", USAGE_SYNC, "batch"],
                "Step 2a: usage-sync batch",
                input_data=stdin_json,
            )

        # Step 2b: usage-finalize
        run(
            ["python3", UPDATE_STATE, "usage-finalize", registry_key],
            "Step 2b: usage-finalize",
        )

    # ── Step 3: 아카이빙 (비차단) ──
    run(
        ["python3", HISTORY_SYNC, "archive", registry_key],
        "Step 3: archive",
    )

    # ── Step 4: .kanbanboard 갱신 (workflow_id 있을 때만, 비차단) ──
    if workflow_id:
        kanban_path = find_kanbanboard()
        if kanban_path:
            kanban_status = "completed" if status == "완료" else "failed"
            run(
                ["bash", UPDATE_KANBAN, kanban_path, workflow_id, kanban_status],
                "Step 4: kanbanboard update",
            )

    if status == "완료":
        status_label = f"{C_YELLOW}완료{C_RESET}"
    else:
        status_label = f"{C_RED}실패{C_RESET}"
    print(f"{C_CLAUDE}║ DONE:{C_RESET} {C_DIM}워크플로우{C_RESET} {status_label}", flush=True)
    print(f"{C_CLAUDE}║{C_RESET} {C_DIM}{registry_key}{C_RESET}", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()

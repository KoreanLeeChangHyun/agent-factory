#!/usr/bin/env -S python3 -u
"""워크플로우 마무리 처리 스크립트 (flow-finish).

오케스트레이터가 직접 호출하는 워크플로우 마무리 4단계 결정론적 스크립트.

사용법:
  flow-finish <registryKey> <status> [--workflow-id <id>]

인자:
  registryKey   워크플로우 식별자 (YYYYMMDD-HHMMSS)
  status        완료 | 실패
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

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

# utils 패키지 import
_scripts_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import C_CLAUDE, C_DIM, C_RED, C_RESET, C_YELLOW, load_json_file, resolve_abs_work_dir, resolve_project_root
from data.constants import LOGS_HEADER_LINE, LOGS_SEPARATOR_LINE

PROJECT_ROOT: str = resolve_project_root()

# 스크립트 경로
HISTORY_SYNC: str = os.path.join(PROJECT_ROOT, ".claude", "scripts", "sync", "history_sync.py")
UPDATE_STATE: str = os.path.join(PROJECT_ROOT, ".claude", "scripts", "flow", "update_state.py")
USAGE_SYNC: str = os.path.join(PROJECT_ROOT, ".claude", "scripts", "sync", "usage_sync.py")
UPDATE_KANBAN: str = os.path.join(PROJECT_ROOT, ".claude", "skills", "design-strategy", "scripts", "update-kanban.sh")


def run(
    cmd: list[str],
    label: str,
    critical: bool = False,
    input_data: str | None = None,
) -> int:
    """subprocess 실행 래퍼.

    Args:
        cmd: 실행할 명령어 리스트
        label: 로그용 라벨 (에러/경고 메시지에 표시)
        critical: True이면 실패 시 exit 1로 종료
        input_data: stdin으로 전달할 문자열 (선택)

    Returns:
        프로세스 종료 코드. 타임아웃 또는 예외 시 1 반환.
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


def _find_transcript_path(registry_key: str) -> str | None:
    """registryKey로부터 subagents 디렉터리의 transcript 경로를 구성한다.

    1차: status.json의 linked_sessions에서 세션 ID를 읽고 subagents/ 탐색.
    2차(대체): linked_sessions가 비어있을 때 usage.json의 _agent_map에 기록된
         알려진 agent_id로 glob하여 subagents 디렉터리를 역탐색한다.
    실제 agent-*.jsonl 파일이 존재하는 경우 첫 번째 파일 경로를 반환한다.

    Args:
        registry_key: YYYYMMDD-HHMMSS 형식 워크플로우 식별자

    Returns:
        agent-*.jsonl 파일 절대 경로. 찾지 못하면 None.
    """
    abs_work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
    if not abs_work_dir:
        return None

    status_file = os.path.join(abs_work_dir, "status.json")
    status_data = load_json_file(status_file)
    if not isinstance(status_data, dict):
        return None

    project_slug = PROJECT_ROOT.replace("/", "-")

    # 1차: linked_sessions 기반 탐색
    sessions = status_data.get("linked_sessions", [])
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
                matches = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
                if matches:
                    return matches[0]

    # 2차: _agent_map에 기록된 알려진 agent_id로 역탐색
    usage_file = os.path.join(abs_work_dir, "usage.json")
    usage_data = load_json_file(usage_file)
    if not isinstance(usage_data, dict):
        return None

    agent_map = usage_data.get("_agent_map", {})
    if not agent_map:
        return None

    for claude_base in [
        os.path.expanduser("~/.claude"),
        os.path.expanduser("~/.config/claude"),
    ]:
        projects_dir = os.path.join(claude_base, "projects", project_slug)
        if not os.path.isdir(projects_dir):
            continue
        # _agent_map의 각 agent_id에 대해 glob으로 subagents 디렉터리 탐색
        for agent_id in agent_map:
            pattern = os.path.join(projects_dir, "*", "subagents", f"agent-{agent_id}.jsonl")
            matches = glob.glob(pattern)
            if matches:
                # subagents/ 상위 = session_dir, 해당 디렉터리의 첫 번째 agent-*.jsonl 반환
                subagents_dir = os.path.dirname(matches[0])
                all_agents = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
                if all_agents:
                    return all_agents[0]

    return None


def find_kanbanboard() -> str | None:
    """프로젝트 루트에서 .kanbanboard 파일을 탐색한다.

    .workflow/ 하위와 프로젝트 루트를 순서대로 탐색한다.

    Returns:
        .kanbanboard 파일 절대 경로. 없으면 None.
    """
    pattern = os.path.join(PROJECT_ROOT, ".workflow", "**", ".kanbanboard")
    matches = sorted(glob.glob(pattern, recursive=True))
    if matches:
        return matches[0]
    # 프로젝트 루트 직접 확인
    root_kanban = os.path.join(PROJECT_ROOT, ".kanbanboard")
    if os.path.isfile(root_kanban):
        return root_kanban
    return None


def _acquire_lock(lock_dir: str, max_wait: int = 2) -> bool:
    """mkdir 기반 POSIX 잠금 획득. stale lock 감지 포함.

    디렉터리 생성으로 잠금을 획득하며, PID 파일로 소유자를 기록한다.
    프로세스가 종료되었거나 max_wait 초 초과 시 stale lock을 제거하고 재시도한다.

    Args:
        lock_dir: 잠금 디렉터리 경로
        max_wait: 최대 대기 초 (기본값 2)

    Returns:
        잠금 획득 성공 여부.
    """
    waited = 0
    while True:
        try:
            os.makedirs(lock_dir)
            try:
                with open(os.path.join(lock_dir, "pid"), "w") as f:
                    f.write(f"{os.getpid()} {time.time()}")
            except OSError:
                pass
            return True
        except OSError:
            pid_file = os.path.join(lock_dir, "pid")
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r") as f:
                        pid_content = f.read().strip()
                    parts = pid_content.split()
                    lock_pid = int(parts[0])
                    lock_ts = float(parts[1]) if len(parts) > 1 else 0
                    os.kill(lock_pid, 0)
                    if lock_ts and (time.time() - lock_ts) > max_wait:
                        try:
                            with open(pid_file, "r") as f:
                                recheck = f.read().strip()
                            if recheck == pid_content:
                                shutil.rmtree(lock_dir)
                                waited += 1
                                continue
                        except OSError:
                            pass
                except (ValueError, ProcessLookupError, OSError):
                    try:
                        with open(pid_file, "r") as f:
                            recheck = f.read().strip()
                        if recheck == pid_content:
                            shutil.rmtree(lock_dir)
                    except OSError:
                        pass
                    waited += 1
                    continue
                except PermissionError:
                    pass
            waited += 1
            if waited >= max_wait:
                return False
            time.sleep(1)


def _release_lock(lock_dir: str) -> None:
    """잠금을 해제한다.

    PID 파일 삭제 후 잠금 디렉터리를 제거한다.
    파일시스템 오류는 무시한다.

    Args:
        lock_dir: 해제할 잠금 디렉터리 경로
    """
    try:
        pid_file = os.path.join(lock_dir, "pid")
        if os.path.exists(pid_file):
            os.unlink(pid_file)
    except OSError:
        pass
    try:
        os.rmdir(lock_dir)
    except OSError:
        pass


def _update_logs_md(registry_key: str, abs_work_dir: str) -> None:
    """.dashboard/.logs.md 파일에 워크플로우 로그 통계 행을 삽입한다.

    workflow.log 파일에서 WARN/ERROR 카운트와 파일 크기를 수집하여
    마크다운 테이블 행을 구성하고 원자적으로 삽입한다.
    예외 발생 시 무시하고 계속 진행한다.

    Args:
        registry_key: YYYYMMDD-HHMMSS 형식 워크플로우 식별자
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로
    """
    try:
        marker = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"
        logs_md = os.path.join(PROJECT_ROOT, ".dashboard", ".logs.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".dashboard", ".logs.md.lock")

        # .context.json에서 title, command 읽기
        context_file = os.path.join(abs_work_dir, ".context.json")
        context = load_json_file(context_file)
        title = ""
        command = ""
        if isinstance(context, dict):
            title = context.get("title", "")
            command = context.get("command", "")

        # workflow.log 통계 수집
        log_path = os.path.join(abs_work_dir, "workflow.log")
        if os.path.isfile(log_path):
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                log_content = f.read()
            warn_count = log_content.count("[WARN]")
            error_count = log_content.count("[ERROR]")
            log_size = os.path.getsize(log_path)
            if log_size >= 1024 * 1024:
                size_str = f"{log_size / (1024 * 1024):.1f}MB"
            elif log_size >= 1024:
                size_str = f"{log_size / 1024:.1f}KB"
            else:
                size_str = f"{log_size}B"
        else:
            warn_count = 0
            error_count = 0
            size_str = "-"

        # 날짜: registryKey에서 MM-DD HH:MM 추출 (YYYYMMDD-HHMMSS)
        date_str = "-"
        try:
            parts = registry_key.split("-")
            if len(parts) >= 2:
                ymd = parts[0]  # YYYYMMDD
                hms = parts[1]  # HHMMSS
                date_str = f"{ymd[4:6]}-{ymd[6:8]} {hms[0:2]}:{hms[2:4]}"
        except Exception:
            pass

        # 로그 링크: abs_work_dir에서 .dashboard 기준 상대 경로 계산
        try:
            rel_work_dir = os.path.relpath(abs_work_dir, os.path.join(PROJECT_ROOT, ".dashboard"))
            log_link = f"[로그]({rel_work_dir}/workflow.log)"
        except Exception:
            log_link = "-"

        # 제목 축약 (20자 초과 시)
        title_display = title[:20] + "…" if len(title) > 20 else title

        row = (
            f"| {date_str} | {registry_key} | {title_display} | {command}"
            f" | {warn_count} | {error_count} | {size_str} | {log_link} |"
        )

        # .logs.md 읽기
        content = ""
        if os.path.exists(logs_md):
            with open(logs_md, "r", encoding="utf-8") as f:
                content = f.read()

        if marker not in content:
            content = f"# 워크플로우 로그 추적\n\n{marker}\n\n{LOGS_HEADER_LINE}\n{LOGS_SEPARATOR_LINE}\n"

        # 마커 + separator 후에 행 삽입
        if LOGS_SEPARATOR_LINE in content:
            marker_pos = content.find(marker)
            if marker_pos >= 0:
                sep_pos = content.find(LOGS_SEPARATOR_LINE, marker_pos)
                if sep_pos >= 0:
                    insert_pos = sep_pos + len(LOGS_SEPARATOR_LINE)
                    if insert_pos < len(content) and content[insert_pos] == "\n":
                        insert_pos += 1
                    content = content[:insert_pos] + row + "\n" + content[insert_pos:]
                else:
                    content = content.replace(
                        marker, f"{marker}\n\n{LOGS_HEADER_LINE}\n{LOGS_SEPARATOR_LINE}\n{row}"
                    )
            else:
                content = content.replace(
                    marker, f"{marker}\n\n{LOGS_HEADER_LINE}\n{LOGS_SEPARATOR_LINE}\n{row}"
                )
        else:
            content = content.replace(
                marker, f"{marker}\n\n{LOGS_HEADER_LINE}\n{LOGS_SEPARATOR_LINE}\n{row}"
            )

        # POSIX lock + 원자적 쓰기
        os.makedirs(os.path.dirname(logs_md), exist_ok=True)
        locked = _acquire_lock(lock_dir)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(logs_md), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            shutil.move(tmp, logs_md)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        finally:
            if locked:
                _release_lock(lock_dir)
    except Exception:
        pass


def main() -> None:
    """CLI 진입점. 인자 파싱 후 워크플로우 마무리 4단계를 순서대로 실행한다."""
    parser = argparse.ArgumentParser(
        description="워크플로우 마무리 처리 (flow-finish 5단계)",
    )
    parser.add_argument("registryKey", help="워크플로우 식별자 (YYYYMMDD-HHMMSS)")
    parser.add_argument("status", choices=["완료", "실패"], help="워크플로우 결과 상태")
    parser.add_argument("--workflow-id", default=None, help="WF-N 형식 워크플로우 ID (선택)")

    args = parser.parse_args()

    registry_key: str = args.registryKey
    status: str = args.status
    workflow_id: str | None = args.workflow_id

    # ── Step 1: status.json 완료 처리 (critical) ──
    to_step: str = "DONE" if status == "완료" else "FAILED"

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

    # ── Step 5: 로그/스킬 대시보드 갱신 (비차단) ──
    try:
        abs_work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
        _update_logs_md(registry_key, abs_work_dir)
    except Exception:
        pass

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

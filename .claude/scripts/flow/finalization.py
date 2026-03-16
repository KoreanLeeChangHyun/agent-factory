#!/usr/bin/env -S python3 -u
"""워크플로우 마무리 처리 스크립트 (flow-finish).

오케스트레이터가 직접 호출하는 워크플로우 마무리 5단계 결정론적 스크립트.

사용법:
  flow-finish <registryKey> <status> [--ticket-number <T-NNN>]

인자:
  registryKey      워크플로우 식별자 (YYYYMMDD-HHMMSS)
  status           완료 | 실패
  --ticket-number  T-NNN 형식 티켓 번호 (선택)

6단계:
  1. status.json 완료 처리   (update_state.py status, 이미 대상 상태면 스킵, 그 외 실패 시 exit 1 — sync 포함)
  2. 사용량 확정             (update_state.py usage-finalize, 비차단)
  3. 아카이빙               (history_sync.py archive, 비차단)
  4. 티켓 상태 갱신          (kanban.py move, ticket_number 있을 때만, 비차단)
  4c. 체인 감지 및 다음 스테이지 발사 (chain_launcher.py, 완료+체인 존재 시만, 비동기)
  5. tmux 윈도우 백그라운드 지연 kill (TMUX_PANE+T-* 조건 시만, 비차단)

종료 코드:
  0  성공
  1  status.json 전이 실패
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

# utils 패키지 import
_scripts_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import C_CLAUDE, C_DIM, C_RED, C_RESET, C_YELLOW, load_json_file, resolve_abs_work_dir, resolve_project_root
from data.constants import CHAIN_SEPARATOR, LOGS_HEADER_LINE, LOGS_SEPARATOR_LINE
from flow.tmux_utils import WINDOW_PREFIX_P

PROJECT_ROOT: str = resolve_project_root()


def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """워크플로우 로그에 이벤트를 기록한다."""
    try:
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


# 스크립트 경로
HISTORY_SYNC: str = os.path.join(PROJECT_ROOT, ".claude", "scripts", "sync", "history_sync.py")
UPDATE_STATE: str = os.path.join(PROJECT_ROOT, ".claude", "scripts", "flow", "update_state.py")
USAGE_SYNC: str = os.path.join(PROJECT_ROOT, ".claude", "scripts", "sync", "usage_sync.py")
KANBAN_PY: str = os.path.join(PROJECT_ROOT, ".claude", "scripts", "flow", "kanban.py")
CHAIN_LAUNCHER: str = os.path.join(PROJECT_ROOT, ".claude", "scripts", "flow", "chain_launcher.py")


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

    0차(최우선): usage.json의 _main_transcript 경로로부터 subagents/ 탐색.
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

    # 0차: usage.json의 _main_transcript 경로로부터 subagents/ 탐색
    usage_file = os.path.join(abs_work_dir, "usage.json")
    usage_data_early = load_json_file(usage_file)
    if isinstance(usage_data_early, dict):
        main_transcript = usage_data_early.get("_main_transcript", "")
        if main_transcript and os.path.isfile(main_transcript):
            # _main_transcript 파일의 디렉터리에 subagents/ 폴더가 있으면 탐색
            transcript_dir = os.path.dirname(main_transcript)
            subagents_dir = os.path.join(transcript_dir, "subagents")
            if os.path.isdir(subagents_dir):
                matches = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
                if matches:
                    return matches[0]

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


def _resolve_current_subnumber_id(ticket_number: str) -> int | None:
    """티켓 XML에서 현재 활성 subnumber ID를 반환한다.

    `.kanban/T-NNN.xml`을 파싱하여 `<metadata>` > `<current>` 텍스트를 int로 반환한다.
    `.kanban/done/T-NNN.xml`도 폴백 탐색한다. 파싱 실패 시 None을 반환한다.

    Args:
        ticket_number: T-NNN 형식 티켓 번호

    Returns:
        현재 subnumber ID (int). 파싱 실패 또는 미존재 시 None.
    """
    for subdir in ("", "done"):
        path = os.path.join(PROJECT_ROOT, ".kanban", subdir, f"{ticket_number}.xml")
        if not os.path.isfile(path):
            continue
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            metadata = root.find("metadata")
            if metadata is not None:
                current_el = metadata.find("current")
                if current_el is not None and current_el.text:
                    return int(current_el.text.strip())
        except Exception:
            pass
    return None


def _build_result_update_args(abs_work_dir: str) -> list[str]:
    """update-subnumber CLI 추가 인자 리스트를 반환한다.

    abs_work_dir에서 registryKey를 추출하고, plan.md / report.md 존재 여부를
    확인하여 update-subnumber CLI에 전달할 인자 리스트를 반환한다.

    Args:
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로
            (.workflow/{registryKey}/{workName}/{command} 구조)

    Returns:
        ["--registrykey", registryKey, "--workdir", workDir상대경로] 에
        plan.md / report.md가 존재하면 각각 "--plan" / "--report" 인자를 추가한 리스트.
        registryKey 추출 실패 시 빈 리스트.
    """
    import re as _re

    # abs_work_dir 에서 YYYYMMDD-HHMMSS 패턴 추출
    # 경로 형식: .../`.workflow`/{registryKey}/{workName}/{command}
    _ts_pattern = _re.compile(r"\.workflow[/\\](\d{8}-\d{6}(?:-\d+)?)")
    _match = _ts_pattern.search(abs_work_dir)
    if not _match:
        return []

    registry_key: str = _match.group(1)

    # 상대 workDir: .workflow/{registryKey}/... 이후 부분을 포함한 경로
    _wf_idx = abs_work_dir.find(".workflow/")
    if _wf_idx == -1:
        _wf_idx = abs_work_dir.find(".workflow\\")
    if _wf_idx == -1:
        return []
    work_dir_rel: str = abs_work_dir[_wf_idx:]
    # 경로 구분자를 슬래시로 통일하고 끝 슬래시 정규화
    work_dir_rel = work_dir_rel.replace("\\", "/").rstrip("/") + "/"

    args: list[str] = ["--registrykey", registry_key, "--workdir", work_dir_rel]

    plan_abs: str = os.path.join(abs_work_dir, "plan.md")
    if os.path.isfile(plan_abs):
        plan_rel: str = work_dir_rel + "plan.md"
        args += ["--plan", plan_rel]

    report_abs: str = os.path.join(abs_work_dir, "report.md")
    if os.path.isfile(report_abs):
        report_rel: str = work_dir_rel + "report.md"
        args += ["--report", report_rel]

    return args


def main() -> None:
    """CLI 진입점. 인자 파싱 후 워크플로우 마무리 6단계를 순서대로 실행한다."""
    parser = argparse.ArgumentParser(
        description="워크플로우 마무리 처리 (flow-finish 6단계)",
    )
    parser.add_argument("registryKey", help="워크플로우 식별자 (YYYYMMDD-HHMMSS)")
    parser.add_argument("status", choices=["완료", "실패"], help="워크플로우 결과 상태")
    parser.add_argument("--ticket-number", default=None, help="T-NNN 형식 티켓 번호 (선택)")

    args = parser.parse_args()

    registry_key: str = args.registryKey
    status: str = args.status
    ticket_number: str | None = args.ticket_number

    # ── Step 1: status.json 완료 처리 (critical) ──
    to_step: str = "DONE" if status == "완료" else "FAILED"

    # 이중 전이 방어: 이미 대상 상태이면 run() 호출 스킵
    _step1_skip: bool = False
    abs_work_dir: str | None = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
    if abs_work_dir is not None:
        _status_data = load_json_file(os.path.join(abs_work_dir, "status.json"))
        if _status_data is not None and _status_data.get("step") == to_step:
            print(f"[INFO] Step 1: already {to_step}, skipping status transition", file=sys.stderr, flush=True)
            _step1_skip = True

    if abs_work_dir is not None:
        _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP1: registryKey={registry_key} toStep={to_step}")

    if not _step1_skip:
        run(
            ["python3", UPDATE_STATE, "status", registry_key, to_step],
            "Step 1: status.json transition",
            critical=True,
        )

    if abs_work_dir is not None:
        _append_log(abs_work_dir, "INFO", f"Workflow finalized: {registry_key} ({status})")

    # ── Step 2: 사용량 확정 (비차단, 성공 시만) ──
    if status == "완료":
        # Step 2a: JSONL 일괄 파싱 (usage_sync.py batch)
        transcript_path = _find_transcript_path(registry_key)
        if transcript_path:
            if abs_work_dir is not None:
                _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP2A: transcript=found path={transcript_path}")
            stdin_json = json.dumps({"agent_type": "orchestrator", "agent_transcript_path": transcript_path})
            run(
                ["python3", USAGE_SYNC, "batch"],
                "Step 2a: usage-sync batch",
                input_data=stdin_json,
            )
        else:
            if abs_work_dir is not None:
                _append_log(abs_work_dir, "WARN", "FINALIZE_STEP2A: transcript=not_found")

        # Step 2b: usage-finalize
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP2B: usage-finalize registryKey={registry_key}")
        run(
            ["python3", UPDATE_STATE, "usage-finalize", registry_key],
            "Step 2b: usage-finalize",
        )

    # ── Step 5: 로그/스킬 대시보드 갱신 (비차단) ──
    try:
        abs_work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
        _update_logs_md(registry_key, abs_work_dir)
        if abs_work_dir is not None:
            # workflow.log 통계 수집 (로그 기록 전)
            _log_path = os.path.join(abs_work_dir, "workflow.log")
            _warn_count = 0
            _error_count = 0
            if os.path.isfile(_log_path):
                try:
                    with open(_log_path, "r", encoding="utf-8", errors="replace") as _f:
                        _log_content = _f.read()
                    _warn_count = _log_content.count("[WARN]")
                    _error_count = _log_content.count("[ERROR]")
                except Exception:
                    pass
            _append_log(abs_work_dir, "INFO", f"FINALIZE_LOGS_MD: registryKey={registry_key} warn={_warn_count} error={_error_count}")
    except Exception:
        pass

    # ── Step 3: 아카이빙 (비차단) ──
    if abs_work_dir is not None:
        _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP3: archive registryKey={registry_key}")
    run(
        ["python3", HISTORY_SYNC, "archive", registry_key],
        "Step 3: archive",
    )

    # ── Step 4: 티켓 상태 갱신 (ticket_number 있을 때만, 비차단) ──
    if ticket_number:
        target_column = "review" if status == "완료" else "open"
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP4: kanban ticket={ticket_number} column={target_column}")
        run(
            ["python3", KANBAN_PY, "move", ticket_number, target_column],
            "Step 4: ticket status update",
        )

        # ── Step 4b: 결과 워크플로우 번호 기록 (완료 시만, 비차단) ──
        if status == "완료" and abs_work_dir is not None:
            sub_id = _resolve_current_subnumber_id(ticket_number)
            if sub_id is None:
                if abs_work_dir is not None:
                    _append_log(abs_work_dir, "WARN", f"FINALIZE_STEP4B: subnumber_id=None ticket={ticket_number}, skipping result update")
                print(f"[WARN] Step 4b: cannot resolve current subnumber for {ticket_number}", file=sys.stderr)
            else:
                update_args = _build_result_update_args(abs_work_dir)
                if not update_args:
                    _append_log(abs_work_dir, "WARN", f"FINALIZE_STEP4B: no workflow number in status.json ticket={ticket_number}, skipping result update")
                else:
                    _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP4B: ticket={ticket_number} sub_id={sub_id} update_args={update_args}")
                    run(
                        ["python3", KANBAN_PY, "update-subnumber", ticket_number, "--id", str(sub_id)] + update_args,
                        "Step 4b: ticket result workflow update",
                    )

    # ── Step 4c: 체인 감지 및 다음 스테이지 발사 (비동기) ──
    # .context.json의 command에 ">" 구분자가 포함되면 체인으로 판별한다.
    # 현재 command(첫 세그먼트)를 제거한 나머지(remaining)가 있으면
    # chain_launcher.py를 비동기로 호출하여 다음 스테이지를 발사한다.
    _chain_launched: bool = False
    if status == "완료" and ticket_number and abs_work_dir is not None:
        context_file: str = os.path.join(abs_work_dir, ".context.json")
        context_data = load_json_file(context_file)
        full_command: str = ""
        if isinstance(context_data, dict):
            full_command = context_data.get("command", "")

        if CHAIN_SEPARATOR in full_command:
            segments: list[str] = [s.strip() for s in full_command.split(CHAIN_SEPARATOR)]
            remaining_segments: list[str] = segments[1:]  # 첫 세그먼트(현재 command) 제거

            if remaining_segments:
                remaining_chain: str = CHAIN_SEPARATOR.join(remaining_segments)
                report_path: str = os.path.join(abs_work_dir, "report.md")

                if not os.path.isfile(report_path):
                    _append_log(abs_work_dir, "WARN", f"FINALIZE_CHAIN: report.md not found at {report_path}, using workdir as fallback")
                    report_path = abs_work_dir

                if os.path.isfile(CHAIN_LAUNCHER):
                    _append_log(
                        abs_work_dir,
                        "INFO",
                        f"FINALIZE_CHAIN: ticket={ticket_number} remaining={remaining_chain} prev_report={report_path}",
                    )
                    try:
                        _chain_log_path: str = os.path.join(abs_work_dir, "chain_launcher.log")
                        try:
                            _chain_log_fh = open(_chain_log_path, "a", encoding="utf-8")
                        except Exception:
                            _chain_log_fh = subprocess.DEVNULL  # type: ignore[assignment]
                        subprocess.Popen(
                            [
                                "python3",
                                CHAIN_LAUNCHER,
                                ticket_number,
                                remaining_chain,
                                report_path,
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=_chain_log_fh,
                            start_new_session=True,
                        )
                        _chain_launched = True
                        _append_log(abs_work_dir, "INFO", "FINALIZE_CHAIN: chain_launcher launched successfully")
                    except Exception as _chain_err:
                        _append_log(abs_work_dir, "ERROR", f"FINALIZE_CHAIN: launch error={_chain_err}")
                        print(f"[ERROR] Step 4c: chain_launcher.py 실행 실패: {_chain_err}", file=sys.stderr)
                        _ticket_num_str = (ticket_number or "").replace("T-", "").lstrip("0") or "N"
                        print(f"  수동으로 다음 스테이지를 시작하려면: /wf -s {_ticket_num_str}", file=sys.stderr)
                        print(f"  남은 체인: {remaining_chain}", file=sys.stderr)
                else:
                    _append_log(abs_work_dir, "WARN", f"FINALIZE_CHAIN: chain_launcher.py not found at {CHAIN_LAUNCHER}")
                    print(f"[WARN] Step 4c: chain_launcher.py not found: {CHAIN_LAUNCHER}", file=sys.stderr)
            else:
                if abs_work_dir is not None:
                    _append_log(abs_work_dir, "INFO", "FINALIZE_CHAIN: chain complete (no remaining segments)")

    # ── Step 5: tmux 윈도우 백그라운드 지연 kill (비차단) ──
    # 체인이 발사된 경우, tmux kill은 chain_launcher.py가 이전 윈도우 사망 대기 후
    # 새 윈도우를 생성하므로 여기서는 기존 로직대로 kill을 진행한다.
    tmux_pane: str | None = os.environ.get("TMUX_PANE")
    if tmux_pane:
        try:
            win_result = subprocess.run(
                ["tmux", "display-message", "-t", tmux_pane, "-p", "#W"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            win_name: str = win_result.stdout.strip()
            if win_name.startswith(f"{WINDOW_PREFIX_P}T-"):
                if abs_work_dir is not None:
                    _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP5: tmux_cleanup win={win_name} pane={tmux_pane} delay=3s")
                # TMUX_PANE(%N)을 직접 타겟으로 사용: 콜론 포함 윈도우명의 세션:윈도우 오해석 방지
                pane_target: str = shlex.quote(tmux_pane)
                bash_cmd: str = f"sleep 3 && tmux kill-window -t {pane_target}"
                subprocess.Popen(
                    ["bash", "-c", bash_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            else:
                if abs_work_dir is not None:
                    _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP5: skip tmux_cleanup win={win_name!r} (not P:T-* prefix)")
        except Exception as _e:
            if abs_work_dir is not None:
                _append_log(abs_work_dir, "WARN", f"FINALIZE_STEP5: tmux_cleanup error={_e}")
    else:
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", "FINALIZE_STEP5: skip tmux_cleanup (TMUX_PANE not set)")

    if status == "완료":
        status_label = f"{C_YELLOW}완료{C_RESET}"
    else:
        status_label = f"{C_RED}실패{C_RESET}"
    print(f"{C_CLAUDE}║ DONE:{C_RESET} {C_DIM}워크플로우{C_RESET} {status_label}", flush=True)
    print(f"{C_CLAUDE}║{C_RESET} {C_DIM}{registry_key}{C_RESET}", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()

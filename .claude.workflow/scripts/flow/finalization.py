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
  4. 티켓 상태 갱신          (kanban.py move -> review, ticket_number 있을 때만, 비차단. 자동 merge 금지)
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
import threading
import time
import urllib.request
import urllib.error

# utils 패키지 import
_scripts_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import C_CLAUDE, C_DIM, C_RED, C_RESET, C_YELLOW, acquire_lock, load_json_file, release_lock, resolve_abs_work_dir, resolve_project_root
from data.constants import CHAIN_SEPARATOR, ERROR_THRESHOLD, LOGS_HEADER_LINE, LOGS_SEPARATOR_LINE
from flow.flow_logger import append_log as _append_log
from flow.session_identifier import WINDOW_PREFIX_P

PROJECT_ROOT: str = resolve_project_root()


# 스크립트 경로
HISTORY_SYNC: str = os.path.join(PROJECT_ROOT, ".claude.workflow", "scripts", "sync", "history_sync.py")
UPDATE_STATE: str = os.path.join(PROJECT_ROOT, ".claude.workflow", "scripts", "flow", "update_state.py")
USAGE_SYNC: str = os.path.join(PROJECT_ROOT, ".claude.workflow", "scripts", "sync", "usage_sync.py")
KANBAN_PY: str = os.path.join(PROJECT_ROOT, ".claude.workflow", "scripts", "flow", "kanban.py")
CHAIN_LAUNCHER: str = os.path.join(PROJECT_ROOT, ".claude.workflow", "scripts", "flow", "chain_launcher.py")


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




def _update_skill_frequency() -> None:
    """dashboard/.skills.md의 스킬 목록 컬럼을 파싱하여 스킬별 누적 빈도 집계표를 갱신한다.

    .skills.md의 테이블 행에서 `스킬 목록` 컬럼(인덱스 5, 0-based)을 읽고
    `<br>` 구분자로 스킬명을 분리하여 전체 사용 횟수를 카운트한다.
    집계 결과를 `## 스킬 빈도 집계` 섹션으로 파일 하단에 추가/갱신한다.

    테이블 형식: | 스킬명 | 사용 횟수 | 비율 | (내림차순 정렬)

    예외 발생 시 무시하고 계속 진행한다.
    """
    try:
        skills_md = os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard", ".skills.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard", ".skills.md.lock")

        if not os.path.isfile(skills_md):
            return

        with open(skills_md, "r", encoding="utf-8") as f:
            content = f.read()

        # 스킬 빈도 집계 섹션 마커
        freq_section_marker = "## 스킬 빈도 집계"

        # 섹션 이전 본문(테이블 부분)만 파싱 대상으로 분리
        if freq_section_marker in content:
            table_part = content[:content.index(freq_section_marker)]
        else:
            table_part = content

        # 테이블 행 파싱: `|`로 시작하고 구분선(---|)이 아닌 행
        skill_counts: dict[str, int] = {}
        for line in table_part.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            # 구분선 행 건너뜀 (예: |------|--------|...)
            if line.replace("|", "").replace("-", "").replace(" ", "") == "":
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) < 6:
                continue
            first_col = cols[0].strip()
            # 헤더 행 건너뜀
            if first_col in ("날짜", "---") or first_col.startswith("---"):
                continue
            # 스킬 목록 컬럼 (0-based index 5)
            skills_raw = cols[5].strip()
            if not skills_raw or skills_raw in ("-", "스킬 목록"):
                continue
            # <br> 구분자로 스킬명 분리 (대소문자 무관)
            skill_list = [s.strip() for s in skills_raw.replace("<BR>", "<br>").split("<br>") if s.strip()]
            for skill in skill_list:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

        if not skill_counts:
            return

        # 내림차순 정렬 (동점 시 스킬명 알파벳 순)
        sorted_skills = sorted(skill_counts.items(), key=lambda x: (-x[1], x[0]))
        total = sum(skill_counts.values())

        # 테이블 생성
        rows: list[str] = []
        rows.append("| 스킬명 | 사용 횟수 | 비율 |")
        rows.append("|--------|----------|------|")
        for skill_name, count in sorted_skills:
            ratio = f"{count / total * 100:.1f}%"
            rows.append(f"| {skill_name} | {count} | {ratio} |")

        freq_section = freq_section_marker + "\n\n" + "\n".join(rows) + "\n"

        # 기존 섹션 교체 또는 하단에 추가
        if freq_section_marker in content:
            new_content = content[:content.index(freq_section_marker)] + freq_section
        else:
            new_content = content.rstrip("\n") + "\n\n" + freq_section

        # POSIX lock + 원자적 쓰기
        os.makedirs(os.path.dirname(skills_md), exist_ok=True)
        locked = acquire_lock(lock_dir)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(skills_md), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            shutil.move(tmp, skills_md)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        finally:
            if locked:
                release_lock(lock_dir)
    except Exception:
        pass


def _update_logs_md(registry_key: str, abs_work_dir: str) -> None:
    """dashboard/.logs.md 파일에 워크플로우 로그 통계 행을 삽입한다.

    workflow.log 파일에서 WARN/ERROR 카운트와 파일 크기를 수집하여
    마크다운 테이블 행을 구성하고 원자적으로 삽입한다.
    예외 발생 시 무시하고 계속 진행한다.

    Args:
        registry_key: YYYYMMDD-HHMMSS 형식 워크플로우 식별자
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로
    """
    try:
        marker = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"
        logs_md = os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard", ".logs.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard", ".logs.md.lock")

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
            hallu_count = log_content.count("HALLUCINATION_SUSPECT")
            artifact_count = log_content.count("ARTIFACT:")
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
            hallu_count = 0
            artifact_count = 0
            size_str = "-"

        # P13: ERROR 임계치 알림
        # error_count >= ERROR_THRESHOLD이면 workflow.log에 WARN 기록 및 stderr 출력
        if error_count >= ERROR_THRESHOLD:
            _append_log(
                abs_work_dir,
                "WARN",
                f"ERROR_THRESHOLD_EXCEEDED: count={error_count} threshold={ERROR_THRESHOLD}",
            )
            print(
                f"[WARN] ERROR_THRESHOLD_EXCEEDED: count={error_count} threshold={ERROR_THRESHOLD}"
                f" (registryKey={registry_key})",
                file=sys.stderr,
                flush=True,
            )
            # TODO: Slack 알림 연동 포인트
            # slack_notify(registry_key, error_count, ERROR_THRESHOLD)

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

        # 로그 링크: abs_work_dir에서 dashboard 기준 상대 경로 계산
        try:
            rel_work_dir = os.path.relpath(abs_work_dir, os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard"))
            log_link = f"[로그]({rel_work_dir}/workflow.log)"
        except Exception:
            log_link = "-"

        # 제목 축약 (20자 초과 시)
        title_display = title[:20] + "…" if len(title) > 20 else title

        row = (
            f"| {date_str} | {registry_key} | {title_display} | {command}"
            f" | {warn_count} | {error_count} | {hallu_count} | {artifact_count} | {size_str} | {log_link} |"
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
        locked = acquire_lock(lock_dir)
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
                release_lock(lock_dir)
    except Exception:
        pass


def _safe_listdir(path: str) -> list[str]:
    """디렉터리 목록을 반환한다. 오류 시 빈 리스트 반환."""
    try:
        return os.listdir(path)
    except OSError:
        return []


def _update_step_durations() -> None:
    """모든 완료된 워크플로우의 단계별 소요 시간을 집계하여 .history.md 하단에 표시한다.

    workflow/ 및 workflow/.history/ 디렉터리를 스캔하여 step이 DONE인
    status.json의 transitions 배열을 읽고, 각 단계(PLAN/WORK/REPORT/DONE) 간
    시간 차이를 초 단위로 계산한다.
    집계 결과를 `## 단계별 평균 소요 시간` 섹션으로 파일 하단에 추가/갱신한다.

    테이블 형식: | 단계 | 평균 소요 | 최소 | 최대 | 횟수 |

    단계 레이블:
        PLAN  : NONE/INIT → PLAN (created_at 기준)
        WORK  : PLAN → WORK
        REPORT: WORK → REPORT
        DONE  : REPORT → DONE

    예외 발생 시 무시하고 계속 진행한다.
    """
    try:
        from datetime import datetime as _dt

        history_md = os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard", ".history.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard", ".history.md.lock")

        wf_base = os.path.join(PROJECT_ROOT, ".claude.workflow", "workflow")
        wf_dirs = [wf_base, os.path.join(wf_base, ".history")]

        # PLAN/WORK/REPORT 단계 소요 시간만 집계 (DONE 이후 측정 불가)
        step_label_order = ["PLAN", "WORK", "REPORT"]
        durations: dict[str, list[float]] = {label: [] for label in step_label_order}

        def _parse_iso(s: str) -> "float | None":
            """ISO 8601 타임스탬프를 Unix 타임스탬프(float)로 변환."""
            try:
                return _dt.fromisoformat(s).timestamp()
            except Exception:
                return None

        for wf_dir in wf_dirs:
            if not os.path.isdir(wf_dir):
                continue
            for ts_entry in _safe_listdir(wf_dir):
                ts_path = os.path.join(wf_dir, ts_entry)
                if not os.path.isdir(ts_path):
                    continue
                for work_name in _safe_listdir(ts_path):
                    work_path = os.path.join(ts_path, work_name)
                    if not os.path.isdir(work_path):
                        continue
                    for cmd_name in _safe_listdir(work_path):
                        cmd_path = os.path.join(work_path, cmd_name)
                        if not os.path.isdir(cmd_path):
                            continue
                        status_file = os.path.join(cmd_path, "status.json")
                        if not os.path.isfile(status_file):
                            continue
                        try:
                            with open(status_file, "r", encoding="utf-8") as _f:
                                data = json.load(_f)
                        except Exception:
                            continue

                        if not isinstance(data, dict):
                            continue
                        if data.get("step") != "DONE":
                            continue

                        transitions = data.get("transitions", [])
                        if not isinstance(transitions, list):
                            continue

                        # transitions 구조: {from, to, at}
                        # at은 해당 전환이 발생한 시각 (= "to" 단계 진입 시각)
                        # 각 단계 소요 시간 = 다음 단계 진입 시각 - 현재 단계 진입 시각
                        # ex) PLAN 소요 = WORK 진입 at - PLAN 진입 at
                        #     WORK 소요 = REPORT 진입 at - WORK 진입 at
                        #     REPORT 소요 = DONE 진입 at - REPORT 진입 at
                        # transitions에서 to: at 맵으로 변환 (각 단계 진입 시각)
                        at_map: dict[str, str] = {}
                        for t in transitions:
                            if isinstance(t, dict) and t.get("to") and t.get("at"):
                                at_map[t["to"]] = t["at"]

                        # 단계 소요 = (다음 단계 진입 시각) - (현재 단계 진입 시각)
                        step_pairs = [
                            ("PLAN",   _parse_iso(at_map.get("PLAN", "")),   _parse_iso(at_map.get("WORK", ""))),
                            ("WORK",   _parse_iso(at_map.get("WORK", "")),   _parse_iso(at_map.get("REPORT", ""))),
                            ("REPORT", _parse_iso(at_map.get("REPORT", "")), _parse_iso(at_map.get("DONE", ""))),
                        ]

                        for label, t_start, t_end in step_pairs:
                            if t_start is not None and t_end is not None and t_end > t_start:
                                durations[label].append(t_end - t_start)

        # ── 소요 시간 포매팅 ──
        def _fmt_seconds(secs: float) -> str:
            """초 단위 소요 시간을 사람이 읽기 쉬운 형식으로 변환."""
            if secs < 1:
                return "<1초"
            if secs < 60:
                return f"{secs:.0f}초"
            mins = int(secs) // 60
            rem_secs = int(secs) % 60
            if mins < 60:
                return f"{mins}분 {rem_secs}초" if rem_secs else f"{mins}분"
            hours = mins // 60
            rem_mins = mins % 60
            return f"{hours}시간 {rem_mins}분" if rem_mins else f"{hours}시간"

        # ── 테이블 생성 ──
        rows: list[str] = []
        rows.append("| 단계 | 평균 소요 | 최소 | 최대 | 횟수 |")
        rows.append("|------|----------|------|------|------|")
        for label in step_label_order:
            vals = durations[label]
            if not vals:
                rows.append(f"| {label} | - | - | - | 0 |")
            else:
                avg = sum(vals) / len(vals)
                mn = min(vals)
                mx = max(vals)
                rows.append(f"| {label} | {_fmt_seconds(avg)} | {_fmt_seconds(mn)} | {_fmt_seconds(mx)} | {len(vals)} |")

        section_marker = "## 단계별 평균 소요 시간"
        new_section = section_marker + "\n\n" + "\n".join(rows) + "\n"

        # ── .history.md 읽기 ──
        if not os.path.isfile(history_md):
            return

        with open(history_md, "r", encoding="utf-8") as f:
            content = f.read()

        # 기존 섹션 교체 또는 하단에 추가
        if section_marker in content:
            new_content = content[:content.index(section_marker)] + new_section
        else:
            new_content = content.rstrip("\n") + "\n\n" + new_section

        # POSIX lock + 원자적 쓰기
        os.makedirs(os.path.dirname(history_md), exist_ok=True)
        locked = acquire_lock(lock_dir)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(history_md), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            shutil.move(tmp, history_md)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        finally:
            if locked:
                release_lock(lock_dir)
    except Exception:
        pass


def _update_task_stats(registry_key: str, abs_work_dir: str) -> None:
    """dashboard/.history.md 하단에 태스크 성공/실패 누적 통계 섹션을 추가/갱신한다.

    전체 워크플로우(workflow/ 및 workflow/.history/)의 status.json을 순회하여
    tasks 객체의 상태별 누적 집계를 계산하고 .history.md에 표시한다.

    집계 기준:
        - completed: 성공 카운트
        - failed: 실패 카운트
        - running/skipped/기타: 미완료로 집계 제외

    테이블 형식: | 총 태스크 | 성공 | 실패 | 성공률 |

    Args:
        registry_key: YYYYMMDD-HHMMSS 형식 워크플로우 식별자 (로그용)
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로 (로그용)

    예외 발생 시 무시하고 계속 진행한다.
    """
    try:
        history_md = os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard", ".history.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".claude.workflow", "dashboard", ".history.md.lock")
        workflow_root = os.path.join(PROJECT_ROOT, ".claude.workflow", "workflow")

        if not os.path.isfile(history_md):
            return

        # 전체 워크플로우 status.json 탐색 (workflow/ 및 workflow/.history/ 포함)
        search_dirs = [workflow_root]
        history_subdir = os.path.join(workflow_root, ".history")
        if os.path.isdir(history_subdir):
            search_dirs.append(history_subdir)

        total_count = 0
        completed_count = 0
        failed_count = 0

        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            # registryKey 디렉터리 순회 (YYYYMMDD-HHMMSS 패턴)
            for entry in _safe_listdir(search_dir):
                entry_path = os.path.join(search_dir, entry)
                if not os.path.isdir(entry_path):
                    continue
                # registryKey 디렉터리 하위에서 status.json 탐색 (workName/command/ 구조)
                for sub1 in _safe_listdir(entry_path):
                    sub1_path = os.path.join(entry_path, sub1)
                    if not os.path.isdir(sub1_path):
                        continue
                    for sub2 in _safe_listdir(sub1_path):
                        status_path = os.path.join(sub1_path, sub2, "status.json")
                        if not os.path.isfile(status_path):
                            continue
                        status_data = load_json_file(status_path)
                        if not isinstance(status_data, dict):
                            continue
                        tasks = status_data.get("tasks", {})
                        if not isinstance(tasks, dict):
                            continue
                        for task_info in tasks.values():
                            if not isinstance(task_info, dict):
                                continue
                            task_status = task_info.get("status", "")
                            if task_status == "completed":
                                total_count += 1
                                completed_count += 1
                            elif task_status == "failed":
                                total_count += 1
                                failed_count += 1

        if total_count == 0:
            return

        success_rate = f"{completed_count / total_count * 100:.1f}%"

        # 통계 섹션 생성
        section_marker = "## 태스크 성공/실패 통계"
        rows: list[str] = [
            "| 총 태스크 | 성공 | 실패 | 성공률 |",
            "|----------|------|------|--------|",
            f"| {total_count} | {completed_count} | {failed_count} | {success_rate} |",
        ]
        new_section = section_marker + "\n\n" + "\n".join(rows) + "\n"

        # .history.md 읽기
        with open(history_md, "r", encoding="utf-8") as f:
            content = f.read()

        # 기존 섹션 교체 또는 하단에 추가
        if section_marker in content:
            new_content = content[:content.index(section_marker)] + new_section
        else:
            new_content = content.rstrip("\n") + "\n\n" + new_section

        # POSIX lock + 원자적 쓰기
        os.makedirs(os.path.dirname(history_md), exist_ok=True)
        locked = acquire_lock(lock_dir)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(history_md), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            shutil.move(tmp, history_md)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        finally:
            if locked:
                release_lock(lock_dir)
    except Exception:
        pass


def _build_result_update_args(abs_work_dir: str) -> list[str]:
    """update-result CLI 추가 인자 리스트를 반환한다.

    abs_work_dir에서 registryKey를 추출하고, plan.md / report.md 존재 여부를
    확인하여 update-result CLI에 전달할 인자 리스트를 반환한다.

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
    _ts_pattern = _re.compile(r"\.claude\.workflow[/\\]workflow[/\\](\d{8}-\d{6}(?:-\d+)?)")
    _match = _ts_pattern.search(abs_work_dir)
    if not _match:
        return []

    registry_key: str = _match.group(1)

    # 상대 workDir: .claude.workflow/workflow/{registryKey}/... 이후 부분을 포함한 경로
    _wf_idx = abs_work_dir.find(".claude.workflow/workflow/")
    if _wf_idx == -1:
        _wf_idx = abs_work_dir.find(".claude.workflow\\workflow\\")
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
    """CLI 진입점. 인자 파싱 후 워크플로우 마무리 6단계를 순서대로 실행한다.

    6단계:
      1. status.json 완료 처리   (update_state.py status, 이미 대상 상태면 스킵, 그 외 실패 시 exit 1 — sync 포함)
      2. 사용량 확정             (update_state.py usage-finalize, 비차단)
      3. 아카이빙               (history_sync.py archive, 비차단)
      4. 티켓 상태 갱신          (kanban.py move -> review, ticket_number 있을 때만, 비차단. 자동 merge 금지)
      4c. 체인 감지 및 다음 스테이지 발사 (chain_launcher.py, 완료+체인 존재 시만, 비동기)
      5. tmux 윈도우 백그라운드 지연 kill (TMUX_PANE+T-* 조건 시만, 비차단)
    """
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

    # ── Step 2: 사용량 확정 (비차단, status 무관) ──
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
            _hallu_count_log = 0
            if os.path.isfile(_log_path):
                try:
                    with open(_log_path, "r", encoding="utf-8", errors="replace") as _f:
                        _log_content = _f.read()
                    _warn_count = _log_content.count("[WARN]")
                    _error_count = _log_content.count("[ERROR]")
                    _hallu_count_log = _log_content.count("HALLUCINATION_SUSPECT")
                except Exception:
                    pass
            _append_log(abs_work_dir, "INFO", f"FINALIZE_LOGS_MD: registryKey={registry_key} warn={_warn_count} error={_error_count} hallu={_hallu_count_log}")
    except Exception:
        pass

    # ── Step 5b: 스킬 빈도 집계 갱신 (비차단) ──
    try:
        _update_skill_frequency()
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_SKILL_FREQ: registryKey={registry_key}")
    except Exception:
        pass

    # ── Step 5c: 태스크 성공/실패 통계 갱신 (비차단) ──
    try:
        _update_task_stats(registry_key, abs_work_dir)
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_TASK_STATS: registryKey={registry_key}")
    except Exception:
        pass

    # ── Step 5d: 단계별 소요 시간 집계 갱신 (비차단) ──
    try:
        _update_step_durations()
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP_DUR: registryKey={registry_key}")
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
            update_args = _build_result_update_args(abs_work_dir)
            if not update_args:
                _append_log(abs_work_dir, "WARN", f"FINALIZE_STEP4B: no workflow number in status.json ticket={ticket_number}, skipping result update")
            else:
                _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP4B: ticket={ticket_number} update_args={update_args}")
                run(
                    ["python3", KANBAN_PY, "update-result", ticket_number] + update_args,
                    "Step 4b: ticket result workflow update",
                )

    # ── Step 4wt: worktree 유지 (Review 단계, merge 금지) ──
    # worktree가 활성화된 경우, Review 상태에서 worktree를 유지한다.
    # 자동 커밋/merge/worktree 정리는 이 단계에서 절대 수행하지 않는다.
    # merge는 사용자의 명시적 완료 지시(/wf -d) 후 flow-merge로만 실행된다.
    # 정리 파이프라인: /wf -d -> 간단검토 -> 완료선택 -> flow-merge
    if ticket_number and abs_work_dir is not None:
        try:
            context_file_wt: str = os.path.join(abs_work_dir, ".context.json")
            context_wt = load_json_file(context_file_wt)
            if isinstance(context_wt, dict) and context_wt.get("worktree", {}).get("enabled"):
                wt_branch = context_wt["worktree"].get("featureBranch", "")
                wt_path = context_wt["worktree"].get("path", "")
                _append_log(
                    abs_work_dir,
                    "INFO",
                    f"FINALIZE_STEP4WT: worktree 유지 (Review 단계) branch={wt_branch} path={wt_path}",
                )
                print(
                    f"[INFO] worktree 유지: {wt_branch} (merge는 /wf -d 완료 지시 후 실행)",
                    file=sys.stderr,
                    flush=True,
                )
        except Exception:
            pass  # worktree 메타데이터 읽기 실패는 무시

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

    # ── Step 5: 세션 백그라운드 지연 kill (비차단) ──
    # 체인이 발사된 경우, chain_launcher.py가 이전 세션 종료 대기 후
    # 새 세션을 생성하므로 여기서는 기존 로직대로 kill을 진행한다.
    #
    # 분기: _WF_SESSION_ID + _WF_SERVER_PORT 환경변수가 둘 다 존재하면
    #       HTTP API 경로, 그 외에는 기존 TMUX_PANE 기반 폴백을 유지한다.
    _wf_session_id: str | None = os.environ.get("_WF_SESSION_ID")
    _wf_server_port: str | None = os.environ.get("_WF_SERVER_PORT")

    if _wf_session_id and _wf_server_port:
        # ── HTTP API 경로: POST /terminal/workflow/kill ──
        def _http_kill_session(session_id: str, port: str, work_dir: str | None) -> None:
            """3초 지연 후 HTTP API로 세션 kill 요청을 보낸다."""
            time.sleep(3)
            url = f"http://127.0.0.1:{port}/terminal/workflow/kill"
            payload = json.dumps({"session_id": session_id}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp.read()
            except Exception:
                pass  # 비차단: kill 실패해도 프로세스 종료에 영향 없음

        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP5: http_kill session_id={_wf_session_id}")
        t = threading.Thread(
            target=_http_kill_session,
            args=(_wf_session_id, _wf_server_port, abs_work_dir),
            daemon=True,
        )
        t.start()
    else:
        # ── TMUX 폴백 경로: 기존 TMUX_PANE 기반 kill ──
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", "FINALIZE_STEP5: tmux_fallback_kill")
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

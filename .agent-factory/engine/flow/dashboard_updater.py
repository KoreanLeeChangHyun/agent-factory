"""워크플로우 종료 시 board/data/ 대시보드(.skills.md / .logs.md / .history.md) 갱신.

finalization.py 비차단 후처리에서 분리. 호출 시그니처와 비차단 패턴(호출부 try/except) 동일.

함수:
    _update_skill_frequency()                       — .skills.md 스킬 빈도 집계
    _update_logs_md(registry_key, abs_work_dir)     — .logs.md 워크플로우 로그 행 삽입
    _update_step_durations()                        — .history.md 단계별 평균 소요 시간
    _update_task_stats(registry_key, abs_work_dir)  — .history.md 태스크 성공/실패 통계
    _safe_listdir(path)                             — 헬퍼 (오류 시 빈 리스트 반환)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

# import utils package (same sys.path processing as finalization.py)
_engine_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import acquire_lock, load_json_file, release_lock, resolve_project_root
from constants import ERROR_THRESHOLD, LOGS_HEADER_LINE, LOGS_SEPARATOR_LINE
from flow.flow_logger import append_log as _append_log

PROJECT_ROOT: str = resolve_project_root()


def _update_skill_frequency() -> None:
    """dashboard/.skills.md의 스킬 목록 컬럼을 파싱하여 스킬별 누적 빈도 집계표를 갱신한다.

    .skills.md의 테이블 행에서 `Skill List` 컬럼(인덱스 5, 0-based)을 읽고
    `<br>` 구분자로 스킬명을 분리하여 전체 사용 횟수를 카운트한다.
    집계 결과를 `## Skill frequency count` 섹션으로 파일 하단에 추가/갱신한다.

    테이블 형식: | 스킬명 | 사용 횟수 | 비율 | (내림차순 정렬)

    예외 발생 시 무시하고 계속 진행한다.
    """
    try:
        skills_md = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".skills.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".skills.md.lock")

        if not os.path.isfile(skills_md):
            return

        with open(skills_md, "r", encoding="utf-8") as f:
            content = f.read()

        # Skill Frequency Count Section Marker
        freq_section_marker = "## Skill frequency count"

        # Separate only the body (table part) before the section as a parsing target
        if freq_section_marker in content:
            table_part = content[:content.index(freq_section_marker)]
        else:
            table_part = content

        # Parsing table rows: rows that start with `|` and are not separator (---|)
        skill_counts: dict[str, int] = {}
        for line in table_part.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            # Skip separator lines (e.g. |------|--------|...)
            if line.replace("|", "").replace("-", "").replace(" ", "") == "":
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) < 6:
                continue
            first_col = cols[0].strip()
            # Skip header row
            if first_col in ("date", "---") or first_col.startswith("---"):
                continue
            # Skill list column (0-based index 5)
            skills_raw = cols[5].strip()
            if not skills_raw or skills_raw in ("-", "Skill List"):
                continue
            # <br> Separate skill names with separators (case is irrelevant)
            skill_list = [s.strip() for s in skills_raw.replace("<BR>", "<br>").split("<br>") if s.strip()]
            for skill in skill_list:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

        if not skill_counts:
            return

        # Sort in descending order (in case of a tie, in alphabetical order by skill name)
        sorted_skills = sorted(skill_counts.items(), key=lambda x: (-x[1], x[0]))
        total = sum(skill_counts.values())

        # Create table
        rows: list[str] = []
        rows.append("| Skill name | Number of uses | ratio |")
        rows.append("|--------|----------|------|")
        for skill_name, count in sorted_skills:
            ratio = f"{count / total * 100:.1f}%"
            rows.append(f"| {skill_name} | {count} | {ratio} |")

        freq_section = freq_section_marker + "\n\n" + "\n".join(rows) + "\n"

        # Replace existing section or add to bottom
        if freq_section_marker in content:
            new_content = content[:content.index(freq_section_marker)] + freq_section
        else:
            new_content = content.rstrip("\n") + "\n\n" + freq_section

        # POSIX lock + atomic write
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
        marker = "<!-- New entries will be added below this line -->"
        logs_md = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".logs.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".logs.md.lock")

        # Read title and command from .context.json
        context_file = os.path.join(abs_work_dir, ".context.json")
        context = load_json_file(context_file)
        title = ""
        command = ""
        if isinstance(context, dict):
            title = context.get("title", "")
            command = context.get("command", "")

        # Collect workflow.log statistics
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

        # P13: ERROR threshold notification
        # If error_count >= ERROR_THRESHOLD, log WARN to workflow.log and print to stderr
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
            # TODO: Slack notification integration points
            # slack_notify(registry_key, error_count, ERROR_THRESHOLD)

        # Date: Extract MM-DD HH:MM from registryKey (YYYYMMDD-HHMMSS)
        date_str = "-"
        try:
            parts = registry_key.split("-")
            if len(parts) >= 2:
                ymd = parts[0]  # YYYYMMDD
                hms = parts[1]  # HHMMSS
                date_str = f"{ymd[4:6]}-{ymd[6:8]} {hms[0:2]}:{hms[2:4]}"
        except Exception:
            pass

        # Log link: Calculate relative path relative to dashboard in abs_work_dir
        try:
            rel_work_dir = os.path.relpath(abs_work_dir, os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data"))
            log_link = f"[Log]({rel_work_dir}/workflow.log)"
        except Exception:
            log_link = "-"

        # Shorten title (if exceeding 20 characters)
        title_display = title[:20] + "…" if len(title) > 20 else title

        row = (
            f"| {date_str} | {registry_key} | {title_display} | {command}"
            f" | {warn_count} | {error_count} | {hallu_count} | {artifact_count} | {size_str} | {log_link} |"
        )

        # Read .logs.md
        content = ""
        if os.path.exists(logs_md):
            with open(logs_md, "r", encoding="utf-8") as f:
                content = f.read()

        if marker not in content:
            content = f"# Workflow log tracking \n \n {marker} \n \n {LOGS_HEADER_LINE} \n {LOGS_SEPARATOR_LINE} \n"

        # Insert row after marker + separator
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

        # POSIX lock + atomic write
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
    """Returns a directory listing. In case of error, an empty list is returned."""
    try:
        return os.listdir(path)
    except OSError:
        return []


def _update_step_durations() -> None:
    """모든 완료된 워크플로우의 단계별 소요 시간을 집계하여 .history.md 하단에 표시한다.

    workflow/ 및 workflow/.history/ 디렉터리를 스캔하여 step이 DONE인
    status.json의 transitions 배열을 읽고, 각 단계(PLAN/WORK/REPORT/DONE) 간
    시간 차이를 초 단위로 계산한다.
    집계 결과를 `## Average time spent per step` 섹션으로 파일 하단에 추가/갱신한다.

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

        history_md = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".history.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".history.md.lock")

        wf_base = os.path.join(PROJECT_ROOT, ".agent-factory", "runs")
        wf_dirs = [wf_base, os.path.join(wf_base, ".history")]

        # Only the time spent in the PLAN/WORK/REPORT step is counted (not measurable after DONE)
        step_label_order = ["PLAN", "WORK", "REPORT"]
        durations: dict[str, list[float]] = {label: [] for label in step_label_order}

        def _parse_iso(s: str) -> "float | None":
            """Convert ISO 8601 timestamp to Unix timestamp (float)."""
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

                status_file = os.path.join(ts_path, "status.json")
                if not os.path.isfile(status_file):
                    continue
                try:
                    with open(status_file, "r", encoding="utf-8") as _f:
                        data = json.load(_f)
                except Exception:
                    continue

                if not isinstance(data, dict):
                    continue
                if (data.get("workflow_phase") or data.get("step")) != "DONE":
                    continue

                transitions = data.get("transitions", [])
                if not isinstance(transitions, list):
                    continue

                # transitions structure: {from, to, at}
                # at is the time when the conversion occurred (= “to” stage entry time)
                # Time required for each stage = Next stage entry time - Current stage entry time
                # ex) PLAN required = WORK entry at - PLAN entry at
                #     WORK required = REPORT entry at - WORK entry at
                #     REPORT required = DONE entry at - REPORT entry at
                # Convert transitions to to: at map (entry time for each step)
                at_map: dict[str, str] = {}
                for t in transitions:
                    if isinstance(t, dict) and t.get("to") and t.get("at"):
                        at_map[t["to"]] = t["at"]

                # Step required = (next step entry time) - (current step entry time)
                step_pairs = [
                    ("PLAN",   _parse_iso(at_map.get("PLAN", "")),   _parse_iso(at_map.get("WORK", ""))),
                    ("WORK",   _parse_iso(at_map.get("WORK", "")),   _parse_iso(at_map.get("REPORT", ""))),
                    ("REPORT", _parse_iso(at_map.get("REPORT", "")), _parse_iso(at_map.get("DONE", ""))),
                ]

                for label, t_start, t_end in step_pairs:
                    if t_start is not None and t_end is not None and t_end > t_start:
                        durations[label].append(t_end - t_start)

        # ── Formatting Time Required ──
        def _fmt_seconds(secs: float) -> str:
            """Convert time spent in seconds to human-readable format."""
            if secs < 1:
                return "<1 second"
            if secs < 60:
                return f"{secs:.0f} seconds"
            mins = int(secs) // 60
            rem_secs = int(secs) % 60
            if mins < 60:
                return f"{mins} minutes {rem_secs} seconds" if rem_secs else f"{mins} minutes"
            hours = mins // 60
            rem_mins = mins % 60
            return f"{hours} hours {rem_mins} minutes" if rem_mins else f"{hours}hours"

        # ── Create table ──
        rows: list[str] = []
        rows.append("| steps | Average Takes | Minimum | max | number of times |")
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

        section_marker = "## Average time spent per step"
        new_section = section_marker + "\n\n" + "\n".join(rows) + "\n"

        # ── Read .history.md ──
        if not os.path.isfile(history_md):
            return

        with open(history_md, "r", encoding="utf-8") as f:
            content = f.read()

        # Replace existing section or add to bottom
        if section_marker in content:
            new_content = content[:content.index(section_marker)] + new_section
        else:
            new_content = content.rstrip("\n") + "\n\n" + new_section

        # POSIX lock + atomic write
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
        history_md = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".history.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".history.md.lock")
        workflow_root = os.path.join(PROJECT_ROOT, ".agent-factory", "runs")

        if not os.path.isfile(history_md):
            return

        # Browse entire workflow status.json (including workflow/ and workflow/.history/)
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
            for entry in _safe_listdir(search_dir):
                entry_path = os.path.join(search_dir, entry)
                if not os.path.isdir(entry_path):
                    continue
                status_path = os.path.join(entry_path, "status.json")
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

        # Create statistics section
        section_marker = "## Task success/failure statistics"
        rows: list[str] = [
            "| Total Tasks | Success | failure | Success Rate |",
            "|----------|------|------|--------|",
            f"| {total_count} | {completed_count} | {failed_count} | {success_rate} |",
        ]
        new_section = section_marker + "\n\n" + "\n".join(rows) + "\n"

        # Read .history.md
        with open(history_md, "r", encoding="utf-8") as f:
            content = f.read()

        # Replace existing section or add to bottom
        if section_marker in content:
            new_content = content[:content.index(section_marker)] + new_section
        else:
            new_content = content.rstrip("\n") + "\n\n" + new_section

        # POSIX lock + atomic write
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

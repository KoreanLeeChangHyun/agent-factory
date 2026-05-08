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

# utils 패키지 import (finalization.py와 동일 sys.path 처리)
_engine_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import acquire_lock, load_json_file, release_lock, resolve_project_root
from constants import ERROR_THRESHOLD, LOGS_HEADER_LINE, LOGS_SEPARATOR_LINE
from flow.flow_logger import append_log as _append_log

PROJECT_ROOT: str = resolve_project_root()


def _update_skill_frequency() -> None:
    """dashboard/.skills.md의 스킬 목록 컬럼을 파싱하여 스킬별 누적 빈도 집계표를 갱신한다.

    .skills.md의 테이블 행에서 `스킬 목록` 컬럼(인덱스 5, 0-based)을 읽고
    `<br>` 구분자로 스킬명을 분리하여 전체 사용 횟수를 카운트한다.
    집계 결과를 `## 스킬 빈도 집계` 섹션으로 파일 하단에 추가/갱신한다.

    테이블 형식: | 스킬명 | 사용 횟수 | 비율 | (내림차순 정렬)

    예외 발생 시 무시하고 계속 진행한다.
    """
    try:
        skills_md = os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data", ".skills.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data", ".skills.md.lock")

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
        logs_md = os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data", ".logs.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data", ".logs.md.lock")

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
            rel_work_dir = os.path.relpath(abs_work_dir, os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data"))
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

        history_md = os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data", ".history.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data", ".history.md.lock")

        wf_base = os.path.join(PROJECT_ROOT, ".claude-organic", "runs")
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

                # dual-mode: 새 구조 (T-448 폴드) 우선, 구 구조 fallback
                # 새 구조: ts_path/status.json 직접 존재
                # 구 구조: ts_path/<work_name>/<cmd_name>/status.json 중첩
                def _collect_status_files(ts_path: str) -> "list[str]":
                    """ts_path 하위에서 status.json 경로 목록을 반환 (dual-mode)."""
                    new_status = os.path.join(ts_path, "status.json")
                    if os.path.isfile(new_status):
                        # 새 구조: ts_path 직속 status.json
                        return [new_status]
                    # 구 구조 fallback: ts_path/<work_name>/<cmd_name>/status.json
                    result = []
                    for work_name in _safe_listdir(ts_path):
                        work_path = os.path.join(ts_path, work_name)
                        if not os.path.isdir(work_path):
                            continue
                        for cmd_name in _safe_listdir(work_path):
                            cmd_path = os.path.join(work_path, cmd_name)
                            if not os.path.isdir(cmd_path):
                                continue
                            sf = os.path.join(cmd_path, "status.json")
                            if os.path.isfile(sf):
                                result.append(sf)
                    return result

                for status_file in _collect_status_files(ts_path):
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
        history_md = os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data", ".history.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".claude-organic", "board", "data", ".history.md.lock")
        workflow_root = os.path.join(PROJECT_ROOT, ".claude-organic", "runs")

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

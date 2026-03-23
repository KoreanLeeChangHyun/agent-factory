"""사용량 추적 모듈.

워크플로우 에이전트별 토큰 사용량 기록, 정산, .dashboard/.usage.md 관리를 담당한다.

주요 함수:
    usage_pending: _pending_workers에 에이전트-태스크 매핑 등록
    usage_record: 에이전트별 토큰 데이터 기록
    usage_finalize: totals 계산 및 .usage.md 행 추가
    usage_regenerate: .usage.md 전체 재생성
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from typing import Any

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import (
    acquire_lock,
    atomic_write_json,
    extract_registry_key,
    load_json_file,
    release_lock,
    resolve_project_root,
)
from flow.flow_logger import append_log as _append_log

PROJECT_ROOT: str = resolve_project_root()


def _calc_effective(d: dict[str, Any]) -> float:
    """토큰 데이터 dict에서 effective_tokens를 계산한다.

    Args:
        d: 토큰 데이터 딕셔너리 (input_tokens, output_tokens,
           cache_creation_tokens, cache_read_tokens 키 포함)

    Returns:
        가중 합산된 effective_tokens 값.
    """
    return (
        d.get("input_tokens", 0)
        + d.get("output_tokens", 0) * 5
        + d.get("cache_creation_tokens", 0) * 1.25
        + d.get("cache_read_tokens", 0) * 0.1
    )


def _sum_tokens(agents_list: list[dict[str, Any]]) -> dict[str, int]:
    """에이전트 토큰 데이터 리스트의 합계를 반환한다.

    Args:
        agents_list: 토큰 데이터 딕셔너리 목록

    Returns:
        input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens
        합산 딕셔너리.
    """
    totals: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }
    for a in agents_list:
        for k in totals:
            totals[k] += a.get(k, 0)
    return totals


def _to_k(n: float | int) -> str:
    """숫자를 k 단위 문자열로 변환한다. 0이면 '-'.

    Args:
        n: 변환할 숫자

    Returns:
        k 단위 문자열 (예: '10k', '-').
    """
    return "-" if n == 0 else f"{int(n) // 1000}k"


def _to_k_precise(n: float | int) -> str:
    """숫자를 소수점 1자리 k 단위 문자열로 변환한다. 0이면 '-'.

    Args:
        n: 변환할 숫자

    Returns:
        소수점 1자리 k 단위 문자열 (예: '10.5k', '-').
    """
    return "-" if n == 0 else f"{n / 1000:.1f}k"


def _update_usage_md(row: str, eff_weighted: float) -> str | None:
    """.dashboard/.usage.md 파일에 사용량 행을 삽입한다.

    Args:
        row: 삽입할 마크다운 테이블 행 문자열 (11컬럼 스키마)
        eff_weighted: 가중 합산 effective_tokens (경고 메시지 생성용)

    Returns:
        성공 시 None, 실패 시 에러 결과 문자열.
    """
    usage_md = os.path.join(PROJECT_ROOT, ".dashboard", ".usage.md")
    marker = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"
    header_line = "| 날짜 | 작업ID | 제목 | 명령 | ORC | PLN | WRK | EXP | VAL | RPT | 합계 |"
    separator_line = "|------|--------|------|------|-----|-----|-----|-----|-----|-----|------|"

    content = ""
    if os.path.exists(usage_md):
        with open(usage_md, "r", encoding="utf-8") as f:
            content = f.read()

    if marker not in content:
        content = f"# 워크플로우 사용량 추적\n\n{marker}\n\n{header_line}\n{separator_line}\n"

    # row 컬럼 수 검증: 11컬럼이 아니면 삽입하지 않음
    if row.count("|") - 1 != 11:
        print(
            f"[WARN] usage-finalize: row column count mismatch (expected 11, got {row.count('|') - 1}). row insertion skipped.",
            file=sys.stderr,
        )
        return f"usage-finalize -> totals: eff={_to_k_precise(eff_weighted)}, usage.md skipped (column mismatch)"

    if separator_line in content:
        marker_pos = content.find(marker)
        if marker_pos >= 0:
            sep_pos = content.find(separator_line, marker_pos)
            if sep_pos >= 0:
                insert_pos = sep_pos + len(separator_line)
                if insert_pos < len(content) and content[insert_pos] == "\n":
                    insert_pos += 1
                content = content[:insert_pos] + row + "\n" + content[insert_pos:]
            else:
                content = content.replace(
                    marker, f"{marker}\n\n{header_line}\n{separator_line}\n{row}"
                )
        else:
            content = content.replace(
                marker, f"{marker}\n\n{header_line}\n{separator_line}\n{row}"
            )
    else:
        content = content.replace(
            marker, f"{marker}\n\n{header_line}\n{separator_line}\n{row}"
        )

    os.makedirs(os.path.dirname(usage_md), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(usage_md), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        shutil.move(tmp, usage_md)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    return None  # 성공


def usage_pending(abs_work_dir: str, agent_id: str, task_id: str) -> str:
    """usage.json의 _pending_workers에 agent_id->taskId 매핑을 등록한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        agent_id: 에이전트 ID (예: 'W01')
        task_id: 매핑할 태스크 ID (예: 'W01')

    Returns:
        처리 결과 문자열. 예: 'usage-pending -> W01=W01',
        'usage-pending -> skipped (missing args)', 'usage-pending -> lock failed'.
    """
    if not agent_id or not task_id:
        print("[WARN] usage-pending: agent_id, task_id 인자가 필요합니다.", file=sys.stderr)
        return "usage-pending -> skipped (missing args)"

    usage_file = os.path.join(abs_work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not acquire_lock(lock_dir, max_wait=5):
        print("[WARN] usage-pending: 잠금 획득 실패", file=sys.stderr)
        return "usage-pending -> lock failed"

    try:
        data = load_json_file(usage_file)
        if not isinstance(data, dict):
            data = {}

        if "_pending_workers" not in data or not isinstance(data.get("_pending_workers"), dict):
            data["_pending_workers"] = {}

        data["_pending_workers"][agent_id] = task_id

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, data)
        _append_log(abs_work_dir, "INFO", f"USAGE_PENDING: agentId={agent_id} taskId={task_id}")
        return f"usage-pending -> {agent_id}={task_id}"
    finally:
        release_lock(lock_dir)


def usage_record(
    abs_work_dir: str,
    agent_name: str,
    input_tokens: int | str,
    output_tokens: int | str,
    cache_creation: int | str = 0,
    cache_read: int | str = 0,
    task_id: str = "",
) -> str:
    """usage.json의 agents 객체에 에이전트별 토큰 데이터를 기록한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        agent_name: 에이전트 이름 (예: 'orchestrator', 'worker')
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        cache_creation: 캐시 생성 토큰 수 (기본값 0)
        cache_read: 캐시 읽기 토큰 수 (기본값 0)
        task_id: worker 에이전트의 태스크 ID (agent_name='worker'일 때만 사용)

    Returns:
        처리 결과 문자열. 예: 'usage -> orchestrator: in=1000 out=500 cc=0 cr=0',
        'usage -> workers.W01: in=2000 out=1000 cc=100 cr=50',
        'usage -> skipped (missing args)', 'usage -> lock failed'.
    """
    if not agent_name or input_tokens is None or output_tokens is None:
        print("[WARN] usage: agent_name, input_tokens, output_tokens 인자가 필요합니다.", file=sys.stderr)
        return "usage -> skipped (missing args)"

    usage_file = os.path.join(abs_work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not acquire_lock(lock_dir, max_wait=5):
        print("[WARN] usage: 잠금 획득 실패", file=sys.stderr)
        return "usage -> lock failed"

    try:
        data = load_json_file(usage_file)
        if not isinstance(data, dict):
            data = {}

        if "agents" not in data or not isinstance(data.get("agents"), dict):
            data["agents"] = {}

        token_data: dict[str, Any] = {
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "cache_creation_tokens": int(cache_creation),
            "cache_read_tokens": int(cache_read),
            "method": "subagent_transcript",
        }

        if agent_name == "worker" and task_id:
            if "workers" not in data["agents"] or not isinstance(data["agents"].get("workers"), dict):
                data["agents"]["workers"] = {}
            data["agents"]["workers"][task_id] = token_data
            label = f"workers.{task_id}"
        else:
            data["agents"][agent_name] = token_data
            label = agent_name

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, data)
        _append_log(abs_work_dir, "INFO", f"USAGE_RECORDED: agent={label}")
        return f"usage -> {label}: in={input_tokens} out={output_tokens} cc={cache_creation} cr={cache_read}"
    finally:
        release_lock(lock_dir)


def usage_finalize(abs_work_dir: str) -> str:
    """totals를 계산하고 effective_tokens를 산출하여 .dashboard/.usage.md에 행을 추가한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로 (usage.json이 위치하는 디렉터리)

    Returns:
        처리 결과 문자열. 예: 'usage-finalize -> totals: eff=12.5k, usage.md updated',
        'usage-finalize -> skipped (file not found)', 'usage-finalize -> failed'.
    """
    usage_file = os.path.join(abs_work_dir, "usage.json")
    if not os.path.isfile(usage_file):
        print(f"[WARN] usage-finalize: usage.json not found: {usage_file}", file=sys.stderr)
        return "usage-finalize -> skipped (file not found)"

    try:
        data = load_json_file(usage_file)
        if not isinstance(data, dict):
            return "usage-finalize -> skipped (invalid format)"

        # $schema 가드: usage-v2가 아니면 마이그레이션
        if data.get("$schema") != "usage-v2":
            data.pop("init", None)
            data.pop("done", None)
            data["$schema"] = "usage-v2"

        agents = data.get("agents", {})

        # 모든 에이전트 토큰 데이터 수집
        all_agents: list[dict[str, Any]] = []
        for key in ["orchestrator", "planner", "explorer", "validator", "reporter"]:
            if key in agents and isinstance(agents[key], dict):
                all_agents.append(agents[key])

        workers = agents.get("workers", {})
        if isinstance(workers, dict):
            for w in workers.values():
                if isinstance(w, dict):
                    all_agents.append(w)

        # totals 계산
        totals = _sum_tokens(all_agents)
        totals["effective_tokens"] = _calc_effective(totals)
        data["totals"] = totals

        atomic_write_json(usage_file, data)

        # registryKey 추출
        registry_key = extract_registry_key(abs_work_dir)

        # .context.json에서 메타데이터 조회
        reg_title = ""
        reg_command = ""
        ctx_file = os.path.join(abs_work_dir, ".context.json")
        ctx_data = load_json_file(ctx_file)
        if isinstance(ctx_data, dict):
            reg_title = ctx_data.get("title", "")
            reg_command = ctx_data.get("command", "")

        title = reg_title[:30] if reg_title else ""

        # 날짜 추출
        date_str = ""
        if len(registry_key) >= 15:
            try:
                date_str = f"{registry_key[4:6]}-{registry_key[6:8]} {registry_key[9:11]}:{registry_key[11:13]}"
            except Exception:
                date_str = registry_key

        # 에이전트별 effective_tokens
        orch_eff = _calc_effective(agents.get("orchestrator", {})) if "orchestrator" in agents else 0
        plan_eff = _calc_effective(agents.get("planner", {})) if "planner" in agents else 0
        work_eff = (
            sum(_calc_effective(w) for w in workers.values() if isinstance(w, dict))
            if isinstance(workers, dict)
            else 0
        )
        exp_eff = _calc_effective(agents.get("explorer", {})) if "explorer" in agents else 0
        val_eff = _calc_effective(agents.get("validator", {})) if "validator" in agents else 0
        report_eff = _calc_effective(agents.get("reporter", {})) if "reporter" in agents else 0
        total_eff = orch_eff + plan_eff + work_eff + exp_eff + val_eff + report_eff
        eff_weighted = totals.get("effective_tokens", total_eff)

        # usage.md 행 생성 (11칼럼 스키마: 날짜|작업ID|제목|명령|ORC|PLN|WRK|EXP|VAL|RPT|합계)
        row = (
            f"| {date_str} "
            f"| {registry_key} "
            f"| {title} "
            f"| {reg_command} "
            f"| {_to_k(orch_eff)} "
            f"| {_to_k(plan_eff)} "
            f"| {_to_k(work_eff)} "
            f"| {_to_k(exp_eff)} "
            f"| {_to_k(val_eff)} "
            f"| {_to_k(report_eff)} "
            f"| {_to_k(total_eff)} |"
        )

        # .dashboard/.usage.md 갱신
        md_err = _update_usage_md(row, eff_weighted)
        if md_err is not None:
            return md_err

        return f"usage-finalize -> totals: eff={_to_k_precise(eff_weighted)}, usage.md updated"
    except Exception as e:
        print(f"[WARN] usage-finalize failed: {e}", file=sys.stderr)
        return "usage-finalize -> failed"


def usage_regenerate() -> str:
    """.workflow/ 및 .workflow/.history/ 하위의 모든 usage.json을 순회하여 .dashboard/.usage.md를 재생성한다.

    v2 스키마 행을 전체 재생성한다.
    registryKey를 날짜 내림차순으로 정렬하여 최신 항목이 상단에 오도록 배치한다.

    Returns:
        처리 결과 문자열. 예: 'usage-regenerate -> rows regenerated: 10',
        'usage-regenerate -> failed'.
    """
    try:
        # 레거시 행 데이터 수집
        rows_data: list[tuple[str, str, str, str, float, float, float, float, float, float, float]] = []

        workflow_base = os.path.join(PROJECT_ROOT, ".workflow")
        workflow_history = os.path.join(workflow_base, ".history")

        dirs_to_scan: list[str] = []
        if os.path.isdir(workflow_base):
            for entry in os.listdir(workflow_base):
                entry_path = os.path.join(workflow_base, entry)
                if os.path.isdir(entry_path) and entry != ".history":
                    dirs_to_scan.append(entry_path)

        if os.path.isdir(workflow_history):
            for entry in os.listdir(workflow_history):
                entry_path = os.path.join(workflow_history, entry)
                if os.path.isdir(entry_path):
                    dirs_to_scan.append(entry_path)

        # 각 워크플로우 디렉터리에서 usage.json과 .context.json 읽기
        for workflow_dir in dirs_to_scan:
            usage_file = os.path.join(workflow_dir, "usage.json")
            context_file = os.path.join(workflow_dir, ".context.json")

            if not os.path.isfile(usage_file):
                continue

            try:
                usage_data = load_json_file(usage_file)
                context_data = load_json_file(context_file) if os.path.isfile(context_file) else {}

                if not isinstance(usage_data, dict):
                    continue

                # v2 스키마 확인
                if usage_data.get("$schema") != "usage-v2":
                    continue

                # registryKey 추출
                try:
                    registry_key = extract_registry_key(workflow_dir)
                except Exception:
                    continue

                # .context.json에서 메타데이터 추출
                title = context_data.get("title", "")[:30] if isinstance(context_data, dict) else ""
                command = context_data.get("command", "") if isinstance(context_data, dict) else ""

                # 날짜 추출
                date_str = ""
                if len(registry_key) >= 15:
                    try:
                        date_str = f"{registry_key[4:6]}-{registry_key[6:8]} {registry_key[9:11]}:{registry_key[11:13]}"
                    except Exception:
                        date_str = registry_key

                # 에이전트별 effective_tokens 계산
                agents = usage_data.get("agents", {})
                orch_eff = _calc_effective(agents.get("orchestrator", {})) if "orchestrator" in agents else 0
                plan_eff = _calc_effective(agents.get("planner", {})) if "planner" in agents else 0
                workers = agents.get("workers", {})
                work_eff = (
                    sum(_calc_effective(w) for w in workers.values() if isinstance(w, dict))
                    if isinstance(workers, dict)
                    else 0
                )
                exp_eff = _calc_effective(agents.get("explorer", {})) if "explorer" in agents else 0
                val_eff = _calc_effective(agents.get("validator", {})) if "validator" in agents else 0
                report_eff = _calc_effective(agents.get("reporter", {})) if "reporter" in agents else 0
                total_eff = orch_eff + plan_eff + work_eff + exp_eff + val_eff + report_eff

                rows_data.append((
                    registry_key, date_str, title, command,
                    orch_eff, plan_eff, work_eff, exp_eff, val_eff, report_eff, total_eff,
                ))

            except Exception:
                # 비차단 원칙: 개별 usage.json 파싱 실패해도 계속 진행
                continue

        # registryKey 날짜 내림차순 정렬 (최신이 상단)
        rows_data.sort(key=lambda x: x[0], reverse=True)

        # .dashboard/.usage.md 읽기
        usage_md = os.path.join(PROJECT_ROOT, ".dashboard", ".usage.md")
        content = ""
        if os.path.isfile(usage_md):
            with open(usage_md, "r", encoding="utf-8") as f:
                content = f.read()

        # 마커와 헤더/분리선 정의
        marker = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"
        header_line = "| 날짜 | 작업ID | 제목 | 명령 | ORC | PLN | WRK | EXP | VAL | RPT | 합계 |"
        separator_line = "|------|--------|------|------|-----|-----|-----|-----|-----|-----|------|"

        # <details> 아카이브 섹션 추출 및 보존
        archive_section = ""
        if "<details>" in content:
            details_start = content.find("<details>")
            archive_section = content[details_start:]

        # 새로운 v2 테이블 행 생성
        new_rows: list[str] = []
        for (
            reg_key, date_str, title, command,
            orch_eff, plan_eff, work_eff, exp_eff, val_eff, report_eff, total_eff,
        ) in rows_data:
            row = (
                f"| {date_str} "
                f"| {reg_key} "
                f"| {title} "
                f"| {command} "
                f"| {_to_k(orch_eff)} "
                f"| {_to_k(plan_eff)} "
                f"| {_to_k(work_eff)} "
                f"| {_to_k(exp_eff)} "
                f"| {_to_k(val_eff)} "
                f"| {_to_k(report_eff)} "
                f"| {_to_k(total_eff)} |"
            )
            new_rows.append(row)

        # 새로운 콘텐츠 구성
        new_content = f"# 워크플로우 사용량 추적\n\n{marker}\n\n{header_line}\n{separator_line}\n"
        for row in new_rows:
            new_content += row + "\n"

        # 아카이브 섹션 추가 (있으면)
        if archive_section:
            new_content += "\n" + archive_section

        # .usage.md 원자적 갱신
        os.makedirs(os.path.dirname(usage_md), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(usage_md), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            shutil.move(tmp, usage_md)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

        return f"usage-regenerate -> rows regenerated: {len(new_rows)}"

    except Exception as e:
        print(f"[WARN] usage-regenerate failed: {e}", file=sys.stderr)
        return "usage-regenerate -> failed"

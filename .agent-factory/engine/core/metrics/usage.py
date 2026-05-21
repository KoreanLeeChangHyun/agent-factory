"""Usage tracking module.

Responsible for recording, settlement, and .dashboard/.usage.md management of token usage for each workflow agent.

Main functions:
    usage_pending: Register agent-task mapping with _pending_workers
    usage_record: Record token data per agent
    usage_finalize: Calculate totals and add .usage.md line
    usage_regenerate: Regenerate entire .usage.md
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any

# import the utils package
_engine_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import (
    acquire_lock,
    atomic_write_json,
    extract_registry_key,
    load_json_file,
    release_lock,
    resolve_project_root,
)
from constants import BUDGET_CEILING, BUDGET_THRESHOLDS, USAGE_HEADER_LINE, USAGE_SEPARATOR_LINE

PROJECT_ROOT: str = resolve_project_root()
_KST = timezone(timedelta(hours=9))


def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """Append a workflow log entry without coupling core metrics to flow runtime."""
    try:
        ts = datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


def _calc_effective(d: dict[str, Any]) -> float:
    """Calculate effective_tokens from token data dict.

    Args:
        d: token data dictionary (input_tokens, output_tokens,
           (includes cache_creation_tokens, cache_read_tokens keys)

    Returns:
        Weighted sum of effective_tokens values.
    """
    return (
        d.get("input_tokens", 0)
        + d.get("output_tokens", 0) * 5
        + d.get("cache_creation_tokens", 0) * 1.25
        + d.get("cache_read_tokens", 0) * 0.1
    )


def _sum_tokens(agents_list: list[dict[str, Any]]) -> dict[str, int]:
    """Returns the sum of the agent token data list.

    Args:
        agents_list: Token data dictionary list

    Returns:
        input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens
        Summation dictionary.
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
    """Convert a number to a k-unit string. If it is 0, it is '-'.

    Args:
        n: Number to convert

    Returns:
        A string in k units (e.g. '10k', '-').
    """
    return "-" if n == 0 else f"{int(n) // 1000}k"


def _to_k_precise(n: float | int) -> str:
    """Converts a number to a k unit string with 1 decimal place. If it is 0, it is '-'.

    Args:
        n: Number to convert

    Returns:
        A k unit string with 1 decimal place (e.g. '10.5k', '-').
    """
    return "-" if n == 0 else f"{n / 1000:.1f}k"


def _get_budget_label(ratio: float) -> str:
    """Returns the budget threshold label corresponding to the ratio(%) value.

    Compares each threshold of BUDGET_THRESHOLDS in descending order and returns the corresponding section label.
    “CRITICAL” if ratio >= 100, “HIGH” if >= 90, “WARN” if >= 80, “INFO” if >= 75.
    If it falls short, “-” is returned.

    Args:
        ratio: Budget utilization (%) value

    Returns:
        Corresponding interval label string (e.g. "CRITICAL", "HIGH", "WARN", "INFO", "-")
    """
    for threshold in sorted(BUDGET_THRESHOLDS.keys(), reverse=True):
        if ratio >= threshold:
            return BUDGET_THRESHOLDS[threshold]
    return "-"


def _check_budget_threshold(abs_work_dir: str, eff_weighted: float) -> str:
    """Check budget thresholds, return labels, and log if necessary.

    If BUDGET_CEILING == 0, “-” is immediately returned to the inactive state.
    When the threshold is reached, it is recorded at WARN level in workflow.log and output to stderr.

    Args:
        abs_work_dir: Absolute path to work directory (for logging purposes)
        eff_weighted: Weighted sum effective_tokens value

    Returns:
        Budget threshold label string (e.g. "CRITICAL", "HIGH", "WARN", "INFO", "-")
    """
    if BUDGET_CEILING == 0:
        return "-"

    ratio = (eff_weighted / BUDGET_CEILING) * 100
    label = _get_budget_label(ratio)

    if label != "-":
        _append_log(
            abs_work_dir,
            "WARN",
            f"BUDGET_THRESHOLD: {ratio:.1f}% ({label}) eff={eff_weighted:.0f} ceiling={BUDGET_CEILING}",
        )
        print(
            f"[WARN] BUDGET_THRESHOLD: {ratio:.1f}% ({label}) eff={eff_weighted:.0f} ceiling={BUDGET_CEILING}",
            file=sys.stderr,
        )

    return label


def _update_usage_md(row: str, eff_weighted: float) -> str | None:
    """Insert a usage line into the .agent-factory/board/data/.usage.md file.

    Args:
        row: Markdown table row string to insert (12-column schema)
        eff_weighted: Weighted sum of effective_tokens (for generating warning messages)

    Returns:
        None on success, error result string on failure.
    """
    usage_md = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".usage.md")
    marker = "<!-- New entries will be added below this line -->"
    header_line = USAGE_HEADER_LINE
    separator_line = USAGE_SEPARATOR_LINE

    content = ""
    if os.path.exists(usage_md):
        with open(usage_md, "r", encoding="utf-8") as f:
            content = f.read()

    if marker not in content:
        content = f"# Track workflow usage \n \n {marker} \n \n {header_line} \n {separator_line} \n"

    # Verification of number of row columns: Do not insert unless there are 12 columns
    if row.count("|") - 1 != 12:
        print(
            f"[WARN] usage-finalize: row column count mismatch (expected 12, got {row.count('|') - 1}). row insertion skipped.",
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

    return None  # success


def usage_pending(abs_work_dir: str, agent_id: str, task_id: str) -> str:
    """Register agent_id->taskId mapping in _pending_workers of usage.json.

    Args:
        abs_work_dir: Absolute path to work directory
        agent_id: Agent ID (e.g. 'W01')
        task_id: Task ID to map (e.g. 'W01')

    Returns:
        Processing result string. Example: 'usage-pending -> W01=W01',
        'usage-pending -> skipped (missing args)', 'usage-pending -> lock failed'.
    """
    if not agent_id or not task_id:
        print("[WARN] usage-pending: agent_id, task_id arguments are required.", file=sys.stderr)
        return "usage-pending -> skipped (missing args)"

    usage_file = os.path.join(abs_work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not acquire_lock(lock_dir, max_wait=5):
        print("[WARN] usage-pending: Lock acquisition failed.", file=sys.stderr)
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


def _append_usage_snapshot(
    abs_work_dir: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation: int,
    cache_read: int,
    effective: float,
) -> None:
    """Records the usage.snapshot event to metrics.jsonl.

    All exceptions are quietly absorbed and have no effect on usage_record calls.
    Silently skips when work_dir is invalid or is called outside the workflow.

    Args:
        abs_work_dir: Absolute path to the work directory.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cache_creation: Number of cache creation tokens.
        cache_read: Number of cache read tokens.
        effective: weighted effective_tokens.
    """
    try:
        if not abs_work_dir or not os.path.isdir(abs_work_dir):
            return

        # step: extract current step from status.json or .context.json
        step = "UNKNOWN"
        try:
            status_path = os.path.join(abs_work_dir, "status.json")
            ctx_path = os.path.join(abs_work_dir, ".context.json")
            if os.path.isfile(status_path):
                import json as _json
                with open(status_path, encoding="utf-8") as f:
                    st = _json.load(f)
                if isinstance(st, dict):
                    step = st.get("workflow_phase") or st.get("step") or st.get("status") or st.get("phase") or "UNKNOWN"
            elif os.path.isfile(ctx_path):
                import json as _json
                with open(ctx_path, encoding="utf-8") as f:
                    ctx = _json.load(f)
                if isinstance(ctx, dict):
                    step = ctx.get("workflow_phase") or ctx.get("step") or ctx.get("status") or "UNKNOWN"
        except Exception:  # noqa: BLE001
            pass

        from . import append_event
        append_event(
            abs_work_dir,
            "usage.snapshot",
            {
                "step": str(step),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_tokens": cache_creation,
                "cache_read_tokens": cache_read,
                "effective_tokens": effective,
            },
        )
    except Exception:  # noqa: BLE001
        pass


def usage_record(
    abs_work_dir: str,
    agent_name: str,
    input_tokens: int | str,
    output_tokens: int | str,
    cache_creation: int | str = 0,
    cache_read: int | str = 0,
    task_id: str = "",
) -> str:
    """Token data for each agent is recorded in the agents object of usage.json.

    Args:
        abs_work_dir: Absolute path to work directory
        agent_name: Agent name (e.g. 'orchestrator', 'worker')
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_creation: Number of cache creation tokens (default 0)
        cache_read: Number of cache read tokens (default 0)
        task_id: Task ID of the worker agent (only used when agent_name='worker')

    Returns:
        Processing result string. Example: 'usage -> orchestrator: in=1000 out=500 cc=0 cr=0',
        'usage -> workers.W01: in=2000 out=1000 cc=100 cr=50',
        'usage -> skipped (missing args)', 'usage -> lock failed'.
    """
    if not agent_name or input_tokens is None or output_tokens is None:
        print("[WARN] usage: agent_name, input_tokens, output_tokens arguments are required.", file=sys.stderr)
        return "usage -> skipped (missing args)"

    usage_file = os.path.join(abs_work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not acquire_lock(lock_dir, max_wait=5):
        print("[WARN] usage: Failed to acquire lock", file=sys.stderr)
        return "usage -> lock failed"

    try:
        data = load_json_file(usage_file)
        if not isinstance(data, dict):
            data = {}

        if "agents" not in data or not isinstance(data.get("agents"), dict):
            data["agents"] = {}

        in_t = int(input_tokens)
        out_t = int(output_tokens)
        cc_t = int(cache_creation)
        cr_t = int(cache_read)

        token_data: dict[str, Any] = {
            "input_tokens": in_t,
            "output_tokens": out_t,
            "cache_creation_tokens": cc_t,
            "cache_read_tokens": cr_t,
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

        # --- metrics: usage.snapshot event log ---
        eff = _calc_effective(token_data)
        _append_usage_snapshot(abs_work_dir, in_t, out_t, cc_t, cr_t, eff)

        return f"usage -> {label}: in={input_tokens} out={output_tokens} cc={cache_creation} cr={cache_read}"
    finally:
        release_lock(lock_dir)


def usage_finalize(abs_work_dir: str) -> str:
    """Calculate totals and calculate effective_tokens and add a row to .dashboard/.usage.md.

    Args:
        abs_work_dir: Absolute path to work directory (directory where usage.json is located)

    Returns:
        Processing result string. Example: 'usage-finalize -> totals: eff=12.5k, usage.md updated',
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

        # $schema guard: migrate if not usage-v2
        if data.get("$schema") != "usage-v2":
            data.pop("init", None)
            data.pop("done", None)
            data["$schema"] = "usage-v2"

        agents = data.get("agents", {})

        # Collect all agent token data
        all_agents: list[dict[str, Any]] = []
        for key in ["orchestrator", "planner", "explorer", "validator", "reporter"]:
            if key in agents and isinstance(agents[key], dict):
                all_agents.append(agents[key])

        workers = agents.get("workers", {})
        if isinstance(workers, dict):
            for w in workers.values():
                if isinstance(w, dict):
                    all_agents.append(w)

        # Calculate totals
        totals = _sum_tokens(all_agents)
        totals["effective_tokens"] = _calc_effective(totals)
        data["totals"] = totals

        atomic_write_json(usage_file, data)

        # Extract registryKey
        registry_key = extract_registry_key(abs_work_dir)

        # Look up metadata in .context.json
        reg_title = ""
        reg_command = ""
        ctx_file = os.path.join(abs_work_dir, ".context.json")
        ctx_data = load_json_file(ctx_file)
        if isinstance(ctx_data, dict):
            reg_title = ctx_data.get("title", "")
            reg_command = ctx_data.get("command", "")

        title = reg_title[:30] if reg_title else ""

        # date extraction
        date_str = ""
        if len(registry_key) >= 15:
            try:
                date_str = f"{registry_key[4:6]}-{registry_key[6:8]} {registry_key[9:11]}:{registry_key[11:13]}"
            except Exception:
                date_str = registry_key

        # effective_tokens per agent
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

        # Check your budget threshold
        budget_label = _check_budget_threshold(abs_work_dir, eff_weighted)

        # Create usage.md row (12-column schema: Date|JobID|Title|Command|ORC|PLN|WRK|EXP|VAL|RPT|Total|Budget)
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
            f"| {_to_k(total_eff)} "
            f"| {budget_label} |"
        )

        # Update .dashboard/.usage.md
        md_err = _update_usage_md(row, eff_weighted)
        if md_err is not None:
            return md_err

        return f"usage-finalize -> totals: eff={_to_k_precise(eff_weighted)}, usage.md updated"
    except Exception as e:
        print(f"[WARN] usage-finalize failed: {e}", file=sys.stderr)
        return "usage-finalize -> failed"


def usage_regenerate() -> str:
    """Iterate through all usage.json under .agent-factory/runs/ and .agent-factory/runs/.history/ and regenerate .agent-factory/board/data/.usage.md.

    Regenerate the entire usage schema row.
    Sort registryKeys in descending date order so that the most recent entries are at the top.

    Returns:
        Processing result string. Example: 'usage-regenerate -> rows regenerated: 10',
        'usage-regenerate -> failed'.
    """
    try:
        # Legacy row data collection
        rows_data: list[tuple[str, str, str, str, float, float, float, float, float, float, float]] = []

        workflow_base = os.path.join(PROJECT_ROOT, ".agent-factory", "runs")
        workflow_history = os.path.join(workflow_base, ".history")

        dirs_to_scan: list[str] = []

        def _collect_dirs(base: str, skip_history: bool = False) -> None:
            """T-448 fold structure: usage.json location directory collection."""
            for entry in os.listdir(base):
                if skip_history and entry == ".history":
                    continue
                entry_path = os.path.join(base, entry)
                if not os.path.isdir(entry_path):
                    continue
                if os.path.isfile(os.path.join(entry_path, "usage.json")):
                    dirs_to_scan.append(entry_path)

        if os.path.isdir(workflow_base):
            _collect_dirs(workflow_base, skip_history=True)

        if os.path.isdir(workflow_history):
            _collect_dirs(workflow_history)

        # Read usage.json and .context.json from each workflow directory
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

                # Check usage schema
                if usage_data.get("$schema") != "usage-v2":
                    continue

                # Extract registryKey
                try:
                    registry_key = extract_registry_key(workflow_dir)
                except Exception:
                    continue

                # Extract metadata from .context.json
                title = context_data.get("title", "")[:30] if isinstance(context_data, dict) else ""
                command = context_data.get("command", "") if isinstance(context_data, dict) else ""

                # date extraction
                date_str = ""
                if len(registry_key) >= 15:
                    try:
                        date_str = f"{registry_key[4:6]}-{registry_key[6:8]} {registry_key[9:11]}:{registry_key[11:13]}"
                    except Exception:
                        date_str = registry_key

                # Calculating effective_tokens per agent
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
                # Non-blocking principle: Continue even if individual usage.json parsing fails
                continue

        # Sort by registryKey date descending (newest at top)
        rows_data.sort(key=lambda x: x[0], reverse=True)

        # Read .dashboard/.usage.md
        usage_md = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".usage.md")
        content = ""
        if os.path.isfile(usage_md):
            with open(usage_md, "r", encoding="utf-8") as f:
                content = f.read()

        # Define markers and headers/separators
        marker = "<!-- New entries will be added below this line -->"
        header_line = USAGE_HEADER_LINE
        separator_line = USAGE_SEPARATOR_LINE

        # <details> Extract and preserve archive sections
        archive_section = ""
        if "<details>" in content:
            details_start = content.find("<details>")
            archive_section = content[details_start:]

        # Create a new usage table row
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
                f"| {_to_k(total_eff)} "
                f"| - |"
            )
            new_rows.append(row)

        # Organize new content
        new_content = f"# Track workflow usage \n \n {marker} \n \n {header_line} \n {separator_line} \n"
        for row in new_rows:
            new_content += row + "\n"

        # Add archive section (if present)
        if archive_section:
            new_content += "\n" + archive_section

        # .usage.md atomic update
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

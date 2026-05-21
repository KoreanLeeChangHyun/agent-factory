#!/usr/bin/env -S python3 -u
"""metrics_cli.py - flow-metrics CLI entry point.

``<workDir>/metrics.jsonl`` jsonl files recorded by W01 (`metrics.py`)
It provides three types of subcommands that aggregate data and output it in a table format that is easy for humans to read.

Subcommand:
    summarize <registryKey>
        ``.agent-factory/runs/<registryKey>/*/*/metrics.jsonl`` glob
        Gather all jsonl lines in that workflow once step/token/tool/regression
        Print a summary table.
    compare <key1> <key2>
        Output the summarized results of the two registryKeys in a diff (key2 - key1) table.
    regression [--last N]
        ``.agent-factory/runs/`` of the most recent N (default 10) workflows.
        Outputs regression.pattern frequency and top-3 signal_summary examples.

Design notes:
    - Use only standard libraries (argparse, json, glob, pathlib, sys, ...).
    - W01 ``schema_for`` / ``known_event_types`` of ``metrics.py``
      Reuse — Do not duplicate schema/event type catalog definitions.
    - Create a module function interface so that the backend API (W06) can import and use it.
      Exposed separately — ``aggregate_run / aggregate_recent /
      regression_counts / diff_runs``. The CLI entry point is a thin
      wrapper.
    - The output is a Markdown pipe table (compatible with terminal + Markdown render).

CLI usage example::

    $ flow-metrics summarize 20260505-183053
    $ flow-metrics compare 20260504-115242 20260505-183053
    $ flow-metrics regression --last 10
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

_AGENT_FACTORY_DIR = str(Path(__file__).resolve().parents[3])
if _AGENT_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _AGENT_FACTORY_DIR)

# W01 module reuse (event catalog/schema single source of truth)
from engine.core.metrics import known_event_types  # noqa: E402,F401
from engine.core.metrics import schema_for  # noqa: E402,F401

# ---------------------------------------------------------------------------
# path constant
# ---------------------------------------------------------------------------

# Location of this module: <ROOT>/.agent-factory/engine/apps/cli/metrics_cli.py
# → ROOT = parents[4]
_ROOT: Path = Path(__file__).resolve().parents[4]
_RUNS_DIR: Path = _ROOT / ".agent-factory" / "runs"

# regression.pattern.kind 5 types (others grouped under “other”)
_REGRESSION_KINDS: tuple[str, ...] = (
    "worker_false_success",
    "hook_deny",
    "empty_bash_card",
    "stage_header_leak",
    "other",
)

# Order of display of steps (semantic order instead of alphabetical order)
_STEP_ORDER: tuple[str, ...] = ("INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE")


# ---------------------------------------------------------------------------
# Low-level helper: jsonl loading
# ---------------------------------------------------------------------------


def _iter_metrics_files(registry_key: str) -> list[Path]:
    """Returns all metrics.jsonl file paths corresponding to registryKey.

    Args:
        registry_key: ``YYYYMMDD-HHMMSS`` format.

    Returns:
        List of existing file paths (sorted). One workflow usually
        There is only one number, but it can be multiple when using multiple commands such as chain.
    """
    pattern = str(_RUNS_DIR / registry_key / "metrics.jsonl")
    paths = sorted(Path(p) for p in glob.glob(pattern))
    return paths


def _load_events(paths: Iterable[Path]) -> list[dict[str, Any]]:
    """Reads all jsonl lines in the file path list and returns them as a dict list.

    Args:
        paths: metrics.jsonl file paths.

    Returns:
        Parsed event dict list. JSON parse failure lines are skipped (integrity
        Prioritize availability — so that the whole thing doesn't fail because of one broken line).
    """
    events: list[dict[str, Any]] = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as fp:
                for ln in fp:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        events.append(json.loads(ln))
                    except json.JSONDecodeError:
                        # Proceed by ignoring broken lines (aggregation takes precedence)
                        continue
        except OSError:
            continue
    return events


def _list_recent_keys(last: int) -> list[str]:
    """Returns the most recent N registryKeys in descending order of mtime.

    Args:
        last: Number to fetch.

    Returns:
        registryKey List of strings (0th most recent). The runs directory is
        If not, an empty list.
    """
    if not _RUNS_DIR.is_dir():
        return []
    keys: list[tuple[float, str]] = []
    for child in _RUNS_DIR.iterdir():
        if not child.is_dir():
            continue
        # registryKey directory only (e.g. 20260505-183053). Excluding files/hybrids like bg/chain_launcher.log.
        name = child.name
        if len(name) != 15 or name[8] != "-":
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        keys.append((mtime, name))
    keys.sort(reverse=True)
    return [k for _, k in keys[: max(0, int(last))]]


# ---------------------------------------------------------------------------
# Module function API (imported by W06 backend)
# ---------------------------------------------------------------------------


def _classify_regression_kind(kind: Any) -> str:
    """Normalize regression.pattern.kind into 5 categories."""
    if isinstance(kind, str) and kind in _REGRESSION_KINDS:
        return kind
    return "other"


def aggregate_run(registry_key: str) -> dict[str, Any]:
    """Aggregates all metrics.jsonl of a single registryKey and returns it as a dict.

    Args:
        registry_key: registryKey to aggregate.

    Returns:
        A dict with the following keys::

            {
              "registry_key": "...",
              "files": [str, ...],          # Aggregated metrics.jsonl path
              "total_events": int,
              "step_durations": {step: {"avg_ms": float, "count": int, "fail": int}},
              "tokens": {"input": int, "output": int,
                         "cache_creation": int, "cache_read": int,
                         "effective": float},
              "tool_calls_allowed": {tool_name: int},
              "tool_deny": int,
              "subagent_spawn": {agent_kind: int},
              "regression": {kind: int},
              "step_end_fail": int,
            }

        If there are no files, an empty dict with ``files=[]`` and ``total_events=0`` is returned.
    """
    paths = _iter_metrics_files(registry_key)
    events = _load_events(paths)

    step_durations_acc: dict[str, list[int]] = defaultdict(list)
    step_fail: Counter[str] = Counter()
    tokens = {
        "input": 0,
        "output": 0,
        "cache_creation": 0,
        "cache_read": 0,
        "effective": 0.0,
    }
    tool_calls_allowed: Counter[str] = Counter()
    tool_deny_count = 0
    subagent_spawn: Counter[str] = Counter()
    regression_counts_local: Counter[str] = Counter()
    step_end_fail = 0

    for ev in events:
        et = ev.get("event_type")
        payload = ev.get("payload") or {}
        if et == "step.end":
            step = str(payload.get("step", "?"))
            dur = payload.get("duration_ms")
            if isinstance(dur, (int, float)):
                step_durations_acc[step].append(int(dur))
            outcome = str(payload.get("outcome", ""))
            if outcome == "fail":
                step_end_fail += 1
                step_fail[step] += 1
        elif et == "usage.snapshot":
            tokens["input"] += int(payload.get("input_tokens", 0) or 0)
            tokens["output"] += int(payload.get("output_tokens", 0) or 0)
            tokens["cache_creation"] += int(
                payload.get("cache_creation_tokens", 0) or 0
            )
            tokens["cache_read"] += int(payload.get("cache_read_tokens", 0) or 0)
            eff = payload.get("effective_tokens", 0) or 0
            try:
                tokens["effective"] += float(eff)
            except (TypeError, ValueError):
                pass
        elif et == "tool.call":
            if bool(payload.get("allowed", False)):
                tool_calls_allowed[str(payload.get("tool_name", "?"))] += 1
        elif et == "tool.deny":
            tool_deny_count += 1
        elif et == "subagent.spawn":
            subagent_spawn[str(payload.get("agent_kind", "?"))] += 1
        elif et == "regression.pattern":
            regression_counts_local[
                _classify_regression_kind(payload.get("kind"))
            ] += 1

    step_durations: dict[str, dict[str, Any]] = {}
    for step, durs in step_durations_acc.items():
        step_durations[step] = {
            "avg_ms": (sum(durs) / len(durs)) if durs else 0.0,
            "count": len(durs),
            "fail": int(step_fail.get(step, 0)),
        }

    return {
        "registry_key": registry_key,
        "files": [str(p) for p in paths],
        "total_events": len(events),
        "step_durations": step_durations,
        "tokens": tokens,
        "tool_calls_allowed": dict(tool_calls_allowed),
        "tool_deny": tool_deny_count,
        "subagent_spawn": dict(subagent_spawn),
        "regression": dict(regression_counts_local),
        "step_end_fail": step_end_fail,
    }


def aggregate_recent(last: int = 20) -> list[dict[str, Any]]:
    """Returns a summary dict list of the most recent N workflows.

    Args:
        last: Number to fetch (default 20).

    Returns:
        ``aggregate_run()`` A list of result dicts. The most recent is number 0.
    """
    return [aggregate_run(k) for k in _list_recent_keys(last)]


def regression_counts(last: int = 10) -> dict[str, Any]:
    """Counts the regression.pattern frequency of the last N workflows.

    Args:
        last: Aggregation range (default 10).

    Returns:
        A dict of the form::

            {
              "scanned_keys": [str, ...],
              "counts": {kind: int},  # 5 types + other
              "examples": {kind: [signal_summary, ...]},  # Most frequent top-3
            }
    """
    keys = _list_recent_keys(last)
    counts: Counter[str] = Counter({k: 0 for k in _REGRESSION_KINDS})
    examples: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        events = _load_events(_iter_metrics_files(key))
        for ev in events:
            if ev.get("event_type") != "regression.pattern":
                continue
            payload = ev.get("payload") or {}
            kind = _classify_regression_kind(payload.get("kind"))
            counts[kind] += 1
            sig = payload.get("signal_summary")
            if isinstance(sig, str) and sig:
                # Save memory — keep only up to 5 per kind
                if len(examples[kind]) < 5:
                    examples[kind].append(sig)

    return {
        "scanned_keys": keys,
        "counts": dict(counts),
        "examples": {k: list(v) for k, v in examples.items()},
    }


def diff_runs(key1: str, key2: str) -> dict[str, Any]:
    """Returns a diff dict comparing the summarized results of two registryKeys.

    The diff meaning is unified as ``key2 - key1`` (positive number = key2 is large, negative number = small).

    Args:
        key1: Comparison criteria (old).
        key2: Comparison target (hereafter).

    Returns:
        A dict of the form::

            {
              "key1": "...", "key2": "...",
              "step_duration_diff": {step: avg_ms_diff},
              "tokens_diff": {input/output/cache_creation/cache_read/effective},
              "tool_calls_diff": {tool_name: count_diff},
              "tool_deny_diff": int,
              "subagent_spawn_diff": {agent_kind: count_diff},
              "regression_diff": {kind: count_diff},
              "step_end_fail_diff": int,
              "summaries": {key1: aggregate_run(...), key2: aggregate_run(...)},
            }
    """
    a = aggregate_run(key1)
    b = aggregate_run(key2)

    # step duration diff (based on avg_ms)
    steps = set(a["step_durations"].keys()) | set(b["step_durations"].keys())
    step_diff: dict[str, float] = {}
    for s in steps:
        av = a["step_durations"].get(s, {}).get("avg_ms", 0.0)
        bv = b["step_durations"].get(s, {}).get("avg_ms", 0.0)
        step_diff[s] = float(bv) - float(av)

    tokens_diff: dict[str, float] = {}
    for k, av in a["tokens"].items():
        tokens_diff[k] = float(b["tokens"].get(k, 0)) - float(av)

    # tool call union diff
    tools = set(a["tool_calls_allowed"].keys()) | set(b["tool_calls_allowed"].keys())
    tool_diff = {
        t: int(b["tool_calls_allowed"].get(t, 0))
        - int(a["tool_calls_allowed"].get(t, 0))
        for t in tools
    }

    sub_kinds = set(a["subagent_spawn"].keys()) | set(b["subagent_spawn"].keys())
    sub_diff = {
        k: int(b["subagent_spawn"].get(k, 0)) - int(a["subagent_spawn"].get(k, 0))
        for k in sub_kinds
    }

    reg_kinds = set(a["regression"].keys()) | set(b["regression"].keys())
    reg_diff = {
        k: int(b["regression"].get(k, 0)) - int(a["regression"].get(k, 0))
        for k in reg_kinds
    }

    return {
        "key1": key1,
        "key2": key2,
        "step_duration_diff": step_diff,
        "tokens_diff": tokens_diff,
        "tool_calls_diff": tool_diff,
        "tool_deny_diff": int(b["tool_deny"]) - int(a["tool_deny"]),
        "subagent_spawn_diff": sub_diff,
        "regression_diff": reg_diff,
        "step_end_fail_diff": int(b["step_end_fail"]) - int(a["step_end_fail"]),
        "summaries": {key1: a, key2: b},
    }


# ---------------------------------------------------------------------------
# Output formatter (Markdown pipe table)
# ---------------------------------------------------------------------------


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Creates a Markdown pipe table string.

    Args:
        headers: Header cell list.
        rows: List of cell strings for each row. All cells assume str (caller responsibility).

    Returns:
        ``| h1 | h2 | \n |---|---| \n | r1 | r2 | \n ...`` format string.
    """
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([head, sep, body]) if rows else "\n".join([head, sep])


def _sorted_steps(step_durations: dict[str, dict[str, Any]]) -> list[str]:
    """Sort the step keys in semantic flow order → alphabet order."""
    known = [s for s in _STEP_ORDER if s in step_durations]
    rest = sorted(s for s in step_durations.keys() if s not in _STEP_ORDER)
    return known + rest


def format_summary(summary: dict[str, Any]) -> str:
    """``aggregate_run()`` Converts the results into a human-readable Markdown string."""
    lines: list[str] = []
    rkey = summary.get("registry_key", "?")
    lines.append(f"# Workflow Summary — `{rkey}`")
    lines.append("")
    files = summary.get("files", [])
    lines.append(f"- aggregate metrics.jsonl: {len(files)}")
    for f in files:
        lines.append(f"  - {f}")
    lines.append(f"- Total number of events: {summary.get('total_events', 0)}")
    lines.append(f"- step.end fail: {summary.get('step_end_fail', 0)}")
    lines.append(f"- tool.deny sum: {summary.get('tool_deny', 0)}")
    lines.append("")

    # Average duration for each step
    lines.append("## Average duration (ms) per step")
    sd = summary.get("step_durations", {})
    if sd:
        rows = []
        for s in _sorted_steps(sd):
            v = sd[s]
            rows.append(
                [
                    s,
                    f"{v.get('avg_ms', 0.0):.1f}",
                    str(v.get("count", 0)),
                    str(v.get("fail", 0)),
                ]
            )
        lines.append(_md_table(["step", "avg_ms", "count", "fail"], rows))
    else:
        lines.append("_(no step.end event)_")
    lines.append("")

    # Token Total
    lines.append("## Token total")
    t = summary.get("tokens", {})
    rows = [
        ["input", str(int(t.get("input", 0)))],
        ["output", str(int(t.get("output", 0)))],
        ["cache_creation", str(int(t.get("cache_creation", 0)))],
        ["cache_read", str(int(t.get("cache_read", 0)))],
        ["effective", f"{float(t.get('effective', 0.0)):.1f}"],
    ]
    lines.append(_md_table(["category", "tokens"], rows))
    lines.append("")

    # Tool call count (allowed=true)
    lines.append("## Tool call count (allowed)")
    tc = summary.get("tool_calls_allowed", {})
    if tc:
        rows = [[k, str(v)] for k, v in sorted(tc.items(), key=lambda x: -x[1])]
        lines.append(_md_table(["tool_name", "count"], rows))
    else:
        lines.append("_(no tool.call allowed event)_")
    lines.append("")

    # subagent.spawn
    lines.append("## subagent.spawn count")
    sp = summary.get("subagent_spawn", {})
    if sp:
        rows = [[k, str(v)] for k, v in sorted(sp.items(), key=lambda x: -x[1])]
        lines.append(_md_table(["agent_kind", "count"], rows))
    else:
        lines.append("_(no subagent.spawn event)_")
    lines.append("")

    # regression.pattern
    lines.append("## regression.pattern count")
    rg = summary.get("regression", {})
    if rg:
        rows = [
            [k, str(v)]
            for k, v in sorted(rg.items(), key=lambda x: -x[1])
        ]
        lines.append(_md_table(["kind", "count"], rows))
    else:
        lines.append("_(no regression.pattern event)_")
    lines.append("")

    return "\n".join(lines)


def format_compare(diff: dict[str, Any]) -> str:
    """``diff_runs()`` Converts the result to a Markdown comparison table string."""
    lines: list[str] = []
    k1, k2 = diff["key1"], diff["key2"]
    lines.append(f"# Workflow Compare — `{k1}` vs `{k2}` (diff = key2 - key1)")
    lines.append("")

    # step duration diff
    lines.append("## step by step avg_ms diff")
    sd = diff.get("step_duration_diff", {})
    if sd:
        rows = []
        for s in _sorted_steps({k: {} for k in sd.keys()}):
            v = sd[s]
            sign = "+" if v >= 0 else ""
            rows.append([s, f"{sign}{v:.1f}"])
        lines.append(_md_table(["step", "diff_ms"], rows))
    else:
        lines.append("_(no step.end event on either side)_")
    lines.append("")

    # tokens diff
    lines.append("## token sum diff")
    rows = []
    for k, v in diff.get("tokens_diff", {}).items():
        sign = "+" if v >= 0 else ""
        # input/output/cache_* means integer, effective means real number
        if k == "effective":
            rows.append([k, f"{sign}{v:.1f}"])
        else:
            rows.append([k, f"{sign}{int(v)}"])
    lines.append(_md_table(["category", "diff"], rows))
    lines.append("")

    # tool calls diff
    lines.append("## tool call count diff (allowed)")
    tc = diff.get("tool_calls_diff", {})
    if tc:
        rows = []
        for k, v in sorted(tc.items(), key=lambda x: -abs(x[1])):
            sign = "+" if v >= 0 else ""
            rows.append([k, f"{sign}{int(v)}"])
        lines.append(_md_table(["tool_name", "diff"], rows))
    else:
        lines.append("_(no tool.call allowed event on either side)_")
    lines.append("")

    # tool.deny diff + subagent + regression
    rows = [
        ["tool.deny", _signed(diff.get("tool_deny_diff", 0))],
        ["step.end fail", _signed(diff.get("step_end_fail_diff", 0))],
    ]
    for k, v in diff.get("subagent_spawn_diff", {}).items():
        rows.append([f"subagent.spawn[{k}]", _signed(v)])
    for k, v in diff.get("regression_diff", {}).items():
        rows.append([f"regression[{k}]", _signed(v)])
    lines.append("## Other count diff")
    lines.append(_md_table(["metric", "diff"], rows))
    lines.append("")

    return "\n".join(lines)


def _signed(v: Any) -> str:
    """Integer string with +/- signs."""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{'+' if n >= 0 else ''}{n}"


def format_regression(report: dict[str, Any]) -> str:
    """Converts the results of ``regression_counts()`` into a Markdown table."""
    lines: list[str] = []
    keys = report.get("scanned_keys", [])
    lines.append(f"# Regression Patterns — Recent {len(keys)} workflows")
    lines.append("")
    if keys:
        lines.append("- Scan target registryKey:")
        for k in keys:
            lines.append(f"  - {k}")
    else:
        lines.append("_(no scannable workflow)_")
    lines.append("")

    counts = report.get("counts", {})
    examples = report.get("examples", {})

    # frequency table
    lines.append("## Frequency by kind")
    rows = [
        [k, str(counts.get(k, 0))]
        for k in sorted(counts.keys(), key=lambda x: -counts.get(x, 0))
    ]
    lines.append(_md_table(["kind", "count"], rows))
    lines.append("")

    # top-3 examples
    top3 = sorted(counts.items(), key=lambda x: -x[1])[:3]
    lines.append("## top-3 signal_summary example")
    if not any(c for _, c in top3):
        lines.append("_(no regression.pattern event)_")
    else:
        for kind, cnt in top3:
            if cnt <= 0:
                continue
            ex_list = examples.get(kind, [])
            ex = ex_list[0] if ex_list else "_(no signal_summary)_"
            lines.append(f"- **{kind}** (count={cnt}): {ex}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _cmd_summarize(args: argparse.Namespace) -> int:
    summary = aggregate_run(args.registry_key)
    if not summary["files"]:
        print(
            f"[flow-metrics] no metrics.jsonl found for registry_key={args.registry_key}",
            file=sys.stderr,
        )
        print(
            f"(Search pattern: {_RUNS_DIR}/{args.registry_key}/metrics.jsonl)",
            file=sys.stderr,
        )
        return 2
    print(format_summary(summary))
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    diff = diff_runs(args.key1, args.key2)
    a = diff["summaries"][args.key1]
    b = diff["summaries"][args.key2]
    missing = []
    if not a["files"]:
        missing.append(args.key1)
    if not b["files"]:
        missing.append(args.key2)
    if missing:
        print(
            f"[flow-metrics] no metrics.jsonl found for: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2
    print(format_compare(diff))
    return 0


def _cmd_regression(args: argparse.Namespace) -> int:
    report = regression_counts(last=args.last)
    print(format_regression(report))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flow-metrics",
        description=(
            "Workflow metrics.jsonl Aggregation CLI — summarize / compare / regression"
            "(Shared catalog with W01 metrics.py)"
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sum = sub.add_parser(
        "summarize",
        help="Output metrics.jsonl summary table for single registryKey",
    )
    p_sum.add_argument(
        "registry_key",
        help="Target registryKey (e.g. 20260505-183053)",
    )
    p_sum.set_defaults(func=_cmd_summarize)

    p_cmp = sub.add_parser(
        "compare", help="Output summarized diff table of two registryKeys"
    )
    p_cmp.add_argument("key1", help="Compare by registryKey (old)")
    p_cmp.add_argument("key2", help="Compare to registryKey (after)")
    p_cmp.set_defaults(func=_cmd_compare)

    p_reg = sub.add_parser(
        "regression",
        help="regression.pattern frequency of N recent workflows",
    )
    p_reg.add_argument(
        "--last",
        type=int,
        default=10,
        help="Number of recent workflows to be counted (default 10)",
    )
    p_reg.set_defaults(func=_cmd_regression)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    try:
        return int(func(args) or 0)
    except KeyboardInterrupt:
        print("[flow-metrics] interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

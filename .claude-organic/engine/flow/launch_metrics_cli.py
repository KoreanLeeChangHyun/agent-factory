#!/usr/bin/env -S python3 -u
"""launch_metrics_cli.py - flow-launch-metrics CLI entry point.

Reads LAUNCH_* events from workflow.log files (parsed by launch_metrics.py)
and renders spawn_duration_ms distribution statistics in Markdown pipe-table
format. Three sub-commands are provided:

Sub-commands:
    summarize <registry_key>
        Print a per-event summary table for a single workflow run.
        Reads <runs_dir>/<registry_key>/workflow.log.

    aggregate [--last N] [--runs-dir PATH]
        Aggregate spawn_duration_ms distribution across the most recent N
        workflow runs. Outputs three sections:
            1. Distribution table (count/min/max/mean/p50/p95/p99)
            2. Per-run table (registry_key / events / avg duration)
            3. Slow-spawn catalog (>= 60 s by default)

    slow [--threshold-ms N] [--last N] [--runs-dir PATH]
        Print only the slow-spawn catalog for spawns >= threshold_ms.

Design notes:
    - Standard library only (argparse, pathlib, sys, os).
    - All LAUNCH_* parsing and statistics logic is delegated to
      launch_metrics.py — no reimplementation here.
    - Module-level functions (aggregate_run_launch, aggregate_recent_launch,
      format_launch_summary, format_launch_aggregate, format_launch_slow) are
      exposed for W06 (handlers/metrics.py) to import directly.
    - Output uses Markdown pipe tables throughout, matching metrics_cli.py style.
    - Graceful handling: zero LAUNCH_* events produces an informational
      message and a zero-row (or zero-count) table rather than an error.

CLI usage examples::

    $ flow-launch-metrics summarize 20260510-175716
    $ flow-launch-metrics aggregate --last 5
    $ flow-launch-metrics aggregate --last 10 --runs-dir /custom/path/runs
    $ flow-launch-metrics slow --threshold-ms 60000 --last 10
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# sys.path correction — same pattern as metrics_cli.py
# "same pattern as other engine scripts — skill_recommender.py etc."
# ---------------------------------------------------------------------------

_engine_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from flow.launch_metrics import (  # noqa: E402
    LaunchEvent,
    aggregate_recent,
    catalog_slow_spawns,
    compute_distribution,
    compute_spawn_durations,
    parse_launch_events,
)

# ---------------------------------------------------------------------------
# Path constants — mirrors metrics_cli.py ROOT-tracking pattern
# Module location: <ROOT>/.claude-organic/engine/flow/launch_metrics_cli.py
# → parents[3] = ROOT
# ---------------------------------------------------------------------------

_ROOT: Path = Path(__file__).resolve().parents[3]
_RUNS_DIR: Path = _ROOT / ".claude-organic" / "runs"

_WORKFLOW_LOG_FILENAME: str = "workflow.log"

# Default slow-spawn threshold (60 seconds in ms)
_DEFAULT_SLOW_THRESHOLD_MS: int = 60_000

# Default number of recent runs to scan
_DEFAULT_LAST: int = 10


# ---------------------------------------------------------------------------
# Markdown pipe table helper — copied verbatim from metrics_cli.py
# (cross-import avoided; each CLI is self-contained)
# ---------------------------------------------------------------------------


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Generate a Markdown pipe table string.

    Args:
        headers: List of header cell strings.
        rows: List of row cell lists. All cells must already be str
              (caller's responsibility).

    Returns:
        ``| h1 | h2 |\\n|---|---|\\n| r1 | r2 |`` formatted string.
        If rows is empty only the header and separator lines are returned.
    """
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([head, sep, body]) if rows else "\n".join([head, sep])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_runs_dir(runs_dir_arg: Optional[str]) -> Path:
    """Resolve the runs directory from a CLI argument or default.

    Args:
        runs_dir_arg: Path string from ``--runs-dir`` argument, or None to
                      use the module-level default.

    Returns:
        Resolved Path object for the runs directory.
    """
    if runs_dir_arg is not None:
        return Path(runs_dir_arg).expanduser().resolve()
    return _RUNS_DIR


def _fmt_optional_int(value: Optional[int]) -> str:
    """Format an optional integer for table display.

    Args:
        value: Integer value or None.

    Returns:
        String representation, or ``"-"`` if value is None.
    """
    return str(value) if value is not None else "-"


def _fmt_optional_float(value: Optional[float]) -> str:
    """Format an optional float for table display (2 decimal places).

    Args:
        value: Float value or None.

    Returns:
        String representation with 2 decimal places, or ``"-"`` if None.
    """
    return f"{value:.2f}" if value is not None else "-"


def _log_path_for(runs_dir: Path, registry_key: str) -> Path:
    """Compute the workflow.log path for a given run.

    Args:
        runs_dir: Root runs directory.
        registry_key: Run identifier (e.g. ``"20260510-175716"``).

    Returns:
        Path to the workflow.log file.
    """
    return runs_dir / registry_key / _WORKFLOW_LOG_FILENAME


def _list_recent_registry_keys(runs_dir: Path, last: int) -> list[str]:
    """Return up to ``last`` registry keys sorted by mtime descending.

    Only directories with names that look like registryKey format
    (15 chars, hyphen at position 8) are included.

    Args:
        runs_dir: Runs directory to scan.
        last:     Maximum number of keys to return.

    Returns:
        List of registry key strings, most recent first.
    """
    if not runs_dir.is_dir():
        return []

    entries: list[tuple[float, str]] = []
    for child in runs_dir.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        # Filter to registryKey-shaped names: "20260510-175716" (15 chars, '-' at [8])
        if len(name) != 15 or name[8] != "-":
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        entries.append((mtime, name))

    entries.sort(reverse=True)
    return [name for _, name in entries[: max(0, int(last))]]


# ---------------------------------------------------------------------------
# Module-level API (importable by W06 handlers/metrics.py)
# ---------------------------------------------------------------------------


def aggregate_run_launch(
    registry_key: str,
    runs_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Aggregate LAUNCH_* statistics for a single workflow run.

    Args:
        registry_key: Run identifier (e.g. ``"20260510-175716"``).
        runs_dir:     Runs directory. Defaults to the module-level ``_RUNS_DIR``.

    Returns:
        Dictionary with keys:
            registry_key  (str):        The requested run identifier.
            log_path      (str):        Resolved workflow.log path (may not exist).
            log_exists    (bool):       Whether the log file was found.
            events        (int):        Number of LAUNCH_* events found.
            spawn_durations (list[int]): Matched spawn durations in ms.
            distribution  (dict):       compute_distribution output.
            slow_spawns   (list[dict]): catalog_slow_spawns output.
            event_rows    (list[dict]): Per-event detail dicts for tabular display.
    """
    rd = runs_dir if runs_dir is not None else _RUNS_DIR
    log_path = _log_path_for(rd, registry_key)
    events: list[LaunchEvent] = parse_launch_events(log_path)
    durations: list[int] = compute_spawn_durations(events)
    distribution = compute_distribution(durations)
    slow = catalog_slow_spawns(events)

    event_rows: list[dict[str, Any]] = [
        {
            "event_type": ev.event_type,
            "timestamp": ev.timestamp,
            "registry_key": ev.registry_key or "-",
            "ticket": ev.ticket or "-",
            "pid": ev.pid or "-",
            "error": ev.error or "-",
        }
        for ev in events
    ]

    return {
        "registry_key": registry_key,
        "log_path": str(log_path),
        "log_exists": log_path.is_file(),
        "events": len(events),
        "spawn_durations": durations,
        "distribution": distribution,
        "slow_spawns": slow,
        "event_rows": event_rows,
    }


def aggregate_recent_launch(
    last: int = _DEFAULT_LAST,
    runs_dir: Optional[Path] = None,
    threshold_ms: int = _DEFAULT_SLOW_THRESHOLD_MS,
) -> dict[str, Any]:
    """Aggregate LAUNCH_* statistics across the most recent workflow runs.

    This is a thin wrapper around ``launch_metrics.aggregate_recent`` that
    adds the per_run average duration field needed for CLI tabular display.

    Args:
        last:         Number of most-recently-modified runs to scan.
        runs_dir:     Runs directory. Defaults to module-level ``_RUNS_DIR``.
        threshold_ms: Slow-spawn threshold in ms (default 60 000).

    Returns:
        Dictionary from ``aggregate_recent`` plus an enriched ``per_run``
        list where each entry additionally has:
            avg_duration_ms (float|None): Mean duration for this run, or None.
    """
    rd = runs_dir if runs_dir is not None else _RUNS_DIR
    result = aggregate_recent(runs_dir=rd, last=last)

    # Enrich per_run with avg_duration_ms for convenient display
    for entry in result.get("per_run", []):
        durs: list[int] = entry.get("durations", [])
        entry["avg_duration_ms"] = (sum(durs) / len(durs)) if durs else None

    return result


# ---------------------------------------------------------------------------
# Formatters (produce Markdown strings; used by CLI commands and W06 API)
# ---------------------------------------------------------------------------


def format_launch_summary(run: dict[str, Any]) -> str:
    """Format a single-run LAUNCH_* event summary as Markdown.

    Args:
        run: Output dict from ``aggregate_run_launch``.

    Returns:
        Markdown string with an event table (or an informational message
        if no LAUNCH_* events were found).
    """
    lines: list[str] = []
    rkey = run.get("registry_key", "?")
    lines.append(f"## Launch Event Summary — `{rkey}`")
    lines.append("")

    if not run.get("log_exists", False):
        lines.append(
            f"_(workflow.log not found: `{run.get('log_path', '?')}`)_"
        )
        return "\n".join(lines)

    event_rows: list[dict[str, Any]] = run.get("event_rows", [])

    if not event_rows:
        lines.append("_(No LAUNCH_* events found in workflow.log — T-475 may not be deployed yet.)_")
        return "\n".join(lines)

    headers = ["event_type", "timestamp", "registry_key", "ticket", "pid", "error"]
    rows: list[list[str]] = [
        [
            str(er.get("event_type", "-")),
            str(er.get("timestamp", "-")),
            str(er.get("registry_key", "-")),
            str(er.get("ticket", "-")),
            str(er.get("pid", "-")),
            str(er.get("error", "-")),
        ]
        for er in event_rows
    ]
    lines.append(_md_table(headers, rows))
    lines.append("")

    # Brief distribution footer
    dist = run.get("distribution", {})
    count = dist.get("count", 0)
    if count > 0:
        lines.append(
            f"spawn_duration_ms: count={count} "
            f"min={_fmt_optional_int(dist.get('min'))} "
            f"max={_fmt_optional_int(dist.get('max'))} "
            f"p50={_fmt_optional_int(dist.get('p50'))}"
        )
    else:
        lines.append("_(No matched START→OK/FAIL pairs — spawn_duration_ms unavailable.)_")

    return "\n".join(lines)


def format_launch_aggregate(result: dict[str, Any]) -> str:
    """Format a multi-run LAUNCH_* aggregate report as Markdown.

    Produces three sections:
        1. Distribution table (count/min/max/mean/p50/p95/p99)
        2. Per-run table (registry_key / events / avg duration ms)
        3. Slow-spawn catalog (>= 60 s)

    Args:
        result: Output dict from ``aggregate_recent_launch``.

    Returns:
        Markdown string.
    """
    lines: list[str] = []
    runs_scanned: int = result.get("runs_scanned", 0)
    events_total: int = result.get("events_total", 0)

    lines.append("## Launch Metrics Aggregate")
    lines.append("")
    lines.append(f"- Runs scanned: {runs_scanned}")
    lines.append(f"- LAUNCH_* events total: {events_total}")
    lines.append("")

    if events_total == 0:
        lines.append(
            "_(No LAUNCH_* events found across scanned runs — "
            "T-475 may not be deployed yet.)_"
        )
        lines.append("")

    # Section 1: distribution
    lines.append("### Section 1: spawn_duration_ms Distribution")
    dist = result.get("distribution", {})
    dist_rows: list[list[str]] = [
        [
            _fmt_optional_int(dist.get("count")),
            _fmt_optional_int(dist.get("min")),
            _fmt_optional_int(dist.get("max")),
            _fmt_optional_float(
                float(dist["mean"]) if dist.get("mean") is not None else None
            ),
            _fmt_optional_int(dist.get("p50")),
            _fmt_optional_int(dist.get("p95")),
            _fmt_optional_int(dist.get("p99")),
        ]
    ]
    lines.append(
        _md_table(["count", "min_ms", "max_ms", "mean_ms", "p50_ms", "p95_ms", "p99_ms"], dist_rows)
    )
    lines.append("")

    # Section 2: per-run breakdown
    lines.append("### Section 2: Per-Run Breakdown")
    per_run: list[dict[str, Any]] = result.get("per_run", [])
    if per_run:
        pr_rows: list[list[str]] = [
            [
                str(pr.get("registry_key", "-")),
                str(pr.get("events", 0)),
                _fmt_optional_float(pr.get("avg_duration_ms")),
            ]
            for pr in per_run
        ]
        lines.append(_md_table(["registry_key", "events", "avg_duration_ms"], pr_rows))
    else:
        lines.append("_(No runs scanned.)_")
    lines.append("")

    # Section 3: slow-spawn catalog
    lines.append("### Section 3: Slow Spawns (>= 60 000 ms)")
    slow_spawns: list[dict[str, Any]] = result.get("slow_spawns", [])
    if slow_spawns:
        sl_rows: list[list[str]] = [
            [
                str(sl.get("registry_key") or "-"),
                str(sl.get("ticket") or "-"),
                str(sl.get("duration_ms", "-")),
                str(sl.get("event_type", "-")),
                str(sl.get("timestamp", "-")),
            ]
            for sl in slow_spawns
        ]
        lines.append(
            _md_table(
                ["registry_key", "ticket", "duration_ms", "event_type", "timestamp"],
                sl_rows,
            )
        )
    else:
        lines.append("_(No slow spawns detected — all spawn durations are below 60 000 ms, or no data.)_")
    lines.append("")

    return "\n".join(lines)


def format_launch_slow(
    slow_spawns: list[dict[str, Any]],
    threshold_ms: int = _DEFAULT_SLOW_THRESHOLD_MS,
) -> str:
    """Format a slow-spawn catalog as a Markdown pipe table.

    Args:
        slow_spawns: List of slow-spawn dicts from ``catalog_slow_spawns``.
        threshold_ms: Threshold used (shown in heading).

    Returns:
        Markdown string.
    """
    lines: list[str] = []
    lines.append(f"## Slow Spawn Catalog (>= {threshold_ms} ms)")
    lines.append("")

    if not slow_spawns:
        lines.append(
            f"_(No spawns >= {threshold_ms} ms found — "
            "either all spawns are fast or T-475 is not yet deployed.)_"
        )
        return "\n".join(lines)

    rows: list[list[str]] = [
        [
            str(sl.get("registry_key") or "-"),
            str(sl.get("ticket") or "-"),
            str(sl.get("duration_ms", "-")),
            str(sl.get("event_type", "-")),
            str(sl.get("timestamp", "-")),
        ]
        for sl in slow_spawns
    ]
    lines.append(
        _md_table(
            ["registry_key", "ticket", "duration_ms", "event_type", "timestamp"],
            rows,
        )
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI command handlers
# ---------------------------------------------------------------------------


def _cmd_summarize(args: argparse.Namespace) -> int:
    """Handle the ``summarize`` sub-command.

    Args:
        args: Parsed argument namespace with ``registry_key`` attribute.

    Returns:
        Exit code (0 = success, 2 = no log found).
    """
    rd = _resolve_runs_dir(getattr(args, "runs_dir", None))
    run = aggregate_run_launch(args.registry_key, runs_dir=rd)

    if not run["log_exists"]:
        print(
            f"[flow-launch-metrics] workflow.log not found for "
            f"registry_key={args.registry_key}",
            file=sys.stderr,
        )
        print(f"  (searched: {run['log_path']})", file=sys.stderr)
        # Still print graceful output (empty event table message)
        print(format_launch_summary(run))
        return 2

    print(format_launch_summary(run))
    return 0


def _cmd_aggregate(args: argparse.Namespace) -> int:
    """Handle the ``aggregate`` sub-command.

    Args:
        args: Parsed argument namespace with ``last`` and ``runs_dir`` attributes.

    Returns:
        Exit code (always 0).
    """
    rd = _resolve_runs_dir(getattr(args, "runs_dir", None))
    result = aggregate_recent_launch(last=args.last, runs_dir=rd)
    print(format_launch_aggregate(result))
    return 0


def _cmd_slow(args: argparse.Namespace) -> int:
    """Handle the ``slow`` sub-command.

    Args:
        args: Parsed argument namespace with ``threshold_ms``, ``last``,
              and ``runs_dir`` attributes.

    Returns:
        Exit code (always 0).
    """
    rd = _resolve_runs_dir(getattr(args, "runs_dir", None))
    keys = _list_recent_registry_keys(rd, args.last)

    all_slow: list[dict[str, Any]] = []
    for key in keys:
        log_path = _log_path_for(rd, key)
        events = parse_launch_events(log_path)
        slow = catalog_slow_spawns(events, threshold_ms=args.threshold_ms)
        all_slow.extend(slow)

    print(format_launch_slow(all_slow, threshold_ms=args.threshold_ms))
    return 0


# ---------------------------------------------------------------------------
# argparse builder
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for flow-launch-metrics.

    Returns:
        Configured ArgumentParser with three sub-commands.
    """
    parser = argparse.ArgumentParser(
        prog="flow-launch-metrics",
        description=(
            "workflow.log LAUNCH_* event CLI — summarize / aggregate / slow "
            "(delegates parsing to launch_metrics.py)"
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # sub-command: summarize
    p_sum = sub.add_parser(
        "summarize",
        help="Print LAUNCH_* event table for a single workflow run",
    )
    p_sum.add_argument(
        "registry_key",
        help="Target registryKey (e.g. 20260510-175716)",
    )
    p_sum.add_argument(
        "--runs-dir",
        dest="runs_dir",
        default=None,
        help="Override default runs directory path",
    )
    p_sum.set_defaults(func=_cmd_summarize)

    # sub-command: aggregate
    p_agg = sub.add_parser(
        "aggregate",
        help="Aggregate spawn_duration_ms distribution across recent runs",
    )
    p_agg.add_argument(
        "--last",
        type=int,
        default=_DEFAULT_LAST,
        help=f"Number of most recent runs to include (default {_DEFAULT_LAST})",
    )
    p_agg.add_argument(
        "--runs-dir",
        dest="runs_dir",
        default=None,
        help="Override default runs directory path",
    )
    p_agg.set_defaults(func=_cmd_aggregate)

    # sub-command: slow
    p_slow = sub.add_parser(
        "slow",
        help=f"Print slow-spawn catalog (default >= {_DEFAULT_SLOW_THRESHOLD_MS} ms)",
    )
    p_slow.add_argument(
        "--threshold-ms",
        dest="threshold_ms",
        type=int,
        default=_DEFAULT_SLOW_THRESHOLD_MS,
        help=f"Minimum spawn duration to include in ms (default {_DEFAULT_SLOW_THRESHOLD_MS})",
    )
    p_slow.add_argument(
        "--last",
        type=int,
        default=_DEFAULT_LAST,
        help=f"Number of most recent runs to scan (default {_DEFAULT_LAST})",
    )
    p_slow.add_argument(
        "--runs-dir",
        dest="runs_dir",
        default=None,
        help="Override default runs directory path",
    )
    p_slow.set_defaults(func=_cmd_slow)

    return parser


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for flow-launch-metrics.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Process exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    try:
        return int(func(args) or 0)
    except KeyboardInterrupt:
        print("[flow-launch-metrics] interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

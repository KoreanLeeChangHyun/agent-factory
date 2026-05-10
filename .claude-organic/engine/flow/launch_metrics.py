"""launch_metrics.py - workflow.log LAUNCH_* parser + spawn_duration_ms distribution stats.

Parses LAUNCH_START / LAUNCH_OK / LAUNCH_FAIL events from workflow.log files
and computes spawn_duration_ms distribution (p50 / p95 / p99) and slow-spawn
catalogs. Designed to activate immediately after T-475 is deployed.

Supported log line formats (bidirectional, T-475 spec TBD):
    Format A (level-tagged):
        [YYYY-MM-DDTHH:MM:SS] [INFO] LAUNCH_START registry_key=... ticket=... pid=...
    Format B (event-tagged):
        [YYYY-MM-DDTHH:MM:SS] [LAUNCH_START] registry_key=... ticket=... pid=...

Key functions:
    parse_launch_events:   Extract LaunchEvent list from a single workflow.log
    compute_spawn_durations: Match START->OK/FAIL pairs, return duration list (ms)
    compute_distribution:  p50/p95/p99/min/max/mean/count from duration list
    catalog_slow_spawns:   Filter spawns >= threshold_ms (default 60 s)
    aggregate_recent:      Aggregate stats across last N workflow run directories

Graceful behavior:
    - Missing workflow.log files are skipped silently.
    - Zero LAUNCH_* events yields count=0, all stats=None.
    - Unmatched LAUNCH_START entries (orphans) are excluded from durations.

Self-check:
    Run `python3 launch_metrics.py` to execute _selfcheck() with 4 synthetic
    test cases and print PASS/FAIL per case.

Example:
    >>> from flow.launch_metrics import aggregate_recent, compute_distribution
    >>> result = aggregate_recent(last=5)
    >>> dist = compute_distribution(result["spawn_durations"])
    >>> print(dist["p50"])
"""

from __future__ import annotations

import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Optional

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_KST = timezone(timedelta(hours=9))

# Event type string constants — avoids hardcoding in regex / logic
_LAUNCH_START = "LAUNCH_START"
_LAUNCH_OK = "LAUNCH_OK"
_LAUNCH_FAIL = "LAUNCH_FAIL"

_LAUNCH_EVENT_TYPES: frozenset[str] = frozenset(
    {_LAUNCH_START, _LAUNCH_OK, _LAUNCH_FAIL}
)

# Path helpers — follows metrics_cli.py ROOT-tracking pattern:
#   <ROOT>/.claude-organic/engine/flow/launch_metrics.py → parents[3] = ROOT
_ROOT: Path = Path(__file__).resolve().parents[3]
_RUNS_DIR: Path = _ROOT / ".claude-organic" / "runs"

_WORKFLOW_LOG_FILENAME: str = "workflow.log"

# Default slow-spawn threshold (60 seconds expressed in ms)
_DEFAULT_SLOW_THRESHOLD_MS: int = 60_000

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Format A: [TS] [LEVEL] LAUNCH_EVENT key=val ...
_RE_FORMAT_A = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]"
    r"\s+\[(?:INFO|WARN|ERROR|DEBUG)\]"
    r"\s+(?P<event>LAUNCH_START|LAUNCH_OK|LAUNCH_FAIL)"
    r"(?P<rest>.*)$"
)

# Format B: [TS] [LAUNCH_EVENT] key=val ...
_RE_FORMAT_B = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]"
    r"\s+\[(?P<event>LAUNCH_START|LAUNCH_OK|LAUNCH_FAIL)\]"
    r"(?P<rest>.*)$"
)

# Key=value extractor for the trailing payload portion
_RE_KV = re.compile(r"(\w+)=(\S+)")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class LaunchEvent:
    """A single LAUNCH_* event parsed from a workflow.log line.

    Attributes:
        event_type:   One of "LAUNCH_START", "LAUNCH_OK", "LAUNCH_FAIL".
        timestamp:    ISO8601 timestamp string (seconds precision, no tz suffix
                      as written by flow_logger).
        registry_key: Workflow run identifier (e.g. "20260510-175716"), or None
                      if not present in the log line.
        ticket:       Ticket number string (e.g. "T-476"), or None.
        pid:          Process ID string if present, or None.
        error:        Reason/error string for LAUNCH_FAIL events, or None.
        raw_line:     The original unmodified log line.
    """

    event_type: str
    timestamp: str
    registry_key: Optional[str] = None
    ticket: Optional[str] = None
    pid: Optional[str] = None
    error: Optional[str] = None
    raw_line: str = field(default="")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse an ISO8601 timestamp string (seconds precision) to datetime.

    Args:
        ts_str: Timestamp string in "YYYY-MM-DDTHH:MM:SS" format.

    Returns:
        Naive datetime if parsing succeeds, or None on failure.
    """
    try:
        return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _extract_kv(rest: str) -> dict[str, str]:
    """Extract key=value pairs from the trailing payload of a log line.

    Args:
        rest: Trailing portion of a log line after the event keyword.

    Returns:
        Dictionary of extracted key-value pairs (all strings).
    """
    return {m.group(1): m.group(2) for m in _RE_KV.finditer(rest)}


def _try_parse_line(line: str) -> Optional[LaunchEvent]:
    """Attempt to parse a log line as a LAUNCH_* event.

    Tries Format A first, then Format B. Returns None if neither matches.

    Args:
        line: A single raw log line (trailing whitespace stripped).

    Returns:
        LaunchEvent if the line is a LAUNCH_* event, otherwise None.
    """
    for pattern in (_RE_FORMAT_A, _RE_FORMAT_B):
        m = pattern.match(line)
        if m is None:
            continue

        ts = m.group("ts")
        event_type = m.group("event")
        rest = m.group("rest")
        kv = _extract_kv(rest)

        return LaunchEvent(
            event_type=event_type,
            timestamp=ts,
            registry_key=kv.get("registry_key"),
            ticket=kv.get("ticket"),
            pid=kv.get("pid"),
            error=kv.get("reason") or kv.get("error"),
            raw_line=line,
        )

    return None


def _percentile(sorted_values: list[int], p: float) -> int:
    """Compute a percentile from a sorted integer list using nearest-rank.

    Args:
        sorted_values: Non-empty sorted list of integers.
        p:             Percentile as a fraction in [0.0, 1.0].

    Returns:
        Percentile value as an integer.
    """
    n = len(sorted_values)
    idx = min(int(round(p * (n - 1))), n - 1)
    return sorted_values[idx]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_launch_events(log_path: Path) -> list[LaunchEvent]:
    """Extract LAUNCH_* events from a workflow.log file.

    Supports two log line formats emitted by T-475 (spec TBD):
        Format A: [TS] [LEVEL]        LAUNCH_EVENT key=val ...
        Format B: [TS] [LAUNCH_EVENT] key=val ...

    Lines that match neither format are silently skipped.

    Args:
        log_path: Absolute path to the workflow.log file.

    Returns:
        List of LaunchEvent objects in file order. Returns an empty list if the
        file does not exist or contains no LAUNCH_* events.
    """
    events: list[LaunchEvent] = []

    if not log_path.is_file():
        return events

    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\n")
                ev = _try_parse_line(line)
                if ev is not None:
                    events.append(ev)
    except OSError:
        pass

    return events


def compute_spawn_durations(events: list[LaunchEvent]) -> list[int]:
    """Match LAUNCH_START to LAUNCH_OK/FAIL pairs and compute durations.

    Matching key: (registry_key, pid). If pid is None for both sides, matching
    falls back to registry_key only. Orphan LAUNCH_START entries (no matching
    end event) are excluded from the result.

    Duration is computed as:
        (end_timestamp - start_timestamp) * 1000  [milliseconds]

    If LAUNCH_OK contains a ``spawn_duration_ms`` key-value in its raw_line,
    that value is used directly (takes priority over timestamp diff).

    Args:
        events: List of LaunchEvent objects (typically from parse_launch_events).

    Returns:
        List of spawn durations in milliseconds (one per matched pair).
        LAUNCH_FAIL events also produce a duration (time until failure).
    """
    # Build lookup: (registry_key, pid) -> start_event
    # Use sentinel "_" for missing pid to keep key a 2-tuple of strings
    pending: dict[tuple[str, str], LaunchEvent] = {}
    durations: list[int] = []

    for ev in events:
        rk = ev.registry_key or ""
        pid = ev.pid or "_"
        key = (rk, pid)

        if ev.event_type == _LAUNCH_START:
            pending[key] = ev

        elif ev.event_type in (_LAUNCH_OK, _LAUNCH_FAIL):
            # Check if LAUNCH_OK carries spawn_duration_ms directly
            if ev.event_type == _LAUNCH_OK:
                direct_ms = _RE_KV.search(ev.raw_line)
                # Re-extract to find spawn_duration_ms specifically
                kv = _extract_kv(ev.raw_line)
                direct_val = kv.get("spawn_duration_ms")
                if direct_val is not None:
                    try:
                        durations.append(int(direct_val))
                        pending.pop(key, None)
                        continue
                    except ValueError:
                        pass

            start_ev = pending.pop(key, None)
            if start_ev is None:
                continue  # orphan end event — skip

            start_dt = _parse_timestamp(start_ev.timestamp)
            end_dt = _parse_timestamp(ev.timestamp)
            if start_dt is None or end_dt is None:
                continue

            delta_ms = int((end_dt - start_dt).total_seconds() * 1000)
            # Guard against clock skew producing negative durations
            if delta_ms >= 0:
                durations.append(delta_ms)

    return durations


def compute_distribution(durations_ms: list[int]) -> dict:
    """Compute descriptive statistics for a list of spawn durations.

    Args:
        durations_ms: List of spawn duration values in milliseconds.

    Returns:
        Dictionary with keys:
            count (int):       Number of data points.
            min   (int|None):  Minimum value, or None if count=0.
            max   (int|None):  Maximum value, or None if count=0.
            mean  (float|None): Arithmetic mean, or None if count=0.
            p50   (int|None):  50th percentile (median), or None if count=0.
            p95   (int|None):  95th percentile, or None if count=0.
            p99   (int|None):  99th percentile, or None if count=0.
    """
    if not durations_ms:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "p50": None,
            "p95": None,
            "p99": None,
        }

    sorted_vals = sorted(durations_ms)
    n = len(sorted_vals)

    return {
        "count": n,
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "mean": round(mean(sorted_vals), 2),
        "p50": _percentile(sorted_vals, 0.50),
        "p95": _percentile(sorted_vals, 0.95),
        "p99": _percentile(sorted_vals, 0.99),
    }


def catalog_slow_spawns(
    events: list[LaunchEvent],
    threshold_ms: int = _DEFAULT_SLOW_THRESHOLD_MS,
) -> list[dict]:
    """Return records for spawns that took >= threshold_ms milliseconds.

    Each returned record pairs a LAUNCH_START with its matching LAUNCH_OK or
    LAUNCH_FAIL end event. Orphan starts are excluded.

    Args:
        events:       List of LaunchEvent objects.
        threshold_ms: Minimum duration to include in the catalog (default 60 000 ms).

    Returns:
        List of dicts, each containing:
            registry_key (str|None): Workflow run identifier.
            ticket       (str|None): Ticket number.
            duration_ms  (int):      Elapsed spawn time in milliseconds.
            event_type   (str):      "LAUNCH_OK" or "LAUNCH_FAIL".
            timestamp    (str):      Timestamp of the end event.
            raw_line     (str):      Raw log line of the end event.
    """
    catalog: list[dict] = []

    pending: dict[tuple[str, str], LaunchEvent] = {}

    for ev in events:
        rk = ev.registry_key or ""
        pid = ev.pid or "_"
        key = (rk, pid)

        if ev.event_type == _LAUNCH_START:
            pending[key] = ev
            continue

        if ev.event_type not in (_LAUNCH_OK, _LAUNCH_FAIL):
            continue

        # Handle direct spawn_duration_ms on LAUNCH_OK
        duration_ms: Optional[int] = None
        if ev.event_type == _LAUNCH_OK:
            kv = _extract_kv(ev.raw_line)
            direct_val = kv.get("spawn_duration_ms")
            if direct_val is not None:
                try:
                    duration_ms = int(direct_val)
                except ValueError:
                    pass

        start_ev = pending.pop(key, None)

        if duration_ms is None:
            if start_ev is None:
                continue
            start_dt = _parse_timestamp(start_ev.timestamp)
            end_dt = _parse_timestamp(ev.timestamp)
            if start_dt is None or end_dt is None:
                continue
            duration_ms = int((end_dt - start_dt).total_seconds() * 1000)

        if duration_ms >= threshold_ms:
            catalog.append(
                {
                    "registry_key": ev.registry_key,
                    "ticket": ev.ticket,
                    "duration_ms": duration_ms,
                    "event_type": ev.event_type,
                    "timestamp": ev.timestamp,
                    "raw_line": ev.raw_line,
                }
            )

    return catalog


def aggregate_recent(runs_dir: Path = _RUNS_DIR, last: int = 10) -> dict:
    """Aggregate LAUNCH_* statistics across the most recent workflow runs.

    Directories inside runs_dir are sorted by modification time (descending)
    and the most recent ``last`` directories are scanned.

    Args:
        runs_dir: Path to the .claude-organic/runs directory.
        last:     Number of most-recently-modified run directories to include.

    Returns:
        Dictionary with keys:
            runs_scanned    (int):       Number of run dirs actually scanned.
            events_total    (int):       Total LAUNCH_* events found.
            spawn_durations (list[int]): All matched spawn durations (ms).
            distribution    (dict):      compute_distribution output.
            slow_spawns     (list[dict]): catalog_slow_spawns output (60s+).
            per_run         (list[dict]): Per-run breakdown:
                [{"registry_key": str, "events": int, "durations": list[int]}]
    """
    all_events: list[LaunchEvent] = []
    all_durations: list[int] = []
    per_run: list[dict] = []
    runs_scanned = 0

    if not runs_dir.is_dir():
        return {
            "runs_scanned": 0,
            "events_total": 0,
            "spawn_durations": [],
            "distribution": compute_distribution([]),
            "slow_spawns": [],
            "per_run": [],
        }

    # Collect directories sorted by mtime descending, take top `last`
    run_dirs = sorted(
        (d for d in runs_dir.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )[:last]

    for run_dir in run_dirs:
        log_path = run_dir / _WORKFLOW_LOG_FILENAME
        events = parse_launch_events(log_path)
        durations = compute_spawn_durations(events)

        runs_scanned += 1
        all_events.extend(events)
        all_durations.extend(durations)

        per_run.append(
            {
                "registry_key": run_dir.name,
                "events": len(events),
                "durations": durations,
            }
        )

    slow = catalog_slow_spawns(all_events)

    return {
        "runs_scanned": runs_scanned,
        "events_total": len(all_events),
        "spawn_durations": all_durations,
        "distribution": compute_distribution(all_durations),
        "slow_spawns": slow,
        "per_run": per_run,
    }


# ---------------------------------------------------------------------------
# Self-check (4 synthetic test cases)
# ---------------------------------------------------------------------------


def _selfcheck() -> int:
    """Run self-check with 4 synthetic test cases. Returns 0 on success, 1 on failure.

    Test cases:
        Case 1: Zero LAUNCH_* events (graceful empty handling)
        Case 2: Normal matched pair (START->OK, timestamp diff)
        Case 3: Slow spawn (>= 60 s threshold)
        Case 4: Orphan LAUNCH_START (no matching end event)

    Returns:
        0 if all cases pass, 1 if any case fails.
    """
    failures: list[str] = []

    def _fail(case: str, reason: str) -> None:
        failures.append(f"  FAIL [{case}]: {reason}")

    def _pass(case: str) -> None:
        print(f"  PASS [{case}]")

    # ------------------------------------------------------------------
    # Case 1: No LAUNCH_* events at all
    # ------------------------------------------------------------------
    case1 = "Case1-no-events"
    with tempfile.TemporaryDirectory() as tmpdir:
        log = Path(tmpdir) / "workflow.log"
        log.write_text(
            "[2026-05-10T12:00:00] [INFO] State transition: NONE -> PLAN\n"
            "[2026-05-10T12:01:00] [INFO] AGENT_DISPATCH: taskId=W01\n",
            encoding="utf-8",
        )
        events = parse_launch_events(log)
        durations = compute_spawn_durations(events)
        dist = compute_distribution(durations)

        if len(events) != 0:
            _fail(case1, f"Expected 0 events, got {len(events)}")
        elif dist["count"] != 0:
            _fail(case1, f"Expected count=0, got {dist['count']}")
        elif dist["p50"] is not None:
            _fail(case1, f"Expected p50=None, got {dist['p50']}")
        else:
            _pass(case1)

    # ------------------------------------------------------------------
    # Case 2: Normal matched pair (START -> OK, 5-second diff = 5000 ms)
    # ------------------------------------------------------------------
    case2 = "Case2-normal-match"
    with tempfile.TemporaryDirectory() as tmpdir:
        log = Path(tmpdir) / "workflow.log"
        log.write_text(
            "[2026-05-10T12:00:00] [INFO] LAUNCH_START registry_key=20260510-120000 ticket=T-001 pid=12345\n"
            "[2026-05-10T12:00:05] [INFO] LAUNCH_OK registry_key=20260510-120000 ticket=T-001 pid=12345\n",
            encoding="utf-8",
        )
        events = parse_launch_events(log)
        durations = compute_spawn_durations(events)
        dist = compute_distribution(durations)

        if len(events) != 2:
            _fail(case2, f"Expected 2 events, got {len(events)}")
        elif len(durations) != 1:
            _fail(case2, f"Expected 1 duration, got {len(durations)}")
        elif durations[0] != 5000:
            _fail(case2, f"Expected duration=5000ms, got {durations[0]}")
        elif dist["count"] != 1:
            _fail(case2, f"Expected count=1, got {dist['count']}")
        elif dist["p50"] != 5000:
            _fail(case2, f"Expected p50=5000, got {dist['p50']}")
        else:
            _pass(case2)

    # ------------------------------------------------------------------
    # Case 3: Slow spawn (70-second diff = 70 000 ms, above 60s threshold)
    #         Also validates Format B parsing
    # ------------------------------------------------------------------
    case3 = "Case3-slow-spawn-format-b"
    with tempfile.TemporaryDirectory() as tmpdir:
        log = Path(tmpdir) / "workflow.log"
        log.write_text(
            # Format B: [TS] [LAUNCH_EVENT] key=val
            "[2026-05-10T13:00:00] [LAUNCH_START] registry_key=20260510-130000 ticket=T-002 pid=99999\n"
            "[2026-05-10T13:01:10] [LAUNCH_FAIL] registry_key=20260510-130000 ticket=T-002 pid=99999 reason=timeout\n",
            encoding="utf-8",
        )
        events = parse_launch_events(log)
        durations = compute_spawn_durations(events)
        slow = catalog_slow_spawns(events, threshold_ms=60_000)

        expected_ms = 70_000  # 70 seconds
        if len(events) != 2:
            _fail(case3, f"Expected 2 events, got {len(events)}")
        elif len(durations) != 1:
            _fail(case3, f"Expected 1 duration, got {len(durations)}")
        elif durations[0] != expected_ms:
            _fail(case3, f"Expected duration={expected_ms}ms, got {durations[0]}")
        elif len(slow) != 1:
            _fail(case3, f"Expected 1 slow spawn, got {len(slow)}")
        elif slow[0]["duration_ms"] != expected_ms:
            _fail(case3, f"Expected slow duration={expected_ms}, got {slow[0]['duration_ms']}")
        elif slow[0]["event_type"] != _LAUNCH_FAIL:
            _fail(case3, f"Expected event_type=LAUNCH_FAIL, got {slow[0]['event_type']}")
        else:
            _pass(case3)

    # ------------------------------------------------------------------
    # Case 4: Orphan LAUNCH_START (no matching end event)
    # ------------------------------------------------------------------
    case4 = "Case4-orphan-start"
    with tempfile.TemporaryDirectory() as tmpdir:
        log = Path(tmpdir) / "workflow.log"
        log.write_text(
            "[2026-05-10T14:00:00] [INFO] LAUNCH_START registry_key=20260510-140000 ticket=T-003 pid=55555\n"
            # No LAUNCH_OK or LAUNCH_FAIL follows
            "[2026-05-10T14:01:00] [INFO] AGENT_DISPATCH: taskId=W01\n",
            encoding="utf-8",
        )
        events = parse_launch_events(log)
        durations = compute_spawn_durations(events)
        slow = catalog_slow_spawns(events)

        if len(events) != 1:
            _fail(case4, f"Expected 1 event, got {len(events)}")
        elif len(durations) != 0:
            _fail(case4, f"Expected 0 durations (orphan excluded), got {len(durations)}")
        elif len(slow) != 0:
            _fail(case4, f"Expected 0 slow spawns, got {len(slow)}")
        else:
            _pass(case4)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = 4
    passed = total - len(failures)
    print(f"\nResult: {passed}/{total} passed")
    if failures:
        for msg in failures:
            print(msg)
        return 1

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("launch_metrics.py selfcheck")
    print("-" * 40)
    rc = _selfcheck()
    sys.exit(rc)

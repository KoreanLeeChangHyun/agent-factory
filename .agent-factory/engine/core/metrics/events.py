"""metrics.py - Workflow metrics jsonl writer infrastructure.

Single jsonl for 12 types of events that occur each time a workflow is executed
Record as append-only in the file (`<workDir>/metrics.jsonl`). The calling party
Either the `MetricsWriter` class or the functional helper `append_event()`
Use it.

Save format:
    JSON Lines (jsonl). One line = one JSON object + `` \n ``.
    Common fields:
        - event_type: One of 12 catalogs
        - timestamp: ISO8601 (KST, UTC+9)
        - work_request: WR-NNN (or None allowed)
        - registry_key: YYYYMMDD-HHMMSS (or None is allowed)
        - work_dir: absolute path
        - payload: dict (verification of required keys by event_type)

12 event_type catalogs:
    step.start, step.end, phase.start, phase.end, tool.call, tool.deny,
    usage.snapshot, subagent.spawn, subagent.end, worktree.io,
    regression.pattern, report.missing

Validation Rules:
    - event_type not registered → ValueError
    - payload is not a dict → ValueError
    - Payload required key missing → ValueError
    - Automatic creation of timestamp (KST ISO8601)

IO Rules:
    - append-only (open mode "a")
    - flush() after write (no fsync)
    - ensure_ascii=False (Korean preserved)
    - 4KB per line recommended — This module only performs verification, truncate is the responsibility of the caller.

example:
    >>> from engine.core.metrics import MetricsWriter, append_event
    >>> w = MetricsWriter("/tmp/run/work", work_request="WR-400",
    ...                   registry_key="20260505-183053")
    >>> w.append("step.start", {"step": "INIT", "source": "banner"})
    >>> w.close()

    Or in functional form:
    >>> append_event("/tmp/run/work", "step.start",
    ...              {"step": "INIT", "source": "banner"},
    ...              work_request="WR-400", registry_key="20260505-183053")
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Union

# KST (UTC+9)
_KST = timezone(timedelta(hours=9))

# Recommended 4KB limit per line (constant recommended for caller truncate)
LINE_BYTE_LIMIT: int = 4096

# metrics.jsonl file name
_METRICS_FILENAME: str = "metrics.jsonl"

# 12 types of event_type → payload required key catalog
# NOTE: The 'step' key in metric event has the same meaning as 'workflow_phase' in status.json (metric event schema BC — separate migration track).
_SCHEMA: dict[str, list[str]] = {
    "step.start": ["step", "source"],
    "step.end": ["step", "duration_ms", "outcome", "source"],
    "phase.start": ["phase_index", "total"],
    "phase.end": ["phase_index", "duration_ms", "outcome"],
    "tool.call": [
        "tool_name",
        "tool_use_id",
        "duration_ms",
        "allowed",
    ],
    "tool.deny": ["tool_name", "tool_use_id", "reason"],
    "usage.snapshot": [
        "step",
        "input_tokens",
        "output_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "effective_tokens",
    ],
    "subagent.spawn": ["agent_kind", "parent_tool_use_id"],
    "subagent.end": ["agent_kind", "tool_use_id", "duration_ms", "outcome"],
    "worktree.io": ["op", "duration_ms", "outcome"],
    "regression.pattern": ["kind", "signal_summary"],
    "report.missing": ["report_path", "signal_summary"],
}


def _now_kst_iso() -> str:
    """Returns the current time in KST ISO8601 format.

    Returns:
        Example: "2026-05-05T18:30:53.123456+09:00"
    """
    return datetime.now(_KST).isoformat()


def schema_for(event_type: str) -> list[str]:
    """Returns a list of payload required keys for event_type.

    Args:
        event_type: One of 12 catalogs.

    Returns:
        A new copy of the required payload key list (caller changes do not affect the catalog).

    Raises:
        KeyError: when event_type is not in the catalog.
    """
    if event_type not in _SCHEMA:
        raise KeyError(
            f"unknown event_type: {event_type!r} "
            f"(known: {sorted(_SCHEMA.keys())})"
        )
    return list(_SCHEMA[event_type])


def known_event_types() -> list[str]:
    """Sorts and returns the 12 registered event_type catalogs.

    Returns:
        event_type List of strings (sorted alphabetically).
    """
    return sorted(_SCHEMA.keys())


def metrics_path(work_dir: Union[str, Path]) -> Path:
    """Returns the absolute path to metrics.jsonl for work_dir.

    Args:
        work_dir: Workflow working directory (str or Path).

    Returns:
        Path object of ``<work_dir>/metrics.jsonl``.
    """
    return Path(work_dir) / _METRICS_FILENAME


def _validate(event_type: str, payload: Any) -> None:
    """Verify the format of event_type / payload and the presence of required keys.

    Args:
        event_type: Must be one of 12 catalogs.
        payload: Must be a dict and contain all keys required by schema_for().

    Raises:
        ValueError: When verification fails. Include reason in message.
    """
    if event_type not in _SCHEMA:
        raise ValueError(
            f"unknown event_type: {event_type!r} "
            f"(known: {sorted(_SCHEMA.keys())})"
        )
    if not isinstance(payload, dict):
        raise ValueError(
            f"payload must be dict, got {type(payload).__name__}"
        )
    required = _SCHEMA[event_type]
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(
            f"payload missing required keys for {event_type!r}: {missing} "
            f"(required: {required})"
        )


def _load_context_defaults(work_dir: Path) -> dict[str, Optional[str]]:
    """Load work_request / registry_key default values from .context.json in work_dir.

    Args:
        work_dir: Workflow working directory.

    Returns:
        {"work_request": <WR-NNN | None>, "registry_key": <YYYYMMDD-HHMMSS | None>}
        Absence of file / Parsing failure / No key → Filled with None.
    """
    ctx_path = Path(work_dir) / ".context.json"
    defaults: dict[str, Optional[str]] = {"work_request": None, "registry_key": None}
    try:
        with open(ctx_path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    work_request_val = data.get("work_request") or data.get("work_request_no")
    rkey_val = data.get("registry_key") or data.get("registryKey")
    if isinstance(work_request_val, str) and work_request_val:
        defaults["work_request"] = work_request_val
    if isinstance(rkey_val, str) and rkey_val:
        defaults["registry_key"] = rkey_val
    return defaults


class MetricsWriter:
    """A writer who appends events to the metrics.jsonl file.

    Attributes:
        work_dir: Workflow working directory (absolute path recommended).
        work_request: Work request number (e.g. "WR-400"). None allowed.
        registry_key: registryKey (e.g. "20260505-183053"). None allowed.
        path: ``<work_dir>/metrics.jsonl`` absolute path.

    Notes:
        - Instance does not hold fd. Every append is short-lived
          Concurrency/conflict by ``open(..., "a")`` → write → flush → close
          Minimize risk (consider subagent + main simultaneous write scenario).
        - close() is provided for compatibility and is a no-op.
    """

    def __init__(
        self,
        work_dir: Union[str, Path],
        work_request: Optional[str] = None,
        registry_key: Optional[str] = None,
    ) -> None:
        """Initializes a Writer instance.

        Args:
            work_dir: Workflow working directory.
            work_request: Work request number (e.g. "WR-400"). Contains common header for all events.
            registry_key: registryKey (e.g. "20260505-183053").
        """
        self.work_dir: Path = Path(work_dir)
        self.work_request: Optional[str] = work_request
        self.registry_key: Optional[str] = registry_key
        self.path: Path = metrics_path(self.work_dir)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        """Append one event line to the jsonl file.

        Args:
            event_type: One of 12 catalogs.
            payload: payload dict for event_type.

        Raises:
            ValueError: event_type is not registered, payload format error, or
                In case of missing required key.
            OSError: When disk IO fails (try/except recommended on the call side).
        """
        _validate(event_type, payload)
        record: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": _now_kst_iso(),
            "work_request": self.work_request,
            "registry_key": self.registry_key,
            "work_dir": str(self.work_dir),
            "payload": payload,
        }
        # Guaranteed parent directory (it's the caller's fault if work_dir itself doesn't exist, but it's a safety net)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with open(self.path, "a", encoding="utf-8") as fp:
            fp.write(line)
            fp.write("\n")
            fp.flush()

    def close(self) -> None:
        """Compatibility dummy. This writer does not have fd, so no-op."""
        return None

    # Context manager support (available in with blocks)
    def __enter__(self) -> "MetricsWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def append_event(
    work_dir: Union[str, Path],
    event_type: str,
    payload: dict[str, Any],
    *,
    work_request: Optional[str] = None,
    registry_key: Optional[str] = None,
) -> None:
    """Functional helper — When performing a one-time append, instance creation is omitted and called.

    If work_dir/.context.json exists, work_request / registry_key is automatically set
    Load it and use it as the default value when the specified argument is None.

    Args:
        work_dir: Workflow working directory.
        event_type: One of 12 catalogs.
        payload: payload dict for event_type.
        work_request: When specified, takes precedence over .context.json.
        registry_key: When specified, takes precedence over .context.json.

    Raises:
        ValueError: When verification fails.
        OSError: When disk IO fails.
    """
    work_dir_path = Path(work_dir)
    if work_request is None or registry_key is None:
        defaults = _load_context_defaults(work_dir_path)
        if work_request is None:
            work_request = defaults.get("work_request")
        if registry_key is None:
            registry_key = defaults.get("registry_key")
    writer = MetricsWriter(
        work_dir=work_dir_path, work_request=work_request, registry_key=registry_key
    )
    writer.append(event_type, payload)


# ---------------------------------------------------------------------------
# Self-verification (__main__)
# ---------------------------------------------------------------------------

def _selfcheck() -> int:
    """Verifies normal/missing cases of 12 types of schema and outputs a result table.

    Returns:
        Number of failure cases. If it is 0, all verification passes.
    """
    import tempfile

    cases: list[tuple[str, str, dict[str, Any], Optional[type[Exception]]]] = []

    # 12 types of normal cases (only required keys filled)
    valid_payloads: dict[str, dict[str, Any]] = {
        "step.start": {"step": "INIT", "source": "banner"},
        "step.end": {
            "step": "INIT",
            "duration_ms": 1234,
            "outcome": "ok",
            "source": "banner",
        },
        "phase.start": {"phase_index": 1, "total": 2},
        "phase.end": {"phase_index": 1, "duration_ms": 5678, "outcome": "ok"},
        "tool.call": {
            "tool_name": "Bash",
            "tool_use_id": "tu_01",
            "duration_ms": 42,
            "allowed": True,
        },
        "tool.deny": {
            "tool_name": "Edit",
            "tool_use_id": "tu_02",
            "reason": "path outside worktree",
        },
        "usage.snapshot": {
            "step": "WORK",
            "input_tokens": 100,
            "output_tokens": 200,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 50,
            "effective_tokens": 1105.0,
        },
        "subagent.spawn": {"agent_kind": "worker", "parent_tool_use_id": "tu_03"},
        "subagent.end": {
            "agent_kind": "worker",
            "tool_use_id": "tu_03",
            "duration_ms": 99999,
            "outcome": "ok",
        },
        "worktree.io": {"op": "create", "duration_ms": 200, "outcome": "ok"},
        "regression.pattern": {
            "kind": "worker_false_success",
            "signal_summary": "Edit count=0 but status=success",
        },
        "report.missing": {
            "report_path": "/tmp/run/work/report.md",
            "signal_summary": "reporter returned without report.md disk write",
        },
    }
    for et in known_event_types():
        cases.append(("normal", et, valid_payloads[et], None))

    # Abnormal cases ≥ 3
    cases.append(
        (
            "Abnormal-unregistered",
            "unknown.event",
            {"foo": "bar"},
            ValueError,
        )
    )
    cases.append(
        (
            "Abnormal-payload type",
            "step.start",
            ["not", "a", "dict"],  # type: ignore[arg-type]
            ValueError,
        )
    )
    cases.append(
        (
            "Abnormal - Required key missing",
            "step.end",
            {"step": "INIT"},  # duration_ms / outcome / source missing
            ValueError,
        )
    )
    cases.append(
        (
            "abnormal-payload=None",
            "tool.call",
            None,  # type: ignore[arg-type]
            ValueError,
        )
    )

    rows: list[tuple[str, str, str]] = []
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        writer = MetricsWriter(
            work_dir=tmp, work_request="WR-400", registry_key="20260505-183053"
        )
        for label, et, payload, expected_exc in cases:
            try:
                writer.append(et, payload)  # type: ignore[arg-type]
                actual = "OK"
                exc_name = "-"
            except Exception as exc:  # noqa: BLE001
                actual = "RAISE"
                exc_name = type(exc).__name__

            if expected_exc is None:
                ok = actual == "OK"
            else:
                ok = actual == "RAISE" and exc_name == expected_exc.__name__

            if not ok:
                failed += 1
            verdict = "PASS" if ok else "FAIL"
            rows.append((label + " / " + et, exc_name + " (" + actual + ")", verdict))

        # Normal case line count verification (jsonl line count == 12)
        path = metrics_path(tmp)
        with open(path, encoding="utf-8") as fp:
            lines = [ln for ln in fp.read().splitlines() if ln.strip()]
        # Ensure only normal cases are recorded
        line_check_ok = len(lines) == len(valid_payloads)
        rows.append(
            (
                "jsonl line number",
                f"{len(lines)} / {len(valid_payloads)}",
                "PASS" if line_check_ok else "FAIL",
            )
        )
        if not line_check_ok:
            failed += 1

        # Check if all lines are valid JSON
        json_ok = True
        for ln in lines:
            try:
                json.loads(ln)
            except json.JSONDecodeError:
                json_ok = False
                break
        rows.append(
            (
                "jsonl JSON parsing",
                f"{len(lines)} lines",
                "PASS" if json_ok else "FAIL",
            )
        )
        if not json_ok:
            failed += 1

        # append_event() Functional helper operation verification (.context.json automatic loading)
        ctx_dir = Path(tmp) / "ctx_test"
        ctx_dir.mkdir()
        with open(ctx_dir / ".context.json", "w", encoding="utf-8") as fp:
            json.dump(
                {"work_request_no": "WR-401", "registry_key": "20260505-190000"}, fp
            )
        append_event(
            ctx_dir,
            "step.start",
            {"step": "PLAN", "source": "fsm"},
        )
        with open(metrics_path(ctx_dir), encoding="utf-8") as fp:
            rec = json.loads(fp.readline())
        ctx_ok = (
            rec["work_request"] == "WR-401"
            and rec["registry_key"] == "20260505-190000"
            and rec["event_type"] == "step.start"
        )
        rows.append(
            (
                "autoload append_event context",
                "work_request=WR-401 / registry_key=20260505-190000",
                "PASS" if ctx_ok else "FAIL",
            )
        )
        if not ctx_ok:
            failed += 1

    # table output
    print("metrics.py self-verification results")
    print("=" * 88)
    header = ("case", "result", "verdict")
    widths = (44, 32, 6)
    print(
        f"{header[0]:<{widths[0]}} | {header[1]:<{widths[1]}} | {header[2]:<{widths[2]}}"
    )
    print("-" * 88)
    for r in rows:
        print(
            f"{r[0]:<{widths[0]}} | {r[1]:<{widths[1]}} | {r[2]:<{widths[2]}}"
        )
    print("=" * 88)
    print(f"total cases: {len(rows)} / failures: {failed}")
    return failed


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(_selfcheck())

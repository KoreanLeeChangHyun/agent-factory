#!/usr/bin/env -S python3 -u
"""Track workflow token usage (incremental + batch).

Subcommand:
    Called from the track SubagentStop hook. Incremental token tracking upon individual agent termination
    Called from batch finalization.py. Final settlement by batch parsing of entire JSONL

Main functions:
    parse_jsonl_usage: Sum up usage of JSONL files
    cmd_track: Execute track subcommand
    cmd_batch: Execute batch subcommand
    main: CLI entry point

Input (stdin JSON): agent_type, agent_id, agent_transcript_path
Non-blocking principle: exit 0 on all error paths
"""

from __future__ import annotations

import glob
import json
import os
import sys
from typing import Optional

_agent_factory_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)

from engine.common import (
    acquire_lock,
    atomic_write_json,
    load_json_file,
    release_lock,
    resolve_project_root,
    scan_active_workflows,
)
from engine.constants import HALLU_TARGET_AGENT_TYPES, HOOK_HALLUCINATION_LOGGER

PROJECT_ROOT = resolve_project_root()


def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """Records events in the workflow log."""
    try:
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


# Upper file size limit (50MB)
MAX_JSONL_SIZE = 50 * 1024 * 1024

VALID_AGENT_TYPES: set[str] = {
    "orchestrator", "planner", "worker", "explorer",
    "validator", "reporter",
}

# Agent types that are not subject to worker queue mapping in _pending_workers
NON_WORKER_AGENT_TYPES: set[str] = {
    "validator", "reporter", "planner", "explorer", "orchestrator",
}


def _normalize_agent_type(raw: str) -> tuple[str, str]:
    """agent_type Normalizes the raw string to one of VALID_AGENT_TYPES.

    Types with model suffixes such as "worker-opus", "worker-sonnet", etc.
    Convert to regular type and model suffix tuple.
    A pure string comparison function that does not throw exceptions.

    Args:
        raw: agent_type string before normalization

    Returns:
        (normalized_type, model_suffix) tuple.
        - normalized_type: Normal type belonging to VALID_AGENT_TYPES. If there is no match, the original raw.
        - model_suffix: Model suffix string. Examples: "sonnet", "opus". If not, an empty string.

    Examples:
        >>> _normalize_agent_type("worker-sonnet")
        ("worker", "sonnet")
        >>> _normalize_agent_type("worker")
        ("worker", "")
        >>> _normalize_agent_type("orchestrator")
        ("orchestrator", "")
    """
    if not isinstance(raw, str):
        return (raw, "")
    if raw in VALID_AGENT_TYPES:
        return (raw, "")
    for t in VALID_AGENT_TYPES:
        if raw.startswith(t + "-"):
            suffix = raw[len(t) + 1:]
            return (t, suffix)
    return (raw, "")


# =============================================================================
# common utilities
# =============================================================================

def _read_stdin_json() -> dict[str, object]:
    """Reads JSON from stdin and returns it. In case of failure, exit 0.

    Returns:
        Parsed JSON dictionary
    """
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)


def _extract_session_id_from_transcript_path(transcript_path: str) -> Optional[str]:
    """transcript_path (main session jsonl) Extract session ID from basename.

    Claude session file naming convention: <session_id>.jsonl
    The session ID must be in UUID format (8-4-4-4-12 hex) to be considered valid.

    Args:
        transcript_path: transcript_path from stdin (=main session jsonl path)

    Returns:
        Extracted session ID string. None if parsing fails or UUID format mismatch.
    """
    import re
    if not transcript_path:
        return None
    basename = os.path.basename(transcript_path)
    if not basename.endswith(".jsonl"):
        return None
    candidate = basename[:-6]  # Remove ".jsonl"
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    if uuid_pattern.match(candidate):
        return candidate
    return None


def _extract_session_id_from_agent_jsonl(agent_transcript_path: str) -> Optional[str]:
    """Agent jsonl Reads the sessionId field of the first line of the user record and returns the session ID.

    Args:
        agent_transcript_path: agent jsonl file path (agent_transcript_path in stdin)

    Returns:
        Extracted session ID string. None if reading fails.
    """
    if not agent_transcript_path or not os.path.isfile(agent_transcript_path):
        return None
    try:
        with open(agent_transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") == "user":
                    session_id = record.get("sessionId", "")
                    if session_id:
                        return session_id
    except Exception:
        pass
    return None


def _call_link_session(status_file: str, session_id: str) -> str:
    """Call flow.state_machine.link_session with dynamic import.

    To avoid module-level circular import, use dynamic import immediately before calling.

    Args:
        status_file: absolute path to status.json file
        session_id: Session ID to register

    Returns:
        link_session Return value string (added/already linked/skipped/failed).
    """
    try:
        from flow.state_machine import link_session  # noqa: PLC0415
        result = link_session(status_file, session_id)
        return result
    except Exception as e:
        return f"link-session -> failed (import error: {e})"


def _try_link_session_from_stdin(
    agent_transcript_path: str,
    main_transcript_path: str,
) -> None:
    """Extract the session ID from the stdin path and register it in status.json linked_sessions.

    Find work_dir with _find_work_dir() and combine the status.json path.
    Called in the early exit path of agents other than VALID_AGENT_TYPES.

    Args:
        agent_transcript_path: agent_transcript_path on stdin
        main_transcript_path: transcript_path from stdin (main session jsonl)
    """
    work_dir = _find_work_dir()
    if not work_dir:
        return
    status_file = os.path.join(work_dir, "status.json")
    _link_sessions_from_stdin(status_file, agent_transcript_path, main_transcript_path)


def _link_sessions_from_stdin(
    status_file: str,
    agent_transcript_path: str,
    main_transcript_path: str,
) -> None:
    """Extract the main + worker session ID from the stdin path and register it in status.json linked_sessions.

    Extraction priority:
      (a) <session_id>.jsonl pattern in transcript_path basename — main session ID
      (b) agent_transcript_path sessionId field of the first user record — fallback or worker ID

    Silent skip if both paths fail.

    Args:
        status_file: absolute path to status.json (called without lock — state_machine.link_session handles atomic_write internally)
        agent_transcript_path: agent_transcript_path on stdin
        main_transcript_path: transcript_path from stdin (main session jsonl)
    """
    registered: set[str] = set()

    # (a) transcript_path basename → main session ID
    main_session_id = _extract_session_id_from_transcript_path(main_transcript_path)
    if main_session_id:
        result = _call_link_session(status_file, main_session_id)
        print(f"[usage-sync] cmd_track: link_session result={result}", file=sys.stderr)
        registered.add(main_session_id)

    # (b) agent jsonl first user record sessionId → worker sessionId (or main fallback)
    worker_session_id = _extract_session_id_from_agent_jsonl(agent_transcript_path)
    if worker_session_id and worker_session_id not in registered:
        result = _call_link_session(status_file, worker_session_id)
        print(
            f"[usage-sync] cmd_track: link_session (worker sessionId) result={result}",
            file=sys.stderr,
        )
        registered.add(worker_session_id)

    if not registered:
        print(
            "[usage-sync] cmd_track: link_session skipped (no session_id extracted)",
            file=sys.stderr,
        )


def _find_work_dir() -> Optional[str]:
    """Directory scan to look up the workDir of an active workflow.

    Returns:
        Absolute workDir path of the active workflow. If not, None.
    """
    workflows = scan_active_workflows(project_root=PROJECT_ROOT)
    if not workflows:
        return None

    for key, entry in workflows.items():
        if isinstance(entry, dict) and "workDir" in entry:
            rel_dir = entry["workDir"]
            candidate = os.path.join(PROJECT_ROOT, rel_dir) if not rel_dir.startswith("/") else rel_dir
            if os.path.isdir(candidate):
                return candidate
    return None


def _load_usage(usage_file: str) -> dict[str, object]:
    """Load usage.json. If not found, returns the default schema.

    Args:
        usage_file: usage.json file path

    Returns:
        usage data dictionary. Includes keys agents, totals, and _pending_workers.
    """
    data = load_json_file(usage_file)
    if not isinstance(data, dict):
        data = {"$schema": "usage-v2", "agents": {}, "totals": {}, "_pending_workers": {}}
    if "agents" not in data:
        data["agents"] = {}
    if "totals" not in data:
        data["totals"] = {}
    # Cleaned up "init" and "done" keys in existing usage.json
    for old_key in ("init", "done"):
        data["agents"].pop(old_key, None)
    return data


def parse_jsonl_usage(filepath: str) -> Optional[dict[str, int]]:
    """Sum up the usage of all assistant records in the JSONL file.

    Args:
        filepath: JSONL file path

    Returns:
        Dictionary of the total number of tokens.
        Keys: input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens.
        None if there is no file or parsing fails.
    """
    totals: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }

    if not os.path.isfile(filepath):
        return None

    file_size = os.path.getsize(filepath)
    if file_size > MAX_JSONL_SIZE:
        print(
            f"[usage-sync] WARNING: JSONL file exceeds {MAX_JSONL_SIZE // (1024*1024)}MB: "
            f"{filepath} ({file_size // (1024*1024)}MB)",
            file=sys.stderr,
        )

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if rec.get("type") != "assistant":
                    continue
                if rec.get("isApiErrorMessage"):
                    continue

                usage = None
                msg = rec.get("message")
                if isinstance(msg, dict) and "usage" in msg:
                    usage = msg["usage"]
                elif "usage" in rec:
                    usage = rec["usage"]

                if isinstance(usage, dict):
                    totals["input_tokens"] += usage.get("input_tokens", 0)
                    totals["output_tokens"] += usage.get("output_tokens", 0)
                    totals["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)
                    totals["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
    except Exception as e:
        print(f"[usage-sync] WARNING: Failed to parse {filepath}: {e}", file=sys.stderr)
        return None

    return totals


def count_tool_use_in_jsonl(filepath: str) -> int:
    """Counts the number of tool_use items in assistant records in the JSONL file.

    Sum up all type == "tool_use" items in the content array of the type == "assistant" record.

    Args:
        filepath: JSONL file path

    Returns:
        Total number of tool_use items. If there is no file or parsing fails, -1 is returned (non-blocking principle).
    """
    if not os.path.isfile(filepath):
        return -1

    count = 0
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if rec.get("type") != "assistant":
                    continue

                content = rec.get("content")
                if not isinstance(content, list):
                    continue

                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        count += 1
    except Exception:
        return -1

    return count


# =============================================================================
# track: Incremental tracking as individual agents exit.
# =============================================================================

def cmd_track() -> None:
    """Called from SubagentStop hook. Record individual agent tokens in usage.json.

    Read JSON from stdin and parse agent_type, agent_id, agent_transcript_path, and
    Extract token usage from the JSONL file and record it incrementally in usage.json.
    exit 0 on all error paths (non-blocking principle).
    """
    input_data = _read_stdin_json()

    agent_type = input_data.get("agent_type", "")
    agent_id = input_data.get("agent_id", "")
    transcript_path = input_data.get("agent_transcript_path", "")
    main_transcript_path = input_data.get("transcript_path", "")

    agent_type, model_suffix = _normalize_agent_type(agent_type)

    if agent_type not in VALID_AGENT_TYPES:
        # Agents other than VALID_AGENT_TYPES also attempt link_session (if transcript_path exists)
        if transcript_path and os.path.isfile(transcript_path):
            _try_link_session_from_stdin(transcript_path, main_transcript_path)
        sys.exit(0)
    if not transcript_path or not os.path.isfile(transcript_path):
        sys.exit(0)

    work_dir = _find_work_dir()
    if not work_dir:
        sys.exit(0)

    # JSONL parsing
    tokens = parse_jsonl_usage(transcript_path)

    # Hallucination detected: tool_use 0 cases && target agent type && logger active
    tool_use_count = count_tool_use_in_jsonl(transcript_path)
    if (
        tool_use_count == 0
        and agent_type in HALLU_TARGET_AGENT_TYPES
        and HOOK_HALLUCINATION_LOGGER == "true"
    ):
        hallu_work_dir = work_dir
        _append_log(
            hallu_work_dir,
            "WARN",
            f"HALLUCINATION_SUSPECT: agent_type={agent_type} agent_id={agent_id} tool_use_count=0",
        )

    if not tokens:
        print(f"[usage-sync] No valid usage data found in: {transcript_path}", file=sys.stderr)
        sys.exit(0)

    tokens["method"] = "subagent_transcript"
    tokens["model"] = model_suffix if model_suffix else "default"

    usage_file = os.path.join(work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not acquire_lock(lock_dir, max_wait=5):
        print(
            f"[usage-sync] WARNING: track lock failed, usage data may be lost for {agent_type}:{agent_id}",
            file=sys.stderr,
        )
        sys.exit(0)

    try:
        usage_data = _load_usage(usage_file)

        # Record agent_id -> agent_type mapping in _agent_map (referenced in batch)
        if "_agent_map" not in usage_data:
            usage_data["_agent_map"] = {}
        usage_data["_agent_map"][agent_id] = agent_type

        # Record main session JSONL path (first time only)
        if "_main_transcript" not in usage_data:
            if main_transcript_path and os.path.isfile(main_transcript_path):
                usage_data["_main_transcript"] = main_transcript_path

        # Register linked_sessions: main session ID + worker's own sessionId (W02)
        status_file = os.path.join(work_dir, "status.json")
        _link_sessions_from_stdin(status_file, transcript_path, main_transcript_path)

        if agent_type == "worker":
            pending = usage_data.get("_pending_workers", {})
            task_id = pending.get(agent_id, None)

            if "workers" not in usage_data["agents"]:
                usage_data["agents"]["workers"] = {}

            existing_workers = usage_data["agents"]["workers"]

            if task_id:
                # When agent_id is mapped directly to pending key (ideal path)
                existing_workers[task_id] = tokens
                del pending[agent_id]
            else:
                # If agent_id is a hex string and is not in pending:
                # Among the pending values ​​(task_id), the first task_id that has not yet been recorded in workers is assigned in a queue manner.
                # Non-worker agent types (validator, reporter, etc.) are excluded from queue candidates.
                assigned_task_id = None
                for pkey, ptid in list(pending.items()):
                    if ptid in NON_WORKER_AGENT_TYPES or pkey in NON_WORKER_AGENT_TYPES:
                        del pending[pkey]
                        print(
                            f"[usage-sync] INFO: cmd_track skipped non-worker pending entry '{pkey}' -> '{ptid}'",
                            file=sys.stderr,
                        )
                        continue
                    if ptid not in existing_workers:
                        assigned_task_id = ptid
                        del pending[pkey]
                        break

                if assigned_task_id:
                    print(
                        f"[usage-sync] INFO: agent_id '{agent_id}' mapped to task_id '{assigned_task_id}' via queue assignment",
                        file=sys.stderr,
                    )
                    existing_workers[assigned_task_id] = tokens
                    # Record agent_id -> task_id relationship in _agent_map (for batch reference)
                    usage_data["_agent_map"][agent_id] = "worker"
                else:
                    # Completely unmappable: record fallback with agent_id as key
                    print(
                        f"[usage-sync] WARNING: agent_id '{agent_id}' not found in _pending_workers and no unassigned task_id, using agent_id as key",
                        file=sys.stderr,
                    )
                    existing_workers[agent_id] = tokens
        else:
            usage_data["agents"][agent_type] = tokens

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, usage_data)
        _append_log(work_dir, "INFO", f"Usage tracked: {agent_type}")
    except Exception as e:
        print(f"[usage-sync] WARNING: track error: {e}", file=sys.stderr)
    finally:
        release_lock(lock_dir)


# =============================================================================
# batch: Settlement of entire JSONL in batch at the end of workflow
# =============================================================================

def _find_subagents_dir(transcript_path: str) -> Optional[str]:
    """Reverse subagents/ directory path from agent_transcript_path.

    Args:
        transcript_path: agent JSONL file absolute path

    Returns:
        subagents/ directory path. None if the parent of transcript_path is not subagents/.
    """
    parent = os.path.dirname(transcript_path)
    if os.path.basename(parent) == "subagents":
        return parent
    return None


def _find_main_session_jsonl(subagents_dir: str) -> Optional[str]:
    """Find the main session JSONL at the top of subagents/.

    Args:
        subagents_dir: absolute path to subagents/ directory

    Returns:
        Main session JSONL file path. If not, None.
    """
    session_dir = os.path.dirname(subagents_dir)
    session_jsonl = session_dir + ".jsonl"
    if os.path.isfile(session_jsonl):
        return session_jsonl
    return None


def _find_main_session_from_status(work_dir: str) -> Optional[str]:
    """Configure the main session JSONL path in linked_sessions or _agent_map in status.json.

    0th order (highest priority): Directly returns the _main_transcript path in usage.json.
    1st: Directly search <session_id>.jsonl with the session ID recorded in linked_sessions.
    Secondary (replacement): when linked_sessions is empty, recorded in _agent_map in usage.json
         Backtracks the subagents directory with a known agent_id and returns the parent session JSONL.

    Args:
        work_dir: Absolute path to the workflow working directory.

    Returns:
        Main session JSONL file path. If not, None.
    """
    # 0th: Directly returns the _main_transcript path in usage.json
    usage_file = os.path.join(work_dir, "usage.json")
    usage_data_early = load_json_file(usage_file)
    if isinstance(usage_data_early, dict):
        main_transcript = usage_data_early.get("_main_transcript", "")
        if main_transcript and os.path.isfile(main_transcript):
            return main_transcript

    status_file = os.path.join(work_dir, "status.json")
    status = load_json_file(status_file)
    if not isinstance(status, dict):
        return None

    project_slug = PROJECT_ROOT.replace("/", "-")

    # Round 1: linked_sessions based navigation
    sessions = status.get("linked_sessions", [])
    for claude_base in [
        os.path.expanduser("~/.claude"),
        os.path.expanduser("~/.config/claude"),
    ]:
        projects_dir = os.path.join(claude_base, "projects", project_slug)
        if not os.path.isdir(projects_dir):
            continue
        for session_id in sessions:
            path = os.path.join(projects_dir, f"{session_id}.jsonl")
            if os.path.isfile(path):
                return path

    # 2nd: Back-lookup with known agent_id recorded in _agent_map
    usage_file = os.path.join(work_dir, "usage.json")
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
        for agent_id in agent_map:
            pattern = os.path.join(projects_dir, "*", "subagents", f"agent-{agent_id}.jsonl")
            matches = glob.glob(pattern)
            if matches:
                # subagents/ -> session_dir -> session_dir.jsonl
                session_dir = os.path.dirname(os.path.dirname(matches[0]))
                main_jsonl = session_dir + ".jsonl"
                if os.path.isfile(main_jsonl):
                    return main_jsonl

    return None


def _resolve_agent_type(
    agent_filename: str,
    agent_map: dict[str, str],
    subagents_dir: Optional[str] = None,
) -> Optional[str]:
    """Identifies the agent_type of agent-<id>.jsonl. Apply multiple fallback chains.

    Fallback order:
      1. _agent_map mapping query (source=agent_map)
      2. agentType field in agent-<id>.meta.json (source=meta_json)
      3. JSONL slug key of the first user record (source=jsonl_slug)
      4. JSONL attributionAgent key of the first assistant record (source=jsonl_attribution)
      5. If agentId is in hex format and subagents_dir is given, "worker" defaults (source=hex_default)

    Args:
        agent_filename: agent JSONL file path
        agent_map: agent_id -> agent_type mapping dictionary
        subagents_dir: subagents/ directory path. If None, meta.json fallback·hex_default is disabled.

    Returns:
        Identified agent_type string. None if identification is not possible.
    """
    basename = os.path.basename(agent_filename)
    agent_id: Optional[str] = None
    if basename.startswith("agent-") and basename.endswith(".jsonl"):
        agent_id = basename[len("agent-"):-len(".jsonl")]

    # Fallback 1: _agent_map mapping lookup
    if agent_id:
        mapped = agent_map.get(agent_id)
        if mapped:
            print(
                f"[usage-sync] _resolve_agent_type: agent_id={agent_id} source=agent_map result={mapped}",
                file=sys.stderr,
            )
            return mapped

    # Fallback 2: agentType field in agent-<id>.meta.json
    if agent_id and subagents_dir:
        meta_path = os.path.join(subagents_dir, f"agent-{agent_id}.meta.json")
        try:
            with open(meta_path, "r", encoding="utf-8") as mf:
                meta = json.load(mf)
            raw_type = meta.get("agentType", "")
            if raw_type:
                normalized, _suffix = _normalize_agent_type(raw_type)
                if normalized in VALID_AGENT_TYPES:
                    print(
                        f"[usage-sync] _resolve_agent_type: agent_id={agent_id} source=meta_json result={normalized}",
                        file=sys.stderr,
                    )
                    return normalized
        except Exception:
            pass

    # Fallback 3 & 4: JSONL parsing (slug → attributionAgent)
    try:
        with open(agent_filename, "r", encoding="utf-8") as f:
            first_user_done = False
            attribution_candidate: Optional[str] = None
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rec_type = rec.get("type")

                # Fallback 3: slug on first user record
                if rec_type == "user" and not first_user_done:
                    first_user_done = True
                    slug = rec.get("slug", "")
                    if slug:
                        normalized, _suffix = _normalize_agent_type(slug)
                        if normalized in VALID_AGENT_TYPES:
                            print(
                                f"[usage-sync] _resolve_agent_type: agent_id={agent_id} source=jsonl_slug result={normalized}",
                                file=sys.stderr,
                            )
                            return normalized

                # Fallback 4: attributionAgent on assistant record
                if rec_type == "assistant" and attribution_candidate is None:
                    attr = rec.get("attributionAgent", "")
                    if attr:
                        normalized, _suffix = _normalize_agent_type(attr)
                        if normalized in VALID_AGENT_TYPES:
                            attribution_candidate = normalized

                # Early exit when both user + attribution are completed
                if first_user_done and attribution_candidate is not None:
                    break

            if attribution_candidate:
                print(
                    f"[usage-sync] _resolve_agent_type: agent_id={agent_id} source=jsonl_attribution result={attribution_candidate}",
                    file=sys.stderr,
                )
                return attribution_candidate
    except Exception:
        pass

    # Fallback 5: Defaults to "worker" if agentId is in hex format and subagents_dir is given.
    if agent_id and subagents_dir:
        import re
        if re.fullmatch(r"[0-9a-f]{10,}", agent_id):
            print(
                f"[usage-sync] _resolve_agent_type: agent_id={agent_id} source=hex_default result=worker",
                file=sys.stderr,
            )
            return "worker"

    return None


def cmd_batch() -> None:
    """Called from finalization.py. Final settlement of usage.json by batch parsing of entire JSONL.

    Read JSON from stdin and parse agent_transcript_path. The input path is worker
    If agent JSONL (parent is ``subagents/``), use that directory directly, otherwise
    Otherwise (e.g. finalization.py passes the orchestrator main session JSONL)
    work_dir → status.json.linked_sessions → ``subagents/`` next to main session JSONL
    Use a fallback path that inverts.
    Agents that have been collected through track are skipped to supplementary mode.
    exit 0 on all error paths (non-blocking principle).
    """
    input_data = _read_stdin_json()

    transcript_path = input_data.get("agent_transcript_path", "")

    work_dir = _find_work_dir()
    if not work_dir:
        sys.exit(0)

    # Determine subagents_dir:
    #  1) If transcript_path is worker agent JSONL (parent == 'subagents/'), use directly (backwards compatible)
    #  2) For others (main session JSONL or missing), in status.json.linked_sessions in work_dir
    #     Find the main session JSONL and translate it into the <session_id>/subagents/ directory next to it.
    subagents_dir: Optional[str] = None
    if transcript_path and os.path.isfile(transcript_path):
        subagents_dir = _find_subagents_dir(transcript_path)
    if not subagents_dir:
        main_jsonl = _find_main_session_from_status(work_dir)
        if main_jsonl and main_jsonl.endswith(".jsonl"):
            session_dir = main_jsonl[: -len(".jsonl")]
            candidate = os.path.join(session_dir, "subagents")
            if os.path.isdir(candidate):
                subagents_dir = candidate
    if not subagents_dir or not os.path.isdir(subagents_dir):
        print("[usage-sync] subagents directory not found", file=sys.stderr)
        sys.exit(0)

    usage_file = os.path.join(work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not acquire_lock(lock_dir, max_wait=10):
        print("[usage-sync] WARNING: Could not acquire lock", file=sys.stderr)
        sys.exit(0)

    try:
        usage_data = _load_usage(usage_file)
        agent_map = usage_data.get("_agent_map", {})

        # subagents/ Enumerate all my agent-*.jsonl files
        agent_files = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
        if not agent_files:
            print("[usage-sync] No agent JSONL files found", file=sys.stderr)
            release_lock(lock_dir)
            sys.exit(0)

        # JSONL parsing for each agent (complementary mode: skip agents that have been collected through track)
        worker_tokens: dict[str, dict[str, int]] = {}
        skipped_agents: list[str] = []
        for agent_file in agent_files:
            a_type = _resolve_agent_type(agent_file, agent_map, subagents_dir=subagents_dir)
            if not a_type:
                print(
                    f"[usage-sync] WARNING: Could not identify agent_type for {os.path.basename(agent_file)}",
                    file=sys.stderr,
                )
                continue

            # Skip supplementary mode: non-worker agents collected by track
            if a_type != "worker":
                existing = usage_data["agents"].get(a_type)
                if isinstance(existing, dict) and existing.get("method") == "subagent_transcript":
                    skipped_agents.append(a_type)
                    continue

            tokens = parse_jsonl_usage(agent_file)
            if not tokens:
                continue

            tokens["method"] = "jsonl_full_parse"

            if a_type == "worker":
                basename = os.path.basename(agent_file)
                agent_id = basename[len("agent-"):-len(".jsonl")] if basename.startswith("agent-") else basename
                worker_tokens[agent_id] = tokens
            else:
                usage_data["agents"][a_type] = tokens

        # Worker token processing (complementary mode: workers that have been collected through track are skipped)
        if worker_tokens:
            if "workers" not in usage_data["agents"]:
                usage_data["agents"]["workers"] = {}

            existing_workers = usage_data["agents"]["workers"]
            pending = usage_data.get("_pending_workers", {})

            # agent_to_task: _pending_workers If the value (task_id) is the key and
            # Process all cases where agent_id is the key.
            # _pending_workers can be in the form {task_id: task_id} or {agent_id: task_id}.
            # If agent_id is a hex string and pending is in the form {task_id: task_id}:
            # Mapping the value (task_id) list of pending and the agent_id list of worker_tokens in order.
            # agent_to_task: direct mapping if pkey of _pending_workers is actual agent_id
            # Non-worker agent types (validator, reporter, etc.) are excluded from worker queue mapping.
            agent_to_task: dict[str, str] = {}
            non_worker_pending_keys: list[str] = []
            for pkey, ptid in pending.items():
                if pkey in NON_WORKER_AGENT_TYPES or ptid in NON_WORKER_AGENT_TYPES:
                    non_worker_pending_keys.append(pkey)
                    print(
                        f"[usage-sync] INFO: cmd_batch skipped non-worker pending entry '{pkey}' -> '{ptid}'",
                        file=sys.stderr,
                    )
                    continue
                agent_to_task[pkey] = ptid

            for nw_key in non_worker_pending_keys:
                del pending[nw_key]

            # Add only pending tasks of the form task_id=task_id to the unassigned queue.
            # Fallback queue for sequential mapping when agent_id is a hex string.
            already_mapped_tasks = set(existing_workers.keys())
            unassigned_queue: list[str] = [
                ptid for pkey, ptid in pending.items()
                if pkey == ptid and ptid not in already_mapped_tasks
            ]

            for agent_id, tokens in worker_tokens.items():
                # First: try mapping directly from agent_to_task
                task_id = agent_to_task.get(agent_id)

                if not task_id:
                    # If agent_id is a hex string: assigned in order from unassigned_queue
                    if unassigned_queue:
                        task_id = unassigned_queue.pop(0)
                        print(
                            f"[usage-sync] INFO: batch agent_id '{agent_id}' mapped to task_id '{task_id}' via queue",
                            file=sys.stderr,
                        )

                key = task_id if task_id else agent_id
                # Skip supplementary mode: worker tasks collected as tracks
                if isinstance(existing_workers.get(key), dict) and existing_workers[key].get("method") == "subagent_transcript":
                    skipped_agents.append(f"worker/{key}")
                    continue
                # Duplicate check: Skip if existing item with same 4 token field signature
                _token_fields = ("input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens")
                existing_entry = existing_workers.get(key)
                if isinstance(existing_entry, dict):
                    new_sig = tuple(tokens.get(f, 0) for f in _token_fields)
                    existing_sig = tuple(existing_entry.get(f, 0) for f in _token_fields)
                    if new_sig == existing_sig:
                        print(
                            f"[usage-sync] INFO: duplicate token signature detected for worker/{key}, skipping",
                            file=sys.stderr,
                        )
                        skipped_agents.append(f"worker/{key}(duplicate)")
                        continue
                existing_workers[key] = tokens

        # Skipped agent list log
        if skipped_agents:
            print(f"[usage-sync] batch: skipped already-tracked: {skipped_agents}", file=sys.stderr)

        # Main session JSONL parsing (orchestrator token)
        main_jsonl = _find_main_session_jsonl(subagents_dir)
        if not main_jsonl:
            main_jsonl = _find_main_session_from_status(work_dir)

        if main_jsonl:
            orc_tokens = parse_jsonl_usage(main_jsonl)
            if orc_tokens:
                orc_tokens["method"] = "jsonl_full_parse"
                usage_data["agents"]["orchestrator"] = orc_tokens
        else:
            print("[usage-sync] WARNING: Main session JSONL not found", file=sys.stderr)

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, usage_data)
        _append_log(work_dir, "INFO", "Usage batch finalized")
    except Exception as e:
        print(f"[usage-sync] WARNING: batch error: {e}", file=sys.stderr)
    finally:
        release_lock(lock_dir)


# =============================================================================
# main
# =============================================================================

def main() -> None:
    """CLI entry point. Parse and execute subcommands (track/batch).

    If there is no subcommand, track is used as the default (backwards compatible).
    Unknown subcommands exit 0 (non-blocking principle).
    """
    # Subcommand parsing. If there are no arguments, track (backwards compatible)
    subcmd = sys.argv[1] if len(sys.argv) > 1 else "track"

    if subcmd == "track":
        cmd_track()
    elif subcmd == "batch":
        cmd_batch()
    else:
        print(f"[usage-sync] Unknown subcommand: {subcmd} (track|batch)", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()

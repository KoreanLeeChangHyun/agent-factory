"""Workflow hook 공통 헬퍼.

active workflow 탐색, status.json 읽기/쓰기, flow-* wrapper 호출,
hook_fail 잔재 기록을 제공한다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from typing import Any

_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import scan_active_workflows, resolve_project_root, load_json_file  # noqa: E402

ALLOWED_SUBAGENT_TYPES: frozenset[str] = frozenset({
    "worker-opus",
    "worker-sonnet",
    "explorer",
    "explorer-file-haiku",
    "explorer-file-sonnet",
    "explorer-web-sonnet",
    "planner",
    "reporter",
    "validator",
})

WORKER_SUBAGENT_TYPES: frozenset[str] = frozenset({
    "worker-opus",
    "worker-sonnet",
    "explorer",
    "explorer-file-haiku",
    "explorer-file-sonnet",
    "explorer-web-sonnet",
})

TERMINAL_PHASES_LOCAL: frozenset[str] = frozenset({"DONE", "FAILED", "STALE", "CANCELLED"})


def project_root() -> str:
    """프로젝트 루트 절대 경로를 반환한다."""
    return resolve_project_root()


def bin_path(name: str) -> str:
    """.claude-organic/bin/<name> 절대 경로를 반환한다."""
    return os.path.join(project_root(), ".claude-organic", "bin", name)


def find_active_workflow(ticket_id: str | None) -> tuple[str, str, dict] | tuple[None, None, None]:
    """active workflow 의 (registryKey, workDir_abs, status_dict) 를 반환한다.

    ticket_id 가 주어지면 .context.json 의 ticketNumber 와 매칭되는 항목 우선.
    매칭이 없거나 ticket_id 가 None 이면 updated_at 최신순으로 첫 active 항목 반환.
    """
    try:
        root = project_root()
        workflows = scan_active_workflows(project_root=root)
        if not workflows:
            return None, None, None

        candidates: list[tuple[str, str, dict, dict]] = []
        for key, entry in workflows.items():
            rel = entry.get("workDir", "")
            abs_wd = rel if os.path.isabs(rel) else os.path.join(root, rel)
            status_path = os.path.join(abs_wd, "status.json")
            ctx_path = os.path.join(abs_wd, ".context.json")
            status = load_json_file(status_path) or {}
            ctx = load_json_file(ctx_path) or {}
            candidates.append((key, abs_wd, status, ctx))

        if ticket_id:
            for key, abs_wd, status, ctx in candidates:
                if ctx.get("ticketNumber") == ticket_id:
                    return key, abs_wd, status

        candidates.sort(key=lambda t: t[2].get("updated_at", ""), reverse=True)
        if candidates:
            key, abs_wd, status, _ctx = candidates[0]
            return key, abs_wd, status
    except Exception:  # noqa: BLE001
        pass
    return None, None, None


def current_phase(status: dict) -> str:
    """status.json dict 에서 workflow_phase 를 반환한다."""
    if not isinstance(status, dict):
        return "NONE"
    return str(status.get("workflow_phase") or status.get("step") or status.get("phase") or "NONE")


def phase_zero_done(status: dict) -> bool:
    """Phase 0 (skillmap) 수행 여부를 task_events 로 추정한다."""
    if not isinstance(status, dict):
        return False
    return bool(status.get("phase_zero_done"))


def mark_phase_zero_done(status_path: str) -> None:
    """status.json 에 phase_zero_done=true 를 박는다."""
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["phase_zero_done"] = True
        data["updated_at"] = _now_iso()
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        pass


def record_hook_fail(work_dir_abs: str, phase: str, command: str, exit_code: int, stderr: str) -> None:
    """status.json 의 hook_fail 필드에 실패 정보를 기록한다.

    advisory only — 다음 hook 또는 LLM 인지용. blocking 미수행.
    """
    try:
        status_path = os.path.join(work_dir_abs, "status.json")
        if not os.path.isfile(status_path):
            return
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fails = data.setdefault("hook_fails", [])
        fails.append({
            "phase": phase,
            "command": command,
            "exit_code": exit_code,
            "stderr": (stderr or "")[:500],
            "at": _now_iso(),
        })
        if len(fails) > 20:
            data["hook_fails"] = fails[-20:]
        data["updated_at"] = _now_iso()
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        pass


def pop_hook_fails(work_dir_abs: str) -> list[dict]:
    """status.json 의 hook_fails 를 읽고 비운다."""
    try:
        status_path = os.path.join(work_dir_abs, "status.json")
        if not os.path.isfile(status_path):
            return []
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fails = data.get("hook_fails") or []
        if fails:
            data["hook_fails"] = []
            data["updated_at"] = _now_iso()
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return list(fails)
    except Exception:  # noqa: BLE001
        return []


def run_wrapper(args: list[str], work_dir_abs: str | None, phase: str, timeout: int = 30) -> tuple[int, str, str]:
    """flow-* wrapper 를 호출하고 (exit_code, stdout, stderr) 를 반환한다.

    실패 시 hook_fail 자동 기록.
    """
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root(),
        )
        if proc.returncode != 0 and work_dir_abs:
            record_hook_fail(work_dir_abs, phase, " ".join(args), proc.returncode, proc.stderr)
        return proc.returncode, proc.stdout, proc.stderr
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as e:
        if work_dir_abs:
            record_hook_fail(work_dir_abs, phase, " ".join(args), -1, str(e))
        return -1, "", str(e)


def extract_task_meta(prompt: str) -> dict[str, str]:
    """Task prompt 에서 taskId, phase, workId 등을 추출한다.

    SKILL.md 컨벤션: `prompt="command: X, workId: 123456, taskId: W01, phase: 2, ..."`
    """
    meta: dict[str, str] = {}
    if not isinstance(prompt, str):
        return meta
    for key in ("taskId", "phase", "workId", "command"):
        m = re.search(rf"\b{key}\s*[:=]\s*([A-Za-z0-9_+\-./]+)", prompt)
        if m:
            meta[key] = m.group(1).strip(",;.")
    return meta


def extract_subagent_type(tool_input: dict) -> str:
    """tool_input 에서 subagent_type 을 추출한다."""
    if not isinstance(tool_input, dict):
        return ""
    val = tool_input.get("subagent_type", "")
    if val:
        return str(val).strip()
    prompt = tool_input.get("prompt", "")
    if isinstance(prompt, str):
        m = re.search(r'subagent_type\s*=\s*["\']([^"\']+)["\']', prompt)
        if m:
            return m.group(1).strip()
    return ""


def get_ticket_id_from_env() -> str | None:
    """워크플로우 세션 환경변수에서 ticket id 를 읽는다."""
    val = os.environ.get("_WF_TICKET_ID", "").strip()
    return val or None


def is_workflow_session() -> bool:
    """현재 프로세스가 워크플로우 세션인지 _WF_SESSION_TYPE 으로 판별한다."""
    return os.environ.get("_WF_SESSION_TYPE", "") == "workflow"


def is_orchestration_enabled() -> bool:
    """HOOK_WORKFLOW_ORCHESTRATION 플래그 활성 여부."""
    val = os.environ.get("HOOK_WORKFLOW_ORCHESTRATION", "").strip().lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    return _read_settings_flag("HOOK_WORKFLOW_ORCHESTRATION", default=False)


def _read_settings_flag(key: str, default: bool) -> bool:
    """.claude-organic/.settings 에서 단일 플래그 값을 읽는다."""
    try:
        settings_path = os.path.join(project_root(), ".claude-organic", ".settings")
        if not os.path.isfile(settings_path):
            return default
        with open(settings_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() != key:
                    continue
                val = v.strip().lower()
                if val in ("true", "1", "yes", "on"):
                    return True
                if val in ("false", "0", "no", "off"):
                    return False
                return default
    except Exception:  # noqa: BLE001
        pass
    return default


def emit_allow(reason: str = "워크플로우 hook 통과.") -> None:
    """PreToolUse allow JSON 을 stdout 에 출력한다."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def emit_deny(reason: str) -> None:
    """PreToolUse deny JSON 을 stdout 에 출력한다.

    general.md PreToolUse Hook 출력 schema MUST 룰 정합 — updatedInput 필드 미포함.
    """
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def format_hook_fail_alert(fails: list[dict]) -> str:
    """hook_fails 잔재를 LLM 가시 안내 문자열로 정형한다."""
    lines = [
        "[WORKFLOW HOOK FAIL RESIDUE] 직전 PreToolUse/PostToolUse hook 에서 결정론 wrapper 호출이 "
        f"{len(fails)}건 실패했습니다. status.json.hook_fails[] 참고. 본 deny 는 1회 통보용 —"
        " 같은 Task 를 재호출하면 통과합니다 (잔재 비움).",
    ]
    for f in fails[-5:]:
        lines.append(
            f"  - phase={f.get('phase')} exit={f.get('exit_code')} "
            f"cmd={(f.get('command') or '')[:160]} stderr={(f.get('stderr') or '')[:160]}"
        )
    return "\n".join(lines)


def log_workflow_event(work_dir_abs: str, message: str) -> None:
    """workflow.log 에 한 줄을 기록한다."""
    try:
        log_path = os.path.join(work_dir_abs, "workflow.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:  # noqa: BLE001
        pass


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

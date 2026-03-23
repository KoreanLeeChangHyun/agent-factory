#!/usr/bin/env -S python3 -u
"""워크플로우 상태 일괄 업데이트 스크립트 (라우터).

비즈니스 로직은 4개 하위 모듈에 위임하고, 이 파일은 CLI 인자 파싱과
핸들러 디스패치만 담당한다.

모듈 분할:
    state_machine.py: 상태 전이, 컨텍스트 갱신, 세션 링크
    usage_tracker.py: 사용량 추적, 정산, .usage.md 관리
    task_tracker.py: 태스크 상태 관리
    env_manager.py: 환경변수 관리

사용법:
  update_state.py context <registryKey> <agent>
  update_state.py status <registryKey> <toPhase>
  update_state.py both <registryKey> <agent> <toPhase>
  update_state.py link-session <registryKey> <sessionId>
  update_state.py usage-pending <registryKey> <id1> [id2] ...
  update_state.py usage <registryKey> <agent_name> <input_tokens> <output_tokens> [cache_creation] [cache_read] [task_id]
  update_state.py usage-finalize <registryKey>
  update_state.py usage-regenerate (no args)
  update_state.py env <registryKey> set|unset <KEY> [VALUE]
  update_state.py task-status <registryKey> <status> <id1> [id2] ...
  update_state.py task-status <registryKey> <taskId> <status>  (레거시)
  update_state.py task-start <registryKey> <id1> [id2] ...

종료 코드:
  항상 0 (비차단 원칙)
"""
from __future__ import annotations

import os
import sys

_scripts_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import STEP_COLORS, load_json_file, resolve_abs_work_dir, resolve_project_root  # noqa: E402
from flow.flow_logger import append_log as _append_log  # noqa: E402
from flow.state_machine import _print_state_banner, update_context, update_status, link_session  # noqa: E402
from flow.usage_tracker import usage_pending, usage_record, usage_finalize, usage_regenerate  # noqa: E402
from flow.task_tracker import update_task_status  # noqa: E402
from flow.env_manager import env_manage  # noqa: E402

# 하위 호환 별칭
PHASE_COLORS: dict[str, str] = STEP_COLORS

SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT: str = resolve_project_root()

# 핸들러 공통 반환 타입: (banner_from, banner_to, banner_ok)
_HandlerResult = tuple[str | None, str | None, bool]
_NO_BANNER: _HandlerResult = (None, None, False)


def resolve_paths(work_dir_arg: str) -> tuple[str, str, str]:
    """workDir 인자를 절대 경로로 해석하고 관련 경로들을 반환한다.

    Args:
        work_dir_arg: 워크 디렉터리 인자 (registryKey 또는 절대 경로)

    Returns:
        (abs_work_dir, local_context, status_file) 3-tuple.
    """
    abs_work_dir: str = resolve_abs_work_dir(work_dir_arg, PROJECT_ROOT)
    local_context: str = os.path.join(abs_work_dir, ".context.json")
    status_file: str = os.path.join(abs_work_dir, "status.json")
    return abs_work_dir, local_context, status_file


_VALID_MODES: frozenset[str] = frozenset({
    "context", "status", "both", "link-session",
    "usage-pending", "usage", "usage-finalize", "usage-regenerate",
    "env", "task-status", "task-start",
})


def _read_current_step(status_file: str) -> str:
    """status.json에서 현재 step을 읽어 반환한다."""
    _data = load_json_file(status_file) if os.path.isfile(status_file) else None
    if isinstance(_data, dict):
        return _data.get("step") or _data.get("phase", "NONE")
    return "NONE"


def _check_banner_ok(result: str) -> bool:
    """상태 전이 결과에서 배너 표시 여부를 판단한다."""
    return not any(x in result for x in ("blocked", "skipped", "failed"))


def _handle_context(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """context 모드: .context.json agent 필드를 갱신한다."""
    agent: str = sys.argv[3] if len(sys.argv) > 3 else ""
    if not agent:
        print("[WARN] context 모드: agent 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    update_context(local_context, agent)
    return _NO_BANNER


def _handle_status(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """status 모드: status.json FSM 상태를 전이한다."""
    to_step: str = sys.argv[3] if len(sys.argv) > 3 else ""
    if not to_step:
        print("[WARN] status 모드: toPhase 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    from_step: str = _read_current_step(status_file)
    result: str = update_status(abs_work_dir, status_file, from_step, to_step)
    return from_step, to_step, _check_banner_ok(result)


def _handle_both(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """both 모드: context 갱신 + status 전이를 함께 수행한다."""
    agent: str = sys.argv[3] if len(sys.argv) > 3 else ""
    to_step: str = sys.argv[4] if len(sys.argv) > 4 else ""
    if not agent or not to_step:
        print("[WARN] both 모드: agent, toPhase 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    from_step: str = _read_current_step(status_file)
    update_context(local_context, agent)
    result: str = update_status(abs_work_dir, status_file, from_step, to_step)
    banner_ok: bool = _check_banner_ok(result)
    if banner_ok:
        _append_log(abs_work_dir, "INFO", f"STATE_BOTH: agent={agent} step={from_step}->{to_step}")
    return from_step, to_step, banner_ok


def _handle_link_session(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """link-session 모드: status.json에 세션 ID를 등록한다."""
    session_id: str = sys.argv[3] if len(sys.argv) > 3 else ""
    if not session_id:
        print("[WARN] link-session 모드: sessionId 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    link_session(status_file, session_id)
    return _NO_BANNER


def _handle_usage_pending(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """usage-pending 모드: _pending_workers에 에이전트-태스크 매핑을 등록한다."""
    task_ids: list[str] = sys.argv[3:]
    if not task_ids:
        print("[WARN] usage-pending 모드: task_id 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    seen: set[str] = set()
    for tid in task_ids:
        if tid not in seen:
            seen.add(tid)
            usage_pending(abs_work_dir, tid, tid)
    return _NO_BANNER


def _handle_usage(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """usage 모드: 에이전트별 토큰 데이터를 기록한다."""
    agent_name: str = sys.argv[3] if len(sys.argv) > 3 else ""
    input_tokens: str = sys.argv[4] if len(sys.argv) > 4 else ""
    output_tokens: str = sys.argv[5] if len(sys.argv) > 5 else ""
    cache_creation: str = sys.argv[6] if len(sys.argv) > 6 else "0"
    cache_read: str = sys.argv[7] if len(sys.argv) > 7 else "0"
    task_id_arg: str = sys.argv[8] if len(sys.argv) > 8 else ""
    if not agent_name or not input_tokens or not output_tokens:
        print("[WARN] usage 모드: agent_name, input_tokens, output_tokens 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    usage_record(abs_work_dir, agent_name, input_tokens, output_tokens, cache_creation, cache_read, task_id_arg)
    return _NO_BANNER


def _handle_usage_finalize(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """usage-finalize 모드: totals를 계산하고 .usage.md를 갱신한다."""
    usage_finalize(abs_work_dir)
    return _NO_BANNER


def _handle_usage_regenerate(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """usage-regenerate 모드: .usage.md를 전체 재생성한다."""
    usage_regenerate()
    return _NO_BANNER


def _handle_env(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """env 모드: .claude.env 환경변수를 set/unset한다."""
    action: str = sys.argv[3] if len(sys.argv) > 3 else ""
    key: str = sys.argv[4] if len(sys.argv) > 4 else ""
    value: str = sys.argv[5] if len(sys.argv) > 5 else ""
    if not action or not key:
        print("[WARN] env 모드: action(set|unset), KEY 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    env_manage(action, key, value)
    return _NO_BANNER


def _handle_task_start(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """task-start 모드: 태스크를 running으로 설정하고 usage-pending을 등록한다."""
    task_ids: list[str] = sys.argv[3:]
    if not task_ids:
        print("[WARN] task-start 모드: task_id 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    seen: set[str] = set()
    for tid in task_ids:
        if tid not in seen:
            seen.add(tid)
            update_task_status(status_file, tid, "running")
            usage_pending(abs_work_dir, tid, tid)
    return _NO_BANNER


def _handle_task_status(abs_work_dir: str, local_context: str, status_file: str) -> _HandlerResult:
    """task-status 모드: 복수/레거시 형식으로 태스크 상태를 기록한다."""
    _TS_VALID_STATUSES: set[str] = {"pending", "running", "completed", "failed", "in_progress"}
    arg3: str = sys.argv[3] if len(sys.argv) > 3 else ""
    arg4: str = sys.argv[4] if len(sys.argv) > 4 else ""
    if not arg3:
        print("[WARN] task-status 모드: status, task_id 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    if arg3 in _TS_VALID_STATUSES:
        for tid in sys.argv[4:]:
            update_task_status(status_file, tid, arg3)
    else:
        update_task_status(status_file, arg3, arg4)
    return _NO_BANNER


_HANDLERS: dict[str, object] = {
    "context": _handle_context,
    "status": _handle_status,
    "both": _handle_both,
    "link-session": _handle_link_session,
    "usage-pending": _handle_usage_pending,
    "usage": _handle_usage,
    "usage-finalize": _handle_usage_finalize,
    "usage-regenerate": _handle_usage_regenerate,
    "env": _handle_env,
    "task-status": _handle_task_status,
    "task-start": _handle_task_start,
}


def main() -> None:
    """커맨드라인 인자를 파싱하여 적절한 핸들러를 디스패치한다."""
    if len(sys.argv) < 3:
        print(
            "[WARN] 사용법: update_state.py context|status|both|link-session|"
            "usage-pending|usage|usage-finalize|usage-regenerate|env|task-status|"
            "task-start <workDir> [args...]",
            file=sys.stderr,
        )
        sys.exit(0)

    mode: str = sys.argv[1]
    work_dir_arg: str = sys.argv[2]

    # 인자 순서 자동 교정: argv[1]이 모드가 아니고 argv[2]가 모드인 경우 swap
    if mode not in _VALID_MODES and work_dir_arg in _VALID_MODES:
        mode, work_dir_arg = work_dir_arg, mode
        print(
            f"[WARN] 인자 순서 자동 교정: mode={mode}, workDir={work_dir_arg} "
            f"(올바른 사용법: update_state.py <mode> <workDir> [args...])",
            file=sys.stderr,
        )

    abs_work_dir: str
    local_context: str
    status_file: str
    abs_work_dir, local_context, status_file = resolve_paths(work_dir_arg)

    handler = _HANDLERS.get(mode)
    if handler is None:
        print(
            f"[WARN] 알 수 없는 모드: {mode} (context|status|both|link-session|"
            "usage-pending|usage|usage-finalize|usage-regenerate|env|task-status|"
            "task-start 중 선택)",
            file=sys.stderr,
        )
        print("FAIL", flush=True)
        sys.exit(0)

    _banner_from, _banner_to, _banner_ok = handler(abs_work_dir, local_context, status_file)

    if _banner_ok and _banner_from and _banner_to:
        _print_state_banner(_banner_from, _banner_to, abs_work_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()

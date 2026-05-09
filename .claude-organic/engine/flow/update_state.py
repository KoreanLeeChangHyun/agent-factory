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
  flow-update context <registryKey> <agent>
  flow-update status <registryKey> <toStep>
  flow-update both <registryKey> <agent> <toStep>
  flow-update link-session <registryKey> <sessionId>
  flow-update usage-pending <registryKey> <id>...
  flow-update usage <registryKey> <agent_name> <input_tokens> <output_tokens> [cache_creation] [cache_read] [task_id]
  flow-update usage-finalize <registryKey>
  flow-update usage-regenerate
  flow-update env <registryKey> <set|unset> <key> [value]
  flow-update task-status <registryKey> <status> <id>...
  flow-update task-start <registryKey> <id>...
  flow-update metrics-event <event_type> [--key=value ...]

종료 코드:
  항상 0 (비차단 원칙)
"""
from __future__ import annotations

import argparse
import os
import sys

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import STEP_COLORS, load_json_file, resolve_abs_work_dir, resolve_project_root  # noqa: E402
from flow.cli_utils import build_common_epilog, deprecation_warning, registry_key_type  # noqa: E402
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

# 인자 순서 자동 교정용 모드 집합
_VALID_MODES: frozenset[str] = frozenset({
    "context", "status", "both", "link-session",
    "usage-pending", "usage", "usage-finalize", "usage-regenerate",
    "env", "task-status", "task-start", "metrics-event",
})


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


def _append_fsm_metrics(abs_work_dir: str, from_step: str, to_step: str) -> None:
    """FSM 전이 성공 후 step.end{prev} + step.start{next} 를 metrics.jsonl 에 append 한다.

    실패 시 WARN 출력 후 무시한다 (비차단).

    Args:
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로.
        from_step: 이전 단계 이름 (예: "PLAN").
        to_step: 다음 단계 이름 (예: "WORK").
    """
    try:
        import importlib.util as _ilu
        import time as _time

        _metrics_path = os.path.join(_engine_dir, "flow", "metrics.py")
        if not os.path.isfile(_metrics_path):
            return
        _spec = _ilu.spec_from_file_location("flow.metrics", _metrics_path)
        if _spec is None or _spec.loader is None:
            return
        _metrics_mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_metrics_mod)  # type: ignore[attr-defined]

        # duration 계산: step.start 때 기록한 임시 파일 참조
        _tmp_file = os.path.join(abs_work_dir, f".metrics_step_start_{from_step}.tmp")
        _duration_ms: object = None
        if os.path.isfile(_tmp_file):
            try:
                _start_ms = int(open(_tmp_file).read().strip())
                _end_ms = int(_time.time() * 1000)
                _duration_ms = _end_ms - _start_ms
                os.remove(_tmp_file)
            except Exception:
                _duration_ms = None

        # step.end{prev} — metric event 의 'step' 키는 status.json 'workflow_phase' 와 동일 의미 (metric event schema BC)
        _metrics_mod.append_event(  # type: ignore[attr-defined]
            abs_work_dir,
            "step.end",
            {
                "step": from_step,
                "duration_ms": _duration_ms,
                "outcome": "ok",
                "source": "fsm",
            },
        )
        # step.start{next} + 임시 파일 생성
        _next_tmp = os.path.join(abs_work_dir, f".metrics_step_start_{to_step}.tmp")
        try:
            with open(_next_tmp, "w") as _fp:
                _fp.write(str(int(_time.time() * 1000)))
        except Exception:
            pass
        # step.start{next} — metric event 의 'step' 키는 status.json 'workflow_phase' 와 동일 의미 (metric event schema BC)
        _metrics_mod.append_event(  # type: ignore[attr-defined]
            abs_work_dir,
            "step.start",
            {"step": to_step, "source": "fsm"},
        )
    except Exception as _exc:
        import sys as _sys
        print(f"[WARN] _append_fsm_metrics failed: {_exc}", file=_sys.stderr)


def _read_current_step(status_file: str) -> str:
    """status.json에서 현재 step을 읽어 반환한다.

    T-459: workflow_phase 단일 키. step/phase 는 legacy status.json (pre-T-459) 호환 read fallback.
    state_machine.py:update_status() 의 read 패턴과 정합 유지.
    """
    _data = load_json_file(status_file) if os.path.isfile(status_file) else None
    if isinstance(_data, dict):
        return (
            _data.get("workflow_phase")   # T-459 단일 키
            or _data.get("step")          # legacy status.json (pre-T-459) 호환 read fallback
            or _data.get("phase", "NONE") # legacy status.json (pre-T-453) 호환 read fallback
        )
    return "NONE"


def _check_banner_ok(result: str) -> bool:
    """상태 전이 결과에서 배너 표시 여부를 판단한다."""
    return not any(x in result for x in ("blocked", "skipped", "failed"))


# ─── 서브커맨드 핸들러 ───────────────────────────────────────────────────────

def _handle_context(args: argparse.Namespace) -> _HandlerResult:
    """context 모드: .context.json agent 필드를 갱신한다."""
    abs_work_dir, local_context, _status_file = resolve_paths(args.registry_key)
    update_context(local_context, args.agent)
    return _NO_BANNER


def _handle_status(args: argparse.Namespace) -> _HandlerResult:
    """status 모드: status.json FSM 상태를 전이한다."""
    abs_work_dir, _local_context, status_file = resolve_paths(args.registry_key)
    from_step: str = _read_current_step(status_file)
    result: str = update_status(abs_work_dir, status_file, from_step, args.to_step)
    banner_ok = _check_banner_ok(result)
    # FSM 전이 성공 시 step.end{prev} + step.start{next} metrics append (source: "fsm")
    if banner_ok and from_step != args.to_step:
        _append_fsm_metrics(abs_work_dir, from_step, args.to_step)
    return from_step, args.to_step, banner_ok


def _handle_both(args: argparse.Namespace) -> _HandlerResult:
    """both 모드: context 갱신 + status 전이를 함께 수행한다."""
    abs_work_dir, local_context, status_file = resolve_paths(args.registry_key)
    from_step: str = _read_current_step(status_file)
    update_context(local_context, args.agent)
    result: str = update_status(abs_work_dir, status_file, from_step, args.to_step)
    banner_ok: bool = _check_banner_ok(result)
    if banner_ok:
        _append_log(abs_work_dir, "INFO", f"STATE_BOTH: agent={args.agent} step={from_step}->{args.to_step}")
        # FSM 전이 성공 시 step.end{prev} + step.start{next} metrics append (source: "fsm")
        if from_step != args.to_step:
            _append_fsm_metrics(abs_work_dir, from_step, args.to_step)
    return from_step, args.to_step, banner_ok


def _handle_link_session(args: argparse.Namespace) -> _HandlerResult:
    """link-session 모드: status.json에 세션 ID를 등록한다."""
    _abs_work_dir, _local_context, status_file = resolve_paths(args.registry_key)
    link_session(status_file, args.session_id)
    return _NO_BANNER


def _handle_usage_pending(args: argparse.Namespace) -> _HandlerResult:
    """usage-pending 모드: _pending_workers에 에이전트-태스크 매핑을 등록한다."""
    abs_work_dir, _local_context, _status_file = resolve_paths(args.registry_key)
    seen: set[str] = set()
    for tid in args.ids:
        if tid not in seen:
            seen.add(tid)
            usage_pending(abs_work_dir, tid, tid)
    return _NO_BANNER


def _handle_usage(args: argparse.Namespace) -> _HandlerResult:
    """usage 모드: 에이전트별 토큰 데이터를 기록한다."""
    abs_work_dir, _local_context, _status_file = resolve_paths(args.registry_key)
    cache_creation: str = args.cache_creation or "0"
    cache_read: str = args.cache_read or "0"
    task_id_arg: str = args.task_id or ""
    usage_record(abs_work_dir, args.agent_name, args.input_tokens, args.output_tokens, cache_creation, cache_read, task_id_arg)
    return _NO_BANNER


def _handle_usage_finalize(args: argparse.Namespace) -> _HandlerResult:
    """usage-finalize 모드: totals를 계산하고 .usage.md를 갱신한다."""
    abs_work_dir, _local_context, _status_file = resolve_paths(args.registry_key)
    usage_finalize(abs_work_dir)
    return _NO_BANNER


def _handle_usage_regenerate(args: argparse.Namespace) -> _HandlerResult:
    """usage-regenerate 모드: .usage.md를 전체 재생성한다."""
    usage_regenerate()
    return _NO_BANNER


def _handle_env(args: argparse.Namespace) -> _HandlerResult:
    """env 모드: .claude-organic/.settings 환경변수를 set/unset한다."""
    resolve_paths(args.registry_key)  # registryKey 유효성 검증용
    value: str = args.value or ""
    env_manage(args.action, args.key, value)
    return _NO_BANNER


def _handle_task_start(args: argparse.Namespace) -> _HandlerResult:
    """task-start 모드: 태스크를 running으로 설정하고 usage-pending을 등록한다."""
    abs_work_dir, _local_context, status_file = resolve_paths(args.registry_key)
    seen: set[str] = set()
    for tid in args.ids:
        if tid not in seen:
            seen.add(tid)
            update_task_status(status_file, tid, "running")
            usage_pending(abs_work_dir, tid, tid)
    return _NO_BANNER


def _handle_task_status(args: argparse.Namespace) -> _HandlerResult:
    """task-status 모드: 복수/레거시 형식으로 태스크 상태를 기록한다."""
    _TS_VALID_STATUSES: set[str] = {"pending", "running", "completed", "failed", "in_progress"}
    _abs_work_dir, _local_context, status_file = resolve_paths(args.registry_key)

    # status_or_id: 새 형식이면 status, 레거시 형식이면 taskId
    status_or_id: str = args.status_or_id
    rest: list[str] = args.ids or []

    if status_or_id in _TS_VALID_STATUSES:
        # 새 형식: task-status <registryKey> <status> <id1> [id2] ...
        for tid in rest:
            update_task_status(status_file, tid, status_or_id)
    else:
        # 레거시 형식: task-status <registryKey> <taskId> <status>
        legacy_status: str = rest[0] if rest else ""
        update_task_status(status_file, status_or_id, legacy_status)
    return _NO_BANNER


def _handle_metrics_event(args: argparse.Namespace) -> _HandlerResult:
    """metrics-event 모드: metrics.jsonl 에 단일 이벤트를 append 한다.

    banners (flow_step_banner.sh / flow_phase_banner.sh) 가 이 서브커맨드를
    호출하여 step.start / step.end / phase.start / phase.end 이벤트를 기록한다.

    인자 형식:
        flow-update metrics-event <event_type> --key1=value1 --key2=value2 ...

    payload 는 --key=value 형태로 전달되며, 숫자 문자열은 float/int 로 자동 변환한다.
    registry_key 와 work_dir 은 환경변수 또는 .context.json 에서 자동 추출한다.

    비차단: metrics 기록 실패 시 WARN 출력 후 계속 진행한다.
    """
    event_type: str = args.event_type

    # --registry-key / --registry_key 는 kwargs 에서 먼저 추출
    # (REMAINDER 사용으로 named option 이 kwargs 에 섞일 수 있음)
    raw_kwargs: list[str] = list(args.kwargs or [])
    registry_key_from_kwargs: str = ""
    filtered_kwargs: list[str] = []
    for _kv in raw_kwargs:
        _k_part = _kv.lstrip("-").partition("=")[0].replace("-", "_")
        if _k_part in ("registry_key",):
            _v_part = _kv.partition("=")[2]
            if _v_part:
                registry_key_from_kwargs = _v_part
        else:
            filtered_kwargs.append(_kv)

    # --key=value 목록을 payload dict 로 변환
    payload: dict[str, object] = {}
    for kv in filtered_kwargs:
        if "=" in kv:
            k, _, v = kv.partition("=")
            k = k.lstrip("-")
            # 숫자 자동 변환: int 우선 → float 시도
            try:
                payload[k] = int(v)
            except ValueError:
                try:
                    payload[k] = float(v)
                except ValueError:
                    # "true"/"false" → bool 변환
                    if v.lower() == "true":
                        payload[k] = True
                    elif v.lower() == "false":
                        payload[k] = False
                    elif v.lower() == "null":
                        payload[k] = None
                    else:
                        payload[k] = v

    # work_dir 결정: 명시 인자 → kwargs 에서 추출한 값 → 환경변수 순
    registry_key: str = (getattr(args, "registry_key", "") or "").strip()
    if not registry_key:
        registry_key = registry_key_from_kwargs
    if not registry_key:
        registry_key = os.environ.get("_WF_REGISTRY_KEY", "")

    try:
        if registry_key:
            abs_work_dir, _, _ = resolve_paths(registry_key)
        else:
            abs_work_dir = os.environ.get("_WF_WORK_DIR", "")

        if not abs_work_dir:
            print("[WARN] metrics-event: work_dir 결정 불가 (registry_key 미전달)", file=sys.stderr)
            return _NO_BANNER

        # metrics.py 동적 import (worktree / main 저장소 양쪽 호환)
        import importlib.util as _ilu
        _metrics_candidates = [
            os.path.join(_engine_dir, "flow", "metrics.py"),
        ]
        _metrics_mod = None
        for _mc in _metrics_candidates:
            if os.path.isfile(_mc):
                _spec = _ilu.spec_from_file_location("flow.metrics", _mc)
                if _spec and _spec.loader:
                    _metrics_mod = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_metrics_mod)  # type: ignore[attr-defined]
                    break

        if _metrics_mod is None:
            # 정규 import 시도 (sys.path 에 이미 등록된 경우)
            from flow import metrics as _metrics_mod  # type: ignore[no-redef]

        _metrics_mod.append_event(abs_work_dir, event_type, payload)  # type: ignore[attr-defined]
    except Exception as exc:
        print(f"[WARN] metrics-event append failed: {exc}", file=sys.stderr)

    return _NO_BANNER


# ─── argparse 구축 ──────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """argparse 파서와 서브커맨드를 구축하여 반환한다."""
    parser = argparse.ArgumentParser(
        prog="flow-update",
        description="워크플로우 상태 일괄 업데이트 (라우터)",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        title="서브커맨드",
        description="사용 가능한 모드",
        metavar="<subcommand>",
    )

    # --- context ---
    p_context = subparsers.add_parser(
        "context",
        help=".context.json agent 필드 갱신",
        description="context 모드: .context.json의 agent 필드를 갱신한다.",
    )
    p_context.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_context.add_argument("agent", help="에이전트 이름")
    p_context.set_defaults(handler=_handle_context)

    # --- status ---
    p_status = subparsers.add_parser(
        "status",
        help="status.json FSM 상태 전이",
        description="status 모드: status.json FSM 상태를 전이한다.",
    )
    p_status.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_status.add_argument("to_step", metavar="toStep", help="전이할 대상 상태")
    p_status.set_defaults(handler=_handle_status)

    # --- both ---
    p_both = subparsers.add_parser(
        "both",
        help="context 갱신 + status 전이 동시 수행",
        description="both 모드: context 갱신과 status 전이를 함께 수행한다.",
    )
    p_both.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_both.add_argument("agent", help="에이전트 이름")
    p_both.add_argument("to_step", metavar="toStep", help="전이할 대상 상태")
    p_both.set_defaults(handler=_handle_both)

    # --- link-session ---
    p_link = subparsers.add_parser(
        "link-session",
        help="status.json에 세션 ID 등록",
        description="link-session 모드: status.json에 세션 ID를 등록한다.",
    )
    p_link.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_link.add_argument("session_id", metavar="sessionId", help="세션 ID")
    p_link.set_defaults(handler=_handle_link_session)

    # --- usage-pending ---
    p_usage_pending = subparsers.add_parser(
        "usage-pending",
        help="사용량 추적 대상(pending worker) 등록",
        description="usage-pending 모드: _pending_workers에 에이전트-태스크 매핑을 등록한다.",
    )
    p_usage_pending.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_usage_pending.add_argument("ids", nargs="+", metavar="id", help="태스크 ID (복수 가능)")
    p_usage_pending.set_defaults(handler=_handle_usage_pending)

    # --- usage ---
    p_usage = subparsers.add_parser(
        "usage",
        help="에이전트별 토큰 데이터 기록",
        description="usage 모드: 에이전트별 토큰 사용량 데이터를 기록한다.",
    )
    p_usage.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_usage.add_argument("agent_name", metavar="agent_name", help="에이전트 이름")
    p_usage.add_argument("input_tokens", metavar="input_tokens", help="입력 토큰 수")
    p_usage.add_argument("output_tokens", metavar="output_tokens", help="출력 토큰 수")
    p_usage.add_argument("cache_creation", nargs="?", default="0", metavar="cache_creation", help="캐시 생성 토큰 수 (기본값: 0)")
    p_usage.add_argument("cache_read", nargs="?", default="0", metavar="cache_read", help="캐시 읽기 토큰 수 (기본값: 0)")
    p_usage.add_argument("task_id", nargs="?", default="", metavar="task_id", help="태스크 ID (선택)")
    p_usage.set_defaults(handler=_handle_usage)

    # --- usage-finalize ---
    p_usage_finalize = subparsers.add_parser(
        "usage-finalize",
        help="totals 계산 및 .usage.md 갱신",
        description="usage-finalize 모드: totals를 계산하고 .usage.md를 갱신한다.",
    )
    p_usage_finalize.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_usage_finalize.set_defaults(handler=_handle_usage_finalize)

    # --- usage-regenerate ---
    p_usage_regenerate = subparsers.add_parser(
        "usage-regenerate",
        help=".usage.md 전체 재생성",
        description="usage-regenerate 모드: .usage.md를 전체 재생성한다.",
    )
    p_usage_regenerate.set_defaults(handler=_handle_usage_regenerate)

    # --- env ---
    p_env = subparsers.add_parser(
        "env",
        help=".settings 환경변수 관리",
        description="env 모드: .claude-organic/.settings 환경변수를 set/unset한다.",
    )
    p_env.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_env.add_argument("action", choices=["set", "unset"], help="수행할 동작")
    p_env.add_argument("key", metavar="KEY", help="환경변수 키")
    p_env.add_argument("value", nargs="?", default="", metavar="VALUE", help="설정할 값 (set 시 사용)")
    p_env.set_defaults(handler=_handle_env)

    # --- task-status ---
    p_task_status = subparsers.add_parser(
        "task-status",
        help="태스크 상태 일괄 변경",
        description=(
            "task-status 모드: 태스크 상태를 변경한다.\n\n"
            "새 형식: task-status <registryKey> <status> <id1> [id2] ...\n"
            "레거시:  task-status <registryKey> <taskId> <status>"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_task_status.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_task_status.add_argument("status_or_id", metavar="status_or_id", help="상태 (pending|running|completed|failed|in_progress) 또는 레거시 태스크 ID")
    p_task_status.add_argument("ids", nargs="*", metavar="id", help="태스크 ID 목록 (새 형식) 또는 상태 (레거시)")
    p_task_status.set_defaults(handler=_handle_task_status)

    # --- task-start ---
    p_task_start = subparsers.add_parser(
        "task-start",
        help="태스크를 running으로 설정 + usage-pending 등록",
        description="task-start 모드: 태스크를 running으로 설정하고 usage-pending을 등록한다.",
    )
    p_task_start.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS 형식 레지스트리 키")
    p_task_start.add_argument("ids", nargs="+", metavar="id", help="태스크 ID (복수 가능)")
    p_task_start.set_defaults(handler=_handle_task_start)

    # --- metrics-event ---
    p_metrics = subparsers.add_parser(
        "metrics-event",
        help="metrics.jsonl 에 단일 이벤트 append",
        description=(
            "metrics-event 모드: metrics.jsonl 에 이벤트 한 줄을 append 한다.\n\n"
            "사용법: flow-update metrics-event <event_type> [--key=value ...]\n\n"
            "예시:\n"
            "  flow-update metrics-event step.start --step=INIT --source=banner\n"
            "  flow-update metrics-event phase.start --phase_index=1 --total=2\n\n"
            "registry_key 는 선택 인자이며, 미전달 시 _WF_REGISTRY_KEY 환경변수를 사용한다."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_metrics.add_argument(
        "event_type",
        metavar="event_type",
        help="11종 카탈로그 중 하나 (step.start, step.end, phase.start, phase.end, ...)",
    )
    p_metrics.add_argument(
        "kwargs",
        nargs=argparse.REMAINDER,
        metavar="--key=value",
        help="payload 키-값 쌍 (--key=value 형식, 복수 가능)",
    )
    p_metrics.add_argument(
        "--registry-key",
        dest="registry_key",
        default="",
        metavar="registryKey",
        help="YYYYMMDD-HHMMSS 형식 레지스트리 키 (미전달 시 _WF_REGISTRY_KEY 환경변수 사용)",
    )
    p_metrics.set_defaults(handler=_handle_metrics_event)

    return parser


# ─── 하위 호환: 인자 순서 자동 교정 ────────────────────────────────────────────

def _maybe_swap_args(argv: list[str]) -> list[str]:
    """레거시 호출에서 인자 순서가 뒤바뀐 경우 자동 교정한다.

    기존 호출 패턴:
        update_state.py <workDir> <mode> [args...]  (잘못된 순서)
    올바른 패턴:
        update_state.py <mode> <registryKey> [args...]

    argv[1]이 유효 모드가 아니고 argv[2]가 유효 모드인 경우
    두 인자를 교환하고 deprecation 경고를 출력한다.

    Args:
        argv: sys.argv 복사본 (인플레이스 수정 안전).

    Returns:
        교정된 argv 리스트.
    """
    if len(argv) < 3:
        return argv
    arg1, arg2 = argv[1], argv[2]
    if arg1 not in _VALID_MODES and arg2 in _VALID_MODES:
        deprecation_warning(
            f"update_state.py {arg1} {arg2} ... (workDir mode 순서)",
            f"flow-update {arg2} {arg1} ... (mode registryKey 순서)",
        )
        result = argv[:]
        result[1], result[2] = arg2, arg1
        return result
    return argv


# ─── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    """커맨드라인 인자를 파싱하여 적절한 핸들러를 디스패치한다."""
    # 하위 호환: 인자 순서 자동 교정 (deprecated)
    corrected_argv: list[str] = _maybe_swap_args(sys.argv[:])

    parser = _build_parser()

    # argparse가 인식하지 못하는 경우에 대한 안전장치
    # (비차단 원칙: exit 0)
    try:
        args = parser.parse_args(corrected_argv[1:])
    except SystemExit as exc:
        # argparse가 --help나 에러 시 SystemExit을 발생시킴
        # --help는 exit(0), 에러는 exit(2)
        # 비차단 원칙에 따라 에러 시에도 exit(0)으로 통일
        if exc.code == 0:
            sys.exit(0)
        sys.exit(0)

    if not hasattr(args, "handler"):
        parser.print_help(sys.stderr)
        sys.exit(0)

    _banner_from, _banner_to, _banner_ok = args.handler(args)

    if _banner_ok and _banner_from and _banner_to:
        abs_work_dir = resolve_abs_work_dir(args.registry_key, PROJECT_ROOT)
        _print_state_banner(_banner_from, _banner_to, abs_work_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()

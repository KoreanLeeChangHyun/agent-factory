#!/usr/bin/env -S python3 -u
"""SubagentStop event dispatcher.

Dispatches subagent-stop hooks based on HOOK_* flags in .claude-organic/.settings.
Replaces individual wrapper scripts in .claude-organic/hooks/subagent-stop/.

T-455 W04: sentinel 감지 + flow-fail-record 비차단 트리거 분기 추가.
  - HOOK_FAIL_RECORD=true 일 때만 활성 (기본 false — 회귀 0건 보장).
  - 활성 워크플로우 workDir 의 `.workflow-failed` sentinel 검사 →
    `.workflow-failed.recorded` 마커 부재 시 `flow-fail-record record <key>`
    비차단(Popen + DEVNULL + start_new_session=True) 호출.
  - 모든 예외는 WARN 로그만 (워크플로우 로그 또는 stderr) — 기존 usage 추적
    흐름 비차단 보장. T-411 폐기 사례 캐논 준수.
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    load_env_flags,
    dispatch_async,
    scripts_dir,
)


def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """워크플로우 로그에 이벤트를 기록한다."""
    try:
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


def _resolve_fail_record_bin() -> str | None:
    """`.claude-organic/bin/flow-fail-record` 절대 경로를 반환한다.

    PATH 의존을 회피하고 워크트리/메인 리포 양쪽에서 안정 동작하도록
    `CLAUDE_PROJECT_DIR` 환경변수 또는 dispatcher 의 project_root 탐색을
    그대로 활용한다. 실행 가능 파일이 아닌 경우 None.
    """
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if not project_root:
        try:
            # dispatcher 의 project_root 탐색을 재사용 — 워크트리에서도 메인 리포 추적
            from dispatcher import _find_project_root  # noqa: WPS437
            project_root = _find_project_root()
        except Exception:
            project_root = ""

    if not project_root:
        return None
    candidate = os.path.join(
        project_root, ".claude-organic", "bin", "flow-fail-record"
    )
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def _scan_and_trigger_fail_record(flags: dict) -> None:
    """활성 워크플로우 workDir 를 스캔하여 sentinel 감지 시 비차단 트리거.

    조건:
      - `HOOK_FAIL_RECORD` flag 가 .settings 에서 true 로 명시 활성 (기본 false).
      - workDir 에 `.workflow-failed` 가 존재.
      - workDir 에 `.workflow-failed.recorded` 마커가 부재 (중복 호출 차단).
      - `flow-fail-record` 실행 파일이 존재.

    호출 방식:
      `subprocess.Popen([bin, "record", <registry_key>], stdout=DEVNULL,
                        stderr=DEVNULL, start_new_session=True)`
      — 좀비 프로세스/부모 차단 0건 보장.

    회귀 0건 보장:
      - flag 미활성 시 즉시 반환 (스캔 비용 0).
      - 모든 예외는 try/except 로 흡수, hook 본 흐름 차단 0건.

    Args:
        flags: load_env_flags() 결과 dict.
    """
    # 가드 1: flag 명시 활성 여부 (기본 False — 회귀 0건 보장)
    if not flags.get("HOOK_FAIL_RECORD", False):
        return

    # 가드 2: 실행 파일 존재 여부
    bin_path = _resolve_fail_record_bin()
    if bin_path is None:
        return

    # 활성 워크플로우 스캔 (common.scan_active_workflows 재사용)
    try:
        _scripts_path = os.path.normpath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), '..', 'engine'
            )
        )
        if _scripts_path not in sys.path:
            sys.path.insert(0, _scripts_path)
        from common import scan_active_workflows, resolve_project_root  # noqa: PLC0415

        project_root = resolve_project_root()
        workflows = scan_active_workflows(project_root=project_root)
    except Exception as exc:  # noqa: BLE001
        # 스캔 실패는 WARN — 본 흐름 비차단
        sys.stderr.write(
            f"[WARN] subagent-stop fail-record scan failed: {exc}\n"
        )
        return

    if not workflows:
        return

    for registry_key, entry in workflows.items():
        try:
            if not isinstance(entry, dict) or "workDir" not in entry:
                continue
            rel = entry["workDir"]
            abs_wd = (
                rel if os.path.isabs(rel) else os.path.join(project_root, rel)
            )
            if not os.path.isdir(abs_wd):
                continue

            sentinel = os.path.join(abs_wd, ".workflow-failed")
            recorded = os.path.join(abs_wd, ".workflow-failed.recorded")

            # 가드 3: sentinel 부재 → skip
            if not os.path.isfile(sentinel):
                continue

            # 가드 4: 이미 처리된 sentinel → skip (중복 호출 차단)
            if os.path.exists(recorded):
                continue

            # 비차단 호출 — Popen + DEVNULL + start_new_session=True 로 격리
            try:
                subprocess.Popen(
                    [bin_path, "record", registry_key],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                _append_log(
                    abs_wd,
                    "INFO",
                    f"flow-fail-record dispatched (key={registry_key})",
                )
            except OSError as exc:
                _append_log(
                    abs_wd,
                    "WARN",
                    f"flow-fail-record Popen failed: {exc}",
                )
        except Exception as exc:  # noqa: BLE001
            # 개별 entry 처리 실패가 다른 entry 처리를 막지 않도록 보호
            sys.stderr.write(
                f"[WARN] subagent-stop fail-record entry skipped "
                f"(key={registry_key}): {exc}\n"
            )
            continue


def main() -> None:
    """Dispatch subagent-stop hooks for each registered async hook.

    Reads raw stdin data and dispatches async fire-and-forget hooks.
    All hooks in this dispatcher are async; exits with 0 unconditionally.
    """
    stdin_data = sys.stdin.buffer.read()
    flags = load_env_flags()

    # usage-tracker (async)
    dispatch_async(
        'HOOK_USAGE_TRACKER',
        scripts_dir('sync', 'usage_sync.py'),  # subcmd: track (default)
        stdin_data,
        flags=flags,
    )

    # dispatch_async 호출 직후 활성 워크플로우에 로그 기록 (비차단)
    try:
        _scripts_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'engine'))
        if _scripts_path not in sys.path:
            sys.path.insert(0, _scripts_path)
        from common import scan_active_workflows, resolve_project_root
        _project_root = resolve_project_root()
        _workflows = scan_active_workflows(project_root=_project_root)
        if _workflows:
            for _key, _entry in _workflows.items():
                if isinstance(_entry, dict) and "workDir" in _entry:
                    _rel = _entry["workDir"]
                    _abs = os.path.join(_project_root, _rel) if not _rel.startswith("/") else _rel
                    if os.path.isdir(_abs):
                        _append_log(_abs, "INFO", "Subagent stop event dispatched")
                        break
    except Exception:
        pass

    # T-455 W04: sentinel 감지 + flow-fail-record 비차단 트리거
    # HOOK_FAIL_RECORD=true 일 때만 활성. 모든 예외 try/except 로 흡수.
    try:
        _scan_and_trigger_fail_record(flags)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            f"[WARN] _scan_and_trigger_fail_record top-level failure: {exc}\n"
        )

    # usage-jsonl-sync: 워크플로우 종료 시 전체 JSONL 일괄 파싱 (async)
    # finalization.py(flow-finish)에서 직접 호출하므로 subagent-stop에서는 비활성
    # (done 에이전트 제거로 subagent-stop 트리거 경로 사용하지 않음)

    # All hooks are async/fire-and-forget, no exit code aggregation needed
    sys.exit(0)


if __name__ == '__main__':
    main()

"""상태 전이, 컨텍스트 갱신, 세션 링크 모듈.

update_state.py에서 분리된 상태 관련 비즈니스 로직을 제공한다.

책임 범위:
    - 상태 전이 배너 출력 (_print_state_banner)
    - .context.json agent 필드 갱신 (update_context)
    - status.json FSM 상태 전이 (update_status)
    - status.json 세션 링크 관리 (link_session)

주요 함수:
    _print_state_banner: 상태 전이 배너를 2줄 포맷으로 출력
    update_context: .context.json의 agent 필드 갱신
    update_status: status.json 상태 전이 + FSM 검증
    link_session: status.json linked_sessions 배열에 세션 추가
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from typing import Any

# sys.path 보장: scripts/ 디렉터리를 path에 추가
_engine_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import (  # noqa: E402
    atomic_write_json,
    load_json_file,
)
from constants import FSM_TRANSITIONS, KST  # noqa: E402
from flow.flow_logger import append_log as _append_log  # noqa: E402

# history_sync.py 절대 경로
HISTORY_SYNC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sync",
    "history_sync.py",
)


def _print_state_banner(
    from_step: str, to_step: str, abs_work_dir: str = ""
) -> None:
    """상태 전이 배너를 2줄 포맷으로 출력한다.

    Args:
        from_step: 이전 단계 이름 (예: 'PLAN', 'WORK')
        to_step: 다음 단계 이름 (예: 'WORK', 'REPORT')
        abs_work_dir: 워크 디렉터리 절대 경로 (로그 기록용, 빈 문자열이면 로그 생략)
    """
    line1 = "[STATE] 단계 변경"
    line2 = f">> {from_step} -> {to_step}"
    print(line1, flush=True)
    print(line2, flush=True)
    if abs_work_dir:
        _append_log(abs_work_dir, "INFO", line1)
        _append_log(abs_work_dir, "INFO", line2)


def update_context(local_context: str, agent: str) -> str:
    """context.json의 agent 필드만 갱신한다.

    Args:
        local_context: .context.json 파일 절대 경로
        agent: 설정할 에이전트 이름

    Returns:
        처리 결과 문자열. 예: 'context -> agent=orchestrator',
        'context -> skipped (file not found)', 'context -> failed'.
    """
    if not os.path.exists(local_context):
        print(f"[WARN] .context.json not found: {local_context}", file=sys.stderr)
        return "context -> skipped (file not found)"

    try:
        data = load_json_file(local_context)
        if data is None:
            print(f"[WARN] .context.json read failed: {local_context}", file=sys.stderr)
            return "context -> skipped (read failed)"

        data["agent"] = agent
        atomic_write_json(local_context, data)
        _append_log(os.path.dirname(local_context), "INFO", f"Context updated: agent={agent}")
        return f"context -> agent={agent}"
    except Exception as e:
        print(f"[WARN] .context.json update failed ({local_context}): {e}", file=sys.stderr)
        return "context -> failed"


def update_status(
    abs_work_dir: str, status_file: str, from_step: str, to_step: str
) -> str:
    """status.json을 업데이트하고 registry step을 동기화한다.

    FSM 검증 로직:
      1. WORKFLOW_SKIP_GUARD=1 환경변수가 설정된 경우 검증을 건너뜀
      2. current_step 확인: status.json의 현재 step과 from_step이 일치하는지 검증
      3. allowed 확인: FSM_TRANSITIONS(constants.py)에서 현재 mode/from_step에 허용된
         대상 목록을 조회하고 to_step이 포함되어 있는지 검증

    비차단 원칙:
      FSM 검증 실패 시에도 프로세스를 종료하지 않음 (항상 exit 0).

    호출 방식:
      CLI 호출 시 from_step은 status.json에서 자동 읽기.
      라이브러리 호출 시 from_step을 명시적으로 전달 필요.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        status_file: status.json 파일 경로
        from_step: 전이 시작 단계 이름
        to_step: 전이 목표 단계 이름

    Returns:
        처리 결과 문자열. 예: 'status -> PLAN->WORK',
        'status -> FSM guard blocked (reason: ...)',
        'status -> skipped (file not found)', 'status -> failed'.
    """
    skip_guard = os.environ.get("WORKFLOW_SKIP_GUARD", "") == "1"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        _append_log(abs_work_dir, "WARN", f"status.json not found: {status_file}")
        return "status -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            print(f"[WARN] status.json read failed: {status_file}", file=sys.stderr)
            _append_log(abs_work_dir, "WARN", f"status.json read failed: {status_file}")
            return "status -> skipped (read failed)"

        # FSM 전이 검증
        if skip_guard:
            print(
                f"[AUDIT] WORKFLOW_SKIP_GUARD active: {from_step}->{to_step}",
                file=sys.stderr,
                flush=True,
            )
            _append_log(
                abs_work_dir,
                "AUDIT",
                f"WORKFLOW_SKIP_GUARD active: {from_step}->{to_step}",
            )
        else:
            current_step = data.get("step") or data.get("phase", "NONE")
            workflow_mode = data.get("mode", "full").lower()

            # allowed_targets는 두 검증 모두에서 에러 메시지에 필요하므로 미리 조회
            allowed_table = FSM_TRANSITIONS.get(
                workflow_mode, FSM_TRANSITIONS.get("full", {})
            )
            allowed = allowed_table.get(current_step, [])

            if from_step != current_step:
                print(
                    f"[ERROR] FSM guard: from_step mismatch. "
                    f"from_step={from_step}, to_step={to_step}, "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                    file=sys.stderr,
                )
                _append_log(
                    abs_work_dir,
                    "ERROR",
                    f"FSM guard: from_step mismatch. from_step={from_step}, to_step={to_step}, "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                )
                return (
                    f"status -> FSM guard blocked "
                    f"(reason: from_step mismatch, expected={current_step}, got={from_step}, "
                    f"workflow_mode={workflow_mode}, allowed_targets={allowed})"
                )

            if to_step not in allowed:
                print(
                    f"[ERROR] FSM guard: illegal transition {from_step}->{to_step}. "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                    file=sys.stderr,
                )
                _append_log(
                    abs_work_dir,
                    "ERROR",
                    f"FSM guard: illegal transition {from_step}->{to_step}. "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                )
                return (
                    f"status -> FSM guard blocked "
                    f"(reason: illegal transition {from_step}->{to_step}, "
                    f"workflow_mode={workflow_mode}, allowed_targets={allowed})"
                )

        # KST 시간
        kst = KST
        now = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")

        data["step"] = to_step
        data["updated_at"] = now

        if "transitions" not in data:
            data["transitions"] = []
        data["transitions"].append({"from": from_step, "to": to_step, "at": now})

        atomic_write_json(status_file, data)
        _append_log(abs_work_dir, "INFO", f"State transition: {from_step} -> {to_step}")

        # history_sync.py sync 호출 (비차단 원칙: 실패 시 경고만 출력)
        try:
            subprocess.run(
                ["python3", HISTORY_SYNC_PATH, "sync"],
                capture_output=True,
                timeout=30,
            )
        except Exception as e:
            print(f"[WARN] history sync failed: {e}", file=sys.stderr)
            _append_log(abs_work_dir, "WARN", f"history sync failed: {e}")

        # 반환값에는 ANSI 코드 없음 (배너는 _print_state_banner()가 담당)
        result = f"status -> {from_step}->{to_step}"
    except Exception as e:
        print(f"[WARN] status.json update failed: {e}", file=sys.stderr)
        _append_log(abs_work_dir, "WARN", f"status.json update failed: {e}")
        return "status -> failed"

    return result


def link_session(status_file: str, session_id: str) -> str:
    """status.json의 linked_sessions 배열에 세션 ID를 추가한다.

    Args:
        status_file: status.json 파일 경로
        session_id: 등록할 Claude 세션 ID

    Returns:
        처리 결과 문자열. 예: 'link-session -> added: abc123 (total: 2)',
        'link-session -> already linked: abc123',
        'link-session -> skipped (empty)', 'link-session -> failed'.
    """
    if not session_id:
        print("[WARN] link-session: sessionId가 비어있어 무시합니다.", file=sys.stderr)
        return "link-session -> skipped (empty)"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        return "link-session -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            return "link-session -> skipped (read failed)"

        if "linked_sessions" not in data or not isinstance(
            data.get("linked_sessions"), list
        ):
            data["linked_sessions"] = []

        if session_id in data["linked_sessions"]:
            return f"link-session -> already linked: {session_id}"

        data["linked_sessions"].append(session_id)
        atomic_write_json(status_file, data)
        count = len(data["linked_sessions"])
        _append_log(
            os.path.dirname(status_file),
            "INFO",
            f"SESSION_LINKED: sessionId={session_id} total={count}",
        )
        return f"link-session -> added: {session_id} (total: {count})"
    except Exception as e:
        print(f"[WARN] link-session failed: {e}", file=sys.stderr)
        return "link-session -> failed"

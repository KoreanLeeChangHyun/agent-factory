"""worker_return_parser.py - 워커 반환 2줄 형식 파싱 + advisory 경고 emit.

워커(worker-sonnet / worker-opus / explorer 계열)가 반환하는 2줄 형식을 파싱하고,
커밋 누락 시 workflow.log에 [ADVISORY] 경고를 기록한다.

반환 형식 (2줄 규약):
    상태: 성공 | 부분성공 | 실패
    커밋: <7~40자 SHA> | 없음

레거시 1줄 형식 (커밋 라인 없음):
    상태: 성공 | 부분성공 | 실패

설계 원칙:
    - 자동 강제 전이 / kanban move / finalization step skip 절대 금지 (MUST NOT)
    - advisory emit은 비차단 / no-op 분기 — 기존 finalization 흐름에 영향 0
    - "커밋: 없음" 또는 커밋 라인 미제공 시 경고 로그만 emit
    - 사용자 수동 수습 경로 완전 보존:
        flow-merge --force / Board UI 1클릭 commit / /wf -e 재작업
"""

from __future__ import annotations

import re
from typing import Optional

from flow.flow_logger import append_log


# 커밋 라인 정규식: "커밋: <SHA(7~40자 hex)>" 또는 "커밋: 없음"
_COMMIT_LINE_RE = re.compile(r"^커밋:\s*([0-9a-f]{7,40}|없음)\s*$", re.IGNORECASE)

# 상태 라인 정규식: "상태: 성공 | 부분성공 | 실패"
_STATUS_LINE_RE = re.compile(r"^상태:\s*(성공|부분성공|실패)\s*$")


def parse_worker_return(stdout: str) -> tuple[Optional[str], Optional[str]]:
    """워커 반환 stdout을 파싱하여 (status, commit) 튜플을 반환한다.

    2줄 형식 (표준):
        상태: 성공                  → ("성공", None) or ("성공", "abc1234")
        커밋: abc1234               → commit 파싱

    1줄 레거시 형식 (커밋 라인 없음):
        상태: 성공                  → ("성공", None)

    잘못된 형식 (상태 라인 미인식):
                                    → (None, None)

    Args:
        stdout: 워커가 반환한 전체 stdout 문자열.

    Returns:
        (status, commit) 튜플.
          - status: "성공" | "부분성공" | "실패" | None (파싱 실패 시)
          - commit: 7~40자 hex SHA | "없음" | None (커밋 라인 없음 또는 파싱 실패 시)
    """
    if not stdout:
        return (None, None)

    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return (None, None)

    # 첫 번째 상태 라인 파싱
    status_match = _STATUS_LINE_RE.match(lines[0])
    if not status_match:
        return (None, None)

    status: str = status_match.group(1)

    # 두 번째 커밋 라인 파싱 (없으면 legacy 1줄 형식)
    if len(lines) < 2:
        return (status, None)

    commit_match = _COMMIT_LINE_RE.match(lines[1])
    if not commit_match:
        # 두 번째 라인이 있지만 커밋 형식이 아닌 경우 → legacy로 간주
        return (status, None)

    commit: str = commit_match.group(1)
    return (status, commit)


def emit_commit_advisory(
    registry_key: str,
    abs_work_dir: str,
    status: str,
    commit: Optional[str],
) -> None:
    """커밋 누락 시 workflow.log에 [ADVISORY] 경고를 기록한다.

    commit == "없음" 또는 commit is None 인 경우에만 경고를 emit한다.
    commit이 유효한 SHA인 경우 아무 작업도 수행하지 않는다.

    경고 메시지는 사용자 수동 수습 경로를 안내할 뿐,
    상태 강제 전이 / kanban move / finalization step skip 등
    자동 강제 정책을 일절 수행하지 않는다 (MUST NOT).

    사용자 수동 수습 경로 (완전 보존):
        - flow-merge --force <T-NNN>
        - Board UI 1클릭 commit
        - /wf -e 재작업

    Args:
        registry_key: 워크플로우 식별자 (YYYYMMDD-HHMMSS).
        abs_work_dir: workflow.log가 위치하는 절대 경로.
        status: 워커 반환 상태 ("성공" | "부분성공" | "실패").
        commit: 파싱된 커밋 값. 유효 SHA이면 emit 스킵.
    """
    # 유효 SHA이면 advisory 불필요 — no-op
    if commit is not None and commit != "없음":
        return

    commit_repr = commit if commit is not None else "N/A"
    message = (
        f"[ADVISORY] worker returned commit={commit_repr}; "
        f"status={status}; "
        f"사용자 수동 수습 경로 안내 "
        f"(flow-merge --force / Board 1클릭 / /wf -e)"
    )
    # 비차단: append_log는 모든 예외를 조용히 흡수한다
    append_log(abs_work_dir, "WARN", message)


def emit_report_advisory(
    registry_key: str,
    abs_work_dir: str,
    report_path: str,
) -> None:
    """REPORT 단계 종료 후 report.md 디스크 존재 검증 (advisory only).

    T-447: reporter agent가 'Subagents should return findings as text, not write
    report files' SDK 정책에 의해 Write 도구가 차단되는 경우 report.md가 디스크에
    생성되지 않은 채 워크플로우가 정상 완료로 보고되는 회귀를 탐지하기 위한 advisory.

    report.md 파일이 디스크에 존재하지 않을 때만 WARN 로그를 emit한다.
    파일이 존재하면 아무 작업도 수행하지 않는다 (no-op).

    설계 원칙 (T-411 폐지 사례 참조, commit 0c970fa):
        advisory only — 강제 전이 / 자동 회귀 / 자동 차단 절대 금지 (MUST NOT).
        T-411 finalize AND 가드 폐기 사례 인용: 검증 자체가 아니라 자동 강제 전이가
        문제. 본 함수는 WARN 로그 + metrics 이벤트만 emit한다.
        사용자 명시 동의 없이 자동 강제 정책 도입 절대 금지.

    사용자 수동 수습 경로 (완전 보존):
        - 메인 세션에서 work/ 통합하여 report.md 작성 가능
        - Board UI 1클릭 commit
        - /wf -e 재작업

    Args:
        registry_key: 워크플로우 registry key (예: 20260508-191559).
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로. workflow.log 위치.
        report_path: report.md 파일의 절대 경로.
    """
    import os

    # 파일이 존재하면 advisory 불필요 — no-op
    if os.path.isfile(report_path):
        return

    message = (
        f"[ADVISORY] reporter returned without report.md (path={report_path})\n"
        f"- SDK가 서브에이전트의 Write를 차단했을 가능성 (T-446 사례)\n"
        f"- 사용자 수동 수습: 메인 세션에서 work/ 통합하여 report.md 작성 가능"
    )
    # 비차단: append_log는 모든 예외를 조용히 흡수한다
    append_log(abs_work_dir, "WARN", message)

    # metrics 이벤트 emit (try/except 비차단 보호)
    try:
        from flow.metrics import append_event  # noqa: PLC0415

        payload = {
            "report_path": report_path,
            "signal_summary": "reporter returned without report.md disk write",
        }
        append_event(abs_work_dir, "report.missing", payload)
    except Exception:
        # metrics emit 실패는 advisory 자체를 깨뜨리지 않도록 흡수
        pass

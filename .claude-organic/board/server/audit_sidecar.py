"""Audit sidecar — Review 컬럼 티켓 자동 감사 (T-413 Phase 1).

별도 daemon thread 에서 60초 주기로 ``.claude-organic/tickets/review/`` 디렉터리를
스캔한다. ``audit/results/`` 에 최근 결과가 없는 티켓을 발견하면
``audit/auditor.py`` 를 subprocess 로 실행해 T1 정형 검증을 돌린다.

격리:
    auditor.py 는 별도 프로세스로 spawn 되므로 board 서버 메모리/import 그래프와
    완전 분리된다. 사이드카 자체는 subprocess + 표준 라이브러리만 의존한다.

Phase 1 범위:
    Review 컬럼 자동 감사 + 결과 파일 저장.
    SSE audit_result 이벤트 push 는 Phase 3 에서 추가.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

from ._common import logger


_AUDIT_INTERVAL_DEFAULT: float = 60.0
_AUDIT_RECENT_AGE_SECONDS: int = 3600  # 1시간 이내 결과는 재감사 안 함
_AUDIT_SUBPROCESS_TIMEOUT: float = 30.0


def _project_root() -> Path:
    """본 모듈(.claude-organic/board/server/audit_sidecar.py) 기준 project root."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _list_review_tickets(root: Path) -> list[str]:
    """review/ 컬럼의 티켓 번호 목록 (T-NNN)."""
    review_dir = root / ".claude-organic" / "tickets" / "review"
    if not review_dir.is_dir():
        return []
    return sorted(p.stem for p in review_dir.glob("T-*.xml"))


def _newest_audit_age(root: Path, ticket_number: str) -> Optional[float]:
    """audit/results/T-NNN-*.json 중 가장 최근 파일의 age(초). 없으면 None."""
    results_dir = root / ".claude-organic" / "audit" / "results"
    if not results_dir.is_dir():
        return None
    matches = list(results_dir.glob(f"{ticket_number}-*.json"))
    if not matches:
        return None
    newest_mtime = max(p.stat().st_mtime for p in matches)
    return time.time() - newest_mtime


def _run_audit(root: Path, ticket_number: str) -> None:
    """auditor.py 를 subprocess 로 실행 (격리)."""
    auditor_path = root / ".claude-organic" / "audit" / "auditor.py"
    if not auditor_path.is_file():
        logger.warning("[audit-sidecar] auditor.py not found: %s", auditor_path)
        return
    try:
        result = subprocess.run(
            ["python3", str(auditor_path), ticket_number, "--tier", "1"],
            capture_output=True,
            timeout=_AUDIT_SUBPROCESS_TIMEOUT,
            text=True,
        )
        verdict = "PASS" if result.returncode == 0 else "FAIL"
        logger.info("[audit-sidecar] %s %s", ticket_number, verdict)
        if result.returncode != 0 and result.stderr:
            logger.warning(
                "[audit-sidecar] %s stderr: %s",
                ticket_number,
                result.stderr.strip()[:200],
            )
    except subprocess.TimeoutExpired:
        logger.warning("[audit-sidecar] %s TIMEOUT (%.0fs)", ticket_number, _AUDIT_SUBPROCESS_TIMEOUT)
    except Exception as exc:
        logger.warning("[audit-sidecar] %s ERROR %s", ticket_number, exc)


def review_audit_loop(interval: float = _AUDIT_INTERVAL_DEFAULT) -> None:
    """Review 컬럼의 미감사 티켓을 주기적으로 자동 감사하는 daemon 루프."""
    root = _project_root()
    while True:
        try:
            tickets = _list_review_tickets(root)
            for ticket_number in tickets:
                age = _newest_audit_age(root, ticket_number)
                if age is None or age >= _AUDIT_RECENT_AGE_SECONDS:
                    _run_audit(root, ticket_number)
        except Exception as exc:
            # 비차단: 루프 자체는 어떤 예외에도 죽지 않는다.
            logger.warning("[audit-sidecar] loop error %s", exc)
        time.sleep(interval)

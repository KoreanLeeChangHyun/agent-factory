#!/usr/bin/env -S python3 -u
"""failure_handler.py - 워크플로우 단계별 실패 처리 단일 진실 공급원.

T-455: retry/sentinel/flow-fail-record 인프라.

본 모듈은 워크플로우의 phase (INIT/PLAN/WORK/VALIDATE/REPORT) 실패 시점에
호출되어 다음을 처리한다:

  1. `<workDir>/.workflow-failed` sentinel 파일 생성 (idempotent)
  2. `<workDir>/retry-context.json` 5필드 갱신 (atomic + locked)
  3. retry 가능 여부 판정 (`PHASE_RETRY_MAX` vs `retry_count`)
  4. CLI 진입점 (`record` 서브커맨드) — `bin/flow-fail-record` 가 위임

5개 핵심 API:
  - create_sentinel(work_dir, registry_key, phase, *, error)
  - record_failure(work_dir, phase, error, hint)
  - update_retry_context(work_dir, phase, error, hint)
  - is_retry_available(work_dir, phase)
  - load_retry_context(work_dir)

회귀 0건 보장 (MUST):
  - 모든 함수는 비차단. 예외 발생 시 stderr WARN 로그만 출력하고 호출자 흐름 차단 0건
  - sentinel/recorded 마커는 단방향 (생성만, 삭제 안 함). 정리는 finalization 영역

    누락 자동 검출 로직 절대 추가 금지

CLI 사용법:
  python3 failure_handler.py record <registry_key> [--phase PHASE]
                                                   [--error TEXT]
                                                   [--hint TEXT]
                                                   [--work-dir PATH]

종료 코드:
  0  성공 (또는 비차단 무시)
  1  치명적 입력 오류 (registry_key 누락 등) — 호출자가 명시적으로 처리할 때만 발생
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# -- sys.path 보장: 직접 실행될 때 engine/ 디렉터리 등록 --
_engine_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import (  # noqa: E402
    acquire_lock,
    atomic_write_json,
    load_json_file,
    release_lock,
    resolve_abs_work_dir,
    resolve_project_root,
)
from constants import (  # noqa: E402
    PHASE_RETRY_MAX,
    WORKFLOW_RETRY_PROMPT_N,
)

# =============================================================================
# 상수
# =============================================================================

VALID_PHASES: frozenset[str] = frozenset(
    {"INIT", "PLAN", "WORK", "VALIDATE", "REPORT"}
)

SENTINEL_FILENAME: str = ".workflow-failed"
SENTINEL_RECORDED_FILENAME: str = ".workflow-failed.recorded"
RETRY_CONTEXT_FILENAME: str = "retry-context.json"
RETRY_CONTEXT_LOCK_FILENAME: str = ".retry-context.lock"

# 직전 실패 사유 텍스트 최대 길이 (4KB)
LAST_ERROR_MAX_BYTES: int = 4096

KST_TZ: timezone = timezone(timedelta(hours=9))


# =============================================================================
# RetryContext dataclass
# =============================================================================


@dataclass
class RetryContext:
    """retry-context.json 5필드 영속 모델.

    Attributes:
        phase: 직전 실패 phase 식별자. INIT/PLAN/WORK/VALIDATE/REPORT 중 하나.
        retry_count: 같은 phase 면 +1, phase 변경 시 0 으로 reset.
        last_error: 직전 실패 사유 텍스트 (4KB truncate).
        last_attempt_at: ISO 8601 KST timestamp (`YYYY-MM-DDTHH:MM:SS+09:00`).
        hint_history: append-only 배열, cap = WORKFLOW_RETRY_PROMPT_N.
            cap 초과 시 가장 오래된 항목 제거 (FIFO truncate).
    """

    phase: str = ""
    retry_count: int = 0
    last_error: str = ""
    last_attempt_at: str = ""
    hint_history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """JSON 직렬화 가능한 dict 로 변환."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RetryContext":
        """dict 로부터 RetryContext 복원. 누락된 필드는 기본값 사용."""
        if not isinstance(data, dict):
            return cls()
        hist = data.get("hint_history", [])
        if not isinstance(hist, list):
            hist = []
        return cls(
            phase=str(data.get("phase", "") or ""),
            retry_count=int(data.get("retry_count", 0) or 0),
            last_error=str(data.get("last_error", "") or ""),
            last_attempt_at=str(data.get("last_attempt_at", "") or ""),
            hint_history=[str(h) for h in hist if isinstance(h, (str, int, float))],
        )


# =============================================================================
# 내부 헬퍼
# =============================================================================


def _warn(msg: str) -> None:
    """비차단 WARN 로그 — stderr 에 한 줄 출력. 예외 발생해도 무시."""
    try:
        print(f"[WARN] failure_handler: {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass


def _now_kst_iso() -> str:
    """ISO 8601 KST timestamp (`+09:00` 오프셋, 초 단위)."""
    return datetime.now(KST_TZ).isoformat(timespec="seconds")


def _truncate_error(error: str | None, max_bytes: int = LAST_ERROR_MAX_BYTES) -> str:
    """error 텍스트를 max_bytes 바이트로 안전하게 자른다.

    UTF-8 멀티바이트 경계를 보존한다 — 부분 시퀀스로 끊지 않음.
    """
    if not error:
        return ""
    text = str(error)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    cut = encoded[:max_bytes]
    # UTF-8 경계까지 후퇴 (마지막 0x80~0xBF continuation 바이트 trim)
    while cut and (cut[-1] & 0xC0) == 0x80:
        cut = cut[:-1]
    try:
        return cut.decode("utf-8", errors="ignore")
    except Exception:
        return text[:max_bytes]


def _resolve_work_dir(work_dir: str | os.PathLike) -> Path:
    """work_dir 입력을 절대 경로 Path 로 정규화. 단축 키도 허용."""
    raw = str(work_dir)
    try:
        abs_path = resolve_abs_work_dir(raw)
    except Exception as exc:  # noqa: BLE001
        _warn(f"resolve_abs_work_dir failed for {raw!r}: {exc}")
        abs_path = raw if os.path.isabs(raw) else os.path.abspath(raw)
    return Path(abs_path)


def _ensure_dir(path: Path) -> bool:
    """디렉터리를 생성한다. 실패 시 WARN 로그만 출력하고 False 반환."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as exc:
        _warn(f"mkdir failed for {path}: {exc}")
        return False


def _retry_context_path(work_dir: Path) -> Path:
    return work_dir / RETRY_CONTEXT_FILENAME


def _retry_context_lock_dir(work_dir: Path) -> str:
    return str(work_dir / RETRY_CONTEXT_LOCK_FILENAME)


def _sentinel_path(work_dir: Path) -> Path:
    return work_dir / SENTINEL_FILENAME


def _sentinel_recorded_path(work_dir: Path) -> Path:
    return work_dir / SENTINEL_RECORDED_FILENAME


def _normalize_phase(phase: str | None) -> str:
    """phase 입력을 대문자로 정규화. 알 수 없는 값이면 빈 문자열 반환."""
    if not phase:
        return ""
    upper = str(phase).strip().upper()
    if upper not in VALID_PHASES:
        _warn(f"unknown phase {phase!r}; tolerated as raw uppercase string")
    return upper


# =============================================================================
# Public API
# =============================================================================


def load_retry_context(work_dir: str | os.PathLike) -> RetryContext | None:
    """retry-context.json 을 로드한다.

    Args:
        work_dir: 워크플로우 디렉터리 (절대 경로 / 상대 경로 / 단축 키 허용).

    Returns:
        파일이 존재하고 파싱 성공 시 RetryContext 인스턴스. 파일 없거나
        파싱 실패 시 None. 어떤 예외도 호출자에게 전파하지 않는다.
    """
    try:
        wd = _resolve_work_dir(work_dir)
        ctx_path = _retry_context_path(wd)
        if not ctx_path.exists():
            return None
        data = load_json_file(str(ctx_path))
        if data is None:
            return None
        return RetryContext.from_dict(data)
    except Exception as exc:  # noqa: BLE001
        _warn(f"load_retry_context failed: {exc}")
        return None


def is_retry_available(work_dir: str | os.PathLike, phase: str) -> bool:
    """현재 retry_count 가 `WORKFLOW_RETRY_<PHASE>` 미만인지 판정한다.

    retry-context.json 의 `phase` 필드가 인자 phase 와 다르면 retry_count 는
    0 으로 reset 된 것으로 간주한다 (phase 전환 = 새 시도).

    Args:
        work_dir: 워크플로우 디렉터리.
        phase: 검사 대상 phase (INIT/PLAN/WORK/VALIDATE/REPORT).

    Returns:
        retry 가능하면 True. PHASE_RETRY_MAX 미정의 / phase 미상 / 예외 등
        모든 비정상 경로에서 False 반환 (안전한 기본 — 자동 retry 트리거 0건).
    """
    try:
        norm_phase = _normalize_phase(phase)
        if not norm_phase or norm_phase not in PHASE_RETRY_MAX:
            return False
        max_retry = int(PHASE_RETRY_MAX.get(norm_phase, 0) or 0)
        if max_retry <= 0:
            return False

        ctx = load_retry_context(work_dir)
        if ctx is None:
            # 첫 시도 — 1회 retry 가능 (max_retry >= 1 인 경우)
            return max_retry >= 1

        # phase 전환 = retry_count reset 효과
        current = ctx.retry_count if ctx.phase == norm_phase else 0
        return current < max_retry
    except Exception as exc:  # noqa: BLE001
        _warn(f"is_retry_available failed: {exc}")
        return False


def update_retry_context(
    work_dir: str | os.PathLike,
    phase: str,
    error: str,
    hint: str | None = None,
) -> RetryContext:
    """retry-context.json 을 read-modify-write 로 갱신한다.

    동작:
      - phase 가 직전과 같으면 retry_count += 1, 다르면 0 으로 reset.
      - last_error 는 매 호출마다 덮어쓰며 4KB 로 truncate.
      - last_attempt_at 은 매 호출마다 KST 타임스탬프로 갱신.
      - hint 가 비어있지 않으면 hint_history 에 append.
        cap = WORKFLOW_RETRY_PROMPT_N 초과 시 가장 오래된 항목 제거 (FIFO truncate).

    원자성 / 동시성:
      - `acquire_lock` (mkdir 기반) 으로 동시 접근 race 방지.
      - `atomic_write_json` 으로 임시 파일 + rename 보장.
      - 락 획득 실패 시 WARN 로그 출력 후 lock 없이 best-effort 갱신 시도.

    Args:
        work_dir: 워크플로우 디렉터리.
        phase: 실패한 phase (정규화되어 대문자로 저장).
        error: 실패 사유 텍스트 (4KB truncate).
        hint: 다음 시도용 hint (선택). 빈 문자열/None 이면 append 안 함.

    Returns:
        갱신된 RetryContext 인스턴스. 어떤 예외도 호출자에게 전파하지 않으며,
        실패 시 최선노력 기본값으로 채워진 RetryContext 를 반환한다.
    """
    norm_phase = _normalize_phase(phase)
    truncated_error = _truncate_error(error)
    now_iso = _now_kst_iso()

    cap = max(0, int(WORKFLOW_RETRY_PROMPT_N or 0))
    hint_clean = (hint or "").strip()

    wd = _resolve_work_dir(work_dir)
    if not _ensure_dir(wd):
        # 폴백: 디렉터리 생성 실패해도 in-memory RetryContext 반환
        return RetryContext(
            phase=norm_phase,
            retry_count=0,
            last_error=truncated_error,
            last_attempt_at=now_iso,
            hint_history=[hint_clean] if hint_clean and cap > 0 else [],
        )

    lock_dir = _retry_context_lock_dir(wd)
    locked = False
    try:
        locked = acquire_lock(lock_dir, max_wait=2)
    except Exception as exc:  # noqa: BLE001
        _warn(f"acquire_lock failed: {exc}")

    if not locked:
        _warn(
            f"retry-context.json lock not acquired for {wd}; "
            "proceeding best-effort without lock"
        )

    try:
        existing = load_retry_context(wd)
        if existing is None:
            existing = RetryContext()

        if existing.phase == norm_phase and norm_phase:
            new_count = int(existing.retry_count or 0) + 1
        else:
            new_count = 0

        new_history = list(existing.hint_history or [])
        if hint_clean and cap > 0:
            new_history.append(hint_clean)
            # FIFO truncate: 가장 오래된 항목부터 제거
            while len(new_history) > cap:
                new_history.pop(0)
        elif cap == 0:
            # cap 0 = hint_history 비활성
            new_history = []

        updated = RetryContext(
            phase=norm_phase or existing.phase,
            retry_count=new_count,
            last_error=truncated_error,
            last_attempt_at=now_iso,
            hint_history=new_history,
        )

        try:
            atomic_write_json(str(_retry_context_path(wd)), updated.to_dict())
        except Exception as exc:  # noqa: BLE001
            _warn(f"atomic_write_json failed: {exc}")

        return updated
    except Exception as exc:  # noqa: BLE001
        _warn(f"update_retry_context unexpected failure: {exc}")
        return RetryContext(
            phase=norm_phase,
            retry_count=0,
            last_error=truncated_error,
            last_attempt_at=now_iso,
            hint_history=[hint_clean] if hint_clean and cap > 0 else [],
        )
    finally:
        if locked:
            try:
                release_lock(lock_dir)
            except Exception as exc:  # noqa: BLE001
                _warn(f"release_lock failed: {exc}")


def create_sentinel(
    work_dir: str | os.PathLike,
    registry_key: str,
    phase: str = "WORK",
    *,
    error: str | None = None,
) -> Path:
    """`<workDir>/.workflow-failed` sentinel 파일을 생성한다 (idempotent).

    내용은 1줄 JSON: `{"registry_key": "...", "phase": "...", "created_at": "..."}`.
    이미 존재하면 created_at 만 갱신하여 재기록 (재시도 시간을 추적 가능).

    Args:
        work_dir: 워크플로우 디렉터리.
        registry_key: YYYYMMDD-HHMMSS 형식의 워크플로우 키.
        phase: 실패한 phase (기본 WORK).
        error: 선택적 실패 사유 — sentinel JSON 에 `error` 필드로 포함.

    Returns:
        sentinel 파일의 절대 경로 (Path). 생성 실패해도 의도된 경로를 반환하며
        (호출자가 추후 다시 시도 가능) 어떤 예외도 호출자에게 전파하지 않는다.
    """
    wd = _resolve_work_dir(work_dir)
    sentinel = _sentinel_path(wd)

    if not _ensure_dir(wd):
        return sentinel

    payload: dict = {
        "registry_key": str(registry_key or ""),
        "phase": _normalize_phase(phase) or str(phase or "WORK"),
        "created_at": _now_kst_iso(),
    }
    if error:
        payload["error"] = _truncate_error(error)

    try:
        # 1줄 JSON — atomic_write_json 은 indent=2 가 기본이므로 직접 쓰기.
        line = json.dumps(payload, ensure_ascii=False)
        tmp = sentinel.with_suffix(sentinel.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(line)
                fh.write("\n")
            os.replace(tmp, sentinel)
        finally:
            # tmp 가 남아있으면 정리 (정상 경로에서는 os.replace 후 사라짐)
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
    except Exception as exc:  # noqa: BLE001
        _warn(f"create_sentinel write failed for {sentinel}: {exc}")

    return sentinel


def record_failure(
    work_dir: str | os.PathLike,
    phase: str,
    error: str,
    hint: str | None = None,
) -> RetryContext:
    """실패 1회를 기록한다 — sentinel + retry-context + recorded 마커 (idempotent).

    호출 흐름:
      1. update_retry_context 로 retry-context.json 갱신
      2. create_sentinel 로 sentinel 파일 보장 (이미 있으면 갱신만)
      3. `.workflow-failed.recorded` 마커 생성 (이미 있으면 mtime 만 갱신)

    idempotency:
      recorded 마커가 이미 있어도 재호출은 안전하다 — retry-context 는 호출 횟수만큼
      retry_count 가 증가하므로 호출자가 중복 호출을 가드하고 싶다면 마커 존재
      여부를 사전 검사한다 (예: subagent-stop.py).

    Args:
        work_dir: 워크플로우 디렉터리.
        phase: 실패한 phase.
        error: 실패 사유 텍스트.
        hint: 선택적 다음-시도 hint.

    Returns:
        갱신된 RetryContext.
    """
    wd = _resolve_work_dir(work_dir)

    # 1. retry-context 갱신
    ctx = update_retry_context(wd, phase, error, hint=hint)

    # 2. sentinel 보장 — registry_key 추출 (workDir basename 또는 부모 경로)
    try:
        from common import extract_registry_key  # local import: avoid cycle risk
        registry_key = extract_registry_key(str(wd))
    except Exception as exc:  # noqa: BLE001
        _warn(f"extract_registry_key failed: {exc}")
        registry_key = wd.name

    create_sentinel(wd, registry_key, phase=phase, error=error)

    # 3. recorded 마커 (touch — 이미 있으면 mtime 만 갱신)
    try:
        recorded = _sentinel_recorded_path(wd)
        recorded.touch(exist_ok=True)
    except OSError as exc:
        _warn(f"recorded marker touch failed: {exc}")

    return ctx


# =============================================================================
# CLI 진입점 (bin/flow-fail-record 가 위임)
# =============================================================================


def _resolve_work_dir_from_registry(registry_key: str) -> Path:
    """registry_key 만 주어졌을 때 workDir 를 추론."""
    try:
        from common import resolve_work_dir as _rwd  # noqa: WPS433
        rel = _rwd(registry_key)
        return Path(resolve_abs_work_dir(rel))
    except Exception as exc:  # noqa: BLE001
        _warn(f"resolve_work_dir for {registry_key!r} failed: {exc}")
        # 최후 폴백: project_root/.claude-organic/runs/<registry_key>
        try:
            root = resolve_project_root()
        except Exception:
            root = os.getcwd()
        return Path(root) / ".claude-organic" / "runs" / registry_key


def _cli_record(args: argparse.Namespace) -> int:
    """`record` 서브커맨드 — record_failure 호출."""
    registry_key = (args.registry_key or "").strip()
    if not registry_key:
        _warn("record: registry_key is required")
        return 1

    if args.work_dir:
        work_dir = Path(args.work_dir)
    else:
        work_dir = _resolve_work_dir_from_registry(registry_key)

    phase = args.phase or "WORK"
    error = args.error or ""
    hint = args.hint or None

    ctx = record_failure(work_dir, phase=phase, error=error, hint=hint)

    # 결과 1줄 JSON 으로 stdout 출력 — 호출 측이 파싱 가능
    try:
        out = {
            "registry_key": registry_key,
            "work_dir": str(work_dir),
            "phase": ctx.phase,
            "retry_count": ctx.retry_count,
            "last_attempt_at": ctx.last_attempt_at,
            "hint_history_size": len(ctx.hint_history),
        }
        print(json.dumps(out, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        _warn(f"cli_record stdout serialization failed: {exc}")

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="failure_handler.py",
        description="워크플로우 phase 실패 처리 단일 진실 공급원",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser(
        "record",
        help="record a failure: update retry-context.json + create sentinel + recorded marker",
    )
    rec.add_argument("registry_key", help="YYYYMMDD-HHMMSS workflow key")
    rec.add_argument(
        "--phase",
        default="WORK",
        help="phase that failed (INIT/PLAN/WORK/VALIDATE/REPORT). default: WORK",
    )
    rec.add_argument(
        "--error",
        default="",
        help="failure reason text (truncated to 4KB)",
    )
    rec.add_argument(
        "--hint",
        default=None,
        help="next-attempt hint to append to hint_history",
    )
    rec.add_argument(
        "--work-dir",
        default=None,
        help="explicit workDir path (overrides registry_key resolution)",
    )
    rec.set_defaults(func=_cli_record)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help(sys.stderr)
        return 1
    try:
        return int(func(args) or 0)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        _warn(f"main: unhandled exception: {exc}")
        return 0  # 비차단 보장: CLI 실패해도 0 반환 (호출자 흐름 차단 0건)


if __name__ == "__main__":
    sys.exit(main())

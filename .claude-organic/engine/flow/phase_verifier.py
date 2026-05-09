#!/usr/bin/env -S python3 -u
"""phase_verifier.py — VALIDATE 단계 rule-based 검증 엔진 (T-454).

본 모듈은 LLM 호출 0건. 룰베이스 IO 검증만 수행한다.
호출 진입점: bin/flow-phase-verify (registryKey 1인자).

T-452 §1.1 / §2.4 / §10.1 / §10.6 사양 정합.

VALIDATE 단계 책임 (T-452 §1.1):
    - WORK 직후 / REPORT 직전에 끼는 단계.
    - 산출물 정합성을 룰베이스 검증한다 (LLM 호출 0건).
    - 입력: work/WXX-*.md, plan.md
    - 산출물: verifier 결과 + retry-context.json (실패 시)

command 별 검증 분기 (T-452 §2.4):
    - implement / refactor / build → _verify_implement_like
        (1) plan.md 의 모든 W## ID 가 work/<ID>-*.md 로 존재
        (2) git diff --name-only HEAD 파일 수 ≥ 1
    - research → _verify_research
        (1) 모든 W## 산출물 존재
        (2) report.md 또는 work/RPT-*.md 의 ## 헤더 ≥ 3
        (3) Mermaid 블록 ≥ 1
    - review / analyze → _verify_review
        (1) 모든 W## 산출물 존재
        (2) work/ 또는 report.md 에 "판정"/"결론"/"Decision"/"Verdict" 키워드 ≥ 1
    - architect → _verify_architect
        (1) 모든 W## 산출물 존재
        (2) Mermaid 블록 ≥ 2
        (3) 섹션 헤더 ≥ 4

LLM 호출 0건 룰베이스 강제:
    - 본 모듈은 anthropic / claude_* SDK / API 호출 0건.
    - 모든 검증은 파일 IO + 정규식 + subprocess (git) 만 사용한다.

CLI:
    python3 phase_verifier.py <registry_key>
    종료 코드: 0 = 통과, 1 = 실패, 2 = 사용법 오류
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

# 프로젝트 루트 결정 (engine/common.py 의 resolve_* 헬퍼 활용)
_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root, resolve_work_dir  # noqa: E402

# Verifier 결과 표준 튜플
# (ok: bool, reason: str, failed_step_ids: list[str])
VerifyResult = tuple[bool, str, list[str]]


# ---------------------------------------------------------------------------
# 메인 진입점
# ---------------------------------------------------------------------------


def verify_validate_phase(registry_key: str) -> VerifyResult:
    """VALIDATE 단계 진입점 — command 에 따라 분기한다.

    처리 절차:
        1. registry_key 로 work_dir 결정 (.claude-organic/runs/<key>/).
        2. init-result.json 또는 .context.json 에서 command 추출.
        3. plan.md 로드.
        4. command 분기 4종 dispatch.
        5. 결과 반환 (실패 시 _write_retry_context_on_fail 호출은 W03 helper).

    Args:
        registry_key: 워크플로우 registry key (YYYYMMDD-HHMMSS) 또는 work_dir 경로.

    Returns:
        VerifyResult (ok, reason, failed_step_ids):
            - ok: True 시 verifier 통과, False 시 실패.
            - reason: 통과/실패 사유 1줄 텍스트.
            - failed_step_ids: 실패 시 verifier 가 지적한 워커 ID 목록.
    """
    # 1. work_dir 결정 (절대 경로)
    project_root = resolve_project_root()
    rel_work_dir = resolve_work_dir(registry_key, project_root=project_root)
    if os.path.isabs(rel_work_dir):
        work_dir = rel_work_dir
    else:
        work_dir = os.path.join(project_root, rel_work_dir)

    if not os.path.isdir(work_dir):
        return (False, f"work_dir not found: {work_dir}", [])

    # 2. command 추출
    command = _read_command(work_dir)
    if command is None:
        return (False, "command not found in init-result.json or .context.json", [])

    # 3. plan.md 로드
    plan_path = os.path.join(work_dir, "plan.md")
    if not os.path.isfile(plan_path):
        return (False, f"plan.md not found: {plan_path}", [])
    try:
        with open(plan_path, encoding="utf-8") as fh:
            plan_md = fh.read()
    except OSError as exc:
        return (False, f"plan.md read failed: {exc}", [])

    # 4. command 분기 4종 dispatch
    cmd_lower = command.strip().lower()
    if cmd_lower in {"implement", "refactor", "build"}:
        return _verify_implement_like(work_dir, plan_md)
    if cmd_lower == "research":
        return _verify_research(work_dir, plan_md)
    if cmd_lower in {"review", "analyze"}:
        return _verify_review(work_dir, plan_md)
    if cmd_lower == "architect":
        return _verify_architect(work_dir, plan_md)

    return (False, f"unknown command: {command}", [])


# ---------------------------------------------------------------------------
# command 별 분기 4종
# ---------------------------------------------------------------------------


def _verify_implement_like(work_dir: str, plan_md: str) -> VerifyResult:
    """implement / refactor / build 검증.

    검증 항목:
        (1) plan.md 의 모든 W## ID 가 work/<ID>-*.md 로 존재.
        (2) git diff --name-only HEAD 파일 수 ≥ 1 (워크트리 기준).

    Args:
        work_dir: 워크플로우 work 디렉터리 절대 경로.
        plan_md: plan.md 파일 내용.

    Returns:
        VerifyResult (ok, reason, failed_step_ids).
    """
    _, missing_ids = _check_work_files_exist(plan_md, work_dir)
    if missing_ids:
        return (
            False,
            f"implement: missing work files {missing_ids}",
            missing_ids,
        )

    diff_count = _check_git_diff(work_dir)
    if diff_count < 1:
        return (False, "implement: no git diff (워크트리 변경 0건)", [])

    return (True, "ok: implement verifier passed", [])


def _verify_research(work_dir: str, plan_md: str) -> VerifyResult:
    """research 검증 (경량).

    검증 항목:
        (1) 모든 W## 산출물 존재.
        (2) report.md 또는 work/RPT-*.md 의 ## 헤더 ≥ 3.
        (3) Mermaid 블록 ≥ 1.

    Args:
        work_dir: 워크플로우 work 디렉터리 절대 경로.
        plan_md: plan.md 파일 내용.

    Returns:
        VerifyResult (ok, reason, failed_step_ids).
    """
    _, missing_ids = _check_work_files_exist(plan_md, work_dir)
    if missing_ids:
        return (False, f"research: missing work files {missing_ids}", missing_ids)

    aggregated = _aggregate_md_content(work_dir)
    section_count = _count_sections(aggregated)
    if section_count < 3:
        return (
            False,
            f"research: missing sections (got {section_count}, need 3)",
            [],
        )

    mermaid_count = _count_mermaid_blocks(aggregated)
    if mermaid_count < 1:
        return (False, "research: missing mermaid block", [])

    return (True, "ok: research verifier passed", [])


def _verify_review(work_dir: str, plan_md: str) -> VerifyResult:
    """review / analyze 검증 (경량).

    검증 항목:
        (1) 모든 W## 산출물 존재.
        (2) work/ 또는 report.md 에 "판정"/"결론"/"Decision"/"Verdict" 키워드 ≥ 1.

    Args:
        work_dir: 워크플로우 work 디렉터리 절대 경로.
        plan_md: plan.md 파일 내용.

    Returns:
        VerifyResult (ok, reason, failed_step_ids).
    """
    _, missing_ids = _check_work_files_exist(plan_md, work_dir)
    if missing_ids:
        return (False, f"review: missing work files {missing_ids}", missing_ids)

    aggregated = _aggregate_md_content(work_dir)
    keywords = ("판정", "결론", "Decision", "Verdict")
    if not any(kw in aggregated for kw in keywords):
        return (False, "review: missing verdict section", [])

    return (True, "ok: review verifier passed", [])


def _verify_architect(work_dir: str, plan_md: str) -> VerifyResult:
    """architect 검증.

    검증 항목:
        (1) 모든 W## 산출물 존재.
        (2) Mermaid 블록 ≥ 2.
        (3) 섹션 헤더 ≥ 4.

    Args:
        work_dir: 워크플로우 work 디렉터리 절대 경로.
        plan_md: plan.md 파일 내용.

    Returns:
        VerifyResult (ok, reason, failed_step_ids).
    """
    _, missing_ids = _check_work_files_exist(plan_md, work_dir)
    if missing_ids:
        return (False, f"architect: missing work files {missing_ids}", missing_ids)

    aggregated = _aggregate_md_content(work_dir)
    mermaid_count = _count_mermaid_blocks(aggregated)
    if mermaid_count < 2:
        return (
            False,
            f"architect: insufficient diagrams (got {mermaid_count}, need 2)",
            [],
        )

    section_count = _count_sections(aggregated)
    if section_count < 4:
        return (
            False,
            f"architect: insufficient sections (got {section_count}, need 4)",
            [],
        )

    return (True, "ok: architect verifier passed", [])


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------


# plan.md 의 H3 헤더에서 W## ID 추출 (skill_mapper.py:670 패턴 정합)
_W_ID_PATTERN = re.compile(r"^###\s+(W\d+)[:\s]", re.MULTILINE)

# fallback: 테이블 ID 컬럼 직접 매칭 (`| W01 |`)
_W_ID_TABLE_PATTERN = re.compile(r"^\s*\|\s*(W\d+)\s*\|", re.MULTILINE)

# 섹션 헤더 (## 또는 ###)
_SECTION_PATTERN = re.compile(r"^#{2,3}\s+", re.MULTILINE)

# Mermaid 코드 블록
_MERMAID_PATTERN = re.compile(r"```mermaid\b", re.MULTILINE)


def _check_work_files_exist(
    plan_md_content: str,
    work_dir: str,
) -> tuple[list[str], list[str]]:
    """plan.md 의 W## ID 추출 후 work/<ID>-*.md 존재 여부를 검사한다.

    추출 룰:
        - Primary: H3 헤더 (`### W01:`) — skill_mapper.py:670 패턴.
        - Fallback: 테이블 ID 컬럼 (`| W01 |`) — plan_validator.py 호환.

    RPT 헤더 (`### RPT:`) 는 제외 — 본 verifier 는 워커 산출물만 검증.

    Args:
        plan_md_content: plan.md 파일 내용.
        work_dir: 워크플로우 work 디렉터리 절대 경로.

    Returns:
        (existing_ids, missing_ids): 두 리스트 모두 정렬된 list.
    """
    ids: set[str] = set()
    for match in _W_ID_PATTERN.finditer(plan_md_content):
        ids.add(match.group(1))
    for match in _W_ID_TABLE_PATTERN.finditer(plan_md_content):
        ids.add(match.group(1))

    work_subdir = os.path.join(work_dir, "work")
    existing: list[str] = []
    missing: list[str] = []

    for wid in sorted(ids):
        pattern = os.path.join(work_subdir, f"{wid}-*.md")
        matches = glob.glob(pattern)
        # context 슬라이스 (work/<ID>-context.md / work/context/<ID>*.md) 외에
        # 실제 산출물 파일이 있는지 확인 — 본 verifier 는 슬라이스 제외 정책.
        produced = [p for p in matches if not p.endswith("-context.md")]
        if produced:
            existing.append(wid)
        else:
            missing.append(wid)

    return (existing, missing)


def _count_sections(md_content: str) -> int:
    """## 또는 ### 헤더 라인 수를 카운트한다.

    Args:
        md_content: 마크다운 문자열.

    Returns:
        헤더 라인 수.
    """
    return len(_SECTION_PATTERN.findall(md_content))


def _count_mermaid_blocks(md_content: str) -> int:
    """```mermaid ... ``` 코드 블록 수를 카운트한다.

    Args:
        md_content: 마크다운 문자열.

    Returns:
        Mermaid 코드 블록 수.
    """
    return len(_MERMAID_PATTERN.findall(md_content))


def _check_git_diff(work_dir: str) -> int:
    """git diff --name-only HEAD 의 파일 수를 반환한다.

    워크트리 격리 환경에서는 work_dir 의 git 부모를 찾아 git -C 로 호출.
    subprocess 실패 / git 미설치 / 5초 timeout 시 0 반환 (graceful fallback).

    Args:
        work_dir: 워크플로우 work 디렉터리 절대 경로.

    Returns:
        변경된 파일 수 (line count).
    """
    git_root = _find_git_root(work_dir)
    if git_root is None:
        return 0

    try:
        result = subprocess.run(
            ["git", "-C", git_root, "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0

    if result.returncode != 0:
        return 0

    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return len(lines)


def _aggregate_md_content(work_dir: str) -> str:
    """work/W*.md + work/RPT-*.md + report.md 내용을 합쳐 반환한다.

    section/mermaid 카운트 헬퍼의 입력으로 사용.

    Args:
        work_dir: 워크플로우 work 디렉터리 절대 경로.

    Returns:
        모든 마크다운 내용을 줄바꿈으로 join 한 문자열.
    """
    chunks: list[str] = []
    work_subdir = os.path.join(work_dir, "work")

    patterns = [
        os.path.join(work_subdir, "W*.md"),
        os.path.join(work_subdir, "RPT-*.md"),
    ]
    seen: set[str] = set()
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            # context 슬라이스 제외
            if path.endswith("-context.md"):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    chunks.append(fh.read())
            except OSError:
                continue

    report_path = os.path.join(work_dir, "report.md")
    if os.path.isfile(report_path):
        try:
            with open(report_path, encoding="utf-8") as fh:
                chunks.append(fh.read())
        except OSError:
            pass

    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------


def _read_command(work_dir: str) -> str | None:
    """init-result.json 또는 .context.json 에서 command 필드를 추출한다.

    탐색 순서:
        1. init-result.json
        2. .context.json

    Args:
        work_dir: 워크플로우 work 디렉터리 절대 경로.

    Returns:
        command 문자열 또는 None (둘 다 없거나 파싱 실패 시).
    """
    candidates = [
        os.path.join(work_dir, "init-result.json"),
        os.path.join(work_dir, ".context.json"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        cmd = data.get("command")
        if isinstance(cmd, str) and cmd.strip():
            return cmd
    return None


def _find_git_root(start_dir: str) -> str | None:
    """start_dir 부터 위로 올라가며 .git 디렉터리를 찾는다.

    Args:
        start_dir: 탐색 시작 디렉터리 절대 경로.

    Returns:
        git root 절대 경로 또는 None.
    """
    current = os.path.abspath(start_dir)
    while True:
        if os.path.isdir(os.path.join(current, ".git")) or os.path.isfile(
            os.path.join(current, ".git")
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


# ---------------------------------------------------------------------------
# 결과 영속화 (W03 scope)
# ---------------------------------------------------------------------------


def _write_retry_context_on_fail(
    work_dir: str,
    failure_reason: str,
    failed_steps: list[str],
) -> None:
    """retry-context.json 의 3개 필드를 기록한다 (T-454 scope).

    필드:
        - last_failure_phase: "VALIDATE" 고정.
        - last_failure_reason: failure_reason.
        - failed_work_steps: failed_steps.

    나머지 2필드 (retry_count, prompt_hints) 는 T-455 sentinel/handler 가 갱신.
    기존 파일이 있으면 read-modify-write 로 부분 갱신, 없으면 신설.

    Args:
        work_dir: 워크플로우 work 디렉터리 절대 경로.
        failure_reason: verify_validate_phase 가 반환한 reason 메시지.
        failed_steps: verifier 가 지적한 워커 ID 목록.
    """
    retry_path = os.path.join(work_dir, "retry-context.json")

    # 기존 파일 read (있으면)
    existing: dict = {}
    if os.path.isfile(retry_path):
        try:
            with open(retry_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, dict):
                existing = {}
        except (OSError, json.JSONDecodeError):
            existing = {}

    # 본 티켓 3필드만 갱신, 나머지 보존
    existing["last_failure_phase"] = "VALIDATE"
    existing["last_failure_reason"] = failure_reason
    existing["failed_work_steps"] = list(failed_steps)

    # write
    with open(retry_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점 — flow-phase-verify wrapper 에서 호출.

    사용법:
        python3 phase_verifier.py <registry_key>

    종료 코드:
        0 = 통과 (verifier ok=True).
        1 = 실패 (verifier ok=False).
        2 = 사용법 오류 (인자 누락 / 다중).

    Args:
        argv: 명령행 인자 리스트 (None 이면 sys.argv[1:] 사용).

    Returns:
        종료 코드.
    """
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 1:
        print("usage: phase_verifier.py <registry_key>", file=sys.stderr)
        return 2

    registry_key = argv[0]
    ok, reason, failed = verify_validate_phase(registry_key)
    if ok:
        print(f"OK: {reason}")
        return 0

    failed_str = ",".join(failed) if failed else "-"
    print(f"FAIL: {reason} (failed={failed_str})")
    # retry-context.json 3필드 기록 (T-454 W03)
    work_dir = os.path.join(".claude-organic", "runs", registry_key)
    try:
        _write_retry_context_on_fail(work_dir, reason, failed)
    except OSError as exc:
        print(f"[WARN] retry-context.json 기록 실패: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

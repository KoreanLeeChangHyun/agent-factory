"""cli_utils.py - flow-* 스크립트 공통 argparse 유틸 모듈.

argparse type 함수, 공통 에필로그 빌더, deprecation 경고 유틸을 제공한다.
W02 이후 각 스크립트의 argparse 전환 시 이 모듈을 import하여 사용한다.

사용 예시:
    from flow.cli_utils import registry_key_type, ticket_type, build_common_epilog

    parser = argparse.ArgumentParser(
        prog="flow-update",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("registry_key", type=registry_key_type)
"""

from __future__ import annotations

import argparse
import os
import re
import sys


# ─── 버전 로드 ────────────────────────────────────────────────────────────────

def _load_version() -> str:
    """워크플로우 버전을 .version 파일에서 읽어 반환한다.

    파일 읽기 실패 시 "unknown"을 반환한다.

    Returns:
        버전 문자열 (예: "2.1.17") 또는 "unknown".
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # scripts/flow/ → scripts/ → .claude.workflow/
        workflow_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
        version_path = os.path.join(workflow_root, ".version")
        with open(version_path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return "unknown"


# ─── argparse type 함수 ───────────────────────────────────────────────────────

def registry_key_type(value: str) -> str:
    """YYYYMMDD-HHMMSS 형식 registryKey 검증 argparse type 함수.

    argparse add_argument(..., type=registry_key_type) 로 사용한다.
    형식이 맞지 않으면 argparse.ArgumentTypeError를 발생시켜 사용 오류로 처리한다.

    Args:
        value: 사용자가 입력한 registryKey 문자열.

    Returns:
        유효한 경우 입력값을 그대로 반환한다.

    Raises:
        argparse.ArgumentTypeError: 형식이 YYYYMMDD-HHMMSS와 다른 경우.

    Examples:
        >>> registry_key_type("20260329-224421")
        '20260329-224421'
        >>> registry_key_type("bad-key")
        # ArgumentTypeError 발생
    """
    pattern = r"^\d{8}-\d{6}$"
    if not re.match(pattern, value):
        raise argparse.ArgumentTypeError(
            f"registryKey 형식 오류: '{value}' — YYYYMMDD-HHMMSS 형식이어야 합니다 (예: 20260329-224421)"
        )
    return value


def ticket_type(value: str) -> str:
    """T-NNN / NNN / #N 형식 티켓 번호를 T-NNN 으로 정규화하는 argparse type 함수.

    kanban_cli.py / ticket_repository.py 의 normalize_ticket_number 와 동일한
    정규화 규칙을 따르되, argparse type 함수 인터페이스를 제공한다.

    지원 입력 형식:
        - T-001, T-1, t-001 (대소문자 무시)
        - 001, 1 (순수 숫자)
        - #001, #1 (# 접두사)

    Args:
        value: 사용자가 입력한 티켓 번호 문자열.

    Returns:
        T-NNN 형식으로 정규화된 문자열 (예: "T-042").

    Raises:
        argparse.ArgumentTypeError: 인식할 수 없는 티켓 번호 형식인 경우.

    Examples:
        >>> ticket_type("42")
        'T-042'
        >>> ticket_type("#5")
        'T-005'
        >>> ticket_type("T-007")
        'T-007'
    """
    raw = value.strip().lstrip("#")
    # T-NNN 형식 (대소문자 무시)
    if re.match(r"^[Tt]-\d+$", raw):
        parts = raw.split("-", 1)
        num = int(parts[1])
        return f"T-{num:03d}"
    # 순수 숫자
    if re.match(r"^\d+$", raw):
        return f"T-{int(raw):03d}"
    raise argparse.ArgumentTypeError(
        f"티켓 번호 형식 오류: '{value}' — T-NNN, NNN, #N 형식 중 하나여야 합니다"
    )


# ─── 공통 에필로그 ────────────────────────────────────────────────────────────

def build_common_epilog() -> str:
    """argparse 파서에 사용할 공통 도움말 에필로그를 반환한다.

    워크플로우 버전과 문서 참조 안내를 포함한다.
    RawDescriptionHelpFormatter와 함께 사용할 것을 권장한다.

    Returns:
        여러 줄로 구성된 에필로그 문자열.

    Examples:
        parser = argparse.ArgumentParser(
            epilog=build_common_epilog(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
    """
    version = _load_version()
    return (
        f"워크플로우 버전: {version}\n"
        "문서: .claude.workflow/docs/ 또는 .claude/rules/workflow.md 참조\n"
        "티켓 관리: flow-kanban <서브커맨드> --help"
    )


# ─── deprecation 경고 유틸 ───────────────────────────────────────────────────

def deprecation_warning(old: str, new: str) -> None:
    """하위 호환 경고를 stderr에 출력한다.

    argparse 전환 후 기존 호출 패턴이 일시적으로 허용되는 동안
    사용자에게 새 형식을 안내하기 위해 사용한다.

    경고는 항상 stderr로 출력되며 프로그램 실행을 중단하지 않는다.

    Args:
        old: 사용 중인 기존(deprecated) 호출 형식 또는 옵션명.
        new: 대체할 새 호출 형식 또는 옵션명.

    Examples:
        deprecation_warning(
            "update_state.py context <workDir> <agent>",
            "flow-update context <registryKey> <agent>",
        )
    """
    print(
        f"[DEPRECATED] '{old}' 형식은 향후 제거될 예정입니다. "
        f"대신 '{new}' 형식을 사용하세요.",
        file=sys.stderr,
    )

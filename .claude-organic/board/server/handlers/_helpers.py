"""Shared helpers for handler mixins."""

from __future__ import annotations

import os
import re
import sys

# ---- flow-kanban done 결과 파싱용 정규식 상수 ----
# 성공 시 stdout 에서 merge 정보 추출: '<branch> -> develop 병합 완료 (<sha8>)'
_DONE_MERGE_OK_RE = re.compile(
    r'(.+?)\s*->\s*develop\s+병합\s+완료\s+\(([0-9a-f]{6,})\)',
)

# 티켓 번호 형식 정규식
_TICKET_RE = re.compile(r'^T-\d+$')
# 칸반 전체 디렉터리 목록 (derived-from 가드에서 사용)
_KANBAN_ALL_DIRS = ('todo', 'open', 'progress', 'review', 'done')
# 충돌 헤더 라인 검출: '[ERROR]' 로 시작하는 라인
_DONE_CONFLICT_HEADER = re.compile(r'^\[ERROR\]')
# 미커밋 변경 헤더 라인 검출
_DONE_DIRTY_HEADER = re.compile(r'미커밋\s+파일\s+목록\s*:')
# 충돌/미커밋 파일 경로 라인: '    - <path>' 패턴
_DONE_PATH_RE = re.compile(r'^\s+-\s+(.+)$')
# rc=0 이지만 merge_commit 이 빈 문자열일 때 재판별용:
# cmd_done 의 '[WARN] worktree 병합 실패: 병합 충돌 발생: ...' 형식 매칭
_DONE_CONFLICT_WARN_RE = re.compile(
    r'\[WARN\].*(병합\s*충돌|merge\s+conflict)',
    re.IGNORECASE,
)

# 전략 식별: '[undo-done] 전략 1: reset --hard 진행' / '전략 2: revert -m 1 진행'
_UNDO_STRATEGY_RESET = re.compile(r'\[undo-done\]\s+전략\s+1\s*:\s*reset')
_UNDO_STRATEGY_REVERT = re.compile(r'\[undo-done\]\s+전략\s+2\s*:\s*revert')
# 워크트리 재생성 정보: '[undo-done] 워크트리 재생성 완료: path=<path> branch=<branch>'
_UNDO_WORKTREE_RE = re.compile(
    r'\[undo-done\]\s+워크트리\s+재생성\s+완료\s*:\s*path=(\S+)\s+branch=(\S+)',
)
# 에러 라인: '[undo-done] ERROR: <message>'
_UNDO_ERROR_RE = re.compile(r'\[undo-done\]\s+ERROR\s*:\s*(.+)')


def _classify_done_failure(stdout: str, stderr: str) -> dict:
    """flow-kanban done 실패(또는 rc=0 + 빈 hash) 시 stdout/stderr 를 분석해 error_kind 를 분류한다.

    반환 dict 구조:
        {
            'error_kind': 'merge_conflict' | 'dirty_worktree' | 'other',
            'conflicts':  list[str],   # 충돌 파일 경로 목록
            'dirty_files': list[str],  # 미커밋 파일 목록
            'message':    str,         # 사용자 표시용 에러 메시지
        }

    우선순위:
        1. '[ERROR]' 헤더 라인 → merge_conflict (기존 fail 분기 패턴)
        2. _DONE_CONFLICT_WARN_RE 패턴 → merge_conflict (rc=0 + 빈 hash 보조 판별)
        3. '미커밋 파일 목록:' 헤더 라인 → dirty_worktree
        4. 그 외 → other
    """
    lines = stdout.splitlines()
    error_kind = 'other'
    conflicts: list[str] = []
    dirty_files: list[str] = []
    error_message = ''
    in_dirty_block = False

    for line in lines:
        if _DONE_CONFLICT_HEADER.match(line):
            error_kind = 'merge_conflict'
            error_message = line.strip()
            in_dirty_block = False
        elif _DONE_CONFLICT_WARN_RE.search(line):
            # rc=0 + 빈 hash 케이스: '[WARN] worktree 병합 실패: 병합 충돌 발생: ...' 매칭
            if error_kind == 'other':
                error_kind = 'merge_conflict'
            if not error_message:
                error_message = line.strip()
            in_dirty_block = False
        elif _DONE_DIRTY_HEADER.search(line):
            error_kind = 'dirty_worktree'
            in_dirty_block = True
        elif _DONE_PATH_RE.match(line):
            path_val = _DONE_PATH_RE.match(line).group(1).strip()
            if error_kind == 'merge_conflict':
                conflicts.append(path_val)
            elif in_dirty_block:
                dirty_files.append(path_val)
        else:
            in_dirty_block = False
            if not error_message and line.strip():
                error_message = line.strip()

    stderr_text = stderr.strip()
    if not error_message and stderr_text:
        error_message = stderr_text

    return {
        'error_kind': error_kind,
        'conflicts': conflicts,
        'dirty_files': dirty_files,
        'message': error_message,
    }


def _import_metrics_cli():
    """metrics_cli 모듈을 lazy import 한다.

    engine/ 디렉터리를 sys.path 에 추가한 뒤 ``flow.metrics_cli`` 를
    import. board 서버의 sys.path 에는 board/ 만 등록되어 있으므로
    엔진 import 가 필요한 시점에서만 path 를 보충한다.
    """
    engine_dir = os.path.normpath(
        os.path.join(os.getcwd(), '.claude-organic', 'engine'),
    )
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    from flow import metrics_cli  # noqa: WPS433
    return metrics_cli


def _import_launch_metrics_cli():
    """launch_metrics_cli 모듈을 lazy import 한다.

    engine/ 디렉터리를 sys.path 에 추가한 뒤 ``flow.launch_metrics_cli`` 를
    import. _import_metrics_cli 와 동일한 패턴으로 엔진 import 가
    필요한 시점에서만 path 를 보충한다.
    """
    engine_dir = os.path.normpath(
        os.path.join(os.getcwd(), '.claude-organic', 'engine'),
    )
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    from flow import launch_metrics_cli  # noqa: WPS433
    return launch_metrics_cli

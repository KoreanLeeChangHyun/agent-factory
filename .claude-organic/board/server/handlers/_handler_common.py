"""Shared infrastructure for handler mixins — ticket regex, kanban dirs, engine lazy imports."""

from __future__ import annotations

import os
import re
import sys

# 티켓 번호 형식 정규식
_TICKET_RE = re.compile(r'^T-\d+$')
# 칸반 전체 디렉터리 목록 (derived-from 가드에서 사용)
_KANBAN_ALL_DIRS = ('todo', 'open', 'progress', 'review', 'done')


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

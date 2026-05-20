"""server/__main__.py — entry point for ``python3 -m board.server``."""

from __future__ import annotations

import os
import subprocess
import sys

from .app import _run_server
from engine.apps.board_api.runtime import (
    is_port_in_use,
    read_board_url_port,
    refresh_existing_board_url,
    remove_board_url_file,
)


# 이 스크립트가 백그라운드로 재기동될 때 호출할 안정된 경로 (shim).
_SHIM_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'server.py')
)


def main() -> int:
    """서버를 백그라운드로 시작한다.

    .board.url 파일 존재 여부와 해당 포트 활성 상태로 중복 실행을 방지한다.

    Returns:
        종료 코드. 서버가 이미 실행 중이면 0, 성공 시 0.
    """
    project_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', '..')
    )

    recorded_port = read_board_url_port(project_root)
    if recorded_port and is_port_in_use(recorded_port):
        # 서버가 이미 실행 중 — URL 파일만 갱신
        refresh_existing_board_url(project_root, recorded_port)
        return 0
    if recorded_port is not None:
        # stale 파일: 포트가 비활성 상태이므로 파일 삭제 후 새로 시작
        remove_board_url_file(project_root)

    # 자신을 --serve 모드로 백그라운드 실행 (shim 경로 사용)
    subprocess.Popen(
        [sys.executable, _SHIM_PATH, '--serve', project_root],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == '--serve':
        _run_server(sys.argv[2])
    else:
        sys.exit(main())

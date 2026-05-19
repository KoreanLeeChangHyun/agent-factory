"""pytest 부트스트랩 — board_data import 를 위한 sys.path 보강.

board.server._common 은 board/board_data.py 를 sibling 모듈로 import.
본 conftest 가 .claude-organic/board/ 를 sys.path 에 미리 등록한다.
"""

from __future__ import annotations

import os
import sys

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SERVER_DIR = os.path.dirname(_TESTS_DIR)
_BOARD_DIR = os.path.dirname(_SERVER_DIR)
_ORGANIC_DIR = os.path.dirname(_BOARD_DIR)
_PROJECT_ROOT = os.path.dirname(_ORGANIC_DIR)

# board_data sibling import 보강
if _BOARD_DIR not in sys.path:
    sys.path.insert(0, _BOARD_DIR)

# `board.server` 패키지 import 를 위해 .claude-organic 상위 (=project_root) 도 등록
# (편의상; 본 테스트는 _common 을 직접 import 한다)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# T-513 P1 — worktree 안 .claude-organic 을 sys.path 최우선에 등록.
# 환경 PYTHONPATH=/home/deus/workspace/claude/.claude-organic (메인 develop)
# 이 미리 박혀 있어 worktree 안 board.server 변경이 import 시 가려지는 회귀
# 차단. _ORGANIC_DIR 안에 board 패키지가 있으므로 `from board.server import ...`
# 가 worktree 본으로 분기된다.
if _ORGANIC_DIR in sys.path:
    sys.path.remove(_ORGANIC_DIR)
sys.path.insert(0, _ORGANIC_DIR)

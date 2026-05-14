"""pytest conftest — sys.path 에 .claude-organic 추가 (engine.v2 import 용).

호출:
  cd <PROJECT_ROOT>
  python3 -m pytest .claude-organic/engine/v2/tests/
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
# .claude-organic/engine/v2/tests/conftest.py → .claude-organic
_ENGINE_ROOT = _HERE.parents[3]
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

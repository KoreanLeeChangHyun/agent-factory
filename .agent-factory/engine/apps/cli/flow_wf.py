"""flow-wf CLI application entrypoint.

The active implementation still lives in ``engine.v2.driver``. This module is
the stable app-layer entrypoint while driver internals continue to be extracted.
"""

from __future__ import annotations

import sys

from engine.v2.driver import main as driver_main


def main(argv: list[str] | None = None) -> int:
    """Run the current workflow driver."""
    return driver_main(argv)


if __name__ == "__main__":
    sys.exit(main())

"""flow-wf CLI application entrypoint."""

from __future__ import annotations

import sys

from engine.apps.production_line import main as driver_main


def main(argv: list[str] | None = None) -> int:
    """Run the current workflow driver."""
    return driver_main(argv)


if __name__ == "__main__":
    sys.exit(main())

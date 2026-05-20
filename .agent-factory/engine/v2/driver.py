"""Compatibility wrapper for the workflow driver."""

from __future__ import annotations

import sys

from engine.apps.production_line import main


if __name__ == "__main__":
    sys.exit(main())

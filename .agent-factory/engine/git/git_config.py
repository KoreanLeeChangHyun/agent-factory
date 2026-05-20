#!/usr/bin/env -S python3 -u
"""Compatibility wrapper for Git config CLI."""

from __future__ import annotations

from engine.adapters.git.config import main


if __name__ == "__main__":
    main()

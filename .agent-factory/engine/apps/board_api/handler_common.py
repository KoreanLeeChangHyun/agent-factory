"""Shared infrastructure for handler mixins — WorkRequest regex, conveyor dirs, engine lazy imports."""

from __future__ import annotations

import os
import re
import sys

# WorkRequest number format regular expression
_WORK_REQUEST_RE = re.compile(r'^WR-\d+$')
# Conveyor full directory listing (used in derived-from guard)
_CONVEYOR_ALL_DIRS = ('draft', 'accepted', 'executing', 'verifying', 'complete')


def _import_metrics_cli():
    """internal helper — not exposed as endpoint.

    Lazy import the metrics_cli module.

    After adding the .agent-factory directory to sys.path
    Import ``engine.apps.cli.metrics_cli``. Since only board/ is registered in the sys.path of the board server,
    The path is supplemented only when engine import is necessary.
    """
    agent_factory_dir = os.path.normpath(
        os.path.join(os.getcwd(), '.agent-factory'),
    )
    if agent_factory_dir not in sys.path:
        sys.path.insert(0, agent_factory_dir)
    from engine.apps.cli import metrics_cli  # noqa: WPS433
    return metrics_cli


def _import_launch_metrics_cli():
    """internal helper — not exposed as endpoint.

    Lazy import the launch_metrics_cli module.

    After adding the engine/ directory to sys.path, type ``flow.launch_metrics_cli``
    import. Engine import is complete with the same pattern as _import_metrics_cli.
    Supplement path only when necessary.
    """
    engine_dir = os.path.normpath(
        os.path.join(os.getcwd(), '.agent-factory', 'engine'),
    )
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    from flow import launch_metrics_cli  # noqa: WPS433
    return launch_metrics_cli

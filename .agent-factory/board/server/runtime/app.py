"""app module — board server process entrypoint."""

from __future__ import annotations

import atexit
import os
import signal
import sys
import threading
import time
from http.server import ThreadingHTTPServer

from board.server.support.common import (
    PORT_RANGE_START,
    PORT_RANGE_END,
    WATCH_DIRS,
    WATCH_INTERVAL,
    logger,
    _resolve_memory_dir,
    _get_git_branch,
)
from board.server.routing.http_router import BoardHTTPRequestHandler
from board.server.runtime import state as runtime_state
from engine.apps.board_api.runtime import (
    is_port_in_use,
    log_reaped_zombies,
    reap_zombie_children,
    remove_board_url_file,
    resolve_port as _resolve_board_port,
    write_board_url_file,
)
from engine.adapters.board.watchers import FileWatcher, GitBranchWatcher


def resolve_port(project_root: str) -> int:
    """Returns available ports in the range of 9900~9999 based on project path.

    The project path is MD5, which determines the initial port and navigates the sequential when collision.

    Args:
        project root: Project route absolute path

    Returns:
        Available port number (9900~9999 range)

    Raises:
        RuntimeError: 9900~9999 ports in the range are all used
    """
    return _resolve_board_port(
        project_root,
        range_start=PORT_RANGE_START,
        range_end=PORT_RANGE_END,
    )


def _run_server(project_root: str) -> None:
    """Run the server. Called in the forked child process.

    Args:
        project root: root directory of static file serving
    """
    os.chdir(project_root)

    port = resolve_port(project_root)

    # Reset and restore terminal session persist file path based on project root
    last_session_file = os.path.join(project_root, '.agent-factory', '.last-session-id')
    runtime_state.configure_brain_process(project_root, persist_file=last_session_file)
    if os.path.isfile(last_session_file):
        try:
            with open(last_session_file) as _sf:
                _saved_id = _sf.read().strip()
            if _saved_id:
                runtime_state.brain_process.set_session_id(_saved_id)
                logger.debug('Terminal session id Restore: %s', _saved_id)
        except OSError as _e:
            logger.debug('session id restore failed: %s', _e)

    # Legacy V1 workflow session cache is no longer created on startup.
    runtime_state.workflow_registry._persist_dir = None

    # production-line workflow history is persisted per run under work_dir/workflow-events.jsonl.
    # The old root-level production-line session cache is no longer created on startup.
    runtime_state.production_line_registry._persist_dir = None

    def _cleanup_runtime_files() -> None:
        """.agent-factory/.board.url"""
        remove_board_url_file(project_root)

    def _signal_handler(signum: int, frame: object) -> None:
        """When receiving SIGTERM/SIGINT, clean terminal process and runtime files."""
        runtime_state.brain_process.kill()
        _cleanup_runtime_files()
        sys.exit(0)

    atexit.register(_cleanup_runtime_files)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    write_board_url_file(project_root, port)

    # Registered Dynamic to WATCH DIRS for Memory Directories (Used as in the section → os.path.join)
    mem_dir = _resolve_memory_dir(project_root)
    if os.path.isdir(mem_dir):
        WATCH_DIRS[mem_dir] = 'memory'

    # FileWatcher
    def on_change(event_type: str, files: list[str]) -> None:
        """File change detection callback."""
        runtime_state.sse_manager.broadcast(event_type, files)
        runtime_state.poll_tracker.add(event_type, files)

    watcher = FileWatcher(
        project_root,
        on_change,
        watch_dirs=WATCH_DIRS,
        interval=WATCH_INTERVAL,
    )
    watcher_thread = threading.Thread(target=watcher.run, daemon=True)
    watcher_thread.start()

    # GitBranchWatcher starts — ‘.git/HEAD’ changes detection → SSE git branch event push
    def on_branch_change(branch: str) -> None:
        runtime_state.sse_manager.broadcast('git_branch', data={'branch': branch})
        runtime_state.poll_tracker.add('git_branch', [branch])

    git_watcher = GitBranchWatcher(
        project_root,
        on_branch_change,
        get_branch=_get_git_branch,
        interval=WATCH_INTERVAL,
        logger=logger,
    )
    git_watcher_thread = threading.Thread(target=git_watcher.run, daemon=True)
    git_watcher_thread.start()

    def _zombie_reaper_loop(interval: float = 60.0) -> None:
        """Reap a regular zombie child process.

        os.waitpid(-1, WNOHANG) is a child-friendly process that already ends without blunting
        60 seconds The daemon=True thread works and is immediately cleaned when the server ends.
        """
        while True:
            log_reaped_zombies(reap_zombie_children(), logger)
            time.sleep(interval)

    zombie_gc_thread = threading.Thread(
        target=_zombie_reaper_loop,
        name='zombie-gc',
        daemon=True,
    )
    zombie_gc_thread.start()
    logger.info('[zombie-gc] started — interval=60s')

    # Start ThreadingHTTPServer
    server = ThreadingHTTPServer(('0.0.0.0', port), BoardHTTPRequestHandler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        runtime_state.brain_process.kill()
        watcher.stop()
        git_watcher.stop()
        server.shutdown()

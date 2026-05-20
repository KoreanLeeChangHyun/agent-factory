"""T-500: server/production_line_launcher.py unit test.

Verified by:
  - Module import possible (spawn_production_line / _production_line_reader_loop callable)
  - spawn_production_line: env injection (V2_BOARD_POST/V2_REGISTRY_KEY), session_id determinism;
                    Response dict key matching, Popen failure branch, reader thread registration
  - _production_line_reader_loop: LAUNCH_FAILED when rc != 0, silent when rc == 0,
                            thread set self-removal
"""

from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

# sys.path setup — board package at <worktree>/.agent-factory/board
_AGENT_FACTORY_ROOT = Path(__file__).resolve().parents[3]
_WORKTREE_ROOT = _AGENT_FACTORY_ROOT.parent
for _p in (_WORKTREE_ROOT, _AGENT_FACTORY_ROOT):
    _path = str(_p)
    if _path not in sys.path:
        sys.path.insert(0, _path)


# ==============================================================================
# T01 — module import + symbol callable
# ==============================================================================


class TestModuleImport(unittest.TestCase):
    """Import production_line_launcher module + check core symbol callable."""

    def test_module_import(self):
        from board.server.processes import production_line_launcher
        self.assertTrue(callable(production_line_launcher.spawn_production_line))
        self.assertTrue(callable(production_line_launcher._production_line_reader_loop))
        self.assertIsInstance(production_line_launcher._LAUNCH_READER_THREADS, set)
        self.assertIsInstance(production_line_launcher._LAUNCH_READER_LOCK, type(threading.Lock()))


# ==============================================================================
# T02 — spawn_production_line side effects / response / environment variables
# ==============================================================================


def _make_mock_proc(returncode: int = 0, stdout: str = '', stderr: str = '') -> MagicMock:
    """Popen mock — Returns (stdout, stderr) when calling communicate()."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = MagicMock(return_value=(stdout, stderr))
    return proc


class TestSpawnProductionLine(unittest.TestCase):

    def setUp(self):
        from board.server.processes import production_line_launcher
        # The reader thread left behind by the previous test may remain in the set.
        with production_line_launcher._LAUNCH_READER_LOCK:
            production_line_launcher._LAUNCH_READER_THREADS.clear()
        self.production_line_launcher = production_line_launcher

    def tearDown(self):
        # Threads that can join wait until termination (mock proc.communicate returns immediately)
        with self.production_line_launcher._LAUNCH_READER_LOCK:
            threads = list(self.production_line_launcher._LAUNCH_READER_THREADS)
        for t in threads:
            t.join(timeout=2.0)

    def test_env_injection(self):
        """V2_BOARD_POST=true, V2_REGISTRY_KEY=YYYYMMDD-HHMMSS is injected into Popen env."""
        captured = {}

        def _fake_popen(cmd, **kwargs):
            captured['cmd'] = cmd
            captured['env'] = kwargs.get('env')
            captured['cwd'] = kwargs.get('cwd')
            return _make_mock_proc()

        with patch.object(self.production_line_launcher.subprocess, 'Popen', side_effect=_fake_popen), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe'):
            result = self.production_line_launcher.spawn_production_line('T-001', 'implement')

        self.assertTrue(result.get('ok'))
        self.assertEqual(captured['env']['V2_BOARD_POST'], 'true')
        registry_key = captured['env']['V2_REGISTRY_KEY']
        # Format YYYYMMDD-HHMMSS — 14 characters + 1 dash
        self.assertEqual(len(registry_key), 15)
        self.assertEqual(registry_key[8], '-')
        self.assertTrue(registry_key[:8].isdigit())
        self.assertTrue(registry_key[9:].isdigit())
        self.assertTrue(captured['cwd'])

    def test_session_id_determinism(self):
        """When fixing submitted_at session_id == f'wf-{ticket}-{registry_key}'."""
        fixed_dt = datetime(2026, 5, 19, 12, 30, 45, tzinfo=timezone.utc)

        with patch.object(self.production_line_launcher.subprocess, 'Popen', return_value=_make_mock_proc()), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe'), \
             patch.object(self.production_line_launcher, '_now_utc', return_value=fixed_dt):
            result = self.production_line_launcher.spawn_production_line('T-042', 'research')

        self.assertEqual(result['session_id'], 'wf-T-042-20260519-123045')
        self.assertEqual(result['submitted_at'], fixed_dt.isoformat())

    def test_response_shape(self):
        """Returns dict key set matching."""
        with patch.object(self.production_line_launcher.subprocess, 'Popen', return_value=_make_mock_proc()), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe'):
            result = self.production_line_launcher.spawn_production_line('T-099', 'implement')

        self.assertEqual(set(result.keys()), {
            'ok', 'status', 'ticket', 'command', 'submitted_at', 'session_id',
        })
        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 'starting')
        self.assertEqual(result['ticket'], 'T-099')
        self.assertEqual(result['command'], 'implement')

    def test_popen_failure_file_not_found(self):
        """If flow-wf binary does not exist, ok=False + error_kind='flow_wf_not_found'."""
        with patch.object(self.production_line_launcher.subprocess, 'Popen',
                          side_effect=FileNotFoundError('flow-wf')), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe'):
            result = self.production_line_launcher.spawn_production_line('T-001', 'implement')

        self.assertFalse(result['ok'])
        self.assertEqual(result['error_kind'], 'flow_wf_not_found')
        self.assertIn('message', result)

    def test_popen_failure_os_error(self):
        """When OSError ok=False + error_kind='popen_failed'."""
        with patch.object(self.production_line_launcher.subprocess, 'Popen',
                          side_effect=OSError('permission denied')), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe'):
            result = self.production_line_launcher.spawn_production_line('T-002', 'implement')

        self.assertFalse(result['ok'])
        self.assertEqual(result['error_kind'], 'popen_failed')

    def test_reader_thread_registered(self):
        """Immediately after spawn, one reader is added to _LAUNCH_READER_THREADS."""
        # Mock so that communicate does not return immediately but waits for a while
        proc = MagicMock()
        proc.returncode = 0

        comm_event = threading.Event()

        def _slow_communicate(timeout=None):
            comm_event.wait(timeout=5.0)
            return ('', '')

        proc.communicate = _slow_communicate

        with patch.object(self.production_line_launcher.subprocess, 'Popen', return_value=proc), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe'):
            self.production_line_launcher.spawn_production_line('T-201', 'implement')

            # Confirm registration in thread set immediately after spawn
            with self.production_line_launcher._LAUNCH_READER_LOCK:
                count = len(self.production_line_launcher._LAUNCH_READER_THREADS)
            self.assertEqual(count, 1)

            # reader termination signal
            comm_event.set()

    def test_emits_pending_and_started(self):
        """LAUNCH_PENDING + LAUNCH_STARTED is called by the _emit function."""
        emitted = []

        def _capture_emit(event, ticket, **kwargs):
            emitted.append((event, ticket, kwargs))

        with patch.object(self.production_line_launcher.subprocess, 'Popen', return_value=_make_mock_proc()), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe', side_effect=_capture_emit):
            self.production_line_launcher.spawn_production_line('T-301', 'review')

        events = [e[0] for e in emitted]
        self.assertIn('LAUNCH_PENDING', events)
        self.assertIn('LAUNCH_STARTED', events)


# ==============================================================================
# T03 — _production_line_reader_loop operation
# ==============================================================================


class TestReaderLoop(unittest.TestCase):

    def setUp(self):
        from board.server.processes import production_line_launcher
        with production_line_launcher._LAUNCH_READER_LOCK:
            production_line_launcher._LAUNCH_READER_THREADS.clear()
        self.production_line_launcher = production_line_launcher

    def test_silent_on_zero_exit(self):
        """When rc == 0 (normal completion), LAUNCH_FAILED emits 0 cases."""
        emitted = []

        def _capture(event, ticket, **kwargs):
            emitted.append((event, ticket, kwargs))

        proc = _make_mock_proc(returncode=0, stdout='ok', stderr='')
        submitted = datetime.now(timezone.utc)

        with patch.object(self.production_line_launcher, '_emit_launch_event_safe', side_effect=_capture):
            # Direct call (without thread spawn)
            self_thread = threading.current_thread()
            with self.production_line_launcher._LAUNCH_READER_LOCK:
                self.production_line_launcher._LAUNCH_READER_THREADS.add(self_thread)
            self.production_line_launcher._production_line_reader_loop(proc, 'T-401', 'implement', submitted)

        # LAUNCH_FAILED 0 calls
        self.assertEqual(emitted, [])

    def test_emits_failed_on_nonzero_exit(self):
        """rc != 0 at LAUNCH_FAILED + reason='driver_nonzero_exit' + returncode/error_message carry."""
        emitted = []

        def _capture(event, ticket, **kwargs):
            emitted.append((event, ticket, kwargs))

        proc = _make_mock_proc(returncode=1, stdout='', stderr='driver crashed')
        submitted = datetime.now(timezone.utc)

        with patch.object(self.production_line_launcher, '_emit_launch_event_safe', side_effect=_capture):
            self_thread = threading.current_thread()
            with self.production_line_launcher._LAUNCH_READER_LOCK:
                self.production_line_launcher._LAUNCH_READER_THREADS.add(self_thread)
            self.production_line_launcher._production_line_reader_loop(proc, 'T-402', 'implement', submitted)

        self.assertEqual(len(emitted), 1)
        event, ticket, payload = emitted[0]
        self.assertEqual(event, 'LAUNCH_FAILED')
        self.assertEqual(ticket, 'T-402')
        self.assertEqual(payload['reason'], 'driver_nonzero_exit')
        self.assertEqual(payload['returncode'], 1)
        self.assertEqual(payload['command'], 'implement')
        self.assertIn('driver crashed', payload['error_message'])

    def test_thread_set_self_discard(self):
        """After the reader terminates, remove itself from _LAUNCH_READER_THREADS (block GC leak)."""
        proc = _make_mock_proc(returncode=0)
        submitted = datetime.now(timezone.utc)

        # Self_thread identification is meaningful only when executed as a real thread.
        with patch.object(self.production_line_launcher, '_emit_launch_event_safe'):
            reader = threading.Thread(
                target=self.production_line_launcher._production_line_reader_loop,
                args=(proc, 'T-501', 'implement', submitted),
                daemon=True,
            )
            with self.production_line_launcher._LAUNCH_READER_LOCK:
                self.production_line_launcher._LAUNCH_READER_THREADS.add(reader)
            reader.start()
            reader.join(timeout=5.0)

        with self.production_line_launcher._LAUNCH_READER_LOCK:
            self.assertNotIn(reader, self.production_line_launcher._LAUNCH_READER_THREADS)


# ==============================================================================
# T04 — Race condition unit (P3 reinforcement — thread leak verification after concurrent spawn)
# ==============================================================================


class TestConcurrentSpawn(unittest.TestCase):
    """P3 race condition unit — Verification of thread set leaks/conflicts after concurrent spawn."""

    def setUp(self):
        from board.server.processes import production_line_launcher
        with production_line_launcher._LAUNCH_READER_LOCK:
            production_line_launcher._LAUNCH_READER_THREADS.clear()
        self.production_line_launcher = production_line_launcher

    def test_concurrent_spawn_no_thread_leak(self):
        """After spawning twice, wait until the reader thread ends → thread set size 0."""
        # terminate immediately mock
        with patch.object(self.production_line_launcher.subprocess, 'Popen',
                          return_value=_make_mock_proc()), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe'):
            self.production_line_launcher.spawn_production_line('T-601', 'implement')
            self.production_line_launcher.spawn_production_line('T-602', 'implement')

        # Wait for both reader joins (mock proc.communicate returns immediately → reader exits soon)
        # Wait up to 2 seconds
        deadline = time.time() + 2.0
        while time.time() < deadline:
            with self.production_line_launcher._LAUNCH_READER_LOCK:
                if len(self.production_line_launcher._LAUNCH_READER_THREADS) == 0:
                    break
            time.sleep(0.05)

        with self.production_line_launcher._LAUNCH_READER_LOCK:
            remaining = len(self.production_line_launcher._LAUNCH_READER_THREADS)
        self.assertEqual(remaining, 0, 'reader threads leaked')

    def test_concurrent_spawn_distinct_session_ids(self):
        """session_id is different for different timestamps without time.sleep(>=1s) (advisory)."""
        # datetime.now monkeypatch — force 1 second difference
        dt1 = datetime(2026, 5, 19, 12, 30, 45, tzinfo=timezone.utc)
        dt2 = datetime(2026, 5, 19, 12, 30, 46, tzinfo=timezone.utc)
        seq = iter([dt1, dt2, dt2])  # call now 1+ inside spawn (submitted_at + spawn_elapsed)

        def _next_now():
            try:
                return next(seq)
            except StopIteration:
                return dt2

        with patch.object(self.production_line_launcher.subprocess, 'Popen',
                          return_value=_make_mock_proc()), \
             patch.object(self.production_line_launcher, '_emit_launch_event_safe'), \
             patch.object(self.production_line_launcher, '_now_utc', side_effect=_next_now):
            r1 = self.production_line_launcher.spawn_production_line('T-701', 'implement')
            # seq reset — second call starts with dt2
            seq2 = iter([dt2, dt2])

            def _next_now2():
                try:
                    return next(seq2)
                except StopIteration:
                    return dt2

            with patch.object(self.production_line_launcher, '_now_utc', side_effect=_next_now2):
                r2 = self.production_line_launcher.spawn_production_line('T-702', 'implement')

        self.assertNotEqual(r1['session_id'], r2['session_id'])


if __name__ == '__main__':
    unittest.main()

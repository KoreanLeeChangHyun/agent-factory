"""T-500: server/v2_launcher.py 단위 테스트.

검증 대상:
  - 모듈 import 가능 (spawn_v2_driver / _v2_driver_reader_loop callable)
  - spawn_v2_driver: env 주입 (V2_BOARD_POST/V2_REGISTRY_KEY), session_id 결정론,
                    응답 dict 키 정합, Popen 실패 분기, reader thread 등록
  - _v2_driver_reader_loop: rc != 0 시 LAUNCH_FAILED, rc == 0 시 silent,
                            thread set 자기 제거
"""

from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# sys.path setup — board package at <worktree>/.claude-organic/board
_WORKTREE_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'),
)
_CLAUDE_ORGANIC = os.path.normpath(os.path.join(_WORKTREE_ROOT, '.claude-organic'))
for _p in (_WORKTREE_ROOT, _CLAUDE_ORGANIC):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ==============================================================================
# T01 — 모듈 import + 심볼 callable
# ==============================================================================


class TestModuleImport(unittest.TestCase):
    """v2_launcher 모듈 import + 핵심 심볼 callable 확인."""

    def test_module_import(self):
        from board.server import v2_launcher
        self.assertTrue(callable(v2_launcher.spawn_v2_driver))
        self.assertTrue(callable(v2_launcher._v2_driver_reader_loop))
        self.assertIsInstance(v2_launcher._LAUNCH_READER_THREADS, set)
        self.assertIsInstance(v2_launcher._LAUNCH_READER_LOCK, type(threading.Lock()))


# ==============================================================================
# T02 — spawn_v2_driver 부수효과 / 응답 / 환경 변수
# ==============================================================================


def _make_mock_proc(returncode: int = 0, stdout: str = '', stderr: str = '') -> MagicMock:
    """Popen mock — communicate() 호출 시 (stdout, stderr) 반환."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = MagicMock(return_value=(stdout, stderr))
    return proc


class TestSpawnV2Driver(unittest.TestCase):

    def setUp(self):
        from board.server import v2_launcher
        # 이전 테스트가 남긴 reader thread 가 set 에 남아있을 수 있어 정리
        with v2_launcher._LAUNCH_READER_LOCK:
            v2_launcher._LAUNCH_READER_THREADS.clear()
        self.v2_launcher = v2_launcher

    def tearDown(self):
        # join 가능한 thread 는 종료까지 대기 (mock proc.communicate 즉시 반환)
        with self.v2_launcher._LAUNCH_READER_LOCK:
            threads = list(self.v2_launcher._LAUNCH_READER_THREADS)
        for t in threads:
            t.join(timeout=2.0)

    def test_env_injection(self):
        """V2_BOARD_POST=true, V2_REGISTRY_KEY=YYYYMMDD-HHMMSS 가 Popen env 에 주입된다."""
        captured = {}

        def _fake_popen(cmd, **kwargs):
            captured['cmd'] = cmd
            captured['env'] = kwargs.get('env')
            captured['cwd'] = kwargs.get('cwd')
            return _make_mock_proc()

        with patch.object(self.v2_launcher.subprocess, 'Popen', side_effect=_fake_popen), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe'):
            result = self.v2_launcher.spawn_v2_driver('T-001', 'implement')

        self.assertTrue(result.get('ok'))
        self.assertEqual(captured['env']['V2_BOARD_POST'], 'true')
        registry_key = captured['env']['V2_REGISTRY_KEY']
        # YYYYMMDD-HHMMSS 형태 — 14자 + 1 dash
        self.assertEqual(len(registry_key), 15)
        self.assertEqual(registry_key[8], '-')
        self.assertTrue(registry_key[:8].isdigit())
        self.assertTrue(registry_key[9:].isdigit())
        self.assertTrue(captured['cwd'])

    def test_session_id_determinism(self):
        """submitted_at 고정 시 session_id == f'wf-{ticket}-{registry_key}'."""
        fixed_dt = datetime(2026, 5, 19, 12, 30, 45, tzinfo=timezone.utc)

        with patch.object(self.v2_launcher.subprocess, 'Popen', return_value=_make_mock_proc()), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe'), \
             patch.object(self.v2_launcher, '_now_utc', return_value=fixed_dt):
            result = self.v2_launcher.spawn_v2_driver('T-042', 'research')

        self.assertEqual(result['session_id'], 'wf-T-042-20260519-123045')
        self.assertEqual(result['submitted_at'], fixed_dt.isoformat())

    def test_response_shape(self):
        """반환 dict 키 set 정합."""
        with patch.object(self.v2_launcher.subprocess, 'Popen', return_value=_make_mock_proc()), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe'):
            result = self.v2_launcher.spawn_v2_driver('T-099', 'implement')

        self.assertEqual(set(result.keys()), {
            'ok', 'status', 'ticket', 'command', 'submitted_at', 'session_id',
        })
        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 'starting')
        self.assertEqual(result['ticket'], 'T-099')
        self.assertEqual(result['command'], 'implement')

    def test_popen_failure_file_not_found(self):
        """flow-wf binary 미존재 시 ok=False + error_kind='flow_wf_not_found'."""
        with patch.object(self.v2_launcher.subprocess, 'Popen',
                          side_effect=FileNotFoundError('flow-wf')), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe'):
            result = self.v2_launcher.spawn_v2_driver('T-001', 'implement')

        self.assertFalse(result['ok'])
        self.assertEqual(result['error_kind'], 'flow_wf_not_found')
        self.assertIn('message', result)

    def test_popen_failure_os_error(self):
        """OSError 시 ok=False + error_kind='popen_failed'."""
        with patch.object(self.v2_launcher.subprocess, 'Popen',
                          side_effect=OSError('permission denied')), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe'):
            result = self.v2_launcher.spawn_v2_driver('T-002', 'implement')

        self.assertFalse(result['ok'])
        self.assertEqual(result['error_kind'], 'popen_failed')

    def test_reader_thread_registered(self):
        """spawn 직후 _LAUNCH_READER_THREADS 에 reader 가 1건 추가된다."""
        # communicate 가 즉시 반환되지 않고 잠시 대기하도록 mock
        proc = MagicMock()
        proc.returncode = 0

        comm_event = threading.Event()

        def _slow_communicate(timeout=None):
            comm_event.wait(timeout=5.0)
            return ('', '')

        proc.communicate = _slow_communicate

        with patch.object(self.v2_launcher.subprocess, 'Popen', return_value=proc), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe'):
            self.v2_launcher.spawn_v2_driver('T-201', 'implement')

            # spawn 직후 thread set 에 등록 확인
            with self.v2_launcher._LAUNCH_READER_LOCK:
                count = len(self.v2_launcher._LAUNCH_READER_THREADS)
            self.assertEqual(count, 1)

            # reader 종료 신호
            comm_event.set()

    def test_emits_pending_and_started(self):
        """LAUNCH_PENDING + LAUNCH_STARTED 가 _emit 함수에 의해 호출된다."""
        emitted = []

        def _capture_emit(event, ticket, **kwargs):
            emitted.append((event, ticket, kwargs))

        with patch.object(self.v2_launcher.subprocess, 'Popen', return_value=_make_mock_proc()), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe', side_effect=_capture_emit):
            self.v2_launcher.spawn_v2_driver('T-301', 'review')

        events = [e[0] for e in emitted]
        self.assertIn('LAUNCH_PENDING', events)
        self.assertIn('LAUNCH_STARTED', events)


# ==============================================================================
# T03 — _v2_driver_reader_loop 동작
# ==============================================================================


class TestReaderLoop(unittest.TestCase):

    def setUp(self):
        from board.server import v2_launcher
        with v2_launcher._LAUNCH_READER_LOCK:
            v2_launcher._LAUNCH_READER_THREADS.clear()
        self.v2_launcher = v2_launcher

    def test_silent_on_zero_exit(self):
        """rc == 0 (정상 완료) 시 LAUNCH_FAILED emit 0 건."""
        emitted = []

        def _capture(event, ticket, **kwargs):
            emitted.append((event, ticket, kwargs))

        proc = _make_mock_proc(returncode=0, stdout='ok', stderr='')
        submitted = datetime.now(timezone.utc)

        with patch.object(self.v2_launcher, '_emit_launch_event_safe', side_effect=_capture):
            # 직접 호출 (thread spawn 없이)
            self_thread = threading.current_thread()
            with self.v2_launcher._LAUNCH_READER_LOCK:
                self.v2_launcher._LAUNCH_READER_THREADS.add(self_thread)
            self.v2_launcher._v2_driver_reader_loop(proc, 'T-401', 'implement', submitted)

        # LAUNCH_FAILED 호출 0건
        self.assertEqual(emitted, [])

    def test_emits_failed_on_nonzero_exit(self):
        """rc != 0 시 LAUNCH_FAILED + reason='driver_nonzero_exit' + returncode/error_message 캐리."""
        emitted = []

        def _capture(event, ticket, **kwargs):
            emitted.append((event, ticket, kwargs))

        proc = _make_mock_proc(returncode=1, stdout='', stderr='driver crashed')
        submitted = datetime.now(timezone.utc)

        with patch.object(self.v2_launcher, '_emit_launch_event_safe', side_effect=_capture):
            self_thread = threading.current_thread()
            with self.v2_launcher._LAUNCH_READER_LOCK:
                self.v2_launcher._LAUNCH_READER_THREADS.add(self_thread)
            self.v2_launcher._v2_driver_reader_loop(proc, 'T-402', 'implement', submitted)

        self.assertEqual(len(emitted), 1)
        event, ticket, payload = emitted[0]
        self.assertEqual(event, 'LAUNCH_FAILED')
        self.assertEqual(ticket, 'T-402')
        self.assertEqual(payload['reason'], 'driver_nonzero_exit')
        self.assertEqual(payload['returncode'], 1)
        self.assertEqual(payload['command'], 'implement')
        self.assertIn('driver crashed', payload['error_message'])

    def test_thread_set_self_discard(self):
        """reader 종료 후 자기 자신을 _LAUNCH_READER_THREADS 에서 제거 (GC 누수 차단)."""
        proc = _make_mock_proc(returncode=0)
        submitted = datetime.now(timezone.utc)

        # 진짜 thread 로 실행해야 self_thread 식별 의미 있음
        with patch.object(self.v2_launcher, '_emit_launch_event_safe'):
            reader = threading.Thread(
                target=self.v2_launcher._v2_driver_reader_loop,
                args=(proc, 'T-501', 'implement', submitted),
                daemon=True,
            )
            with self.v2_launcher._LAUNCH_READER_LOCK:
                self.v2_launcher._LAUNCH_READER_THREADS.add(reader)
            reader.start()
            reader.join(timeout=5.0)

        with self.v2_launcher._LAUNCH_READER_LOCK:
            self.assertNotIn(reader, self.v2_launcher._LAUNCH_READER_THREADS)


# ==============================================================================
# T04 — race condition 단위 (P3 보강 — concurrent spawn 후 thread leak 검증)
# ==============================================================================


class TestConcurrentSpawn(unittest.TestCase):
    """P3 race condition 단위 — concurrent spawn 후 thread set 누수/충돌 검증."""

    def setUp(self):
        from board.server import v2_launcher
        with v2_launcher._LAUNCH_READER_LOCK:
            v2_launcher._LAUNCH_READER_THREADS.clear()
        self.v2_launcher = v2_launcher

    def test_concurrent_spawn_no_thread_leak(self):
        """2회 spawn 후 reader thread 종료까지 대기 → thread set size 0."""
        # 즉시 종료 mock
        with patch.object(self.v2_launcher.subprocess, 'Popen',
                          return_value=_make_mock_proc()), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe'):
            self.v2_launcher.spawn_v2_driver('T-601', 'implement')
            self.v2_launcher.spawn_v2_driver('T-602', 'implement')

        # 양쪽 reader join 대기 (mock proc.communicate 즉시 반환 → reader 곧 종료)
        # 최대 2초 대기
        deadline = time.time() + 2.0
        while time.time() < deadline:
            with self.v2_launcher._LAUNCH_READER_LOCK:
                if len(self.v2_launcher._LAUNCH_READER_THREADS) == 0:
                    break
            time.sleep(0.05)

        with self.v2_launcher._LAUNCH_READER_LOCK:
            remaining = len(self.v2_launcher._LAUNCH_READER_THREADS)
        self.assertEqual(remaining, 0, 'reader threads leaked')

    def test_concurrent_spawn_distinct_session_ids(self):
        """time.sleep(>=1s) 없이 다른 timestamp 시 session_id 다름 (advisory)."""
        # datetime.now monkeypatch — 1초 차이 강제
        dt1 = datetime(2026, 5, 19, 12, 30, 45, tzinfo=timezone.utc)
        dt2 = datetime(2026, 5, 19, 12, 30, 46, tzinfo=timezone.utc)
        seq = iter([dt1, dt2, dt2])  # spawn 안에서 now 1+ 호출 (submitted_at + spawn_elapsed)

        def _next_now():
            try:
                return next(seq)
            except StopIteration:
                return dt2

        with patch.object(self.v2_launcher.subprocess, 'Popen',
                          return_value=_make_mock_proc()), \
             patch.object(self.v2_launcher, '_emit_launch_event_safe'), \
             patch.object(self.v2_launcher, '_now_utc', side_effect=_next_now):
            r1 = self.v2_launcher.spawn_v2_driver('T-701', 'implement')
            # seq 재설정 — 두 번째 호출은 dt2 로 시작
            seq2 = iter([dt2, dt2])

            def _next_now2():
                try:
                    return next(seq2)
                except StopIteration:
                    return dt2

            with patch.object(self.v2_launcher, '_now_utc', side_effect=_next_now2):
                r2 = self.v2_launcher.spawn_v2_driver('T-702', 'implement')

        self.assertNotEqual(r1['session_id'], r2['session_id'])


if __name__ == '__main__':
    unittest.main()

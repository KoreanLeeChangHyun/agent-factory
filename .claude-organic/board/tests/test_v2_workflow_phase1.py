"""T-495 Phase 1 회귀 테스트 — v2 워크플로우 백엔드 인프라.

검증 대상:
  - V2WorkflowSession dataclass + V2WorkflowSessionRegistry (CRUD + idempotent)
  - V2WorkflowSSEChannel (broadcast + emit_* + jsonl persist + client fan-out)
  - V2WorkflowHandlerMixin._SESSION_PATH_RE (path parsing 정합)
  - http_router 임포트 smoke + Mixin 합성 검증
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import unittest

# sys.path — `.claude-organic/` (board.server.* 절대 import 용)
_WORKTREE_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'),
)
_ORGANIC_ROOT = os.path.normpath(os.path.join(_WORKTREE_ROOT, '.claude-organic'))
_BOARD_ROOT = os.path.join(_ORGANIC_ROOT, 'board')
for _p in (_WORKTREE_ROOT, _ORGANIC_ROOT, _BOARD_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ==============================================================================
# T01 — V2WorkflowSession dataclass + Registry CRUD
# ==============================================================================


class TestV2WorkflowSession(unittest.TestCase):

    def test_dataclass_defaults(self):
        from board.server.v2_workflow_session import V2WorkflowSession
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        channel = V2WorkflowSSEChannel(session_id='wf-T-001-abc')
        s = V2WorkflowSession(
            session_id='wf-T-001-abc',
            ticket_id='T-001',
            command='implement',
            work_dir='/tmp/runs/20260516',
            channel=channel,
        )
        self.assertEqual(s.status, 'idle')
        self.assertEqual(s.current_step, 'NONE')
        self.assertEqual(s.current_phase, '')
        self.assertEqual(s.worktree_path, '')
        self.assertGreater(s.cycle_start_ts, 0)
        self.assertGreater(s.step_ts, 0)
        self.assertEqual(s.artifacts, {})


class TestV2WorkflowSessionRegistry(unittest.TestCase):

    def setUp(self):
        from board.server.v2_workflow_session import V2WorkflowSessionRegistry
        self.tmpdir = tempfile.mkdtemp(prefix='v2reg_')
        self.reg = V2WorkflowSessionRegistry(persist_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_and_get(self):
        s = self.reg.create('wf-T-001-a', 'T-001', 'implement', '/tmp/w1')
        self.assertEqual(s.session_id, 'wf-T-001-a')
        self.assertEqual(self.reg.get('wf-T-001-a'), s)
        self.assertIsNone(self.reg.get('missing'))

    def test_create_idempotent(self):
        s1 = self.reg.create('wf-T-002-a', 'T-002', 'implement', '/tmp/w2')
        s2 = self.reg.create('wf-T-002-a', 'T-002', 'implement', '/tmp/w2')
        self.assertIs(s1, s2)

    def test_get_by_ticket(self):
        self.reg.create('wf-T-003-a', 'T-003', 'research', '/tmp/w3')
        s = self.reg.get_by_ticket('T-003')
        self.assertIsNotNone(s)
        self.assertEqual(s.ticket_id, 'T-003')

    def test_list_all(self):
        self.reg.create('wf-T-004-a', 'T-004', 'implement', '/tmp/w4')
        self.reg.create('wf-T-005-a', 'T-005', 'review', '/tmp/w5')
        sessions = self.reg.list_all()
        self.assertEqual(len(sessions), 2)
        keys = {s['session_id'] for s in sessions}
        self.assertEqual(keys, {'wf-T-004-a', 'wf-T-005-a'})

    def test_update_step_status_mapping(self):
        self.reg.create('wf-T-006-a', 'T-006', 'implement', '/tmp/w6')
        s = self.reg.update_step('wf-T-006-a', 'PLAN')
        self.assertEqual(s.current_step, 'PLAN')
        self.assertEqual(s.status, 'running')

        s = self.reg.update_step('wf-T-006-a', 'DONE')
        self.assertEqual(s.status, 'completed')

        # FAILED 매핑 — 새 세션으로
        self.reg.create('wf-T-007-a', 'T-007', 'implement', '/tmp/w7')
        s = self.reg.update_step('wf-T-007-a', 'FAILED')
        self.assertEqual(s.status, 'failed')

    def test_update_step_with_phase(self):
        self.reg.create('wf-T-008-a', 'T-008', 'implement', '/tmp/w8')
        s = self.reg.update_step('wf-T-008-a', 'WORK', phase='P1')
        self.assertEqual(s.current_step, 'WORK')
        self.assertEqual(s.current_phase, 'P1')

    def test_set_status(self):
        self.reg.create('wf-T-009-a', 'T-009', 'implement', '/tmp/w9')
        s = self.reg.set_status('wf-T-009-a', 'completed')
        self.assertEqual(s.status, 'completed')

    def test_add_artifact(self):
        self.reg.create('wf-T-010-a', 'T-010', 'implement', '/tmp/w10')
        s = self.reg.add_artifact('wf-T-010-a', 'plan.md', size=1024)
        self.assertIn('plan.md', s.artifacts)
        self.assertEqual(s.artifacts['plan.md']['size'], 1024)

    def test_remove_vs_purge(self):
        self.reg.create('wf-T-011-a', 'T-011', 'implement', '/tmp/w11')
        fpath = os.path.join(self.tmpdir, 'wf-T-011-a.jsonl')
        self.assertTrue(os.path.exists(fpath))
        # remove → 디스크 보존
        self.assertTrue(self.reg.remove('wf-T-011-a'))
        self.assertTrue(os.path.exists(fpath))
        # purge → 디스크 삭제
        self.reg.create('wf-T-012-a', 'T-012', 'implement', '/tmp/w12')
        fpath2 = os.path.join(self.tmpdir, 'wf-T-012-a.jsonl')
        self.assertTrue(self.reg.purge('wf-T-012-a'))
        self.assertFalse(os.path.exists(fpath2))

    def test_persist_meta_first_line(self):
        self.reg.create('wf-T-013-a', 'T-013', 'implement', '/tmp/w13', worktree_path='/tmp/wt13')
        fpath = os.path.join(self.tmpdir, 'wf-T-013-a.jsonl')
        with open(fpath) as f:
            first = json.loads(f.readline())
        meta = first['_meta']
        self.assertEqual(meta['session_id'], 'wf-T-013-a')
        self.assertEqual(meta['ticket_id'], 'T-013')
        self.assertEqual(meta['command'], 'implement')
        self.assertEqual(meta['worktree_path'], '/tmp/wt13')
        self.assertEqual(meta['engine_version'], 'v2')

    def test_load_from_disk(self):
        from board.server.v2_workflow_session import V2WorkflowSessionRegistry
        self.reg.create('wf-T-014-a', 'T-014', 'implement', '/tmp/w14')
        self.reg.create('wf-T-015-a', 'T-015', 'research', '/tmp/w15')

        reg2 = V2WorkflowSessionRegistry(persist_dir=self.tmpdir)
        loaded = reg2.load_from_disk()
        self.assertEqual(loaded, 2)
        s = reg2.get('wf-T-014-a')
        self.assertEqual(s.ticket_id, 'T-014')
        self.assertEqual(s.status, 'completed')


# ==============================================================================
# T02 — V2WorkflowSSEChannel broadcast + persist
# ==============================================================================


class _FakeWFile:
    """SSE 전송 대상 mock — bytes 누적."""

    def __init__(self):
        self.buf = io.BytesIO()

    def write(self, data: bytes) -> int:
        return self.buf.write(data)

    def flush(self) -> None:
        pass

    def value(self) -> bytes:
        return self.buf.getvalue()


class TestV2WorkflowSSEChannel(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='v2chan_')
        self.persist_path = os.path.join(self.tmpdir, 'session.jsonl')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_broadcast_to_client(self):
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        ch = V2WorkflowSSEChannel(session_id='wf-T-100-a', persist_path=self.persist_path)
        client = _FakeWFile()
        ch.add(client)
        self.assertEqual(ch.client_count(), 1)
        ch.broadcast('workflow_step', {'step': 'PLAN'})
        data = client.value().decode('utf-8')
        self.assertIn('event: workflow_step', data)
        self.assertIn('"step": "PLAN"', data)
        # seq id 가 0 부여
        self.assertIn('id: 0\n', data)

    def test_persist_writes_jsonl(self):
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        ch = V2WorkflowSSEChannel(session_id='wf-T-101-a', persist_path=self.persist_path)
        ch.broadcast('workflow_step', {'step': 'PLAN'})
        ch.broadcast('workflow_step', {'step': 'WORK'})
        with open(self.persist_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)
        rec1 = json.loads(lines[0])
        self.assertEqual(rec1['event'], 'workflow_step')
        self.assertEqual(rec1['payload']['step'], 'PLAN')

    def test_emit_step_payload(self):
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        ch = V2WorkflowSSEChannel(session_id='wf-T-102-a')
        client = _FakeWFile()
        ch.add(client)
        ch.emit_step('WORK', phase='P1', prev_step='PLAN')
        data = client.value().decode('utf-8')
        self.assertIn('"step": "WORK"', data)
        self.assertIn('"phase": "P1"', data)
        self.assertIn('"prev_step": "PLAN"', data)

    def test_emit_stdout_payload(self):
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        ch = V2WorkflowSSEChannel(session_id='wf-T-103-a')
        client = _FakeWFile()
        ch.add(client)
        ch.emit_stdout('hello', raw={'type': 'assistant'})
        data = client.value().decode('utf-8')
        self.assertIn('event: workflow_stdout', data)
        self.assertIn('"text": "hello"', data)
        self.assertIn('"raw":', data)

    def test_emit_phase_payload(self):
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        ch = V2WorkflowSSEChannel(session_id='wf-T-104-a')
        client = _FakeWFile()
        ch.add(client)
        ch.emit_phase('P2', action='end')
        data = client.value().decode('utf-8')
        self.assertIn('event: workflow_phase', data)
        self.assertIn('"phase": "P2"', data)
        self.assertIn('"action": "end"', data)

    def test_emit_finish_payload(self):
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        ch = V2WorkflowSSEChannel(session_id='wf-T-105-a')
        client = _FakeWFile()
        ch.add(client)
        ch.emit_finish('ok', summary='all green')
        data = client.value().decode('utf-8')
        self.assertIn('event: workflow_finish', data)
        self.assertIn('"outcome": "ok"', data)
        self.assertIn('"summary": "all green"', data)

    def test_client_remove(self):
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        ch = V2WorkflowSSEChannel(session_id='wf-T-106-a')
        client = _FakeWFile()
        ch.add(client)
        self.assertEqual(ch.client_count(), 1)
        ch.remove(client)
        self.assertEqual(ch.client_count(), 0)

    def test_dead_client_pruned(self):
        from board.server.v2_sse_channel import V2WorkflowSSEChannel
        ch = V2WorkflowSSEChannel(session_id='wf-T-107-a')

        class _BrokenWFile:
            def write(self, _):
                raise BrokenPipeError('client gone')

            def flush(self):
                pass

        client = _BrokenWFile()
        ch.add(client)
        ch.broadcast('workflow_step', {'step': 'PLAN'})
        # broadcast 후 dead client 가 제거됨
        self.assertEqual(ch.client_count(), 0)


# ==============================================================================
# T03 — V2WorkflowHandlerMixin path parser
# ==============================================================================


class TestV2WorkflowPathRegex(unittest.TestCase):

    def test_session_path_re(self):
        from board.server.handlers.v2_workflow import _SESSION_PATH_RE

        m = _SESSION_PATH_RE.match('/api/v2/sessions/wf-T-100-a')
        self.assertIsNotNone(m)
        self.assertEqual(m.group('session_id'), 'wf-T-100-a')
        self.assertIsNone(m.group('sub'))

        m = _SESSION_PATH_RE.match('/api/v2/sessions/wf-T-100-a/events')
        self.assertEqual(m.group('sub'), 'events')

        m = _SESSION_PATH_RE.match('/api/v2/sessions/wf-T-100-a/step')
        self.assertEqual(m.group('sub'), 'step')

        m = _SESSION_PATH_RE.match('/api/v2/sessions/wf-T-100-a/artifacts/plan.md')
        self.assertEqual(m.group('sub'), 'artifacts/plan.md')

        m = _SESSION_PATH_RE.match('/api/v2/sessions/wf-T-100-a/artifacts/work/P1.md')
        self.assertEqual(m.group('sub'), 'artifacts/work/P1.md')

        # 매칭 실패 케이스
        self.assertIsNone(_SESSION_PATH_RE.match('/api/v2/sessions'))
        self.assertIsNone(_SESSION_PATH_RE.match('/api/v1/sessions/abc'))


# ==============================================================================
# T04 — Import smoke + Mixin 합성 검증
# ==============================================================================


class TestImportSmoke(unittest.TestCase):

    def test_import_v2_modules(self):
        try:
            from board.server.v2_workflow_session import (
                V2WorkflowSession,
                V2WorkflowSessionRegistry,
            )
            from board.server.v2_sse_channel import V2WorkflowSSEChannel
            from board.server.handlers.v2_workflow import V2WorkflowHandlerMixin
        except ImportError as exc:
            self.fail(f'ImportError: {exc}')

    def test_state_singleton_registered(self):
        from board.server import state
        from board.server.v2_workflow_session import V2WorkflowSessionRegistry
        self.assertIsInstance(state.v2_workflow_registry, V2WorkflowSessionRegistry)

    def test_http_router_mixin_composition(self):
        from board.server.http_router import BoardHTTPRequestHandler
        from board.server.handlers.v2_workflow import V2WorkflowHandlerMixin
        self.assertTrue(issubclass(BoardHTTPRequestHandler, V2WorkflowHandlerMixin))

    def test_dispatch_methods_exist(self):
        from board.server.http_router import BoardHTTPRequestHandler
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_dispatch_get'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_dispatch_post'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_session_create'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_sessions_list'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_session_detail'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_session_events'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_session_step'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_session_stdout'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_session_phase'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_session_finish'))
        self.assertTrue(hasattr(BoardHTTPRequestHandler, '_v2_handle_session_artifact'))


if __name__ == '__main__':
    unittest.main()

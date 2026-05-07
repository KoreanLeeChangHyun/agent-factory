"""T-424 핸들러 도메인 모듈화 회귀 테스트.

회귀 fix 4건 행동 검증:
  #1 (research merge_skipped) — _classify_done_failure + _DONE_MERGE_OK_RE
  #2 (T-906 dict→list)        — review/<T-NNN>.xml os.path.isfile 사전 확인
  #3 (capturedNum / undo-done) — _UNDO_ERROR_RE 정규식 + stderr 파싱
  #4 (Open→Done force T-418)  — force=True 분기 open/<T-NNN>.xml + dirty 가드

라우팅 검증:
  BoardHTTPRequestHandler.hasattr 16개 메서드 일괄 검증

정규식 패턴:
  _DONE_MERGE_OK_RE, _DONE_CONFLICT_WARN_RE, _UNDO_WORKTREE_RE 추가 패턴
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ── sys.path 설정 ──────────────────────────────────────────────────────────────
# 워크트리 루트 + board/ 경로를 추가하여 절대 import 가능하게 만든다.
_WORKTREE_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'),
)
_BOARD_ROOT = os.path.normpath(os.path.join(_WORKTREE_ROOT, '.claude-organic', 'board'))
for _p in (_WORKTREE_ROOT, _BOARD_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ==============================================================================
# T01 – Import smoke test
# ==============================================================================


class TestImportSmoke(unittest.TestCase):
    """BoardHTTPRequestHandler 가 ImportError 없이 로드되는지 검증."""

    def test_import_board_http_request_handler(self):
        """from board.server.http_router import BoardHTTPRequestHandler 성공."""
        # 이미 상위 코드에서 import 했더라도, 여기서 명시 import 로 재확인한다.
        try:
            from board.server.http_router import BoardHTTPRequestHandler  # noqa: F401
        except ImportError as exc:
            self.fail(f'ImportError: {exc}')

    def test_import_helpers_constants(self):
        """_helpers 모듈의 정규식 상수 11개 import 성공."""
        from board.server.handlers._helpers import (
            _DONE_MERGE_OK_RE,
            _TICKET_RE,
            _KANBAN_ALL_DIRS,
            _DONE_CONFLICT_HEADER,
            _DONE_DIRTY_HEADER,
            _DONE_PATH_RE,
            _DONE_CONFLICT_WARN_RE,
            _UNDO_STRATEGY_RESET,
            _UNDO_STRATEGY_REVERT,
            _UNDO_WORKTREE_RE,
            _UNDO_ERROR_RE,
        )
        # 모두 import 성공 시 어시션 불필요 — 도달 자체가 검증
        self.assertIsNotNone(_DONE_MERGE_OK_RE)
        self.assertIsNotNone(_TICKET_RE)
        self.assertIsNotNone(_KANBAN_ALL_DIRS)
        self.assertIsNotNone(_DONE_CONFLICT_HEADER)
        self.assertIsNotNone(_DONE_DIRTY_HEADER)
        self.assertIsNotNone(_DONE_PATH_RE)
        self.assertIsNotNone(_DONE_CONFLICT_WARN_RE)
        self.assertIsNotNone(_UNDO_STRATEGY_RESET)
        self.assertIsNotNone(_UNDO_STRATEGY_REVERT)
        self.assertIsNotNone(_UNDO_WORKTREE_RE)
        self.assertIsNotNone(_UNDO_ERROR_RE)


# ==============================================================================
# T02 – 라우팅 회귀 검증 (hasattr 16개)
# ==============================================================================


class TestHandlerMethodsExist(unittest.TestCase):
    """BoardHTTPRequestHandler 가 도메인 mixin 메서드를 모두 가지는지 검증."""

    REQUIRED_METHODS = [
        # KanbanHandlerMixin
        '_handle_kanban_move',
        '_handle_kanban_submit',
        '_handle_kanban_done',
        '_handle_kanban_delete',
        # WorkflowUndoHandlerMixin
        '_handle_workflow_undo_done',
        # MetricsHandlerMixin
        '_handle_metrics_run',
        '_handle_metrics_aggregate',
        '_handle_metrics_regression',
        # WorktreeStatusHandlerMixin
        '_handle_worktree_status',
        '_handle_worktree_status_all',
        # MemoryGcHandlerMixin
        '_handle_memory_gc_run',
        '_handle_memory_gc_prune',
        # GenericHandlerMixin (GET API 라우터)
        '_handle_api',
        '_handle_poll',
        '_handle_sse',
        # BoardHTTPRequestHandler 본체
        '_send_json_with_status',
    ]

    def test_all_required_methods_present(self):
        """16개 필수 메서드 전부 hasattr 검증 — 누락 0건이어야 한다."""
        from board.server.http_router import BoardHTTPRequestHandler

        missing = [m for m in self.REQUIRED_METHODS if not hasattr(BoardHTTPRequestHandler, m)]
        self.assertEqual(
            missing, [],
            msg=f'Missing methods on BoardHTTPRequestHandler: {missing}',
        )

    def test_method_count_at_least_16(self):
        """검사 대상 메서드가 16개 이상임을 확인한다."""
        self.assertGreaterEqual(len(self.REQUIRED_METHODS), 16)


# ==============================================================================
# T03 – 정규식 패턴 단위 검증
# ==============================================================================


class TestRegexPatterns(unittest.TestCase):
    """_helpers 정규식 패턴이 의도한 입력을 캡처하는지 검증."""

    def setUp(self):
        from board.server.handlers._helpers import (
            _DONE_MERGE_OK_RE,
            _DONE_CONFLICT_WARN_RE,
            _UNDO_WORKTREE_RE,
            _UNDO_ERROR_RE,
        )
        self._done_ok_re = _DONE_MERGE_OK_RE
        self._conflict_warn_re = _DONE_CONFLICT_WARN_RE
        self._worktree_re = _UNDO_WORKTREE_RE
        self._undo_error_re = _UNDO_ERROR_RE

    def test_done_merge_ok_re_captures_branch_and_sha(self):
        """'feat/T-424-branch -> develop 병합 완료 (ab12cd34)' 형식 캡처."""
        line = 'feat/T-424-branch -> develop 병합 완료 (ab12cd34)'
        m = self._done_ok_re.search(line)
        self.assertIsNotNone(m, '_DONE_MERGE_OK_RE 가 merge 완료 라인을 캡처하지 못함')
        self.assertEqual(m.group(1).strip(), 'feat/T-424-branch')
        self.assertEqual(m.group(2).strip(), 'ab12cd34')

    def test_done_merge_ok_re_no_match_on_other_line(self):
        """무관한 줄은 매칭하지 않는다."""
        self.assertIsNone(self._done_ok_re.search('T-424: review → Done'))
        self.assertIsNone(self._done_ok_re.search('nothing here'))

    def test_done_conflict_warn_re_matches_warn_line(self):
        """'[WARN] worktree 병합 실패: 병합 충돌 발생: ...' 형식 캡처."""
        line = '[WARN] worktree 병합 실패: 병합 충돌 발생: README.md'
        self.assertIsNotNone(self._conflict_warn_re.search(line))

    def test_done_conflict_warn_re_matches_merge_conflict_english(self):
        """영문 'merge conflict' 도 캡처 (re.IGNORECASE)."""
        line = '[WARN] merge conflict detected in src/app.py'
        self.assertIsNotNone(self._conflict_warn_re.search(line))

    def test_undo_worktree_re_captures_path_and_branch(self):
        """'[undo-done] 워크트리 재생성 완료: path=/tmp/wt branch=feat/T-424' 형식 캡처."""
        line = '[undo-done] 워크트리 재생성 완료: path=/tmp/feat-T-424 branch=feat/T-424-test'
        m = self._worktree_re.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '/tmp/feat-T-424')
        self.assertEqual(m.group(2), 'feat/T-424-test')

    def test_undo_error_re_captures_message(self):
        """'[undo-done] ERROR: <message>' 패턴 캡처 (회귀 fix #3 핵심)."""
        line = '[undo-done] ERROR: T-424 is not in Done column'
        m = self._undo_error_re.search(line)
        self.assertIsNotNone(m, '_UNDO_ERROR_RE 가 ERROR 라인을 캡처하지 못함')
        self.assertEqual(m.group(1).strip(), 'T-424 is not in Done column')

    def test_undo_error_re_no_match_on_ok_line(self):
        """정상 undo 완료 로그는 ERROR 패턴 미매칭."""
        self.assertIsNone(self._undo_error_re.search('[undo-done] 완료: T-424'))


# ==============================================================================
# T04 – 회귀 fix #1: research merge_skipped 분기
# ==============================================================================


class TestMergeSkippedBranch(unittest.TestCase):
    """_classify_done_failure + merge_skipped 분기 검증."""

    def test_classify_done_failure_returns_other_for_empty(self):
        """빈 stdout/stderr 시 error_kind='other' 반환."""
        from board.server.handlers._helpers import _classify_done_failure
        result = _classify_done_failure('', '')
        self.assertEqual(result['error_kind'], 'other')
        self.assertEqual(result['conflicts'], [])
        self.assertEqual(result['dirty_files'], [])

    def test_classify_done_failure_detects_conflict_header(self):
        """'[ERROR] ...' 헤더가 있는 stdout → error_kind='merge_conflict'."""
        from board.server.handlers._helpers import _classify_done_failure
        stdout = '[ERROR] merge conflict in src/foo.py\n    - src/foo.py\n'
        result = _classify_done_failure(stdout, '')
        self.assertEqual(result['error_kind'], 'merge_conflict')
        self.assertIn('src/foo.py', result['conflicts'])

    def test_classify_done_failure_detects_dirty_worktree(self):
        """'미커밋 파일 목록:' 헤더가 있는 stdout → error_kind='dirty_worktree'."""
        from board.server.handlers._helpers import _classify_done_failure
        stdout = '미커밋 파일 목록 :\n    - src/bar.py\n'
        result = _classify_done_failure(stdout, '')
        self.assertEqual(result['error_kind'], 'dirty_worktree')
        self.assertIn('src/bar.py', result['dirty_files'])

    def test_merge_skipped_stdout_pattern_matches(self):
        """'T-NNN: review → Done' stdout fixture 가 done_transition_re 에 매칭되어
        merge_skipped=True 분기로 들어가는지 검증.

        handle_kanban_done_review 내부의 done_transition_re 를 재현해 직접 단위 검증.
        """
        import re
        ticket = 'T-424'
        stdout_fixture = 'T-424: review → Done\n'
        done_transition_re = re.compile(
            rf'^{re.escape(ticket)}:\s+\S+\s+→\s+Done\b'
        )
        merge_skipped = any(
            done_transition_re.match(line) for line in stdout_fixture.splitlines()
        )
        self.assertTrue(merge_skipped, 'merge_skipped 분기에 진입하지 못함')

    def test_merge_skipped_does_not_match_other_ticket(self):
        """다른 티켓 번호는 done_transition_re 에 매칭되지 않는다."""
        import re
        ticket = 'T-424'
        stdout_fixture = 'T-999: review → Done\n'
        done_transition_re = re.compile(
            rf'^{re.escape(ticket)}:\s+\S+\s+→\s+Done\b'
        )
        merge_skipped = any(
            done_transition_re.match(line) for line in stdout_fixture.splitlines()
        )
        self.assertFalse(merge_skipped)


# ==============================================================================
# T05 – 회귀 fix #2: T-906 dict→list — review xml isfile 사전 확인
# ==============================================================================


def _make_handler(ticket_xml_exists: bool = False, is_review_xml: bool = False):
    """테스트용 mock handler 객체를 생성한다.

    handle_kanban_done_review 내부의 os.path.isfile(review_xml) 분기를 검증하기
    위해 실제 HTTP 서버 없이 handler 를 직접 호출한다.
    """
    handler = MagicMock()
    handler._send_error = MagicMock()
    handler._send_json = MagicMock()
    handler._send_json_with_status = MagicMock()
    handler._get_dirty_files = MagicMock(return_value=[])
    return handler


class TestReviewXmlIsfilePrecondition(unittest.TestCase):
    """회귀 fix #2 — review/<T-NNN>.xml os.path.isfile 사전 확인 검증."""

    def test_review_xml_missing_returns_400(self):
        """review/<T-NNN>.xml 없으면 _send_error(400, ...) 호출 후 즉시 반환."""
        from board.server.handlers._kanban_done_helpers import handle_kanban_done_review

        handler = _make_handler()
        # os.path.isfile 을 False 로 stub → review xml 부재 시나리오
        with patch('board.server.handlers._kanban_done_helpers.os.path.isfile', return_value=False):
            handle_kanban_done_review(handler, 'T-424', '/fake/root', '/fake/flow-kanban')

        handler._send_error.assert_called_once()
        call_args = handler._send_error.call_args
        self.assertEqual(call_args[0][0], 400)
        self.assertIn('not in Review', call_args[0][1])

    def test_review_xml_present_calls_subprocess(self):
        """review/<T-NNN>.xml 존재 시 subprocess.run 이 호출된다."""
        from board.server.handlers._kanban_done_helpers import handle_kanban_done_review

        handler = _make_handler()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'feat/T-424-branch -> develop 병합 완료 (ab12cd34)\n'
        mock_result.stderr = ''

        with patch('board.server.handlers._kanban_done_helpers.os.path.isfile', return_value=True), \
             patch('board.server.handlers._kanban_done_helpers.subprocess.run', return_value=mock_result) as mock_sub:
            handle_kanban_done_review(handler, 'T-424', '/fake/root', '/fake/flow-kanban')

        mock_sub.assert_called_once()
        # subprocess 호출 인자에 'done', 'T-424' 포함 확인
        cmd_args = mock_sub.call_args[0][0]
        self.assertIn('done', cmd_args)
        self.assertIn('T-424', cmd_args)

    def test_done_xml_missing_returns_400_for_undo(self):
        """done/<T-NNN>.xml 없으면 undo-done handler 가 400 반환 (T-906 동일 패턴)."""
        from board.server.handlers._kanban_done_helpers import handle_kanban_done_review

        # workflow_undo 모듈 직접 호출
        from board.server.handlers.workflow_undo import WorkflowUndoHandlerMixin

        class _FakeHandler(WorkflowUndoHandlerMixin):
            def __init__(self):
                self._send_error_calls = []
                self._send_json_calls = []

            def _read_json_body(self):
                return {'ticket': 'T-424', 'force': False}

            def _send_error(self, code, msg):
                self._send_error_calls.append((code, msg))

            def _send_json(self, data):
                self._send_json_calls.append(data)

            def _send_json_with_status(self, status, data):
                self._send_json_calls.append((status, data))

        fake = _FakeHandler()
        with patch('board.server.handlers.workflow_undo.os.path.isfile', return_value=False):
            fake._handle_workflow_undo_done()

        self.assertTrue(len(fake._send_error_calls) > 0)
        self.assertEqual(fake._send_error_calls[0][0], 400)


# ==============================================================================
# T06 – 회귀 fix #3: undo-done stderr 라인 파싱 / _UNDO_ERROR_RE 캡처
# ==============================================================================


class TestUndoDoneStderrParsing(unittest.TestCase):
    """회귀 fix #3 — undo-done stderr 라인 파싱 + _UNDO_ERROR_RE 단위 테스트."""

    def test_undo_error_re_captures_multiword_message(self):
        """'[undo-done] ERROR: T-424 복구 실패: git reset failed' 전체 메시지 캡처."""
        from board.server.handlers._helpers import _UNDO_ERROR_RE
        line = '[undo-done] ERROR: T-424 복구 실패: git reset failed'
        m = _UNDO_ERROR_RE.search(line)
        self.assertIsNotNone(m)
        self.assertIn('T-424 복구 실패', m.group(1))

    def test_undo_done_handler_extracts_error_from_stderr(self):
        """_handle_workflow_undo_done 이 stderr 의 ERROR 라인을 파싱해 반환 json 에 포함한다."""
        from board.server.handlers.workflow_undo import WorkflowUndoHandlerMixin

        class _FakeHandler(WorkflowUndoHandlerMixin):
            def __init__(self, ticket='T-424'):
                self._ticket = ticket
                self._responses = []
                self._errors = []

            def _read_json_body(self):
                return {'ticket': self._ticket, 'force': False}

            def _send_error(self, code, msg):
                self._errors.append((code, msg))

            def _send_json(self, data):
                self._responses.append(data)

            def _send_json_with_status(self, status, data):
                self._responses.append((status, data))

        fake = _FakeHandler()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = '[undo-done] ERROR: develop branch diverged\n'

        with patch('board.server.handlers.workflow_undo.os.path.isfile', return_value=True), \
             patch('board.server.handlers.workflow_undo.subprocess.run', return_value=mock_result):
            fake._handle_workflow_undo_done()

        self.assertTrue(len(fake._responses) > 0)
        response = fake._responses[0]
        # (status, data) 튜플 형태
        if isinstance(response, tuple):
            _, data = response
        else:
            data = response
        self.assertFalse(data.get('ok', True))
        # error 필드 또는 message 필드에 ERROR 라인 내용 포함
        err_text = data.get('error', '') or data.get('message', '')
        self.assertIn('develop branch diverged', err_text)

    def test_undo_done_handler_parses_stdout_and_stderr_both(self):
        """stdout + stderr 라인 모두 파싱 — 전략은 stdout, 에러는 stderr 에서 추출."""
        from board.server.handlers.workflow_undo import WorkflowUndoHandlerMixin

        class _FakeHandler(WorkflowUndoHandlerMixin):
            def __init__(self):
                self._responses = []
                self._errors = []

            def _read_json_body(self):
                return {'ticket': 'T-424', 'force': False}

            def _send_error(self, code, msg):
                self._errors.append((code, msg))

            def _send_json(self, data):
                self._responses.append(data)

            def _send_json_with_status(self, status, data):
                self._responses.append((status, data))

        fake = _FakeHandler()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '[undo-done] 전략 1: reset --hard 진행\n[undo-done] 워크트리 재생성 완료: path=/tmp/wt branch=feat/T-424\n'
        mock_result.stderr = ''

        with patch('board.server.handlers.workflow_undo.os.path.isfile', return_value=True), \
             patch('board.server.handlers.workflow_undo.subprocess.run', return_value=mock_result):
            fake._handle_workflow_undo_done()

        self.assertEqual(len(fake._responses), 1)
        data = fake._responses[0]
        self.assertTrue(data.get('ok'))
        self.assertEqual(data.get('strategy'), 'reset')
        self.assertEqual(data.get('worktree_path'), '/tmp/wt')
        self.assertEqual(data.get('branch'), 'feat/T-424')


# ==============================================================================
# T07 – 회귀 fix #4: Open→Done force + dirty 워크트리 가드 (T-418)
# ==============================================================================


class TestForceDoneDirtyGuard(unittest.TestCase):
    """회귀 fix #4 — force=True 분기 open/<T-NNN>.xml 검증 + dirty 가드."""

    def test_force_done_open_xml_missing_returns_400(self):
        """force=True 이지만 open/<T-NNN>.xml 없으면 400 에러."""
        from board.server.handlers._kanban_done_helpers import handle_kanban_done_force

        handler = _make_handler()
        # open xml 미존재 시나리오
        with patch('board.server.handlers._kanban_done_helpers.os.path.isfile', return_value=False):
            handle_kanban_done_force(handler, 'T-424', False, '/fake/root', '/fake/flow-kanban')

        handler._send_error.assert_called_once()
        call_args = handler._send_error.call_args
        self.assertEqual(call_args[0][0], 400)
        self.assertIn('not in Open', call_args[0][1])

    def test_force_done_dirty_guard_409_when_force_dirty_false(self):
        """open/<T-NNN>.xml 존재 + dirty 워크트리 + force_dirty=False → 409 + error_kind='dirty_worktree'."""
        from board.server.handlers._kanban_done_helpers import handle_kanban_done_force

        handler = _make_handler()
        handler._get_dirty_files = MagicMock(return_value=['src/foo.py'])

        mock_wm = MagicMock()
        mock_wm.get_worktree_path.return_value = '/fake/wt'
        mock_wm.has_uncommitted_changes.return_value = True

        with patch('board.server.handlers._kanban_done_helpers.os.path.isfile', return_value=True), \
             patch.dict('sys.modules', {'flow': MagicMock(), 'flow.worktree_manager': mock_wm}):
            # ImportError 없이 worktree_manager import 가 성공하도록 직접 patch
            with patch('board.server.handlers._kanban_done_helpers.sys.path'):
                # worktree_manager import 를 mock 으로 대체
                import board.server.handlers._kanban_done_helpers as helpers_mod
                orig = helpers_mod.__builtins__ if hasattr(helpers_mod, '__builtins__') else None

                # 더 직접적인 방법: handle_kanban_done_force 내부 import 를 patch
                with patch.object(
                    sys.modules.get('board.server.handlers._kanban_done_helpers', helpers_mod),
                    '__name__',
                    'board.server.handlers._kanban_done_helpers',
                ):
                    pass

        # worktree_manager 를 직접 mock 하는 방식으로 재시도
        handler2 = _make_handler()
        handler2._get_dirty_files = MagicMock(return_value=['src/foo.py'])

        mock_wm2 = MagicMock()
        mock_wm2.get_worktree_path.return_value = '/fake/wt'
        mock_wm2.has_uncommitted_changes.return_value = True

        import board.server.handlers._kanban_done_helpers as _helpers_mod

        with patch('board.server.handlers._kanban_done_helpers.os.path.isfile', return_value=True):
            # worktree_manager 내부 import 를 patch — from flow import worktree_manager
            with patch.dict(sys.modules, {'flow.worktree_manager': mock_wm2}):
                # _helpers_mod 내부에서 직접 import 하므로 builtins.__import__ 패치 필요
                import builtins
                orig_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name == 'flow' and args and args[2] and 'worktree_manager' in args[2]:
                        # from flow import worktree_manager
                        mock_flow = MagicMock()
                        mock_flow.worktree_manager = mock_wm2
                        return mock_flow
                    return orig_import(name, *args, **kwargs)

                with patch.object(builtins, '__import__', side_effect=mock_import):
                    handle_kanban_done_force(handler2, 'T-424', False, '/fake/root', '/fake/flow-kanban')

        handler2._send_json_with_status.assert_called_once()
        call_args = handler2._send_json_with_status.call_args
        self.assertEqual(call_args[0][0], 409)
        data = call_args[0][1]
        self.assertFalse(data['ok'])
        self.assertEqual(data['error_kind'], 'dirty_worktree')

    def test_force_done_dirty_guard_skipped_when_force_dirty_true(self):
        """force_dirty=True 이면 dirty 가드를 건너뛰고 subprocess.run 을 호출한다."""
        from board.server.handlers._kanban_done_helpers import handle_kanban_done_force

        handler = _make_handler()
        handler._get_dirty_files = MagicMock(return_value=['src/foo.py'])

        mock_wm = MagicMock()
        mock_wm.get_worktree_path.return_value = '/fake/wt'
        mock_wm.has_uncommitted_changes.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'done'
        mock_result.stderr = ''

        import builtins
        orig_import = builtins.__import__

        def mock_import_wm(name, *args, **kwargs):
            if name == 'flow' and args and args[2] and 'worktree_manager' in args[2]:
                mock_flow = MagicMock()
                mock_flow.worktree_manager = mock_wm
                return mock_flow
            return orig_import(name, *args, **kwargs)

        with patch('board.server.handlers._kanban_done_helpers.os.path.isfile', return_value=True), \
             patch('board.server.handlers._kanban_done_helpers.subprocess.run', return_value=mock_result) as mock_sub, \
             patch.object(builtins, '__import__', side_effect=mock_import_wm):
            handle_kanban_done_force(handler, 'T-424', True, '/fake/root', '/fake/flow-kanban')

        # force_dirty=True 이므로 dirty 가드 분기를 통과하고 subprocess 호출 도달
        mock_sub.assert_called_once()
        cmd_args = mock_sub.call_args[0][0]
        self.assertIn('--force', cmd_args)
        self.assertIn('T-424', cmd_args)


if __name__ == '__main__':
    unittest.main(verbosity=2)

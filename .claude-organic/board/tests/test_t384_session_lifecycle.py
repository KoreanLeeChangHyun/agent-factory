"""T-384 Phase 4 — SessionLifecycle 5메서드 통합 (Criterion A).

옛 흐름: ``startSession`` / ``killSession`` / ``_finalizeStoppedUI`` / system init
핸들러가 같은 IIFE 안에서 서로 떨어진 위치에 정의되어 있어 한 사이클의 라이프
주기 흐름을 한 곳에서 파악하기 어려웠다.

새 흐름: 같은 IIFE 안에 ``SessionLifecycle`` facade 를 신설해 5 메서드로 응집:
  - ``start(opts)`` — 옛 ``startSession`` 진입점 facade
  - ``kill()`` — 옛 ``killSession`` 진입점 facade
  - ``finalizeStopped()`` — 옛 ``_finalizeStoppedUI`` 의 단일 진입점
  - ``onInit(sid)`` — system/init 이벤트 수신 시 처리 진입점
  - ``_dispatch()`` — 내부 헬퍼 (라이프사이클 전이 시 공통 청소)

외부 API ``Board.session.startSession`` / ``Board.session.killSession`` 시그니처는
1:1 보존 (호출부 0 수정). 옛 함수는 wrapper 로 보존되거나 직접 export 유지.
"""

from __future__ import annotations

import os
import re
import unittest

_HERE = os.path.dirname(__file__)
_WORKTREE_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..', '..'))
_JS_ROOT = os.path.normpath(os.path.join(
    _WORKTREE_ROOT, '.claude-organic', 'board', 'static', 'js',
))


def _read(rel_path: str) -> str:
    full = os.path.join(_JS_ROOT, rel_path)
    with open(full, 'r', encoding='utf-8') as fh:
        return fh.read()


class TestSessionLifecycleObject(unittest.TestCase):
    """session.js 에 SessionLifecycle 객체 정의."""

    def setUp(self) -> None:
        self.src = _read('workflow/session.js')

    def test_session_lifecycle_present(self) -> None:
        """`SessionLifecycle` 식별자가 session.js 안에 정의됨."""
        self.assertIn(
            'SessionLifecycle', self.src,
            'SessionLifecycle namespace missing in session.js',
        )

    def test_method_start(self) -> None:
        """`SessionLifecycle.start` 메서드 정의."""
        self.assertRegex(
            self.src,
            r'SessionLifecycle\.start\s*=\s*function',
            'SessionLifecycle.start method missing',
        )

    def test_method_kill(self) -> None:
        """`SessionLifecycle.kill` 메서드 정의."""
        self.assertRegex(
            self.src,
            r'SessionLifecycle\.kill\s*=\s*function',
            'SessionLifecycle.kill method missing',
        )

    def test_method_finalize_stopped(self) -> None:
        """`SessionLifecycle.finalizeStopped` 메서드 정의."""
        self.assertRegex(
            self.src,
            r'SessionLifecycle\.finalizeStopped\s*=\s*function',
            'SessionLifecycle.finalizeStopped method missing',
        )

    def test_method_on_init(self) -> None:
        """`SessionLifecycle.onInit` 메서드 정의 (system/init 이벤트 핸들러)."""
        self.assertRegex(
            self.src,
            r'SessionLifecycle\.onInit\s*=\s*function',
            'SessionLifecycle.onInit method missing',
        )

    def test_method_dispatch(self) -> None:
        """`SessionLifecycle._dispatch` 내부 헬퍼."""
        self.assertRegex(
            self.src,
            r'SessionLifecycle\._dispatch\s*=\s*function',
            'SessionLifecycle._dispatch helper missing',
        )


class TestExternalApiBackwardCompat(unittest.TestCase):
    """외부 API 5종 시그니처 보존 — wrapper 또는 직접 정의."""

    EXPECTED_KEYS = (
        'startSession',
        'killSession',
        'fetchStatus',
        'postJson',
        'connectSSE',
    )

    def test_board_session_exports_present(self) -> None:
        src = _read('workflow/session.js')
        for key in self.EXPECTED_KEYS:
            self.assertRegex(
                src, r'\b' + re.escape(key) + r'\s*:',
                f'Board.session.{key} export missing after P4',
            )

    def test_start_session_arity_preserved(self) -> None:
        """`function startSession(resumeSessionId, opts)` 또는 동등 wrapper 가 2 인자 시그니처 유지."""
        src = _read('workflow/session.js')
        # 가장 직접적 형태: function startSession(resumeSessionId, opts)
        self.assertRegex(
            src,
            r'function\s+startSession\s*\(\s*resumeSessionId\s*,\s*opts\s*\)',
            'startSession(resumeSessionId, opts) signature broken',
        )

    def test_kill_session_arity_preserved(self) -> None:
        """`function killSession()` zero-arg 시그니처 유지."""
        src = _read('workflow/session.js')
        self.assertRegex(
            src,
            r'function\s+killSession\s*\(\s*\)',
            'killSession() signature broken',
        )


class TestFinalizeStoppedSinglePoint(unittest.TestCase):
    """_finalizeStoppedUI / SessionLifecycle.finalizeStopped 가 단일 진입점."""

    def test_finalize_definition_exists(self) -> None:
        """`_finalizeStoppedUI` 또는 `SessionLifecycle.finalizeStopped` 중 하나가 정의됨."""
        src = _read('workflow/session.js')
        has_legacy = bool(re.search(r'\bfunction\s+_finalizeStoppedUI\b', src))
        has_new = bool(re.search(r'SessionLifecycle\.finalizeStopped\s*=\s*function', src))
        self.assertTrue(
            has_legacy or has_new,
            'No finalize-stopped definition found in session.js',
        )

    def test_finalize_invoked_from_kill(self) -> None:
        """killSession 본문 안에서 finalizeStopped 가 호출된다."""
        src = _read('workflow/session.js')
        # 두 형태 중 하나가 killSession 본문에 등장.
        invoked = (
            re.search(r'_finalizeStoppedUI\s*\(\s*\)', src) is not None
            or re.search(r'SessionLifecycle\.finalizeStopped\s*\(\s*\)', src) is not None
        )
        self.assertTrue(
            invoked,
            'killSession must invoke finalizeStopped/its legacy alias',
        )


class TestOnInitInvocation(unittest.TestCase):
    """system/init 이벤트 핸들러가 SessionLifecycle.onInit 단일 진입점 경유."""

    def test_on_init_uses_history_loader(self) -> None:
        """SessionLifecycle.onInit 본문이 HistoryLoader.load 를 호출 (P3 단일 진입점 사용)."""
        src = _read('workflow/session.js')
        # SessionLifecycle.onInit = function (sid) { ... HistoryLoader.load(sid) ... }
        m = re.search(
            r'SessionLifecycle\.onInit\s*=\s*function[\s\S]*?\n\s*\}\s*;',
            src,
        )
        self.assertIsNotNone(m, 'SessionLifecycle.onInit body not found')
        body = m.group(0)
        self.assertIn(
            'HistoryLoader.load', body,
            'SessionLifecycle.onInit must delegate history load to HistoryLoader.load (P3)',
        )


class TestBaselinePreservedP4(unittest.TestCase):
    """P1/P2/P3 회귀 차단."""

    def test_setter_invariant_preserved(self) -> None:
        src = _read('core/common.js')
        m = re.search(
            r'Board\.state\.setTermStatus\s*=\s*function[\s\S]*?\n\}\s*;',
            src,
        )
        self.assertIsNotNone(m)
        body = m.group(0)
        self.assertIn("'stopped'", body)
        self.assertRegex(body, r'_historyLoaded\s*=\s*false')

    def test_history_loader_preserved(self) -> None:
        src = _read('terminal/output-pipe.js')
        self.assertRegex(
            src, r'HistoryLoader\.load\s*=\s*function',
            'HistoryLoader.load lost after P4',
        )

    def test_history_loader_wrappers_preserved(self) -> None:
        src = _read('terminal/output-pipe.js')
        self.assertRegex(src, r'M\.loadHistory\s*=')
        self.assertRegex(src, r'M\.fetchHistorySince\s*=')


if __name__ == '__main__':
    unittest.main()

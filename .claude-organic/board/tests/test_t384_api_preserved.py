"""T-384 Phase 5 — 외부 API 시그니처 보존 + 응집 회귀 차단.

P1~P4 의 모든 회귀 안전망을 한 곳에서 재실행하는 메타 단계. 본 파일의 테스트는
구조적 검증만 수행하며, 동작 검증 (5 시나리오) 은 ``work/P5/W1.md`` 의 수동
체크리스트가 담당 (사용자가 board 9927 에서 직접 재현).

검증 영역:
  1. ``Board.session.*`` 5종 API 시그니처 + arity 1:1 보존
  2. ``_finalizeStoppedUI`` 응집 — closure 외부에서도 접근 가능
  3. P1~P4 회귀 0 (인덱스성 재실행)
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


class TestExternalApiSignatures(unittest.TestCase):
    """Board.session 5종 API 시그니처 1:1 보존."""

    def setUp(self) -> None:
        self.src = _read('workflow/session.js')

    def test_export_block_contains_five_keys(self) -> None:
        """`Board.session = { ... }` 블록 안에 5 키가 모두 존재."""
        # 첫 export block 만 추출 — 줄바꿈 허용 정규식.
        m = re.search(
            r'Board\.session\s*=\s*\{[\s\S]*?\};',
            self.src,
        )
        self.assertIsNotNone(m, 'Board.session export block not found')
        block = m.group(0)
        for key in ('startSession', 'killSession', 'fetchStatus', 'postJson', 'connectSSE'):
            self.assertRegex(
                block, r'\b' + re.escape(key) + r'\s*:',
                f'Board.session.{key} missing in export block',
            )

    def test_start_session_arity(self) -> None:
        """`function startSession(resumeSessionId, opts)` — 2-arg arity."""
        self.assertRegex(
            self.src,
            r'function\s+startSession\s*\(\s*resumeSessionId\s*,\s*opts\s*\)',
        )

    def test_kill_session_arity(self) -> None:
        """`function killSession()` — 0-arg arity."""
        self.assertRegex(
            self.src,
            r'function\s+killSession\s*\(\s*\)',
        )

    def test_fetch_status_arity(self) -> None:
        """`function fetchStatus()` 또는 `fetchStatus = function ()` — 0-arg arity."""
        self.assertTrue(
            re.search(r'function\s+fetchStatus\s*\(\s*\)', self.src) is not None
            or re.search(r'fetchStatus\s*=\s*function\s*\(\s*\)', self.src) is not None,
            'fetchStatus() signature broken',
        )

    def test_post_json_arity(self) -> None:
        """`function postJson(path, body)` — 2-arg arity."""
        self.assertRegex(
            self.src,
            r'function\s+postJson\s*\(\s*[A-Za-z_][\w]*\s*,\s*[A-Za-z_][\w]*\s*\)',
            'postJson(path, body) signature broken',
        )

    def test_connect_sse_arity(self) -> None:
        """`function connectSSE()` — 0-arg arity."""
        self.assertRegex(
            self.src,
            r'function\s+connectSSE\s*\(\s*\)',
        )


class TestFinalizeStoppedCohesion(unittest.TestCase):
    """`_finalizeStoppedUI` 가 모듈 스코프로 응집되어 SessionLifecycle 에서도 호출 가능."""

    def setUp(self) -> None:
        self.src = _read('workflow/session.js')

    def test_finalize_module_scope(self) -> None:
        """`_finalizeStoppedUI` 정의가 nested closure 가 아닌 모듈 스코프에 위치.

        검출 방식: `function _finalizeStoppedUI` 정의 줄의 들여쓰기가
        IIFE 안 모듈 스코프 (2 space) 수준이어야 한다. 옛 nested 정의는
        killSession 안에 있어 4+ space 들여쓰기 였음.
        """
        m = re.search(
            r'^(\s*)function\s+_finalizeStoppedUI\s*\(',
            self.src,
            re.MULTILINE,
        )
        self.assertIsNotNone(m, '_finalizeStoppedUI definition not found')
        indent = m.group(1)
        # IIFE 안 (`(function () { ... })();`) 모듈 스코프는 2-space.
        self.assertEqual(
            len(indent), 2,
            f'_finalizeStoppedUI must be at module scope (2-space indent); got {len(indent)} spaces',
        )

    def test_finalize_invoked_via_facade(self) -> None:
        """`SessionLifecycle.finalizeStopped` 본문이 `_finalizeStoppedUI()` 호출."""
        m = re.search(
            r'SessionLifecycle\.finalizeStopped\s*=\s*function[\s\S]*?\}\s*;',
            self.src,
        )
        self.assertIsNotNone(m)
        body = m.group(0)
        self.assertIn(
            '_finalizeStoppedUI()', body,
            'SessionLifecycle.finalizeStopped must delegate to _finalizeStoppedUI',
        )

    def test_finalize_invoked_from_kill(self) -> None:
        """killSession 본문 안에서도 _finalizeStoppedUI 가 호출됨 (옛 경로 보존)."""
        # killSession 블록 추출.
        m = re.search(
            r'function\s+killSession\s*\(\s*\)\s*\{[\s\S]*?\n\s{0,2}\}\s*\n',
            self.src,
        )
        self.assertIsNotNone(m, 'killSession body not found')
        body = m.group(0)
        self.assertGreaterEqual(
            body.count('_finalizeStoppedUI()'), 2,
            'killSession should invoke _finalizeStoppedUI on success + 409 catch (>=2 calls)',
        )


class TestP1Inventory(unittest.TestCase):
    """P1 베이스라인 회귀 검증."""

    def test_target_files_exist(self) -> None:
        for rel in ('workflow/session.js', 'terminal/output-pipe.js', 'terminal/terminal.js'):
            self.assertTrue(os.path.isfile(os.path.join(_JS_ROOT, rel)))


class TestP2SetterInvariant(unittest.TestCase):
    """P2 setter invariant 회귀 검증."""

    def test_setter_stopped_branch(self) -> None:
        src = _read('core/common.js')
        m = re.search(
            r'Board\.state\.setTermStatus\s*=\s*function[\s\S]*?\n\}\s*;',
            src,
        )
        self.assertIsNotNone(m)
        body = m.group(0)
        for needle in (
            r"next\s*===\s*['\"]stopped['\"]",
            r'termSessionId\s*=\s*null',
            r'_historyLoaded\s*=\s*false',
            r'_historyLastTimestamp\s*=\s*["\']',
            r'_inAutoResume\s*=\s*false',
        ):
            self.assertRegex(
                body, needle,
                f'P2 setter invariant `{needle}` regressed',
            )


class TestP3HistoryLoader(unittest.TestCase):
    """P3 HistoryLoader 단일 진입점 회귀 검증."""

    def test_loader_object_present(self) -> None:
        src = _read('terminal/output-pipe.js')
        self.assertRegex(src, r'HistoryLoader\.load\s*=\s*function')

    def test_loader_used_by_callers(self) -> None:
        session = _read('workflow/session.js')
        terminal = _read('terminal/terminal.js')
        self.assertIn('HistoryLoader.load', session)
        self.assertIn('HistoryLoader.load', terminal)


class TestP4SessionLifecycle(unittest.TestCase):
    """P4 SessionLifecycle facade 회귀 검증."""

    EXPECTED_METHODS = (
        'start',
        'kill',
        'finalizeStopped',
        'onInit',
        '_dispatch',
    )

    def test_lifecycle_5_methods(self) -> None:
        src = _read('workflow/session.js')
        for method in self.EXPECTED_METHODS:
            self.assertRegex(
                src,
                r'SessionLifecycle\.' + re.escape(method) + r'\s*=\s*function',
                f'SessionLifecycle.{method} regressed',
            )

    def test_lifecycle_exposed_on_board_session(self) -> None:
        """`Board.session.lifecycle = SessionLifecycle` 외부 export."""
        src = _read('workflow/session.js')
        m = re.search(
            r'Board\.session\s*=\s*\{[\s\S]*?\};',
            src,
        )
        self.assertIsNotNone(m)
        block = m.group(0)
        self.assertRegex(
            block,
            r'lifecycle\s*:\s*SessionLifecycle',
            'Board.session.lifecycle export missing',
        )


if __name__ == '__main__':
    unittest.main()

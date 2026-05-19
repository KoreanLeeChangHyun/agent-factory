"""T-384 Phase 3 — HistoryLoader 단일 진입점 (Criterion B).

옛 ``M.loadHistory`` (initial full load) 와 ``M.fetchHistorySince`` (gap-fill) 가
호출자 측에서 if/else 로 분기되던 책임을 ``HistoryLoader.load(sid)`` 단일
진입점으로 응집한다. 분기 결정은 LoadHistory 내부에서 ``_historyLoaded`` +
``_historyLastTimestamp`` 두 플래그로 자동 판단된다.

분기 의미:
  - ``!sid || isWorkflowMode``                → skip
  - ``!_historyLoaded``                       → initial (REST /terminal/history)
  - ``_historyLoaded && _historyLastTimestamp`` → gap-fill (since=lastTimestamp)
  - ``_historyLoaded && !_historyLastTimestamp`` → skip (멱등 안전망)

옛 함수 두 개는 wrapper 로 보존 (P5 이후 제거 가능 검토). 외부 호출자는
``HistoryLoader.load(sid)`` 만 직접 호출해야 한다.
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


class TestHistoryLoaderDefinition(unittest.TestCase):
    """output-pipe.js 에 HistoryLoader.load 단일 진입점 정의."""

    def setUp(self) -> None:
        self.src = _read('terminal/output-pipe.js')

    def test_history_loader_object_present(self) -> None:
        """`HistoryLoader` 식별자가 output-pipe.js 안에 정의됨."""
        self.assertIn(
            'HistoryLoader',
            self.src,
            'HistoryLoader namespace missing in output-pipe.js',
        )

    def test_history_loader_load_method(self) -> None:
        """`HistoryLoader.load = function(...)` 또는 등가 정의 존재."""
        self.assertRegex(
            self.src,
            r'HistoryLoader\.load\s*=\s*function',
            'HistoryLoader.load method definition missing',
        )

    def test_branch_initial_full_load(self) -> None:
        """initial full load 분기 — `_historyLoaded` 가 false 일 때 진입."""
        # HistoryLoader.load 내부에 _historyLoaded 검사가 들어 있어야 한다.
        self.assertRegex(
            self.src,
            r'HistoryLoader\.load\s*=\s*function[\s\S]*?_historyLoaded',
            'HistoryLoader.load must inspect _historyLoaded',
        )

    def test_branch_gap_fill_since(self) -> None:
        """gap-fill 분기 — `_historyLastTimestamp` 를 since 로 쓰는 분기."""
        self.assertRegex(
            self.src,
            r'HistoryLoader\.load\s*=\s*function[\s\S]*?_historyLastTimestamp',
            'HistoryLoader.load must inspect _historyLastTimestamp for gap-fill',
        )

    def test_branch_idempotent_skip(self) -> None:
        """멱등 안전망 — _historyLoaded && !_historyLastTimestamp 인 경우 skip.

        옛 fetchHistorySince 의 핵심 가드 ("since 없으면 skip — initial load 가
        담당해야 한다") 를 HistoryLoader.load 가 보존해야 한다.
        """
        # 가장 검출하기 쉬운 형태: `return Promise.resolve()` 가 load 내부에 등장.
        # (HistoryLoader.load 본문 안에 Promise.resolve() 가 ≥ 1번 등장)
        m = re.search(
            r'HistoryLoader\.load\s*=\s*function[\s\S]*?\n\s*\}\s*;',
            self.src,
        )
        self.assertIsNotNone(
            m, 'HistoryLoader.load body not found',
        )
        body = m.group(0)
        self.assertIn(
            'Promise.resolve()', body,
            'HistoryLoader.load must short-circuit skip branches with Promise.resolve()',
        )


class TestLegacyWrappersPreserved(unittest.TestCase):
    """옛 M.loadHistory / M.fetchHistorySince 는 wrapper 로 보존."""

    def setUp(self) -> None:
        self.src = _read('terminal/output-pipe.js')

    def test_load_history_wrapper_present(self) -> None:
        """`M.loadHistory` 정의는 유지된다 (wrapper 또는 alias)."""
        self.assertRegex(
            self.src, r'M\.loadHistory\s*=',
            'M.loadHistory definition removed without wrapper — back-compat broken',
        )

    def test_fetch_history_since_wrapper_present(self) -> None:
        """`M.fetchHistorySince` 정의는 유지된다."""
        self.assertRegex(
            self.src, r'M\.fetchHistorySince\s*=',
            'M.fetchHistorySince definition removed without wrapper',
        )

    def test_wrappers_delegate_to_loader(self) -> None:
        """wrapper 양쪽이 HistoryLoader.load 를 호출한다 (응집 증거)."""
        # 단순 substring 으로 검증 — wrapper 안에서 HistoryLoader.load(sid) 호출.
        # M.loadHistory = function (...) { return HistoryLoader.load(sessionId); }
        # 형태가 가장 자연스럽다.
        load_def_match = re.search(
            r'M\.loadHistory\s*=\s*function[\s\S]*?\n\s*\}\s*;',
            self.src,
        )
        since_def_match = re.search(
            r'M\.fetchHistorySince\s*=\s*function[\s\S]*?\n\s*\}\s*;',
            self.src,
        )
        self.assertIsNotNone(load_def_match)
        self.assertIsNotNone(since_def_match)
        self.assertIn(
            'HistoryLoader.load',
            load_def_match.group(0),
            'M.loadHistory wrapper must delegate to HistoryLoader.load',
        )
        self.assertIn(
            'HistoryLoader.load',
            since_def_match.group(0),
            'M.fetchHistorySince wrapper must delegate to HistoryLoader.load',
        )


class TestCallersMigrated(unittest.TestCase):
    """외부 호출자가 HistoryLoader.load 단일 진입점으로 마이그레이션."""

    def test_session_js_uses_history_loader(self) -> None:
        """session.js 가 HistoryLoader.load 를 호출한다."""
        src = _read('workflow/session.js')
        # 최소 1건 이상 — 4 콜사이트 (749, 1473, 1481, 1962) 중 일부 또는 전부.
        matches = re.findall(r'HistoryLoader\.load\s*\(', src)
        self.assertGreaterEqual(
            len(matches), 1,
            'session.js must invoke HistoryLoader.load at least once',
        )

    def test_terminal_js_uses_history_loader(self) -> None:
        """terminal.js 가 HistoryLoader.load 를 호출한다 (init 경로)."""
        src = _read('terminal/terminal.js')
        # init 경로 (line 670) 가 마이그레이션 됨.
        self.assertIn(
            'HistoryLoader.load',
            src,
            'terminal.js must invoke HistoryLoader.load on init path',
        )

    def test_legacy_direct_call_reduced_in_session(self) -> None:
        """session.js 의 ``loadHistory(`` / ``fetchHistorySince(`` 직접 호출
        총량이 감소.

        베이스라인: 4건 (749 + 1473 + 1481 + 1962). 마이그레이션 후 모두 HistoryLoader.load
        로 치환되어야 하므로 0 이 이상적. 점진 마이그레이션 안전망으로 <= 1 허용.
        """
        src = _read('workflow/session.js')
        total = len(re.findall(
            r'\.(loadHistory|fetchHistorySince)\s*\(', src,
        ))
        self.assertLessEqual(
            total, 1,
            'session.js legacy loadHistory/fetchHistorySince direct calls '
            f'should drop to <= 1; got {total}',
        )


class TestBaselinePreservedP3(unittest.TestCase):
    """P1/P2 회귀 차단."""

    EXPECTED_KEYS = (
        'startSession',
        'killSession',
        'fetchStatus',
        'postJson',
        'connectSSE',
    )

    def test_external_api_preserved(self) -> None:
        src = _read('workflow/session.js')
        for key in self.EXPECTED_KEYS:
            self.assertRegex(
                src, r'\b' + re.escape(key) + r'\s*:',
                f'Board.session.{key} regressed after P3',
            )

    def test_setter_invariant_preserved(self) -> None:
        """P2 setter 'stopped' 분기 invariant 가 P3 변경으로 깨지지 않았다."""
        src = _read('core/common.js')
        # setter 본체에 'stopped' 분기 + _historyLoaded reset 두 가지가 함께 존재.
        m = re.search(
            r'Board\.state\.setTermStatus\s*=\s*function[\s\S]*?\n\}\s*;',
            src,
        )
        self.assertIsNotNone(m, 'setter definition disappeared')
        body = m.group(0)
        self.assertIn("'stopped'", body)
        self.assertRegex(body, r'_historyLoaded\s*=\s*false')


if __name__ == '__main__':
    unittest.main()

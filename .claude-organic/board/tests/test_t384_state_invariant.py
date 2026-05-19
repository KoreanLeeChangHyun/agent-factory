"""T-384 Phase 2 — setTermStatus 'stopped' 분기 invariant setter.

Criterion C: 세션 상태 리셋의 단일 진입점을 ``Board.state.setTermStatus``
함수로 응집한다. 'stopped' 분기에서 다음 invariant 가 setter 안에서 일괄
처리되어야 한다:

- ``Board.state.termSessionId = null``
- ``Board._term._historyLoaded = false``
- ``Board._term._historyLastTimestamp = ""``
- ``Board.state._inAutoResume = false``

호출자 (session.js 등) 가 setter 호출 직후 동일 리셋을 수동 보장하던
중복 코드는 최소 1건 이상 제거되어야 한다.

DOM 청소 (clearOutput / stopSpinner / resetTokens 등) 는 setter 책임이 아니다.
P4 의 ``SessionLifecycle.finalizeStopped`` 가 단일점으로 응집한다.
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


def _setter_body(src: str) -> str:
    """`Board.state.setTermStatus = function (next) { ... }` 의 본문만 추출.

    여러 줄 매칭이 필요하므로 손수 brace 카운팅으로 잘라낸다.
    """
    start = src.find('Board.state.setTermStatus = function')
    assert start >= 0, 'setter definition not found'
    open_brace = src.find('{', start)
    assert open_brace >= 0
    depth = 1
    i = open_brace + 1
    while i < len(src) and depth > 0:
        ch = src[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        i += 1
    return src[open_brace + 1:i - 1]


class TestSetterStoppedInvariant(unittest.TestCase):
    """setter 본체 'stopped' 분기에 invariant 5종이 들어 있다."""

    def setUp(self) -> None:
        common = _read('core/common.js')
        self.body = _setter_body(common)

    def test_has_stopped_branch(self) -> None:
        """setter 본체가 next === 'stopped' 분기를 포함."""
        self.assertRegex(
            self.body,
            r"""next\s*===\s*['"]stopped['"]""",
            "setter must branch on next === 'stopped'",
        )

    def test_invariant_term_session_id_null(self) -> None:
        """stopped 분기에서 termSessionId = null 처리."""
        self.assertRegex(
            self.body,
            r'termSessionId\s*=\s*null',
            'setter stopped branch must reset termSessionId',
        )

    def test_invariant_history_loaded_reset(self) -> None:
        """stopped 분기에서 _historyLoaded = false 처리."""
        self.assertRegex(
            self.body,
            r'_historyLoaded\s*=\s*false',
            'setter stopped branch must reset _historyLoaded',
        )

    def test_invariant_history_timestamp_reset(self) -> None:
        """stopped 분기에서 _historyLastTimestamp 리셋."""
        self.assertRegex(
            self.body,
            r'_historyLastTimestamp\s*=\s*["\']',
            'setter stopped branch must reset _historyLastTimestamp',
        )

    def test_invariant_auto_resume_reset(self) -> None:
        """stopped 분기에서 _inAutoResume = false 처리."""
        self.assertRegex(
            self.body,
            r'_inAutoResume\s*=\s*false',
            'setter stopped branch must reset _inAutoResume',
        )

    def test_no_dom_calls_in_setter(self) -> None:
        """setter 본체는 DOM 청소 (clearOutput / stopSpinner / resetTokens) 호출 금지.

        DOM 작업은 P4 SessionLifecycle.finalizeStopped 단일점에 응집한다.
        setter 가 DOM 을 만지면 호출자가 부수효과를 예측하지 못해 회귀.
        """
        for forbidden in (
            'clearOutput',
            'stopSpinner',
            'resetTokens',
            'setSessionCost',
            'setSessionModel',
        ):
            self.assertNotIn(
                forbidden, self.body,
                f"setter body must not invoke DOM helper '{forbidden}'",
            )


class TestCallerDuplicationRemoved(unittest.TestCase):
    """session.js 호출자에서 setter 직후 수동 리셋 중복 제거."""

    def setUp(self) -> None:
        self.src = _read('workflow/session.js')

    def test_caller_redundancy_reduced(self) -> None:
        """`setTermStatus("stopped")` 호출 직후 다음 줄에 `termSessionId = null` 이
        붙어있는 횟수가 P1 베이스라인 (>=1) 보다 줄어들었다.

        구체적으로: setter 호출 다음 1~3줄 안에 ``Board.state.termSessionId = null``
        이 나오는 회귀 패턴이 0건이어야 한다 (setter 가 이미 처리하므로 중복).
        """
        pat = re.compile(
            r"""setTermStatus\s*\(\s*['"]stopped['"]\s*\)\s*;\s*\n"""
            r"""(?:[^\n]*\n){0,3}?"""
            r"""\s*Board\.state\.termSessionId\s*=\s*null""",
            re.MULTILINE,
        )
        matches = pat.findall(self.src)
        self.assertEqual(
            len(matches), 0,
            'redundant termSessionId=null after setTermStatus("stopped") '
            f'should be 0 after P2, got {len(matches)}',
        )

    def test_term_session_id_null_pattern_count_reduced(self) -> None:
        """session.js 안의 ``termSessionId = null`` 총 출현 횟수가 베이스라인 대비 감소."""
        # 베이스라인 시점 정확히 3건:
        #   - line 1888 (startSession 진입부)
        #   - line 1897 (isResume=false 분기)
        #   - line 2067 (_finalizeStoppedUI)
        # P2 이후: setter 가 진입부 + _finalizeStoppedUI 의 reset 흡수 → 2건↓ 예상
        matches = re.findall(r'termSessionId\s*=\s*null', self.src)
        self.assertLessEqual(
            len(matches), 2,
            'session.js termSessionId=null sites should drop to <= 2 after P2; '
            f'got {len(matches)}',
        )


class TestBoardSessionExportsPreservedP2(unittest.TestCase):
    """P1 회귀 차단: Board.session 5종 export 가 P2 작업으로 깨지지 않았다."""

    EXPECTED_KEYS = (
        'startSession',
        'killSession',
        'fetchStatus',
        'postJson',
        'connectSSE',
    )

    def test_five_keys_present(self) -> None:
        src = _read('workflow/session.js')
        for key in self.EXPECTED_KEYS:
            self.assertRegex(
                src, r'\b' + re.escape(key) + r'\s*:',
                f'Board.session.{key} export regressed after P2',
            )


if __name__ == '__main__':
    unittest.main()

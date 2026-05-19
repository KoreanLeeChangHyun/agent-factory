"""T-384 Phase 1 — 베이스라인 회귀 안전망.

JS 측 자동 테스트 인프라가 부재한 상태에서 리팩토링 산출물의 구조적 결과를
결정론적으로 검증하기 위해, JS 소스 파일을 grep/regex 로 스캔하는 pytest 를
운영한다 (test_handlers_t424.py 와 동일 패턴).

Phase 1 의 책임:
  1. 3 파일 (workflow/session.js, terminal/output-pipe.js, terminal/terminal.js)
     이 존재함을 보장한다.
  2. 외부 API 5종 (startSession, killSession, fetchStatus, postJson, connectSSE)
     이 ``Board.session`` 네임스페이스에 export 되어 있음을 보장한다.
  3. ``core/common.js`` 에 ``Board.state.setTermStatus`` 정의가 정확히 1건
     존재함을 보장한다 (인벤토리 record).
  4. 현재 ``setTermStatus(`` 호출자 수가 일정 수 이상임을 캡처한다
     (회귀 시 호출자 감소가 의도된 변화인지 추적 보조).

본 베이스라인은 동작 변경 0 — green 으로 시작해 P2~P5 사이에 회귀 신호로
계속 평가된다.
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


def _iter_js_files() -> list[str]:
    out: list[str] = []
    for dirpath, _dirs, files in os.walk(_JS_ROOT):
        for name in files:
            if name.endswith('.js'):
                out.append(os.path.join(dirpath, name))
    return out


_TARGET_FILES = (
    'workflow/session.js',
    'terminal/output-pipe.js',
    'terminal/terminal.js',
)


class TestTargetFilesExist(unittest.TestCase):
    """Acceptance Criterion 1: 3 대상 파일이 모두 존재한다."""

    def test_target_files_present(self) -> None:
        for rel in _TARGET_FILES:
            full = os.path.join(_JS_ROOT, rel)
            self.assertTrue(
                os.path.isfile(full),
                f'target file missing: {rel}',
            )
            self.assertGreater(
                os.path.getsize(full), 0,
                f'target file empty: {rel}',
            )


class TestBoardSessionExports(unittest.TestCase):
    """Acceptance Criterion 2: Board.session.* 5종 export 보존."""

    EXPECTED_KEYS = (
        'startSession',
        'killSession',
        'fetchStatus',
        'postJson',
        'connectSSE',
    )

    def setUp(self) -> None:
        self.src = _read('workflow/session.js')

    def test_board_session_block_present(self) -> None:
        """`Board.session = { ... }` 블록 1개가 존재한다."""
        # 단순 substring 으로 진입점 보장 — 위치 규약은 풀어둔다 (P4 리팩토링 여지).
        self.assertIn(
            'Board.session', self.src,
            'Board.session export point missing in session.js',
        )

    def test_five_external_api_keys(self) -> None:
        """5종 키가 모두 export 블록 안에 grep 매칭된다."""
        # 키별 정규식: `KEY:` 형태 (콜론 뒤 함수 참조). 띄어쓰기 허용.
        for key in self.EXPECTED_KEYS:
            pat = re.compile(r'\b' + re.escape(key) + r'\s*:')
            self.assertRegex(
                self.src, pat,
                f'Board.session.{key} export missing in session.js',
            )


class TestSetTermStatusInventory(unittest.TestCase):
    """Acceptance Criterion 3: setTermStatus 본체 정의 1건 + 호출자 카운트 캡처."""

    def test_setter_defined_once_in_common(self) -> None:
        """`Board.state.setTermStatus = function` 정의가 core/common.js 에 정확히 1건."""
        common = _read('core/common.js')
        matches = re.findall(
            r'Board\.state\.setTermStatus\s*=\s*function',
            common,
        )
        self.assertEqual(
            len(matches), 1,
            f'expected 1 setTermStatus definition in core/common.js, got {len(matches)}',
        )

    def test_setter_call_baseline_threshold(self) -> None:
        """`setTermStatus(` 호출 총량이 베이스라인 임계 이상.

        리팩토링이 호출 패턴을 줄이는 것은 정상 진화이므로 상한은 두지 않고
        하한만 강제한다. 본 인벤토리는 P2~P5 의 비교 기준점.
        """
        total = 0
        for full in _iter_js_files():
            with open(full, 'r', encoding='utf-8') as fh:
                total += len(re.findall(r'setTermStatus\s*\(', fh.read()))
        # 베이스라인 시점 총 33건 (core/common 5 + output-pipe 2 + session-switcher 1
        # + terminal-input 5 + terminal 1 + wf-ticket-renderer 2 + session 17).
        # 향후 리팩토링이 줄이거나 늘리는 것 모두 허용하되 0 이 되면 회귀.
        self.assertGreater(
            total, 5,
            'setTermStatus( total call count collapsed below baseline minimum',
        )

    def test_stopped_branch_call_sites_present(self) -> None:
        """`setTermStatus('stopped')` 형태 호출이 최소 1건 존재.

        P2 가 도입할 'stopped' 분기 invariant 의 호출 대상 사이트가
        실재함을 보장 (베이스라인에서 캡처).
        """
        total = 0
        for full in _iter_js_files():
            with open(full, 'r', encoding='utf-8') as fh:
                total += len(re.findall(
                    r"setTermStatus\s*\(\s*['\"]stopped['\"]",
                    fh.read(),
                ))
        self.assertGreater(
            total, 0,
            "setTermStatus('stopped') call site missing — P2 invariant has no target",
        )


class TestHistoryFunctionsBaseline(unittest.TestCase):
    """Acceptance Criterion 4: P3 가 흡수할 옛 함수들의 베이스라인 캡처.

    ``loadHistory`` + ``fetchHistorySince`` 두 함수가 ``output-pipe.js`` 에
    정의되어 있음을 인벤토리로 남겨, P3 가 단일 진입점으로 통합한 뒤에도
    옛 호출이 wrapper 로 보존되는지 추적할 수 있게 한다.
    """

    def test_load_history_defined(self) -> None:
        src = _read('terminal/output-pipe.js')
        self.assertRegex(
            src, r'\bM\.loadHistory\s*=',
            'M.loadHistory definition missing in output-pipe.js',
        )

    def test_fetch_history_since_defined(self) -> None:
        src = _read('terminal/output-pipe.js')
        self.assertRegex(
            src, r'\bM\.fetchHistorySince\s*=',
            'M.fetchHistorySince definition missing in output-pipe.js',
        )


class TestFinalizeStoppedBaseline(unittest.TestCase):
    """Acceptance Criterion 5: P4 가 흡수할 _finalizeStoppedUI 본체 베이스라인."""

    def test_finalize_stopped_present(self) -> None:
        src = _read('workflow/session.js')
        self.assertRegex(
            src, r'\bfunction\s+_finalizeStoppedUI\s*\(',
            '_finalizeStoppedUI definition missing in session.js',
        )

    def test_term_session_id_null_in_finalize(self) -> None:
        """현재 베이스라인에서 termSessionId=null 처리는 _finalizeStoppedUI 안에서만 발생."""
        src = _read('workflow/session.js')
        # session.js 안에 `termSessionId = null` 라인이 1건 이상 — startSession 진입부 +
        # _finalizeStoppedUI 본체 합산. P4 가 단일점으로 응집한 뒤에도 0 으로 떨어지면
        # 회귀로 본다.
        matches = re.findall(r'termSessionId\s*=\s*null', src)
        self.assertGreater(
            len(matches), 0,
            'termSessionId = null pattern missing in session.js',
        )


if __name__ == '__main__':
    unittest.main()

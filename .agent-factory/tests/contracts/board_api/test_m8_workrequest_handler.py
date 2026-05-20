"""M8 WorkRequest facade endpoint tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT_FACTORY = Path(__file__).resolve().parents[3]
_WORKTREE_ROOT = _AGENT_FACTORY.parent
for _p in (_WORKTREE_ROOT, _AGENT_FACTORY):
    _path = str(_p)
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _handler(body: dict):
    from board.server.handlers.kanban import KanbanHandlerMixin

    class FakeHandler(KanbanHandlerMixin):
        def __init__(self):
            self._body = body
            self._sent_json = None
            self._sent_error = None

        def _read_json_body(self):
            return self._body

        def _send_json(self, data):
            self._sent_json = data

        def _send_error(self, code, msg):
            self._sent_error = (code, msg)

    return FakeHandler()


class TestM8WorkRequestHandler(unittest.TestCase):
    def test_create_uses_flow_kanban_create_and_prompt_update(self):
        h = _handler({
            "action": "create",
            "title": "M8 sample",
            "command": "implement",
            "status": "todo",
            "goal": "Build the request",
        })
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[1] == "create":
                return subprocess.CompletedProcess(args, 0, stdout="T-520: M8 sample [To Do]", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout="T-520: prompt 갱신됨", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("os.getcwd", return_value=tmpdir), patch("subprocess.run", side_effect=fake_run):
                h._handle_kanban_workrequest()

        self.assertIsNone(h._sent_error)
        self.assertEqual(h._sent_json["ticket"], "T-520")
        self.assertEqual(calls[0][1:5], ["create", "M8 sample", "--command", "implement"])
        self.assertIn("update-prompt", calls[1])

    def test_accept_moves_to_open(self):
        h = _handler({"action": "accept", "ticket": "T-520"})

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout="T-520: To Do -> Open", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("os.getcwd", return_value=tmpdir), patch("subprocess.run", side_effect=fake_run) as run:
                h._handle_kanban_workrequest()

        self.assertIsNone(h._sent_error)
        self.assertEqual(h._sent_json["action"], "accept")
        self.assertEqual(run.call_args.args[0][1:], ["move", "T-520", "open"])

    def test_invalid_action_returns_400(self):
        h = _handler({"action": "bogus"})
        h._handle_kanban_workrequest()
        self.assertEqual(h._sent_error[0], 400)


if __name__ == "__main__":
    unittest.main()

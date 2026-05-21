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
    from board.server.handlers.conveyor import ConveyorHandlerMixin

    class FakeHandler(ConveyorHandlerMixin):
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
    def test_create_uses_flow_conveyor_create_and_prompt_update(self):
        h = _handler({
            "action": "create",
            "title": "M8 sample",
            "command": "implement",
            "status": "draft",
            "goal": "Build the request",
        })
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[1] == "create":
                return subprocess.CompletedProcess(args, 0, stdout="WR-520: M8 sample [Draft]", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout="WR-520: prompt updated", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("os.getcwd", return_value=tmpdir), patch("subprocess.run", side_effect=fake_run):
                h._handle_conveyor_workrequest()

        self.assertIsNone(h._sent_error)
        self.assertEqual(h._sent_json["work_request"], "WR-520")
        self.assertEqual(calls[0][1:5], ["create", "M8 sample", "--command", "implement"])
        self.assertIn("update-prompt", calls[1])

    def test_accept_moves_to_open(self):
        h = _handler({"action": "accept", "work_request": "WR-520"})

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout="WR-520: Draft -> Accepted", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("os.getcwd", return_value=tmpdir), patch("subprocess.run", side_effect=fake_run) as run:
                h._handle_conveyor_workrequest()

        self.assertIsNone(h._sent_error)
        self.assertEqual(h._sent_json["action"], "accept")
        self.assertEqual(run.call_args.args[0][1:], ["move", "WR-520", "accepted"])

    def test_accept_records_ouroboros_history_when_ticket_exists(self):
        h = _handler({"action": "accept", "work_request": "WR-520"})

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout="WR-520: Draft -> Accepted", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            requests = Path(tmpdir) / ".agent-factory" / "work-requests" / "draft"
            requests.mkdir(parents=True)
            (requests / "WR-520.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<work_request>
  <metadata>
    <number>WR-520</number>
    <title>Accept sample</title>
    <status>Draft</status>
    <command>implement</command>
  </metadata>
  <prompt>
    <goal>Accept the request</goal>
    <criteria>- history is recorded</criteria>
  </prompt>
</work_request>
""",
                encoding="utf-8",
            )
            with patch("os.getcwd", return_value=tmpdir), patch("subprocess.run", side_effect=fake_run):
                h._handle_conveyor_workrequest()

            from engine.adapters.conveyor import XmlWorkRequestStore
            from engine.core.work_requests import OuroborosPhase, WorkRequestRef

            request = XmlWorkRequestStore(Path(tmpdir) / ".agent-factory" / "work-requests").get(
                WorkRequestRef.parse("WR-520")
            )

        self.assertIsNone(h._sent_error)
        self.assertTrue(h._sent_json["ouroborosRecorded"])
        self.assertEqual(
            [entry.phase for entry in request.ouroboros_history],
            [OuroborosPhase.CLARIFY, OuroborosPhase.CRITIQUE, OuroborosPhase.ACCEPT],
        )

    def test_invalid_action_returns_400(self):
        h = _handler({"action": "bogus"})
        h._handle_conveyor_workrequest()
        self.assertEqual(h._sent_error[0], 400)


if __name__ == "__main__":
    unittest.main()

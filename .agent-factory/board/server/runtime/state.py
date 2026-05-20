"""Module-level singletons shared across handlers."""

from __future__ import annotations

import os

from board.server.channels.sse_client_manager import SSEClientManager
from board.server.sessions.poll_tracker import PollChangeTracker
from board.server.channels.terminal_channel import TerminalSSEChannel
from board.server.processes.claude_process import ClaudeProcess
from board.server.sessions.workflow_session import WorkflowSessionRegistry
from board.server.sessions.production_line_session import ProductionLineSessionRegistry

# Module Level SSE Client Manager (Share with Server instances)
sse_manager: SSEClientManager = SSEClientManager()

# Module level polling change tracker (shared with server instances)
poll_tracker: PollChangeTracker = PollChangeTracker()

# Module Level Terminal SSE Channel and Claude Process Manager
terminal_sse_channel: TerminalSSEChannel = TerminalSSEChannel()
claude_process: ClaudeProcess = ClaudeProcess(
    terminal_sse_channel,
    persist_file=os.path.join(os.getcwd(), '.agent-factory', '.last-session-id'),
)

# Module Level Workflow Session Registry
workflow_registry: WorkflowSessionRegistry = WorkflowSessionRegistry()
production_line_registry: ProductionLineSessionRegistry = ProductionLineSessionRegistry()

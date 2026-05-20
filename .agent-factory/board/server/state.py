"""Module-level singletons shared across handlers."""

from __future__ import annotations

import os

from .channels.sse_client_manager import SSEClientManager
from .sessions.poll_tracker import PollChangeTracker
from .channels.terminal_channel import TerminalSSEChannel
from .processes.claude_process import ClaudeProcess
from .sessions.workflow_session import WorkflowSessionRegistry
from .sessions.production_line_session import ProductionLineSessionRegistry

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

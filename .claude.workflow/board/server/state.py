"""Module-level singletons shared across handlers."""

from __future__ import annotations

import os

from .sse_client_manager import SSEClientManager
from .poll_tracker import PollChangeTracker
from .terminal_channel import TerminalSSEChannel
from .claude_process import ClaudeProcess
from .workflow_session import WorkflowSessionRegistry

# 모듈 레벨 SSE 클라이언트 매니저 (서버 인스턴스와 공유)
sse_manager: SSEClientManager = SSEClientManager()

# 모듈 레벨 폴링 변경 추적기 (서버 인스턴스와 공유)
poll_tracker: PollChangeTracker = PollChangeTracker()

# 모듈 레벨 터미널 SSE 채널 및 Claude 프로세스 매니저
terminal_sse_channel: TerminalSSEChannel = TerminalSSEChannel()
claude_process: ClaudeProcess = ClaudeProcess(
    terminal_sse_channel,
    persist_file=os.path.join(os.getcwd(), '.claude.workflow', '.last-session-id'),
)

# 모듈 레벨 워크플로우 세션 레지스트리
workflow_registry: WorkflowSessionRegistry = WorkflowSessionRegistry()

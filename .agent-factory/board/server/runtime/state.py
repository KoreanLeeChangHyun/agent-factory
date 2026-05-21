"""Module-level singletons shared across handlers."""

from __future__ import annotations

import os
from dataclasses import dataclass

from board.server.channels.sse_client_manager import SSEClientManager
from board.server.sessions.poll_tracker import PollChangeTracker
from board.server.channels.terminal_channel import TerminalSSEChannel
from board.server.processes.brain_process import BrainProcess, create_brain_process
from board.server.sessions.workflow_session import WorkflowSessionRegistry
from board.server.sessions.production_line_session import ProductionLineSessionRegistry


@dataclass(frozen=True)
class TerminalProviderConfig:
    provider: str = 'claude'
    codex_bin: str = 'codex'
    codex_model: str | None = None
    codex_profile: str | None = None
    codex_sandbox: str = 'workspace-write'


def _read_settings(project_root: str) -> dict[str, str]:
    settings_path = os.path.join(project_root, '.agent-factory', '.settings')
    if not os.path.isfile(settings_path):
        return {}
    values: dict[str, str] = {}
    try:
        with open(settings_path, encoding='utf-8') as fp:
            for raw in fp:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                values[key.strip()] = value.strip()
    except OSError:
        return {}
    return values


def load_terminal_provider_config(project_root: str) -> TerminalProviderConfig:
    """Load terminal provider config from env and `.agent-factory/.settings`."""
    settings = _read_settings(project_root)

    def get(key: str, default: str | None = None) -> str | None:
        return os.environ.get(key) or settings.get(key) or default

    provider = str(get('AGENT_FACTORY_LLM_PROVIDER', 'claude')).strip().lower()
    if provider not in ('claude', 'codex'):
        provider = 'claude'
    return TerminalProviderConfig(
        provider=provider,
        codex_bin=str(get('CODEX_BIN', 'codex')),
        codex_model=get('CODEX_MODEL'),
        codex_profile=get('CODEX_PROFILE'),
        codex_sandbox=str(get('CODEX_SANDBOX', 'workspace-write')),
    )

# Module Level SSE Client Manager (Share with Server instances)
sse_manager: SSEClientManager = SSEClientManager()

# Module level polling change tracker (shared with server instances)
poll_tracker: PollChangeTracker = PollChangeTracker()

# Module Level Terminal SSE Channel and Claude Process Manager
terminal_sse_channel: TerminalSSEChannel = TerminalSSEChannel()
brain_process: BrainProcess = create_brain_process(
    terminal_sse_channel,
    provider='claude',
    persist_file=os.path.join(os.getcwd(), '.agent-factory', '.last-session-id'),
)
# Compatibility name for older imports. New board API code should use
# ``brain_process`` so terminal routing can become provider-neutral.
claude_process: BrainProcess = brain_process

# Module Level Workflow Session Registry
workflow_registry: WorkflowSessionRegistry = WorkflowSessionRegistry()
production_line_registry: ProductionLineSessionRegistry = ProductionLineSessionRegistry()


def _terminal_process_can_be_replaced(process: BrainProcess) -> bool:
    status = process.status
    if status == 'stopped':
        return True
    return status == 'idle' and not process.awaiting_response


def configure_brain_process(
    project_root: str,
    *,
    persist_file: str | None = None,
) -> BrainProcess:
    """Apply terminal provider settings to the next stopped terminal process."""
    global brain_process, claude_process

    config = load_terminal_provider_config(project_root)
    current_provider = getattr(brain_process, 'provider', 'claude')
    target_persist = persist_file or os.path.join(
        project_root, '.agent-factory', '.last-session-id',
    )

    if not _terminal_process_can_be_replaced(brain_process):
        brain_process.set_persist_file(target_persist)
        return brain_process

    if current_provider == config.provider:
        brain_process.set_persist_file(target_persist)
        return brain_process

    brain_process.kill()
    brain_process = create_brain_process(
        terminal_sse_channel,
        provider=config.provider,
        persist_file=target_persist,
        codex_bin=config.codex_bin,
        codex_model=config.codex_model,
        codex_profile=config.codex_profile,
        codex_sandbox=config.codex_sandbox,
        cwd=project_root,
    )
    claude_process = brain_process
    return brain_process

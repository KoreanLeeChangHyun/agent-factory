# Naming Policy

Agent Factory is the active product and runtime name.

Use `Agent Factory` for operator-facing documentation, board titles, runtime
layout descriptions, and general workflow language. Use `.agent-factory` for
the runtime root path.

Keep provider-specific names only when the text is explicitly about that
provider boundary:

- `Claude Code` for hook payloads, `.claude/` integration files, and the
  Claude CLI process surface.
- `ClaudeAdapter`, `CodexAdapter`, `GeminiAdapter`, and `FakeAdapter` for
  concrete LLM adapter implementations.
- historical names such as `.claude-organic` only in migration records that
  describe the rename itself.

Do not introduce new `organic`, `claude-organic`, or provider-branded names for
core, application, board, or workflow concepts.

Use `ActionRenderEvent` for the provider-neutral Desk rendering contract. Avoid
`DeskRenderEvent`: Desk is the surface, while the renderable unit is an action.

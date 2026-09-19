# Agent Factory Agents

Agent Factory Agents is a single VS Code extension that provides a custom
Codex chat in the editor area. The `linux-x64` VSIX includes its compatible
Codex CLI payload, so it does not download a runtime or depend on the Agent
Factory web application.

The extension uses the existing Codex authentication and configuration visible
to the VS Code Extension Host. Open the Agent Factory Activity Bar and use the
launcher to open chat in the editor area. The command reuses one editor tab and
reconnects the current Main Agent sessions when the tab is reopened.

Requirements and the source layout are documented in `docs/`.

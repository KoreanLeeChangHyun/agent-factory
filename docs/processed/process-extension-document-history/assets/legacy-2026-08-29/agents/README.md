# Agent Factory Agents

Agent Factory Agents is an independent VS Code extension that runs Codex from
the Activity Bar. The `linux-x64` VSIX includes its compatible Codex CLI
payload, so it does not download a runtime or depend on the Agent Factory web
application.

The extension uses the existing Codex authentication and configuration visible
to the VS Code Extension Host. Open the Agent Factory Activity Bar and use the
launcher to open Agents or Workspace in the editor area. The Agents command
reuses one editor tab and reconnects the current Main Agent sessions when the
tab is reopened.

Workflow execution, image attachments, and model controls are outside this
release.

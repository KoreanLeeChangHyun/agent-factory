# Agent Factory

This parent repository brings the three Agent Factory components — the extension,
the MCP service, and the plugin — together with the shared project documentation in a
single workspace. Each is an independent Git repository linked as a submodule that
tracks its `main` branch.

## Core features

- **Document system:** Organize sources, working knowledge, accepted specifications,
  progress, and lessons with clear ownership and one editable source per document.
- **Contracts → Work–Verification loop:** Define the goal, file structure, workers, and
  order in a versioned contract, execute the contracted tasks, record results in the
  contract, and return verification findings for correction.
- **Interviews:** Resolve material requirements and decisions through guided
  questions, options, and a summary of your choices.
- **Lessons learned:** Record errors and judgment differences, retrieve relevant
  experience before work, and consolidate supported lessons into rules when requested.
- **Agent settings:** Choose Main, Work, and Verification models and reasoning levels
  per chat, project, or globally, save them as presets, and run on Codex, Claude Code,
  or Antigravity.
- **Chat workspace:** Choose a per-message action (document, contract, interview,
  planning, or delegated execution), queue messages, keep notes, and follow run status.
- **Work Units:** Isolate a task in its own Git worktree and branch, carry the
  conversation's decisions into a new chat, and merge the result back.

See the [extension guide](https://github.com/KoreanLeeChangHyun/agent-factory-vscode-extension/blob/main/README.md#2-core-features) for the detailed local
workflow, including the [chat workspace](https://github.com/KoreanLeeChangHyun/agent-factory-vscode-extension/blob/main/README.md#3-chat-workspace) and
[agent settings](https://github.com/KoreanLeeChangHyun/agent-factory-vscode-extension/blob/main/README.md#4-agent-settings), and the
[plugin source guide](https://github.com/KoreanLeeChangHyun/agent-factory-plugin-source/blob/main/README.md) for host distributions and tests.
The MCP service is independently operated and is not required by the plugin or extension.

## Project Structure

| Path | Project | Branch |
| --- | --- | --- |
| [extension/](https://github.com/KoreanLeeChangHyun/agent-factory-vscode-extension/tree/main) | VS Code Main chat interface | `main` |
| [mcp/](https://github.com/KoreanLeeChangHyun/agent-factory-mcp/tree/main) | Independent cloud Workspace and MCP server | `main` |
| [plugin/](https://github.com/KoreanLeeChangHyun/agent-factory-plugin-source/tree/main) | Single source for Skills, runtime, and Codex/Claude Code/Antigravity distributions | `main` |
| [docs/](https://github.com/KoreanLeeChangHyun/agent-factory-docs/tree/main) | Shared project documentation | `main` |

- Path links open each repository's `main` branch. GitHub's file list shows
  submodules as `name @ commit` and links to the recorded commit instead.
- The Branch column is the remote branch configured in `.gitmodules`. A local
  checkout may use another branch for ongoing work.

## Clone

Clone the repository together with its submodules:

```bash
git clone --recurse-submodules git@github.com:KoreanLeeChangHyun/agent-factory.git
cd agent-factory
```

If you have already cloned the parent repository without its submodules, initialize them:

```bash
git submodule update --init --recursive
```

## Update

Use the component revisions recorded by the parent repository:

```bash
git pull
git submodule update --init --recursive
```

To advance submodules to their configured remote branches, run
`git submodule update --init --remote --recursive` and review the changed revisions.

To work directly on a project, switch to its directory:

```bash
cd extension    # or mcp, plugin, docs
git status
```

To record new submodule commits in the parent repository, commit the updated pointers from the parent directory:

```bash
cd ..
git add extension mcp plugin docs
git commit -m "chore: update component revisions"
git push
```

## Project Documentation

- The `docs/` submodule owns project documentation. Commit document changes in
  `docs/`, then record the updated pointer in the parent repository.
- Component README and AGENTS.md files are entry points. User-distributed Skills
  in `plugin/skills/` remain separate from developer documentation.

| Location | Purpose |
| --- | --- |
| `docs/original/` | Metadata and links identifying external sources |
| `docs/refined/` | Research, interviews, analysis, and historical records |
| `docs/skills/` | Accepted project information, rules, and designs |
| `docs/progress/` | Versioned contracts, task progress, and execution evidence |
| `docs/lessons-learned/` | Error and judgment records with causes, outcomes, and applications |
| `docs/artifact/` | AI-generated outputs outside Document packages, such as mockups and release files |

- Refined documents retain the `processed` metadata type for compatibility.
- Follow the project documentation rules in `docs/skills/rule-documents/SKILL.md`
  for package structure, source preservation, and ownership.
- After changing `docs/skills/`, run the Document Skill's
  `sync_documents.py --project-root <agent-factory-root>` and check the result.
  `.codex/skills/`, `.claude/skills/`, and `.agents/skills/` (Antigravity) are derived,
  ignored by Git, and must not be edited directly.

## Requirements

- Python 3.10+.
- At least one of the following agent runtimes. Installed runtimes are detected
  automatically, and their models become available together:
  - [Codex CLI](https://developers.openai.com/codex/cli/)
  - [Claude Code](https://code.claude.com/docs/en/setup)
  - [Antigravity CLI](https://antigravity.google/docs/getting-started?tab=cli)

## License

MIT License. See [LICENSE](LICENSE). Each component repository carries its own license.

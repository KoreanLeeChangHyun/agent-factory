# Agent Factory

This parent repository brings Agent Factory projects together in a single workspace.
Each project is an independent Git repository linked as a submodule.

## Core features

- **Document system:** Organize sources, working knowledge, accepted specifications,
  progress, and lessons with clear ownership and one editable source per document.
- **Contracts → Work–Verification loop:** Define scope and completion criteria,
  execute the contracted tasks, and return verification findings for correction.
- **Interviews:** Resolve material requirements and decisions through guided
  questions, options, and a summary of your choices.
- **Lessons learned:** Record errors and judgment differences, retrieve relevant
  experience before work, and consolidate supported lessons into rules when requested.

See the [extension guide](extension/README.md#2-core-features) and
[plugin guide](plugin/README.md#core-features) for the detailed local workflow.
The MCP service is independently operated and is not required by the plugin or extension.

## Project Structure

| Path | Project | Branch |
| --- | --- | --- |
| [plugin/](plugin/README.md) | Agent execution, conventions, and document Skills | `main` |
| [extension/](extension/README.md) | VS Code chat interface | `main` |
| [mcp/](mcp/README.md) | Independent cloud Workspace and MCP server | `main` |

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
cd plugin    # or extension, mcp
git status
```

To record new submodule commits in the parent repository, commit the updated pointers from the parent directory:

```bash
cd ..
git add plugin extension mcp
git commit -m "chore: update component revisions / 구성 요소 참조 갱신"
git push
```

## Project Documentation

- The parent checkout's `docs/` directory owns project documentation.
- Component README and AGENTS.md files are entry points. User-distributed Skills
  in `plugin/skills/` remain separate from developer documentation.

| Location | Purpose |
| --- | --- |
| `docs/original/` | Metadata and links identifying external sources |
| `docs/refined/` | Research, interviews, analysis, and historical records |
| `docs/skills/` | Accepted project information, rules, and designs |
| `docs/progress/` | Versioned contracts, task progress, and execution evidence |
| `docs/lessons-learned/` | Error and judgment records with causes, outcomes, and applications |

- Refined documents retain the `processed` metadata type for compatibility.
- Follow the [project documentation rules](docs/skills/rule-documents/SKILL.md)
  for package structure, source preservation, and ownership.
- After changing `docs/skills/`, run the Document Skill's
  `sync_documents.py --project-root <agent-factory-root>` and check the result.
  `.codex/skills/` is derived and must not be edited directly.

## Runtime installation links

- [Codex CLI](https://developers.openai.com/codex/cli/)
- [Claude Code](https://code.claude.com/docs/en/setup)

# Agent Factory

This parent repository brings Agent Factory projects together in a single workspace.
Each project is an independent Git repository linked as a submodule.

## Project Structure

| Path | Project | Branch |
| --- | --- | --- |
| `plugin/` | Codex plugin | `main` |
| `extension/` | VS Code extension | `main` |
| `mcp/` | Cloud workspace and MCP server | `main` |

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

Update the parent repository and the configured branch of each submodule:

```bash
git pull
git submodule update --init --remote --recursive
```

To work directly on a project, switch to its directory:

```bash
cd plugin    # or extension, mcp
git status
```

To record new submodule commits in the parent repository, commit the updated pointers from the parent directory:

```bash
cd ..
git add plugin extension mcp
git commit -m "Update component revisions"
git push
```

## Project Documentation

The editable source documents are maintained in the parent repository's `docs/` directory.

- [Original](docs/original/): Metadata and links identifying external sources.
- [Processed](docs/processed/): Research, interviews, analysis, past decisions, and execution records.
- [Project Specifications](docs/skills/): The single source of truth for current information, rules, and designs.

Each Processed or Specification document consists of one topic-specific `SKILL.md` and any required `assets/`. HTML documents, English documents, and scattered references covering the same topic are consolidated into the document that owns it, preserving existing source text, sources, code, and identifiers. Follow the [project documentation rules](docs/skills/rule-documents/SKILL.md) for the current requirements.

Component README and AGENTS.md files remain entry points. `plugin/skills/` contains execution skills distributed to users and is separate from project documentation.

After modifying `docs/skills/`, run the Document skill's `sync_documents.py --project-root <agent-factory-root>`. `.codex/skills/` is a derived copy and must not be edited directly. Links in both the source and derived copies must point to the same canonical documents.

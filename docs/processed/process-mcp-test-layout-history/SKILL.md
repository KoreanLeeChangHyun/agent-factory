---
name: mcp-test-layout-history
description: MCP 테스트 배치 이력을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/mcp/tests/STRUCTURE.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# MCP 테스트 배치 이력

- 기존 도메인별 배치와 당시 실행 안내를 보존합니다. 현재 앱·패키지별 배치 규칙의 대체 문서가 아닙니다.

<a id="기존-테스트-구조"></a>

## 1. 기존 테스트 구조

- All project test code lives here, grouped by domain. Tests are not stored beside production source.

| Directory | Domain |
| --- | --- |
| identity | Authentication, authorization, identity and email adapters |
| organizations | Organization membership and management |
| workspaces | Workspace management and personal workspaces |
| workbenches | Shell, registry, runtime, authoring and persistence |
| knowledge | Documents, search, provenance, delivery and previews |
| scheduling | Durable schedules, jobs and worker execution |
| planning | Plan items, calendars and imports |
| agents | Agent definitions, execution and evidence |
| reporting | External reports and reporting runtime |
| connections | Providers, credentials, OAuth and MCP connections |
| mcp | Cross-domain MCP transport and server contracts |
| appearance | Themes and user appearance |
| administration | Platform administration |
| design_system | Shared components, catalog and UI kit |
| database | Database foundation and migrations |
| security | Security and tenant isolation |
| operations | Health, observability, packaging and deployment |
| platform | Cross-domain platform integration |
| contracts | Shared contracts and compatibility |
| architecture | Dependency boundaries |
| support | Shared test helpers |
| tools | Test and verification launchers |

- Within each domain, `core`, `adapters`, `api`, `worker`, `web`, `browser`, `integration`, and `regression` identify the tested boundary. Existing combined tests stay intact instead of splitting behavior assertions mechanically.

- Direct commands from the repository root:

```sh
.venv/bin/python -m pytest tests/knowledge
pnpm exec vitest run tests/knowledge/web
pnpm test
```

- Moving files does not establish that their tests pass. No test suite was run during this relocation, as instructed.

---
name: rule-project
description: Apply this repository's project structure, ownership, development, testing,
  and documentation conventions. Use when implementing, refactoring, reviewing, or
  placing files in the Agent Factory MCP repository; do not use as the source of product
  behavior or domain contracts.
metadata:
  document-type: specification
  category: rule
  domain: null
  name: project
  language: ko
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/rule-project/SKILL.md
    - docs/skills/rule-project/references/directory-structure.md
    - docs/skills/rule-project/references/testing.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: rule-project
      description: Apply this repository's project structure, ownership, development,
        testing, and documentation conventions. Use when implementing, refactoring,
        reviewing, or placing files in the Agent Factory MCP repository; do not use
        as the source of product behavior or domain contracts.
---


# Project Rules

- Keep changes consistent with this FastAPI MCP/Workspace application and its existing ownership boundaries.

<a id="start-with-the-affected-area"></a>

## 1. Start with the affected area

1. Read [directory-structure](#directory-structure) before adding, moving, or substantially reorganizing files.
2. Inspect the owning module, its callers, nearby tests, and established patterns before editing.
3. Use `$info-platform` for maintained facts, `$design-platform` for accepted architecture, and `$rule-platform` for mandatory product behavior. Read only the affected references.
4. For Human-facing Workspace UI work, also use `$rule-ui`; its visual rules supplement this project Skill.

<a id="engineering-conventions"></a>

## 2. Engineering conventions

- Keep transport handlers thin. Follow `$rule-workbench-structure`: app-specific service flows belong in `apps/`; shared business rules and infrastructure implementations belong in `packages/core/` and `packages/adapters/` respectively.
- Preserve organization and Workspace isolation across routes, services, repositories, jobs, MCP tools, and tests. UI visibility is never an authorization boundary.
- Reuse existing abstractions and make the smallest coherent change. Do not mix broad formatting or unrelated cleanup into behavioral work.
- Keep public API, MCP tool, database migration, static asset, and packaging changes synchronized with their owning tests and documentation.
- Add Alembic revisions instead of rewriting migration history. Treat PostgreSQL as authoritative; development adapters are not production architecture.
- 공통 UI의 목표 소유자는 `packages/design-system`입니다. 기존 `static/`·템플릿 경로는 이전 입력이며, 현재 책임과 목표 배치는 구조 규칙을 따릅니다.
- Explain non-obvious constraints and side effects in comments; do not narrate straightforward code. Every TODO needs a reason and a completion condition or issue.
- Preserve unrelated dirty or untracked work. Do not silently move, mirror, migrate, or delete files.

<a id="documentation"></a>

## 3. Documentation

- Apply `$rule-documents` when creating, moving, or promoting documentation.
- Keep Original source material in `../docs/original/`, Processed investigations and verification records in `../docs/processed/`, and Human-requested accepted specifications in `../docs/skills/`.

- Separate accepted requirements, observed implementation facts, inferences, and unresolved decisions.
- Update the owning document instead of copying the same rule into several files or into this Skill.
- Use short sections for distinct topics, tables for repeated mappings, and diagrams only when relationships or state transitions are materially clearer visually.

<a id="verification"></a>

## 4. Verification

- Read [testing](#testing) when selecting gates. Start with the smallest tests that cover the changed behavior, then widen according to risk.

- Focused tests: `.venv/bin/python -m pytest -q <test paths>`
- Common local gate (lint, types, and tests): `make check`

- Domain verification scripts under `scripts/` may start disposable PostgreSQL or build images; run them only when their domain and prerequisites match the change.

- Do not claim integration, browser, container, migration, deployment, or production verification unless that exact check ran successfully.

<a id="current-human-instruction-test-ownership"></a>

## 5. Current Human instruction: test ownership

- All test code and test-only helpers live under root `tests/`. Follow the app/package-first layout in `$rule-workbench-structure`: `api/`, `web/`, `mcp/`, `jobs/`, `packages/`, with `contracts/`, `integration/`, and `support/` for shared verification. 이 규칙이 이전 도메인별 배치표를 대체합니다. [기존 배치 기록](../../../docs/processed/process-mcp-test-layout-history/SKILL.md)은 역사 자료입니다. Do not place tests beside production source. Docker and Makefile execution have been retired; use direct package/runtime commands.

<a id="directory-structure"></a>

## 6. directory-structure

- The single maintained directory contract is [the accepted repository structure](../rule-workbench-structure/SKILL.md#target-structure). Read it before placing or moving files. It owns the complete tree, fixed root boundary, app/package responsibilities, test classification, deployment location, and protection of Human-owned `feedback/` and `uploads/`. Legacy `app/`, `static/`, and `template/` paths in historical records are not instructions to recreate those roots.

<a id="repository-boundaries"></a>

## 7. Repository boundaries

- This repository owns the cloud service, web UI, MCP application, shared business logic, workers, deployment, and tests.
- The sibling Agent Factory plugin owns distributable Skills and local execution-loop behavior. Do not mirror those contracts here.
- Consumer repositories do not receive this server, browser bundle, or a project-local Workspace runtime.
- Preserve ignored local data and tool artifacts. They are not authoritative source, and reorganization does not authorize deleting them.
- Keep secrets and credentials out of Git, generated documents, logs, and test fixtures.

<a id="placement-decisions"></a>

## 8. Placement decisions

- Extend the existing owner before proposing a new structural group.
- Add shared abstractions only when real consumers need the same behavior and no domain is its natural owner.
- Keep generated assets distinct from editable sources and preserve their generation contract.
- Classify tests by the app or package they verify; keep all tests and test-only helpers under root `tests/`.

- Use the owning Specification rather than maintaining competing directory tables.

<a id="testing"></a>

## 9. testing

- Pull requests must pass formatting, lint, type checking, unit/API/security tests, minimum coverage, Bandit, dependency vulnerability audit, a clean PostgreSQL migration to head, and a reproducible package build. Integration tests require explicit infrastructure and never silently use a developer database.

- The whole-application coverage floor is 60%. It is a ratchet: releases may raise it as coverage grows, but must not lower it to accommodate regressions.

- Deployments run `deploy/smoke.sh` against staging before promotion. Smoke tests cover liveness, readiness, static Workspace delivery, and fail-closed admin authentication. Destructive migration downgrade and full backup restore are scheduled release rehearsals rather than per-commit CI operations.

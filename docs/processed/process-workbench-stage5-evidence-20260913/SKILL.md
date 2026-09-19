---
name: workbench-stage5-evidence-20260913
description: Workbench refactor stage 5 implementation evidence을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-13-workbench-stage5-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-13-workbench-stage5-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench refactor stage 5 implementation evidence

<a id="scope-and-prior-gate"></a>

## 1. Scope and prior gate

- This dated Processed note records the RF-600–604 and RF-508 implementation handoff. It does not replace the maintained Workbench specification, ADR-003/006/007, or independent Verification. Stage 4's final pass is recorded in the owning Stage 4 evidence and status documents with its exact Work/Verification run binding and request hash.

<a id="authored-implementation"></a>

## 2. Authored implementation

- `platform-core` now owns Workspace-scoped definition/release values, action-specific permissions,
  optimistic draft/archive/restore commands, immutable publication, queries, errors, and repository /
- validator ports without framework or database imports.
- `platform-adapters` validates persisted JSON through the generated v1 schema bundle, computes
  canonical schema/definition digests, and implements PostgreSQL CAS, row locks, transactional publish,
- idempotent receipt replay, successful-write audit, and tenant-scoped reads.
- Migration `0026` appends Workbench tables and permissions at the current `0025` head, forces
  Workspace RLS, constrains stored JSON and positive revisions, and rejects release update/delete with
- a database trigger.
- Target HTTP routes and the legacy authenticated/CSRF/RBAC mount use the same use cases. MCP read,
  preview, save, publish, and release tools use the same composition and intersect live RBAC with token
- scopes. Draft content is available only through preview authority; release reads use read authority.
- The React authoring route now loads an authenticated server draft, previews the exact in-memory
  draft, preserves changes on conflict/validation/network failure, disables duplicate saves/publishes,
- reuses an ambiguous publish request key, distinguishes unsaved draft state, and renders the latest immutable release separately.
- Focused gates now cover the actual MCPServer schema/error boundary, disposable PostgreSQL
  concurrency, stale writes, idempotent and conflicting publication, immutable release rows,
- failed-audit rollback and cross-tenant RLS, plus authenticated actual-server save, publish, reload, keyboard, theme, desktop and narrow authoring behavior without API interception.

<a id="verification-boundary-and-retained-limits"></a>

## 3. Verification boundary and retained limits

- Work did not run tests, type checks, lint, builds, servers, browser automation, migrations, or a PostgreSQL cluster. Independent Verification must run `scripts/verify-cloud-platform.sh` with the requested PostgreSQL 16.15 / pgvector 0.6.0 image and the established Workbench checks. The disposable gate owns clean migration-to-head, forced RLS, concurrency, transactional/immutable release, HTTP/MCP protocol, permission, and authenticated actual-server browser evidence.

- RF-605–607 remain independent substantial existing-domain/adapter/composition ports. Full standard feature ports, rollout/rollback observation, legacy removal, and remaining global baseline gates are not completed by this slice.

<a id="final-independent-verification"></a>

## 4. Final independent Verification

- Stage 5 received a final independent pass in Verification run `run-20260912T170015039441Z-0c47c5d5`, bound to verified Work run `run-20260912T165904566160Z-b2cd44e5` and original request SHA-256 `3c9c5d5c1add76e9c03830e08c350ba53f69840eba9c0ce701c0e890d59f8f6c`. The final matcher-only revision passed three consecutive unmodified runtime/editor Chromium gates (21 runtime and 3 editor tests before and after each web build) and `make workbench-check` (54 TypeScript and 17 Python tests plus format, lint, types, schema parity, code generation, compatibility, and dependency checks). The unaffected preceding independent evidence covered all six Python package builds, a fresh PostgreSQL 16.15/pgvector 0.6.0 migration through `0026`, three focused PostgreSQL concurrency/RLS/idempotency/immutability/transaction-failure tests, authenticated HTTP/MCP parity, and actual database-backed authoring E2E. This proves the Stage 5 implementation boundary; it does not prove deployment, production observation, or full legacy feature migration.

---
name: declarative-workbench-history
description: 선언형 Workbench 설계 이력을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/skills/design-platform/references/workbench-runtime.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 선언형 Workbench 설계 이력

- 고객 코드 작성이 승인되기 전의 설계입니다. 현재 요구사항을 대체하지 않습니다.

<a id="current-authority--code-based-structure-accepted-2026-09-15"></a>

## 1. Current authority — code-based structure accepted 2026-09-15

- Read [product-overview.md](../../skills/design-platform/SKILL.md#product-overview) and the [target structure](../../skills/rule-workbench-structure/SKILL.md#target-structure) first. Customer-authored code with shared assets and a public SDK supersedes the JSON-only restriction. The accepted owners are workbench-sdk (public API), workbench-build (isolated toolchain), workbench-runtime (host loading/rendering/bridge), and workbench-editor (authoring/preview). Worker dispatch and adapter-managed isolation are separate from build execution. Exact protocols, sandbox technology and file-level behavior require subsequent specifications. The Korean current decision is recorded in [product-overview.html](../../skills/design-platform/SKILL.md#product-overview).

<a id="legacy-declarative-design--migration-reference-only"></a>

## 2. Legacy declarative design — migration reference only

- The remaining sections describe the previous declarative model, not the new customer-code contract. Do not use their JSON-only, closed-tree-only, asset-composition-only or workspace-only ownership assumptions to override the latest Human decisions. Keep existing stored definitions and releases until an explicit migration maps them. Server authorization, credential secrecy, immutable history, bounded requests and stale-response rejection remain applicable principles; old schema fields, permission names and transaction details need explicit mapping, not automatic reuse.

- Customer Workbenches are data, not executable extensions. The JSON Schema source in `contracts/schemas/workbench/v1` is the first validation boundary. The runtime then resolves every referenced layout, icon, component, binding operation, and action through closed versioned registries. Standard and customer definitions use the same registry and renderer. An unknown ID, incompatible major version, invalid region, undeclared action, or malformed property produces a visible field-addressed diagnostic and never crashes the shared shell or silently substitutes another asset.

<a id="rendering-and-content"></a>

## 3. Rendering and content

- Only schema-valid closed trees are rendered. Registry descriptors own stable IDs,
  allowed regions, property and slot shapes, inputs, outputs, supported states, actions,
- accessibility, and provenance.
- Shared layouts and components receive content from their caller or a named preview
  fixture. Public layouts contain no product-specific sample records.
- Native definitions cannot contain executable expressions, imports, raw CSS or SVG,
  credentials, request headers, or arbitrary network destinations. External executable UI
- remains isolated behind the separately governed MCP App host.
- Runtime errors are recoverable states. Loading, empty, stale, and error remain distinct;
  a stale response may retain validated cached data while clearly showing that it is stale.

<a id="binding-operations"></a>

## 4. Binding operations

- The renderer receives an injected `BindingClient`; it does not import a server SDK or choose HTTP, MCP, or another transport. A binding references a named, versioned operation whose exact input and output fields are declared by the host. State mappings can read only closed dotted paths. Both request input and returned output are validated before use.

- Every request is scoped by user, organization, Workspace, Workbench, release, operation, and validated input. Replacement, context change, and unmount cancel pending work, and a generation guard rejects replies from transports that ignore cancellation. The bounded cache uses that complete scope and an operation-defined duration. Refresh bypasses cached data. Errors never turn malformed output into component input.

- The server remains the authorization authority. A browser scope key is isolation context, not evidence that the caller remains authorized.

<a id="actions-and-view-state"></a>

## 5. Actions and view state

- Definitions may invoke only declared `select`, `toggle`, `refresh`, `submit`, internal navigation, and dismissal actions supported by the originating component. Payloads are closed outputs from that component. Internal navigation receives a destination ID, never a URL. Dispatch rechecks the current context, bounds one in-flight invocation per action, and reports double submission or failure as recoverable state.

- View state version 1 contains controlled selection, tree expansion, sidebar visibility and width. Browser storage is bounded by the schema and keyed by user, organization, Workspace, Workbench, and release. Malformed values, another Workbench, stale selection IDs, and stale expanded IDs are removed. Release changes do not inherit incompatible state. Logout, account change, and context change must cancel runtime work and select the new scope before reading state.

<a id="authoring"></a>

## 6. Authoring

- The customer editor searches the same asset registry used by the renderer. It inserts, reorders, and removes only assets allowed in the selected region, exposes descriptor-backed properties and bindings, supports keyboard operation, and provides bounded undo and redo. Its preview renders the exact in-memory draft using the same validator and runtime.

- Serialization and import validate before replacing the current draft. Parse, validation, or transport failure retains the draft and identifies offending fields. Theme editing uses the server-authoritative `ThemeProfile` flow and previews the same resolved theme. Publishing uses the durable Workbench domain below; a local preview does not represent a publication.

<a id="definitions-releases-and-publication"></a>

## 7. Definitions, releases, and publication

- Customer `WorkbenchDefinition` records are Workspace-owned mutable aggregates. A definition has a stable UUID and key, `draft` or `archived` state, an optimistic positive revision, actor provenance, and an optional pointer to its latest release. Create and update accept only a complete validated v1 definition; the descriptor ID must match the stable key. Updates, archive, and restore compare the caller's expected revision. Archive is reversible retained state, not deletion: ordinary lists and draft reads hide archived definitions, while an explicitly authorized retained-data view may include them. Releases remain readable while their definition is archived. Physical retention and tenant deletion follow the platform security retention workflow.

- Code-owned standard descriptor IDs are reserved in platform-core and are rejected for customer create, update, and publish commands. Retained releases created before a reservation remain immutable and readable through retained-data APIs, but authorized task-list projections omit them so they cannot replace or make the standard registry entry unavailable.

- Publish revalidates the persisted draft and locks its definition revision in one PostgreSQL transaction. It appends one immutable `WorkbenchRelease` containing the exact canonical JSON snapshot, definition revision, monotonic release number, schema and asset versions, canonical schema and definition SHA-256 digests, publisher, and publication time; it then advances the definition's latest-release pointer and appends the success audit event. Validation, authorization, stale revision, archive state, digest mismatch, or transaction failure creates no partial release. Release rows reject update and delete at the database boundary. Publishing uses a Workspace-scoped request key and canonical command digest: an identical retry returns the original release, while reuse for another command fails as an idempotency conflict.

- Permissions are independent actions: `workbench.read` reads release projections and definition metadata, `workbench.preview` reads unpublished draft content, `workbench.create` and `workbench.update` edit drafts, `workbench.publish` publishes, and `workbench.archive` / `workbench.restore` change retained visibility. Every HTTP and MCP call derives organization, Workspace, user, effective RBAC, and token-scope intersection from authenticated server context. Payload data, browser visibility, definition JSON, and release IDs never establish scope. PostgreSQL RLS is forced on every Workbench table as defense in depth.

- HTTP and MCP are adapters over the same commands and queries. Inputs are closed and bounded; transports map the same validation, permission, not-found, stale-revision, archive, and idempotency errors to their protocols. Draft responses are no-store. Standard code-owned definitions use the same client registry and read projection but do not expose customer edit, archive, restore, or publish operations. Secret and connection references remain opaque IDs and are reauthorized by the binding operation; definitions never contain credentials, headers, raw URLs, or executable content.

---
name: saas-service-boundaries-20260911
description: SaaS service boundaries을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-11-saas-service-boundaries.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-11-saas-service-boundaries
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# SaaS service boundaries

<a id="decision"></a>

## 1. Decision

- Keep the application as a modular monolith while the product and tenant model are still evolving. HTTP and MCP are adapters; neither owns business rules, persistence commands, or transaction boundaries. A domain may be extracted to a separate process later only when its load, release cadence, or isolation needs justify the operational cost.

<a id="dependency-direction"></a>

## 2. Dependency direction

```text
HTTP / MCP / worker adapter
          |
          v
application use case
          |
          +----> domain service
          +----> domain repository
          +----> infrastructure port
```

- `app/router/` translates HTTP input and output.
- `app/mcp/` translates MCP tools and resources.
- `app/modules/<domain>/` owns use cases, authorization checks, state changes,
  and repository interfaces or implementations.
- `app/infrastructure/` owns brokers, object storage, email, encryption, and
  other external adapters.
- A request adapter may compose a service through a dependency or domain
  factory, but it must not issue SQL or call `commit()`/`rollback()`.

<a id="transaction-rules"></a>

## 3. Transaction rules

- A public mutation use case commits all authoritative records together.
- External effects happen only after the authoritative transaction commits.
- If broker publication fails after a durable Job is committed, recovery
  republishes the Job; it does not recreate the business operation.
- Domain services may expose an uncommitted preparation method only for another
  application service that deliberately composes a larger atomic use case.
- Tenant and Workspace authorization is rechecked at the service boundary and
  is never inferred from route parameters or queue payloads alone.

<a id="current-extraction-seams"></a>

## 4. Current extraction seams

- Agent execution: HTTP and MCP share `AgentExecutionService` and its canonical
  factory. Run and Job persistence share one transaction before publication.
- Organization: account provisioning, transactional HTTP commands, invitation
  delivery, and organization persistence helpers are separate from route code.
- OAuth callback: state ownership, tenant reauthorization, denial consumption,
  and provider completion live behind `OAuthCallbackService`.
- Planning, Workspace, Agent, Schedule, and Auth routes use public repository or
  service methods instead of reaching through another service's private session.

<a id="when-to-extract-a-service"></a>

## 5. When to extract a service

- Consider a process boundary only when there is measured evidence for at least one of these conditions:

- independently scaling worker or request load;
- a separate deployment or availability requirement;
- a materially stronger data or credential isolation requirement;
- an independently owned release lifecycle.

- Before extraction, require a stable API/event contract, idempotency behavior, an outbox or equivalent delivery guarantee, tenant identity propagation, observability, and an explicit data owner. Do not split solely because the application is expected to become SaaS.

<a id="enforcement"></a>

## 6. Enforcement

- `tests/test_architecture_boundaries.py` rejects SQL/session persistence and transaction calls in HTTP routers, and rejects cross-domain imports of private Workspace helpers. Add equivalent guards when another boundary becomes a repeated source of regressions.

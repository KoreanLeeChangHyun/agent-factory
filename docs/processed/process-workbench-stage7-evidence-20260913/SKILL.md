---
name: workbench-stage7-evidence-20260913
description: Workbench refactor stage 7 evidence을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-13-workbench-stage7-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-13-workbench-stage7-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench refactor stage 7 evidence

<a id="scope"></a>

## 1. Scope

- This dated Processed note records the authored identity and authorization dependency slice for RF-605–607 and RF-800. Maintained authentication, authorization, organization, database, security, and Workspace contracts remain authoritative. This Work evidence is not an independent pass record and does not complete organization, Workspace, or administrator UI porting.

<a id="authored-ownership-move"></a>

## 2. Authored ownership move

- `platform-core/identity` now owns immutable identity records, the canonical `Principal`, explicit
  clock/crypto/repository/settings ports, the full password/session/external identity/email
- verification/password reset/API-token lifecycle, structured core errors, and authorization scope/context/policy. Password reset retains all-session revocation and one-time tokens remain an atomic repository operation.
- `platform-core/organizations/permissions.py` is the single permission, default-role, and legacy
  token-alias catalog. Role validation and token scope expansion use core errors. The former
- application module is a compatible import only.
- `platform-adapters/identity` implements Argon2 verification and upgrade, HMAC digests, secure
  randomness, system time, Google/GitHub provider verification, deployed-table PostgreSQL identity
- persistence, transaction-local tenant context, active organization membership gating, live Workspace checks, and direct/team permission-source DTO projection. It imports neither `app.*` nor delivery implementations.
- `apps/api/.../composition/identity.py` constructs the same core services for the target API and
  transitional authenticated application. Its thin session adapter owns the unchanged HTTP cookie
- attributes. Existing dependency function identities, routes, CSRF, OAuth callback, HTTP error handlers, MCP consumers, and callers remain in place through thin aliases or DTO translation.
- No migration was added or rewritten: the adapter uses the deployed schema directly. No renderer,
  public URL, cookie, stored hash, token prefix, role ID, or OAuth flow was intentionally changed.

<a id="authored-verification-coverage"></a>

## 3. Authored verification coverage

- Pure core tests use deterministic clock/crypto and in-memory ports for generic credential failure,
  lockout, hash upgrade, session creation/resolution/logout, external login, email verification,
- one-time reset, all-session revocation, API-token create/list/revoke, scope subset denial, and legacy alias containment.
- The architecture guard now inspects static, dotted, `importlib.import_module`, and `__import__`
  imports. It rejects framework/database/provider/adapter/application imports from core and reverse
- application imports from the new identity adapters. The common Workbench test target now includes the owning core and adapter package unit suites.
- Existing root authentication characterization no longer asserts the removed ORM implementation
  mechanism; provider and HTTP/cookie behavior coverage remains.
- `tests/test_cloud_platform_integration.py` now exercises both production PostgreSQL identity
  repositories and target composition against the disposable PostgreSQL 16/pgvector database. Its
- Stage 7 matrix covers pre-existing credential/session rows, suspended and soft-deleted users, expired and revoked sessions, existing-user and new-user external identity provisioning, password-reset session revocation, concurrent one-time-token consumption, live membership/role/ Workspace changes, two-tenant isolation, transaction-local forced-RLS context, real HTTP login, and authenticated MCP token use.
- `tests/browser/workbench-documents-db.cjs` now obtains its production session through the rendered
  login page, enters the enabled Workbench Documents experience over real HTTP/PostgreSQL, logs out
- with the production CSRF contract, confirms `/api/auth/me` rejects the revoked session, and confirms protected Workbench navigation returns to login. The integration fixture also checks the corresponding persisted session row is revoked.

<a id="exact-independent-commands"></a>

## 4. Exact independent commands

- From the repository root, Verification can provision a labeled disposable `pgvector/pgvector:pg16` container, migrate it, create a `NOSUPERUSER NOBYPASSRLS` application role, run the production HTTP/MCP identity matrix and browser flow, and remove the container with:

```bash
CLOUD_VERIFY_PYTHON=.venv/bin/python bash scripts/verify-cloud-platform.sh
```

- With an independently migrated disposable PostgreSQL already available, the focused identity and browser-containing cases can instead be selected explicitly after setting the same admin and non-owner URLs used by that script:

```bash
AGENT_FACTORY_DATABASE_URL="$CLOUD_TEST_DATABASE_URL" .venv/bin/python -m pytest -q \
  tests/test_cloud_platform_integration.py::test_identity_postgres_http_mcp_lifecycle_and_current_authority \
  tests/test_cloud_platform_integration.py::test_authenticated_workbench_authoring_with_real_postgres_and_http
```

<a id="verification-handoff-and-limitations"></a>

## 5. Verification handoff and limitations

- Work did not execute tests, linters, type checks, builds, browsers, servers, migrations, or PostgreSQL, as required by the Work boundary. Independent Verification must execute the authored fresh forced-RLS PostgreSQL matrix and all remaining acceptance gates from the delegated request, including package/offline installation, focused security checks, and relevant legacy regressions. Real OAuth provider credentials/network login, container image execution, deployment, rollout observation, and legacy removal remain unproved.

<a id="final-independent-decision"></a>

## 6. Final independent decision

- Independent Verification run `run-20260912T210629133865Z-53fef65b` passed the final Stage 7 Work run `run-20260912T210518583300Z-a7174acc`, bound to original-request SHA-256 `280f3444bf846a686f1c56bcf613d1bd14d7927ddfc7926580f979b7afb05002`, with no remaining findings. The final evidence included `make workbench-check` (61 TypeScript and 33 Python tests plus format, lint, types, contracts, and dependency gates), the four personal-Workspace cases, the fresh PostgreSQL identity HTTP/MCP lifecycle matrix, and two independent fresh-database production browser passes. Each database used PostgreSQL 16.15 with pgvector 0.6 and a `NOSUPERUSER NOBYPASSRLS` application role migrated through `0026`. The browser passes covered rendered login, persisted Workbench/Documents authoring and conflict handling, both rollback directions, logout, stored session revocation, HTTP 401, and login redirect.

- This decision closes only the Stage 7 identity/authorization slice. It does not establish full RF-605–607 or RF-800 completion, complete remaining domains or administrator/standard UI, prove full Documents parity, workers, the MCP App case gate, deployment, observation, or removal.

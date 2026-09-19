---
name: workbench-stage9-evidence-20260913
description: Workbench refactor Stage 9 Work evidence을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-13-workbench-stage9-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-13-workbench-stage9-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench refactor Stage 9 Work evidence

<a id="scope-and-authority"></a>

## 1. Scope and authority

- This dated Processed note records the authored platform-administration backend port. The maintained admin, authentication, authorization, organization-management, Workspaces, workers, integrations, database, observability, and security specifications remain authoritative. This Work run did not replace the established renderer or claim the remaining standard React administration Workbench.

- Stage 8's final security closure is recorded in `2026-09-13-workbench-stage8-evidence.md`: Verification run `run-20260912T231126169506Z-9ecd224c` passed with no findings against recovery Work `run-20260912T230625862522Z-db8d383e` and request hash `3485b4a5d535a92e4ee51f272bb2f68bb838ac33a66ad2615690d3e116949240`.

<a id="source-ownership"></a>

## 2. Source ownership

| Concern | New authority | Deployed adapter/consumer |
| --- | --- | --- |
| Active platform administrator and safe dashboard/flags/runtime | `platform-core/administration` | typed PostgreSQL adapter plus immutable API composition settings |
| User status and session lifecycle | `platform-core/identity/administration.py` | deployed `users` and `auth_sessions` tables |
| Additive organization/Workspace owners | `platform-core/{organizations,workspaces}/administration.py` | deployed active membership and stable system-role identities |
| Durable Job administration | `platform-core/executions/administration.py` | row-locked Job/event updates in the PostgreSQL adapter |
| Connection health/disconnect | `platform-core/connections/administration.py` | safe projection and credential/key/cursor removal |
| Immutable audit query | `platform-core/audit/administration.py` | bounded read-only deployed audit projection |
| API composition | `apps/api/.../composition/admin.py` | existing HTTP presenters and route identities |

- `app/modules/admin/repository.py` now retains only the request-scoped session constructor identity. `app/modules/admin/service.py` translates the established route surface to the target application. It contains no SQL, Job transition decision, feature rule policy, audit query, version lookup, or settings access beyond copying the four allowlisted runtime fields into immutable composition.

<a id="authority-and-transaction-behavior"></a>

## 3. Authority and transaction behavior

- The adapter clears transaction-local tenant scopes and administrator state before checking the
  current user row, while retaining only the authenticated user ID required by user-self RLS. It
- enables cross-tenant RLS only for a live, non-deleted, active user whose deployed `is_platform_admin` value is true. The core independently rejects an absent, tenant-only, or unestablished principal. Commit/rollback ends the local settings so pooled reuse cannot inherit administrator context.
- User mutations increment the deployed revision. Self-suspension/deactivation is rejected before
  persistence, and session revocation first requires the target user to exist.
- Owner grants retain all prior owners. Workspace recovery also restores an active organization
  membership without demoting an existing organization role, then upserts the Workspace owner role.
- Job cancellation and retry lock the durable row. Queued/retry become cancelled, running becomes
  cancel-requested, terminal cancellation conflicts, and only failed/dead/cancelled retry. Retry
- clears attempt, next-attempt, queue-task, start/finish/dead-letter, and error state while retaining the authoritative Job identity/payload/result. Each accepted transition appends a Job event in the same transaction; commit failures roll back both.
- Connection responses select only allowlisted fields. Disconnect clears encrypted credentials,
  key version, and cursor, changes status, and increments revision atomically.
- Feature flag keys, descriptions, rule names, identifier shapes, and rollout cardinality are
  bounded in core. `react-workbench` still requires both the global switch and an explicit
- `workspaceIds` match; the current production entry and selection callers now use the target composition and fail closed to legacy.
- Runtime output comes from immutable allowlisted settings/version values plus adapter migration I/O.
  Audit administration is a bounded immutable read and does not replace the established best-effort
- request audit writer.

<a id="authored-acceptance"></a>

## 4. Authored acceptance

- Framework-free package acceptance covers unestablished and unauthorized calls, current-admin self-lockout, session revocation, cancel/retry state matrices, conflict rollback, and bounded feature validation. The existing root admin tests retain route/assets/dependency compatibility and now call the core-owned self-lockout use case.

- The disposable cloud-platform acceptance adds a real session-authenticated HTTP case for every listed admin query and mutation. It provisions a separate active administrator, tenant owner/member, ordinary subject, expired/revoked sessions, controlled connection/Job/audit fixtures, and validates CSRF, bearer/header non-escalation, owner retention, active membership recovery, row-locked Job results, retry resets, secret removal, actual Workbench flag selection, immutable safe audit output, and post-admin non-tenant denial under the NOSUPERUSER/NOBYPASSRLS application role. It uses the existing exact fresh-database fixture contract and no live provider or queue effect.

- Independent Verification must run the new package/core and root admin cases, the complete disposable PostgreSQL case through deployed head, `tests/browser/admin-assets.cjs`, applicable identity, organization, Workspace, scheduling, integration, audit, API, shadow-route, and production browser regressions, `make workbench-check`, target and legacy type checks, static/dynamic dependency guards, scoped Ruff/Bandit without ignores, offline wheels, and the installed-resource probe. Root-wide pre-existing formatting drift remains a later global-gate limitation and must not be reported as a successful `make check`.

<a id="work-boundary-and-remaining-work"></a>

## 5. Work boundary and remaining work

- Work did not run tests, lint, type checks, builds, servers, browsers, migrations, PostgreSQL, package installation, or security scanners. It did not send queue/provider traffic, alter a deployed database, rewrite migration history, deploy, commit, or remove legacy data. Independent Verification must decide acceptance. The standard React administration UI, full scheduler/worker port, and the remaining domains/RF-800 UI work remain subsequent slices.

<a id="first-verification-revision"></a>

## 6. First Verification revision

- Verification run `run-20260912T233446740478Z-1a70881f` failed with four bounded findings. Revision Work run `run-20260912T233914631876Z-22bf35e9` addresses them as follows:

- `stage9-admin-rls-revalidation`: administrator revalidation now establishes only the
  authenticated current-user ID with tenant scopes empty and administrator mode false. The
- user-self RLS policy can therefore expose exactly that row; cross-tenant mode is enabled only after its live active administrator value is confirmed.
- `stage9-workbench-ruff`: reported modern-typing, import ordering, sorted export, and direct row
  mapping findings are corrected across the changed target sources and tests.
- `stage9-target-mypy`: dashboard counts now pass through an explicit integer type guard before
  constructing the typed projection.
- `stage9-bandit-b608`: Job updates now select one of three complete static SQL statements for
  retry, running cancellation, or immediate cancellation. No runtime SQL fragment concatenation or
- warning suppression remains.

- These are authored corrections only. Independent Verification must rerun the fresh forced-RLS administrator HTTP case, complete Workbench gate, target type check, and unchanged scoped Bandit command before recording acceptance.

<a id="second-verification-revision"></a>

## 7. Second Verification revision

- Verification run `run-20260912T234301326126Z-93a98b1f` confirmed the forced-RLS administrator repair with fresh PostgreSQL 16/pgvector and a NOSUPERUSER/NOBYPASSRLS application role. It also confirmed 45 focused admin tests, target mypy across 80 files, scoped Bandit with no findings, legacy mypy across 173 files, the admin-assets browser case, all five JavaScript package suites (61 tests), and 75 Python package/architecture tests. The Workbench gate stopped only on the remaining `stage9-workbench-ruff` RUF022 ordering finding in the organization package exports.

- Revision Work run `run-20260912T234512862541Z-53e388aa` places `INVITATION_LIFETIME` before `AdminOrganization` according to Ruff's case-sensitive required ordering. This is an authored correction only; independent Verification must rerun `make workbench-check` through completion before recording Stage 9 acceptance.

<a id="third-verification-revision"></a>

## 8. Third Verification revision

- Verification run `run-20260912T234625165380Z-ff0d0149` confirmed the complete Workbench gate, including 61 JavaScript and 75 Python package/architecture tests, plus the scoped Bandit, offline wheel, installed-resource, and previously established forced-RLS PostgreSQL evidence. Its applicable legacy regression set found only `stage9-shadow-route-regression`: the shadow-route characterization still passed a legacy `session.get`-only double through the new target rollout composition boundary.

- Revision Work run `run-20260912T234949674533Z-b60e000e` replaces that obsolete persistence double with a bounded asynchronous `react_workbench_rollout` fake. The characterization retains assertions for the exact session, organization and Workspace binding, enabled deep-link state, and fail-closed legacy fallback. Production composition and adapter behavior are unchanged. This is an authored correction only; independent Verification must rerun the shadow-route and applicable regression set before recording Stage 9 acceptance.

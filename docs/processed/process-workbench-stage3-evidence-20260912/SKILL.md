---
name: workbench-stage3-evidence-20260912
description: Workbench refactor stage 3 implementation evidence을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-12-workbench-stage3-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-12-workbench-stage3-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench refactor stage 3 implementation evidence

<a id="scope"></a>

## 1. Scope

- This dated Processed note records the RF-400–405 implementation slice. It does not replace the maintained ThemeProfile specification or ADR-006/010. Work generated contracts and refreshed the dependency lock as implementation steps, but did not run tests, builds, checks, servers, migrations, PostgreSQL, or browser automation.

<a id="implemented-vertical-slice"></a>

## 2. Implemented vertical slice

- `platform-core/appearance` owns the framework-independent profile, revision-zero
  fallback, repository/validator ports, and get/save use cases.
- `platform-adapters/appearance` owns final-palette validation and the SQLAlchemy
  PostgreSQL compare-and-set adapter. Revision-zero insert uses `ON CONFLICT DO NOTHING`;
- later updates match the observed revision and monotonically increment it. Conflicts return the current server profile. Successful writes append revision-only audit data, and audit failure cannot roll back an already committed theme.
- Migration `0025` appends a forced-RLS user profile table with closed JSONB override
  keys and payload bounds. It does not rewrite the existing migration chain.
- The target API route accepts no owner ID, derives the owner from the authenticated
  principal, requires CSRF for writes, sends no-store responses, distinguishes invalid
- profiles from revision conflicts, and is reachable through a thin legacy composition mount at `/api/appearance/theme-profile`.
- The design system owns matching semantic resolution, contrast rules, density and
  reduced-motion application, and the keyboard-native Theme editor. Only four mapped CSS
- custom properties can be set; no raw CSS, URL, markup, SVG, or component style is used.
- The React web bootstrap resolves authentication before consulting the versioned
  user/organization/Workspace cache, validates owner and schema, applies cache only as an
- initial optimization, then reconciles from the server. It cancels stale reads, tolerates storage failure, keeps unsaved intent on errors/conflicts, and offers server recovery.

<a id="verification-handoff-and-retained-boundaries"></a>

## 3. Verification handoff and retained boundaries

- `scripts/verify-theme-profiles.sh` first detects a compatible local PostgreSQL/pgvector installation and accepts only explicit disposable URLs for it; otherwise it can create a labelled disposable pgvector container. It upgrades to head and runs focused domain/API/ RLS/concurrency checks. Independent Verification must additionally run contract parity, package gates, the existing affected Workbench checks/build, and browser coverage for contrast, keyboard editing, reload, separate users and storage failure.

- The current vanilla Workspace shell is retained and is not described as theme-complete. Its product-surface migration remains tracked under RF-800–804 and staged path transition under RF-1004. MCP App read-only theme context remains RF-903. The unrelated full-refactor, legacy Ruff/packaging, source-inventory, runtime-image and deployment limitations remain.

<a id="failed-verification-revision"></a>

## 4. Failed-Verification revision

- The revision following Verification run `run-20260912T123602658947Z-d498b0b2` addresses VF-001 through VF-004 without expanding the Stage 3 product scope:

- Appearance route dependency annotations now evaluate at router construction instead
  of leaving closure-local dependency names for FastAPI to treat as query parameters.
- The mounted-route test covers unauthenticated rejection, CSRF rejection, validation, default read, successful save, owner identity, no-store response and conflict.
- Changed Python sources use the required import forms/order and f-string syntax. The
  PostgreSQL adapter validates and narrows JSONB override mappings before conversion.
- The React bootstrap now accepts the complete owning application scope and resets to a
  validated neutral fallback in a layout effect on every user, organization or Workspace
- transition. `AuthenticatedThemeRoot` obtains the user from `/api/auth/me`, tracks the owning shell's context-change events, invalidates auth on auth-change, aborts stale requests and supplies the resulting scope. Unit coverage includes same-document scope transitions, stale responses and unavailable browser storage.
- The browser scenario uses keyboard focus, arrow/space/enter operation and visible-focus
  assertions. It restores the first user's saved server profile in a second browser
- context, retains a distinct-user context, and exercises same-document organization, Workspace and account transitions.

- Work formatted these correction sources but did not execute tests, lint, type checks, builds, servers, database operations or browser automation. All corrected behavior and the complete mandatory gates remain pending independent Verification.

<a id="second-failed-verification-revision"></a>

## 5. Second failed-Verification revision

- The revision following Verification run `run-20260912T125506926708Z-c2730948` addresses VF-005 through VF-007:

- The unowned document event/data-attribute channel was removed. A typed
  `WorkbenchContextProvider` is now the production composition owner for authenticated
- user, organization and Workspace selection. `AuthenticatedThemeRoot` consumes that provider directly, and its transition test follows the same provider/root composition mounted by `main.tsx`. The test holds the next server response to assert the validated anonymous fallback before both context and account reconciliation complete.
- The disposable verification setup now grants its resolved test identity the same
  schema, table and sequence privileges as the application role, including the tables
- referenced by existing audit RLS policies. The integration test asserts exact revision-only audit events for ordinary saves and the first-write race winner.
- Audit append has a narrow overridable operation beneath the existing best-effort
  boundary. A deliberate failure test confirms the committed theme remains readable and
- no audit event is falsely recorded. Two independent sessions now execute the required concurrent revision-zero race and assert one revision-1 save plus one conflict.
- PostgreSQL fixture emails include their generated user UUIDs, so repeated invocations
  against the same explicit disposable database do not collide with earlier test-owned
- identities.

- Work did not execute the revised tests, verification script, checks, builds, services, database operations or browser automation. Independent Verification remains responsible for demonstrating repeat execution and the complete mandatory gates.

<a id="third-failed-verification-revision"></a>

## 6. Third failed-Verification revision

- The revision following Verification run `run-20260912T130937740937Z-f5a31fec` addresses VF-008. The concurrent first-save audit assertion now reads the native JSON metadata rows and compares their decoded values exactly. This avoids the unsupported PostgreSQL `json = jsonb` operation while retaining the assertion that the race produces exactly one revision-only audit event.

- Work did not execute the revised integration test or verification script. Independent Verification remains responsible for running the maintained gate twice against the same explicitly disposable database.

<a id="final-independent-verification"></a>

## 7. Final independent Verification

- Verification run `run-20260912T131345046578Z-e5de8b0c` passed the final Stage 3 Work run `run-20260912T131224295882Z-f483212c` with no findings. It passed `make workbench-check` (30 TypeScript and 15 Python tests), all web and Python builds, a clean migration from base through `0025`, and `make verify-theme-profiles` twice on the same disposable PostgreSQL 16 plus pgvector database. The database evidence included forced user RLS, concurrent first saves, revision-only audit records, and audit failure without profile rollback. Chromium covered keyboard focus and editing, reduced motion, save/reload/conflict, same-user second-context restoration, distinct-user isolation, and typed organization/Workspace/account context transitions. The database was disposable and stopped afterward; this evidence does not establish legacy vanilla theme migration, deployment, or production rollout.

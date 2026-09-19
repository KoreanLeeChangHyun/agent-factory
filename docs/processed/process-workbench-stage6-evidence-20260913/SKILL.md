---
name: workbench-stage6-evidence-20260913
description: Workbench refactor stage 6 implementation evidence을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-13-workbench-stage6-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-13-workbench-stage6-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench refactor stage 6 implementation evidence

<a id="scope"></a>

## 1. Scope

- This dated Processed note records the RF-700–705 Work handoff. Maintained behavior remains owned by `info-platform`/`design-platform`/`rule-platform`, UI conventions, ADR-004/009/010, and the target-structure contract. It is not an independent pass record and does not claim rollout, deployment, or legacy removal.

<a id="authored-vertical-slice"></a>

## 2. Authored vertical slice

- The existing authenticated FastAPI application serves the built Vite manifest and hashed assets at
  `/workbench/`, falls back to the application entry for deep links, applies configured `root_path`,
- redirects unauthenticated requests through the existing login path, returns immutable asset cache headers, and reports a bounded `workbench_build_missing` diagnostic. The Python wheel and immutable container build copy the same production web output; Vite proxying is not part of that route.
- `packages/design-system` owns the shared **작업 목록 | 사이드바 | 패널** surfaces, tokens,
  responsive geometry, and pointer/keyboard resize primitive. The React shell owns product task
- selection, sidebar visibility and 180–520 px state, and versioned user/organization/Workspace state. Context replacement aborts in-flight selection, published-release, Document, revision, and content reads and applies generation guards before state updates.
- A code-owned standard Documents descriptor and authorized server-projected latest customer releases
  enter the existing `WorkbenchRegistry`. The platform core rejects the reserved `documents` ID at
- create, update, and publish; the HTTP projection and browser registry omit retained historical collisions without removing the standard entry. unpublished drafts, archived definition projections, and releases outside the server-authorized Workspace query do not enter the task list. Standard Documents remains non-editable through customer authoring operations.
- The established `react-workbench` platform-admin flag is interpreted as globally enabled plus an
  explicit `rules.workspaceIds` allowlist. Missing, malformed, disabled, or unmatched rules resolve to
- legacy. The established authenticated legacy Workspace selection calls that server projection before entering a Workspace and routes enabled selections into React. React writes a scope-bound one-shot rollback marker before returning to legacy, so the same selection can remain legacy immediately and return to React on the next explicit Workspace entry without changing server authority.
- The Documents slice calls the existing authenticated Workspace Document HTTP API. It provides a real
  metadata-path hierarchy, selection, current/older revision reads, safe text/JSON/image rendering,
- isolated paired-package preview, safe download fallback for unsupported binary media, Original creation, title CAS updates, Original Markdown revisions, and stale-conflict recovery that refreshes the server record while preserving unsaved title/content input. Server permissions control every read and mutation; UI visibility is only a presentation decision.
- Documents navigation uses a validated versioned key containing authenticated user, organization,
  Workspace, Workbench, and release identities. Selection and folder expansion are restored only when
- compatible, while identity/context replacement unmounts the slice and cancels old requests.

<a id="existing-documents-boundary-inventory"></a>

## 3. Existing Documents boundary inventory

| Existing behavior at this boundary                      | Representative slice evidence                                                                                        | RF-801 remainder                                                                                   |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Workspace-scoped list/get and `metadata.path` hierarchy | Actual list/get APIs, stable UUID selection, path folders                                                            | Full Original table/search views, invalid legacy-path presentation matrix                          |
| Metadata creation/update with optimistic revision       | Original create and title CAS; conflict reload retains draft                                                         | Complete metadata/status/archive/delete/move workflows and all dialogs                             |
| Immutable content revisions and authenticated download  | Original text revision, revision list/select/read                                                                    | Full upload media/size UX, download/export controls, checksum/provenance presentation              |
| Type authority                                          | Original mutation; Processed/Specification shown read-only                                                           | Complete Processed workflows and paired Specification authoring/publication flows                  |
| Preview security                                        | Text/JSON use text nodes, images use bounded Blob URLs, package preview uses opaque sandbox, other binaries download | PDF.js controls/limits, DOCX/ZIP file inventories, all package navigation/error states             |
| Legacy editor interaction surface                       | Basic tree keyboard via shared asset, selection and document detail                                                  | Multi-select/context menus, preview/pinned tabs, four-way splits, DND, F6/Ctrl shortcuts, resizers |
| Search/knowledge/delivery                               | No synthetic search or knowledge database was added                                                                  | Lexical/vector search, provenance graph, package member/download/delivery and knowledge port       |

- The representative slice therefore proves only the literal RF-700–705 boundary after independent Verification. RF-801 remains the complete Documents/search/knowledge/editor/delivery parity milestone; RF-605–607 remain the framework-independent domain, external-adapter, and composition ports. Existing legacy routes and assets remain required for rollback and were not deleted.

<a id="authored-verification-handoff"></a>

## 4. Authored Verification handoff

- `tests/test_workbench_shadow_route.py` covers fail-closed Workspace selection, authenticated deep-link
  fallback, immutable hashed-asset delivery, and missing-build diagnostics.
- `apps/web/src/registry/WorkbenchRegistry.test.ts` covers the standard projection and retained-collision
  fallback. The HTTP case covers reserved-ID authoring rejection and a non-reserved published projection.
- `tests/browser/workbench-shell.cjs` covers late A→B→A Document responses plus account-isolated tree
  expansion across the shared shell and is part of the bounded runtime/browser runner.
- The existing disposable PostgreSQL integration now enables the exact test Workspace, archives the
  colliding authoring fixture through the real use case, and invokes
- `tests/browser/workbench-documents-db.cjs` against the production-built FastAPI shadow route. That browser case authors and reloads a persisted Document revision, exercises a real stale update while retaining edits, checks revision preview, task/shell keyboard use, 180/268/520 and 390 px geometry, and light/high-contrast application without API interception.
- `scripts/verify-cloud-platform.sh` builds the production web bundle before its existing fresh migration,
  PostgreSQL/API/MCP/browser gates. Verification should also run `make workbench-check` and the focused
- legacy Documents/security/browser regressions named in the delegated request.
- `scripts/verify-workbench-runtime.sh` and both browser files share the canonical `/workbench/`
  application base. Readiness and nested runtime/editor/authoring paths append to that base, while the
- shell uses it directly. Initial shell failure diagnostics are bounded to URL, response status/content type, short DOM text, page errors, and the latest request URLs.

<a id="verification-finding-revision"></a>

## 5. Verification-finding revision

- This Work revision addresses RF6-V001 through RF6-V006 in authored source and tests. It does not claim that the revised gates pass; independent Verification remains responsible for executing them and for reporting any revision-caused regressions.

- The follow-up Work revision addresses RF6-V007 through RF6-V009 by applying Ruff's required import and `__all__` ordering, using the canonical Vite application base with bounded browser diagnostics, and making the focused repository fixture advance the latest-release pointer as the PostgreSQL publication transaction does. These corrections likewise remain subject to independent Verification.

- The subsequent Work revision addresses RF6-V010 by giving the disposable PostgreSQL authoring fixture a non-reserved customer key and matching descriptor, while leaving the code-owned standard Documents entry available for the browser registry and persistence assertions.

- The next Work revision addresses RF6-V011 by deriving both the Vite readiness route and the authoring browser URL from the canonical `/workbench` application base. Readiness failures now retain bounded HTTP response and Vite process output diagnostics for independent Verification.

- The diagnostic Work revision for RF6-V012 adds bounded production Documents bootstrap evidence for the initial navigation response and body, final URL, page and console errors, failed and recent requests, recent response statuses, and relevant root/DOM state. The observed bootstrap cause remains for independent Verification to establish before a behavioral correction can be made responsibly.

- The RF6-V013 Work revision replaces browser-time Ajv schema compilation with checked-in standalone validators generated from the same contract schemas. The production Documents flow now explicitly requires both the strict `script-src 'self'` header and a mounted React root before continuing.

- The RF6-V014 and RF6-V015 Work revision excludes only the machine-generated standalone validator from ESLint while retaining lint coverage for its generator, gives that generator explicit Node globals, and restores the production browser to a desktop viewport before selecting the legacy Workspace. The same flow continues from legacy back to React and checks the persisted database-backed revision.

- The follow-up RF6-V015 Work revision uses the visible legacy `작업공간 목록` control before locating the authorized Workspace, expands its containing explorer group when collapsed, and then continues through the existing return-to-React, persisted-revision, and browser-error assertions.

- The RF6-V016 and RF6-V017 Work revision prevents a late initial ThemeProfile response from replacing a newer local preview, adds a controlled deferred-response regression, and synchronizes the production theme choices with the explicit loaded status. The browser now asserts the intended stale-update URL and 409 response, excludes only its exact Chromium console diagnostic, and rejects other page, console, request, or non-success response errors.

- The RF6-V018 Work revision associates request failures with the two deliberate Document reloads and the React-to-legacy and legacy-to-React transitions. It permits only same-origin `net::ERR_ABORTED` revision-content requests during reload/legacy entry and the exact Workspace-visits request during the return to React; every other request failure remains an acceptance failure.

- The RF6-V019 Work revision builds the isolated wheel source fixture from the same private UI catalog allowlist as the packaging hook. The fixture therefore includes each maintained catalog input while excluding dependency and cache content outside that policy, and the archive checks require every catalog file to remain byte-identical alongside the existing legacy and React resource assertions.

- The RF6-V020 Work revision builds the declared local API, core, adapter, and contract distributions as wheels without dependency, build-isolation, or index resolution, then extracts those wheels beside the root wheel for the isolated installed-resource probe. The probe continues to expose only packaged contents through its explicit isolated path; it does not add repository source directories.

- Work did not execute tests, linters, type checks, builds, browsers, servers, migrations, or PostgreSQL. Only write-mode formatters were applied to revised files. The rows RF-700–705 remain partial until independent Verification establishes the exact production route, DB, authorization, isolation, rollback, browser, package, and regression evidence.

<a id="final-independent-verification"></a>

## 6. Final independent Verification

- Verification run `run-20260912T191355170132Z-819b062c` passed the final Work run `run-20260912T191246711239Z-02e7cb7a` for original request SHA-256 `e394b08144a7801ee381e7562fff600225ed87b06123ae13b7d9aaeff3a7bdd8`, with no remaining findings. The independent evidence establishes RF-700–705 at this bounded stage:

- `make workbench-check` passed 61 TypeScript and 17 Python checks, and the runtime/editor runner
  passed 21 runtime and three editor tests plus its Chromium shell, authoring, responsive, theme,
- keyboard, and restoration gate.
- Offline builds of the contracts, core, adapters, API, and root wheels passed the isolated installed
  resource checks, including byte-identical legacy resources, catalog inputs, hashed React assets,
- and the Vite manifest.
- A fresh PostgreSQL 16.15/pgvector 0.6 database migrated through `0026`. A
  NOSUPERUSER/NOBYPASSRLS application role exercised authenticated production HTTP, forced RLS,
- persisted Documents authoring and revision recovery, exact stale-409 recovery, strict CSP, the canonical `/workbench/` base, 180/268/520 px and 390 px layouts, themes, and immediate React-to-legacy-to-React rollback with visible legacy navigation.
- Sixty-four related API/authentication/authorization/legacy Documents/delivery regressions passed.

- This evidence does not establish a real external OAuth login, deployment or rollout observation, full RF-801 Documents/search/knowledge parity, legacy removal, or RF-605–607 ports. The source inventory case requiring the external sibling `skills/document` checkout also remains a fixture limitation. Those items remain explicitly open.

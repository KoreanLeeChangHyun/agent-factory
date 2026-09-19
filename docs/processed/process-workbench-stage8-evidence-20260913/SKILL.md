---
name: workbench-stage8-evidence-20260913
description: Workbench refactor stage 8 Work evidence을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-13-workbench-stage8-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-13-workbench-stage8-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench refactor stage 8 Work evidence

<a id="scope-and-authority"></a>

## 1. Scope and authority

- This dated Processed note records the authored organization and Workspace/account-discovery backend port. Maintained organization-management, Workspace, authorization, authentication, database, security, and observability specifications remain authoritative. The Stage 8 implementation is authored only until independent Verification decides its exact Work run.

- The initial Work run `run-20260912T211245819903Z-759878b5` ended by timeout and its two managed continuations ended without result files. Recovery Work run `run-20260912T215124345855Z-38887587` inspected and continued the handed-off shared-checkout state; the earlier runtime records remain unchanged and are not acceptance evidence.

<a id="source-ownership"></a>

## 2. Source ownership

| Concern | New owner | Transitional consumer |
| --- | --- | --- |
| Organization records, predicates, commands, queries, ports | `packages/platform-core/.../organizations` | Legacy HTTP dependency identity translates requests to target use cases |
| Workspace/account discovery, groups, repository identity | `packages/platform-core/.../workspaces` | `app/modules/workspace/service.py` is a construction/translation bridge |
| Deployed organization/Workspace tables and audit transaction | `packages/platform-adapters/.../{organizations,workspaces}/postgres.py` | Existing migrations and database identities remain unchanged |
| SMTP delivery | `packages/platform-adapters/.../email.py` | `app/infrastructure/email.py` supplies immutable legacy settings only |
| API/MCP construction | `apps/api/.../composition/{organizations,workspaces}.py` | Existing account discovery, organization, Workspace and MCP discovery callers use target composition |

- Core code contains immutable DTOs, permission/delegation and final-owner decisions, role and invitation predicates, explicit repository/unit-of-work/time/token/email ports, Workspace/group visibility decisions, and canonical repository identity. It imports no SQLAlchemy, FastAPI, Pydantic, Settings, ORM, legacy `app`, or adapter package. Adapters use explicit SQL against the deployed tables and import no legacy application or transport code. No migration was added or rewritten.

<a id="callable-map"></a>

## 3. Callable map

| Old callable | Target callable |
| --- | --- |
| `OrganizationService.create/update/delete_organization` | `OrganizationUseCases.create/update/delete` |
| `overview/members/detail/roles/teams/invitations` | typed `OrganizationUseCases` queries through `OrganizationRepository` projections |
| `update_member/transfer/set_workspace_member` | `OrganizationUseCases.update_member/transfer/set_workspace_member` |
| `write_role/delete_role` | `OrganizationUseCases.write_role/delete_role` |
| `write_team/delete_team/set_team_member/set_team_workspace` | `OrganizationUseCases.write_team/delete_team/mutate_team_member/set_team_workspace` |
| `invite/resend_invitation/cancel_invitation/accept_invitation` | `OrganizationUseCases.invite/resend_invitation/cancel_invitation/accept` |
| `workspace_options/events` | `OrganizationUseCases.workspace_options/audit_events` |
| `AccountService.list_organizations/create_personal_workspace` | `WorkspaceUseCases.list_organizations/create_personal_workspace` |
| `WorkspaceService.list/recent/get/create/update/deactivate/record_visit` | corresponding `WorkspaceUseCases` methods |
| Workspace group methods | `list_groups/create_group/update_group/assign_group` |
| Workspace repository and usage methods | `register_repository/list_repositories/delete_repository/usage` |
| `EmailSender` delivery methods | `SMTPEmailSender`, through the settings-only compatibility subclass |

- Direct Workspace membership routes through the same target organization command service so delegation and last-owner handling remain a single authority. Account discovery, Workspace lifecycle/group/repository operations, and organization mutations/invitations construct target use cases. The legacy organization/account/Workspace service and repository modules retain only construction, translation, dependency-override identity, and session-holder behavior; deployed SQL and application decisions no longer remain alongside the target owners. Read presenters and dependency identities remain the bounded compatibility surface pending independent acceptance and their final replacement checkpoint.

<a id="transaction-boundaries"></a>

## 4. Transaction boundaries

- Organization mutation loads the organization with `FOR UPDATE`, evaluates current and proposed
  roles/grants in core, writes the mutation and immutable audit event, then commits once. A commit
- failure rolls back. Audit query is read-only and capped at 200 immutable rows.
- Invitation creation/resend persists the HMAC digest and audit event before commit. SMTP delivery
  occurs only after commit; a controlled delivery failure returns the structured retryable error
- without discarding the invitation. Links keep tokens in the fragment.
- Personal first use obtains a transaction advisory lock, provisions at most one personal
  organization/owner, restores non-elevated organization RLS context, creates the Workspace/owner,
- and commits once. External identity creation does not create a Workspace.
- Workspace, visit, group, assignment, and repository mutations commit once through the target
  application boundary. CAS updates return the existing structured conflict. Repository uniqueness
- remains the deployed `(workspace_id, canonical_location)` constraint.

<a id="authored-acceptance-matrix"></a>

## 5. Authored acceptance matrix

| Layer | Authored coverage | Independent evidence required |
| --- | --- | --- |
| Core | slug/email normalization, delegation subset and owner-only roles, immutable/in-use roles, final organization/Workspace owner, removed-member reinvite, invitation expiry/email/inviter revalidation, deterministic transaction/audit/delivery order, group uniqueness, HTTPS/SSH/local repository identity, serialized personal first use | Run package format/lint/types/tests |
| Dependency | Static/dynamic import guard now applies to the complete adapter tree and core tree | Run dependency gate without ignores |
| Adapter/API | Deployed-table DTO mappings, typed organization query projections, row/advisory locks, CAS, soft delete, visibility-filtered visits/groups, HTTPS/SSH/Git and local-adapter repository identities, atomic audit, SMTP fragment secrecy, target account composition and Workspace/MCP bridges | Run controlled SMTP sink plus legacy/root API cases |
| PostgreSQL | Existing organization and personal integration tests remain the named authoritative cases | Fresh PostgreSQL 16/pgvector through `0026`, forced-RLS non-owner URLs, concurrency and immutable-audit rejection |
| HTTP/MCP/browser | Existing routes and renderer contracts are retained; account discovery and MCP Workspace discovery use target composition. The cloud fixture authors a real-session/forced-RLS organization→Workspace→stale-CAS→group→canonical-repository duplicate→controlled invitation→second-user acceptance/visibility case. | Run that authored case, the existing full organization and personal cases, real Stage 7 session HTTP/MCP lifecycle, established organization/workspace-start regressions, and the stabilized production authoring/Documents/login/rollback/logout/revocation browser case |
| Packaging/security | Adapter declares `aiosmtplib` and lock ownership; no credential/token is placed in DTO/log/audit output | Offline wheels, installed-resource probe, scoped secrecy/security checks |

<a id="deliberate-limits"></a>

## 6. Deliberate limits

- Work did not run tests, linters, type checks, builds, servers, browsers, migrations, PostgreSQL, or SMTP. A scoped write-mode formatter was applied; no execution evidence was promoted to acceptance. No external message was sent. No UI renderer, deployed migration, administrator domain, worker, MCP App host, deployment, observation, data, or legacy file was removed. RF-605–607 and RF-800 remain partial, and RF-1000–1005 remain governed by their existing later acceptance gates.

<a id="first-verification-revision"></a>

## 7. First Verification revision

- Verification run `run-20260912T221017698798Z-c31e39f4` failed before the database and browser matrix. Revision Work run `run-20260912T221353354131Z-1901b9a9` addresses its three findings:

- `VF-STAGE8-001`: Workspace use-case annotations are postponed so the public `list` operation no
  longer shadows the annotation constructor during class creation.
- `VF-STAGE8-002`: the reported import ordering, nested conditional, and unused import findings are
  corrected without changing Ruff configuration.
- `VF-STAGE8-003`: the established concurrent-owner integration assertion now constructs the same
  `OrganizationCommandService` used by production organization routes; its target use case owns the
- transaction commit.

- These are authored corrections only. Independent Verification must rerun the complete `make workbench-check`, focused package/root cases, named forced-RLS organization integration case, and the remaining Stage 8 acceptance matrix before recording any pass.

<a id="second-verification-revision"></a>

## 8. Second Verification revision

- Verification run `run-20260912T221614758857Z-af04f22d` confirmed the complete `make workbench-check`, focused root regressions, fresh migration, and concurrent personal-Workspace case, and confirmed `VF-STAGE8-001` through `VF-STAGE8-003` as corrected. It then found `VF-STAGE8-004` in the normal organization member list/search path: PostgreSQL could not infer the type of an omitted optional `status` bind.

- Revision Work run `run-20260912T221833028527Z-c80d12b4` explicitly casts that bind to the deployed text status type in both branches of the optional predicate. This is an authored correction only; independent Verification must rerun the complete named forced-RLS organization case and all remaining Stage 8 database, HTTP/MCP, browser, packaging, and security gates before recording a pass.

<a id="third-verification-revision"></a>

## 9. Third Verification revision

- Verification run `run-20260912T222046341202Z-a867921b` confirmed `VF-STAGE8-004`, the complete `make workbench-check`, fresh migration, and concurrent personal-Workspace case. The full organization case then found `VF-STAGE8-005`: PostgreSQL inferred the two role parameters in the ownership-transfer `CASE` expression as text although the deployed `role_id` column is `uuid`.

- Revision Work run `run-20260912T222252690615Z-0d3651f9` explicitly casts both the owner and administrator role binds to PostgreSQL `uuid` inside the single atomic promotion/demotion update. This is an authored correction only; independent Verification must rerun the complete named forced-RLS organization case and all remaining Stage 8 acceptance gates before recording a pass.

<a id="fourth-verification-revision"></a>

## 10. Fourth Verification revision

- Verification run `run-20260912T222457762422Z-7bb02b9f` confirmed `VF-STAGE8-005` and advanced the full organization case through ownership transfer. It then found `VF-STAGE8-006`: an overview read of a soft-deleted organization translated the visibility-filtered repository result into a 404, changing the established post-deletion authorization response.

- Revision Work run `run-20260912T222722131090Z-b1686ae9` removes the compatibility actor's visibility-filtered snapshot pre-read, derives ownership from the reserved effective owner permission, and maps an absent visible organization in the authorized overview use case to the same `organization.read` permission denial used for tenant isolation. No deleted organization content is returned. This is an authored correction only; independent Verification must rerun the complete named forced-RLS organization case and all remaining Stage 8 acceptance gates before recording a pass.

<a id="fifth-verification-revision"></a>

## 11. Fifth Verification revision

- Verification run `run-20260912T223152792904Z-48b7a910` confirmed `VF-STAGE8-006` and the fresh database organization, personal-Workspace, HTTP/MCP, and production Workbench browser cases. The Workspace-start regression then found `VF-STAGE8-007`: after selecting another Workspace, the working tenant key changed before the asynchronous Workbench-selection request completed, while the 작업 목록 DOM retained the preceding Workspace's visibility and order until after that request.

- Revision Work run `run-20260912T223510324517Z-489ea18e` applies the newly selected Workspace's user/organization/Workspace-keyed activity order and visibility synchronously with the tenant selection, before the first request boundary. The existing Workbench selection, redirect, and Workspace loading behavior remains unchanged. This is an authored correction only; independent Verification must rerun the complete Workspace-start browser regression consistently and the remaining Stage 8 packaging and security gates before recording a pass.

<a id="sixth-verification-revision"></a>

## 12. Sixth Verification revision

- Verification run `run-20260912T223832834646Z-8770d671` confirmed `VF-STAGE8-007`, the complete Workspace-start browser regression twice, `make workbench-check`, offline packaging, and scoped security checks. Repeated organization browser executions then found `VF-STAGE8-008`: an older organization render could retain pending overview-dependent reads after a new unauthorized view became current. Generation identity prevented the old render from changing the panel, but did not terminate its fetches, so a protected `/members`, `/teams`, or `/roles` read could cross the new action's request boundary while the permission state was visible.

- Revision Work run `run-20260912T224145544908Z-4076e89d` assigns one abort identity to every organization render and propagates its signal through the existing authenticated API adapter. A new view or reset terminates the preceding render's request group before resolving current permissions. The existing no-protected-read assertion remains unchanged, and no timing delay or path allowlist is introduced. This is an authored correction only; independent Verification must rerun the complete organization browser regression consistently before recording a pass.

<a id="seventh-verification-revision"></a>

## 13. Seventh Verification revision

- Verification run `run-20260912T224506879023Z-2cdb3296` found `VF-STAGE8-009` after the abort revision still allowed one protected request start in a ten-attempt organization browser loop. The source lifecycle has two organization renders after an organization mutation: `loadWorkspaces()` restored the persisted organization subview, then the mutation callback opened its intended view. The first render could therefore start the protected endpoint associated with its saved subview (`/members`, `/teams`, or `/roles`) before the second render canceled it.

- Revision Work run `run-20260912T224716849060Z-44a8ef85` suppresses persisted organization-subview restoration only while the mutation callback reloads the changed organization, then opens the callback's explicit view without applying a saved-view override. Normal startup and user-driven organization selection continue to restore their organization-scoped preference. This prevents the duplicate stale render from starting, retains the abort identity as defense for ordinary view changes, and leaves the existing no-protected-read assertion unchanged. This is an authored correction only; independent Verification must rerun the complete organization browser regression consistently before recording a pass.

<a id="eighth-verification-revision"></a>

## 14. Eighth Verification revision

- Verification run `run-20260912T225136982449Z-deea279e` used a generation-tagged diagnostic harness to identify the remaining `VF-STAGE8-010` request precisely. Request 22 was generation 16's overview `GET /api/organizations/11111111-1111-4111-8111-111111111111/members` fetch in the top Workspace frame. It started with the prior `member.read` grant after the surviving organization's header was already visible, then generation 17 rendered the connected `구성원 조회 권한이 없습니다.` state and terminated request 22 with `net::ERR_ABORTED`. This confirms that cancellation occurred after the protected request-start boundary.

- Revision Work run `run-20260912T225711674237Z-ec919e41` serializes the organization mutation transition. Workspace data reloads without publishing the replacement organization identity; the callback then awaits its single explicit organization render, including its permission-dependent reads, before updating the header and sidebar identity. `openOrganizationManagement` now returns that render promise so the boundary is explicit. Normal identity rendering and saved-view restoration remain unchanged outside mutation reloads. The existing no-protected-read assertion is unchanged, with no sleeps, network-idle waits, request allowlists, or cancellation exceptions. This is an authored correction only; independent Verification must rerun the complete organization browser regression consistently before recording a pass.

<a id="final-acceptance-evidence-and-security-closure"></a>

## 15. Final acceptance evidence and security closure

- Verification run `run-20260912T225924554214Z-748abf4f`, bound to Work run `run-20260912T225711674237Z-ec919e41`, recorded a pass receipt with no findings. Its evidence includes the complete `make workbench-check` (61 TypeScript and 55 Python tests), the full fresh forced-RLS organization case, concurrent personal-Workspace provisioning, actual Stage 8 session HTTP, and the Stage 7 identity HTTP/MCP plus authenticated production authoring/Documents/login/rollback/logout/revocation browser evidence retained from Verification run `run-20260912T223152792904Z-48b7a910` for the unchanged backend.

- The final browser evidence completed `organizations.cjs` 30 times serially and `workspace-start.cjs` 15 times serially. The latter serial repetitions followed an initial concurrent failure at the document-view visibility assertion; the evidence therefore does not claim that the browser case never failed. The offline deployment-wheel case first lacked a complete Hatchling backend environment, then passed unchanged after compatible cached Hatchling dependencies were supplied.

- The same Verification event stream records that the unignored scoped Bandit command exited 1 for `B101` at `packages/platform-core/src/agent_factory_core/organizations/use_cases.py:175`. Closure Work run `run-20260912T230625862522Z-db8d383e` replaces that assertion with the established explicit `organization_member_not_found` 404 domain path before delegation.

- Final closure Verification run `run-20260912T231126169506Z-9ecd224c`, bound to that recovery Work run and request hash `3485b4a5d535a92e4ee51f272bb2f68bb838ac33a66ad2615690d3e116949240`, recorded a pass receipt with no findings. It ran scoped Bandit without a B101 ignore and found no issues; 19 focused core tests passed together with the explicit missing-member probe. It typechecked 64 target files and 173 legacy files, and the complete Workbench gate passed with 61 TypeScript and 55 Python tests. The prior forced-RLS database, browser, and offline package records remain accepted with the limitations already recorded above; the closure did not rerun or broaden those unchanged checks. The pending B101 closure is therefore resolved.

- This evidence accepts only the Stage 8 organization/Workspace/account backend port. RF-605–607 and RF-800 remain partial because the other domains, worker composition, administrator and standard UI porting, rollout, and removal checkpoints remain outside Stage 8.

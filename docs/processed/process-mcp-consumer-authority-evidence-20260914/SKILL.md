---
name: mcp-consumer-authority-evidence-20260914
description: MCP credential and status consumer authority checkpoint을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-14-mcp-consumer-authority-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-14-mcp-consumer-authority-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# MCP credential and status consumer authority checkpoint

- This Processed evidence records the static source inventory and authored changes for Work run `run-20260913T165204388195Z-c2791fae`. It is a pre-Verification checkpoint, not proof of runtime acceptance, integrated-stage completion, or permission to delete legacy implementations.

<a id="credential-authority"></a>

## 1. Credential authority

| Public operation | Previous live authority | Authored target authority | Preserved boundary |
| --- | --- | --- | --- |
| `integration_token_set` | `app.mcp.integrations.invoke` → `cloud_services` → legacy `CloudConnections` | `build_target_credential_service` → `provider_credential_use_cases` → target PostgreSQL credential repository | authenticated organization/Workspace, `integration:manage`, `integration.update`, approved scopes, encrypted persistence and redacted MCP result |
| `integration_oauth_begin` | same legacy factory and service | same target credential composition | server configuration identity, approved scopes, encrypted ten-minute state bound to user/Workspace, and public result schema |
| `integration_oauth_complete` | same legacy factory and service | same target credential composition; the scoped connection supplies the provider when the MCP schema has no provider field | one-time consume, expiry/replay rejection, connection/provider/configuration binding, encrypted credentials, and bounded errors |

- New target OAuth states store explicit provider and configuration identities. The completion use case also accepts the prior encrypted `redirect_uri` state shape when provider is absent, derives provider only from the state-bound scoped connection, and still compares the current configuration. This is bounded already-issued-state compatibility; it is not a fallback to the legacy credential service.

- `integration_inspect`, `integration_drive_browse`, and collection list/create/start/ execute/status/results/cancel already call `invoke_target` and `build_target_collection_service`; this checkpoint leaves that authority unchanged. The target collection bridge still consumes established integration ORM tables and models as persistence compatibility. Separate legacy HTTP routes in `app/router/integrations.py`, the packaged guide, model registration, rollback tests, and direct legacy service tests remain concrete consumers of `app/modules/integration`. They are retained and are not deletion candidates in this checkpoint.

<a id="mcp-status-consumers"></a>

## 2. MCP status consumers

- The maintained backend authority is the target `GET .../mcp-connections` route, which returns `{state, connections}`. Its current consumers are:

- `ConnectionsWorkbench`, which reads the aggregate object and renders
  `connections`;
- `WorkspaceWorkbench`, whose management client and refresh/check paths now require
  the aggregate object rather than accepting a second bare-array contract;
- `tests/browser/native-management.cjs`, which now observes pending after issue,
  verified only after a successful real scoped MCP call, and reauth-required after
- revocation through `connections`, while retaining configuration delivery and purge;
- legacy `static/js/mcp-connection.js` and its browser rollback gate, retained until
  the later zero-live-consumer and rollback decision point.

<a id="authored-acceptance-coverage-and-limitations"></a>

## 3. Authored acceptance coverage and limitations

- Focused tests now exercise the actual MCP tool adapters for all three credential operations, exact authorization inputs, stable projections, provider derivation, and secret-redacted domain/unknown failures reaching the session transaction boundary. Target core coverage includes wrong-user/Workspace binding, state expiry/replay, configuration change, encryption persistence, and transitional state decoding. The fresh PostgreSQL acceptance was extended to call target-composed token and OAuth MCP operations, inspect ciphertext rather than plaintext, and cover wrong Workspace, replay, expiry, callback compatibility, and absence of secrets from results/logs.

- Work did not run tests, type checks, builds, migrations, browsers, or runtime probes. Independent Verification must establish the actual results, including fresh forced-RLS composition and the native configuration/revocation/purge scenario. RF-801–804 and RF-1000–1005 remain partial or pending; the integrated stage and definitive deletion remain incomplete.

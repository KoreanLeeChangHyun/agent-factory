# Cloud integrations and gathering

This adapter stores connection secrets on the MCP server and supports two explicit
collection modes. The existing `content` mode collects read-only provider evidence
into immutable Original revisions. The Workspace Google Drive UI uses `reference`
mode, which stores only provider links and metadata and never downloads file bodies.
Neither mode executes local provider scripts, mutates provider sources, deletes gathered
Originals, or promotes evidence to Processed or Specification truth.

A connection identifies one provider account and its encrypted credentials.
Each collection independently fixes a name, source selection, recursion/count/
page/byte bounds, and workspace Original destination. Selection is immutable;
create another collection to change it. Multiple collections can share one
connection. Each start has a durable request key and independent run cursor.
Repeating the key recovers the same run/job; a new key starts a fresh bounded
scan and adds a revision only when the latest content or source metadata differs.

## Workspace Google Drive reference workflow

The Integration Activity lists workspace connections in the Primary Sidebar and
opens a Status, Scope, or Settings panel. Google Drive is the first catalog entry.
The browser creates a credential-free workspace connection and then starts the
server-owned OAuth authorization-code flow. Requested and observed scopes, account
identity, authentication health, and collection refresh state remain separate.

An authorized Human can browse Drive folders through the first-party API, select
the current folder, choose recursive traversal, and create an immutable bounded
`reference` collection. A manual refresh uses the existing durable Job/run path.
Drive listing requests ask only for IDs, names, MIME type, timestamps, checksums,
size, extension, parent IDs, and `webViewLink`; they never request `alt=media` or
native export bytes. The resulting Original has no content revision. It stores the
stable source ID, source URL, provider metadata, collection IDs, last-seen time,
and `body_stored=false` for search and later Agent retrieval through the connector.

Refreshes update changed metadata, deduplicate the same Drive source across
overlapping collections on one connection, mark sources missing after a complete
scan, and mark a scope inaccessible when Drive returns forbidden/not-found. A
bounded scan does not infer deletion. Disabling a collection stops future refreshes
for that workspace while retaining registered Originals. Disconnecting account
authentication clears the workspace's encrypted credential separately; revoking
the Google account grant itself remains an explicit Google Account action.

## Shared application integration

The shared app registers all four cloud models, sequences migration `0019` after
Document migration `0018`, and installs `install_integrations` alongside Document,
planning and reporting tools. Legacy `integration_list` uses an explicit response
schema without credential ciphertext or encryption-key metadata.

New workspace credentials expose `integration:manage` only when the issuer has
`integration.manage`; old credentials retain their recorded scopes. Reads require
`integration:read` and `workspace.read`. Mutations require `integration:manage` and
`integration.manage`; collection create/start/execute additionally require
`document.manage`. Active Workspace availability is checked at authorization.

`app.worker.tasks` dispatches `integration.sync` directly to the trusted-context
handler. A process-held advisory claim serializes each durable Job. Queue identity
arguments are compatibility fields only: the worker reads organization, Workspace
and requester from the durable Job, then reauthorizes the active User and current
permissions before execution. Fresh probes reauthorize before provider requests and
source persistence, and read cancellation from the exact Job. Connection guards
also cover legacy disconnect/cursor mutation. Provision at least four available DB
connections per active collection worker, plus request and control-plane headroom.

Retry scheduling honors the greater of backoff and provider Retry-After. Exceptions
preserve cancellation; permanent failures and exhausted retries reconcile the exact
collection run without losing its checkpoint. Redelivery can recover a RUNNING Job
only after acquiring its released process claim. Periodic dispatch also republishes
stale running Jobs; a live claim prevents takeover. Pending cancellation never
executes provider I/O. Actual lock/restart behavior requires independent testing.

Configured first-party callback paths are
`/api/integrations/oauth/<provider>/callback`, prefixed by `public_base_url`.
The bridge authenticates the browser session, resolves that user's original
Workspace from its expiring durable OAuth state, reauthorizes `integration.manage`,
handles denial without exchange, and redirects to the clean Workspace page.
Configured redirects must exactly match that identity. Responses are no-store and
no-referrer. Uvicorn access logging removes query strings; deployment Caddy skips
callback access logs. Provider HTTP request logging is suppressed. Other upstream
proxies must apply equivalent controls before enabling OAuth. See `cloud-platform.md`.

The composition helper installs a session-local transaction hook so tenant RLS
settings survive the internal commits in DocumentService and ScheduleService.
Use a fresh AsyncSession per authorized request/run. Connection serialization
uses a dedicated PostgreSQL transaction advisory lock across those commits;
provision the shared worker connection budget stated above.
All collection and mapping queries explicitly filter the authenticated workspace.
The schema uses existing simple foreign keys; related-record tenant consistency
is enforced by these service checks, not composite tenant foreign keys.

## Packaged guide

The MCP resource reads `GUIDE` from
`app.modules.integration.cloud_guide`, a Python module included by the existing
`app*` package discovery and container app copy. It does not read repository-root
`docs/` at runtime. This Markdown guide and the module's embedded guide must be
updated together. No additional shared packaging hook is required. The focused
packaging test copies only the app package to an isolated installed layout and
reads the resource in a separate interpreter without checkout docs.

## Server configuration and credentials

Use the existing `integration_encryption_key` and versioned `SecretCipher`.
Connection credential ciphertext is the only persisted token representation.
OAuth verifiers, selection of connection, requested scopes, and redirect binding
are encrypted in expiring, single-use OAuth state records. Completion requires
the same authenticated user/workspace that began consent. A changed callback
configuration invalidates pending consent. Key-version mismatch fails closed;
keyring rotation/migration remains with the owning secret infrastructure.

Configure these environment prefixes, each with `CLIENT_ID`, `CLIENT_SECRET`,
and `REDIRECT_URI` suffixes:

- `AF_GOOGLE_DRIVE_OAUTH_`
- `AF_GMAIL_OAUTH_`
- `AF_ONEDRIVE_OAUTH_` (optional `TENANT`, default `common`)
- `AF_SLACK_OAUTH_`
- `AF_NOTION_OAUTH_`

For example, `AF_GMAIL_OAUTH_REDIRECT_URI` is an administrator-configured HTTPS
cloud callback. It is never accepted from tool input. Google and Microsoft use
web authorization-code exchange with PKCE; Slack and Notion use their
confidential-client exchanges. Request Microsoft's `offline_access` explicitly
when refresh is needed; the adapter does not add it silently. Refresh persists
rotated refresh tokens before further collection. A provider returning scopes
outside the approved set blocks collection without automatically widening consent.

`integration_token_set` supports Slack, Notion, and Discord tokens. Requested
scopes are approval bounds, never treated as granted evidence. It stores the
token without claiming live verification. Token-bearing tool arguments can be
logged by a calling client: a Human secret-entry UI should invoke the same
service through a protected server route and redact request logs. This Work
adds no client transcript/transport log controls. No tool result includes a
credential, refresh token, verifier, signed attachment URL, or provider response
body from an error. Avoid enabling httpx debug/request logging in deployment.

Health inspection is cached by default; `live=true` invokes the provider's
identity/account endpoint. Health, scope-inspection support, requested scopes,
observed grants, observation time, and staleness are separate. OAuth grants come
from token responses; Slack can also report grants in `x-oauth-scopes`.
Notion/Discord permission enumeration is `unsupported`; page sharing, channel
permissions, and Discord privileged message-content intent remain provider-side
constraints. Transient or unrecognized inspection failures produce `unknown`,
not proof of unauthenticated state. Missing observable required OAuth scopes
block collection; an identity endpoint succeeding does not prove all selections
are accessible.

## MCP workflow

Read `agent-factory://integrations/guide`. Create a connection using the existing
integration connection API. Use `integration_oauth_begin` and the configured
callback exchange, or the protected token-entry operation, after explicit Human
provider/account/scope approval. Then:

1. `integration_inspect(connection_id, live=false)` reads known connection state.
2. `collection_create(request)` fixes a bounded selection without external I/O.
3. `collection_start(collection_id, request_key)` enqueues the authorized sync.
4. `collection_status(run_id)` reads progress. `collection_results(run_id)` lists
   durable Document IDs, revision numbers, hashes, and capability limitations.
5. `collection_cancel(run_id)` requests cancellation while retaining persisted
   Originals. Cancellation is checked before HTTP attempts, streamed chunks,
   retry waits, and source persistence. An in-flight storage write can finish.

Collection creation requires an existing connection ID and a nonempty name:

```json
{
  "connection_id": "00000000-0000-4000-8000-000000000001",
  "name": "Project mail",
  "selection": {
    "query": "from:example@example.com after:2026/01/01",
    "max_items": 100,
    "max_pages": 20,
    "max_bytes": 50000000,
    "attachments": true
  }
}
```

Common limits: `max_items` 1–1000, `max_pages` 1–1000, `max_bytes` up to
500,000,000, and at most 100 artifacts per source unit. `max_items` counts
examined listing entries (including visited folders and the selected Notion
page), rather than silently permitting unbounded folder/block traversal. API
metadata and retries consume the byte budget too. Before each HTTP attempt, the
worker durably reserves the full remaining response-byte allowance. Normal
request completion/failure settles that absolute reservation to bytes accepted;
page, partial-result, and error checkpoints therefore include the current byte
charge without adding it twice. A hard crash keeps the outstanding reservation,
which can exhaust the run's budget conservatively rather than permit replay to
exceed it. This bounds accepted response data, not TCP/TLS framing or socket
buffering. A resumed exhausted run fails before further HTTP requests. Provider calls within one
listing page include bounded per-item detail/download requests. Pending cursors
are server-only. `bounded` means the configured cap was reached before provider
exhaustion; it is not a complete mirror. A new key rescans from the selected root
with the same bounds, not a request to silently continue beyond them.

| Provider | Required selection | Preserved output and scope |
| --- | --- | --- |
| Google Drive | Exactly one `folder_id` or `file_id`; optional `recursive` | Native binary bytes; Docs/Slides/Drawings PDF; Sheets XLSX; `drive.readonly` |
| Gmail | Nonempty `query`, or explicit `allow_all=true` | Original RFC message bytes, extracted attachment bytes and header/thread provenance; `gmail.readonly` |
| Slack | `channel_id`, optional `oldest`/`latest`, exact `channel_type` | Message API evidence and `files.info` downloads; matching history scope plus `files:read` when attachments enabled |
| Notion | `page_id` | Page and descendant block API evidence, refreshed hosted and controlled external file bytes; integration read-content capability and page sharing |
| Discord | `channel_id`, optionally one of `before`/`after` | Message API evidence and attachment bytes; bot VIEW_CHANNEL/READ_MESSAGE_HISTORY, subject to message-content intent |
| OneDrive | Exactly one `item_id` or relative `path`; optional recursion | Original file bytes via Graph; `Files.Read`; `include_shared=true` for `Files.Read.All`, required for explicit `drive_id` |

Provider-specific irrelevant fields, injected identifiers, ambiguous boundaries,
and user-supplied download URLs/cursors are rejected. Collection name and source
bounds are not connection configuration. No local destination path is accepted.

## Fidelity, replay, and remaining limits

In `content` mode, one stable source unit maps to one Original per collection and
overlapping collections retain separate selection provenance. In Google Drive
`reference` mode, the same connection/source identity maps to one Original while
each collection retains its own source mapping. Original
metadata records provider, connection, collection, source ID, selection, source
metadata, and limitations. Revision metadata additionally records run ID and
retrieval time. No Document-to-Document derivation relationship is invented for
an external source. Provider native exports are explicitly declared conversions.

DocumentService writes immutable cloud object revisions. A single supported
native artifact is stored directly. Multipart evidence or non-allowlisted MIME
(including EML/XLSX on the current DocumentService) is stored as a deterministic
ZIP package containing unchanged artifact bytes and a filename/MIME/hash
manifest. Empty source bytes are preserved in a ZIP. Object-service upload
limits still apply to the package. This requires no shared Document allowlist
change and does not transcode attachments.

After each source is stored, results are checkpointed. The provider cursor
advances only after the full page's revisions and source mappings persist.
Stable Document slugs recover a crash after Document creation but before mapping
creation; latest-revision hashes and provenance hashes recover a crash after
revision commit. A failure/cancellation can therefore expose already persisted
source results while retaining the previous complete-page cursor. PostgreSQL
connection locks prevent simultaneous refresh/token rotation by cloud operations
for the same account. Legacy connection disconnect/cursor routes now acquire the same guard.

Limitations are explicit:

- Unsupported Google-native types and OneDrive remote-item shortcuts preserve
  metadata with a limitation instead of pretending a binary download occurred.
- Slack thread replies are not traversed (matching the existing bounded script);
  messages with replies report that limitation. Discord content may be empty
  without the privileged intent; collection does not infer full content access.
- Notion external file URLs come only from the selected page/block's fresh API
  response, never from a URL-fetch tool argument. They support public HTTPS
  destinations on port 443, up to three redirects, and the collection's shared
  byte/count/cancellation bounds. Every hop rejects userinfo, invalid URLs, and
  nonpublic DNS answers, then connects to the validated IP with the original
  Host and TLS certificate/SNI name. A fresh client for each hop prevents cookies,
  API credentials, and reused TLS identities from crossing origins. Private
  destination redirects and excess redirect chains fail closed. Hosted Notion
  files retain the provider host allowlist; unknown hosted hosts are reported.
- Ordinary external URLs, including semantic parameters such as `version=2`,
  survive in API evidence and explicit external-source provenance. Notion hosted
  temporary URLs and private provider fields are removed. Known AWS/Google
  signature parameters, Discord CDN signatures, and explicit access/refresh
  token parameters are redacted without deleting unrelated query parameters.
- Automatic redirect following remains disabled for APIs. Attachment redirects
  are individually checked and pinned. Graph's first `/content` redirect and its
  subsequent allowed CDN hops carry no Graph credentials. Slack credentials go
  only to exact `files.slack.com`; Discord/Notion downloads never carry API
  authorization. Provider-owned attachment host families remain allowlisted.
  Retain deployment-level private/metadata-address egress denial as defense in
  depth. Pinned TLS hostname behavior depends on the installed httpx/httpcore
  `sni_hostname` extension and needs integrated transport verification.
- HTTP retries are capped at three attempts. Short `Retry-After` waits are
  cancellable; longer waits return a retryable code/delay to the worker. Health
  inspection preserves both retry classification and `Retry-After` through the
  actual collection and worker-handler boundary. Policy/byte-limit failures stay
  nonretryable rather than being reclassified from their unknown health state. A
  provider pagination token can expire between job retries; this is reported as
  a provider rejection, not permission to widen or restart a selection silently.
- Content-mode Original cloud storage and application encryption settings must be
  configured. Reference mode does not require object storage for file bodies, but
  still requires application encryption for OAuth credentials. No live credentials,
  authentication, synchronization, deployment, or restart are performed by tests.

Independent Verification should run only
`tests/connections/integration/test_cloud_integrations_providers.py` and
`tests/connections/integration/test_cloud_integrations_collections.py`, and
`tests/connections/integration/test_cloud_integrations_packaging.py` first. These are HTTP-mocked,
memory/snapshot-persistence, and isolated-package resource tests, not live-provider
or database migration tests. Work has
not run tests, builds, validators, or runtime probes. PostgreSQL RLS/migration,
shared worker dispatch, callback routing, and deployed egress behavior require
separate integrated Verification using the authored cloud-platform harness.

## Provider references

The existing sibling Gather scripts/contracts supply selection and fidelity
requirements. Primary provider contracts consulted for the cloud adaptation:
[Google web OAuth](https://developers.google.com/identity/protocols/oauth2/web-server),
[Graph content downloads](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0),
[Slack history](https://docs.slack.dev/reference/methods/conversations.history/),
[Notion blocks](https://developers.notion.com/reference/retrieve-a-block), and
[Discord messages](https://docs.discord.com/developers/resources/message).

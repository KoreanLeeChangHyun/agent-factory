# Cloud reporting and literal search

MCP receives durable reports. Local `exec.py` owns process/session/run facts and
`loop.py` owns graph transitions. A report does not launch, resume, cancel, or
complete either runtime. `agent_run_submit` remains a separate legacy API and
must never be invoked as a reporting transport.

The existing `install_reporting(server, authorize)` hook registers
`reporting_read`, `reporting_write`, and the new `reporting_search` tool plus
`agent-factory://reporting/cloud-guide`. No server registration change is needed
where that hook is already installed. The original reporting guide remains at
`agent-factory://reporting/guide`.

The cloud guide is served from `app.modules.reporting.guide.CLOUD_REPORTING_GUIDE`,
a Python text constant included with the app package. Reading this resource does
not require repository Markdown files in the runtime image. Keep this document
and that constant byte-for-byte synchronized whenever the guide changes; the
isolated tests check equality and invoke the resource with filesystem reads
blocked.

## Runtime association

At task registration, optionally supply `task.runtime_binding`:

```json
{
  "project_ref": "project-123",
  "agent_id": "cloud-reporting-work-20260906",
  "session_id": "session-123",
  "run_id": "run-20260905T154744366328Z-b0a5142c",
  "loop_id": "loop-123"
}
```

These are opaque identity references, not locations. Each is 1–160 ASCII
letters/digits/underscore/hyphen, starting with a letter or digit. All fields
except `loop_id` are required; omitted loop identity canonicalizes to null.
Do not send secrets, tokens, paths, URLs, environments, or process arguments.
Unknown fields are rejected. The recipient does no filesystem lookup or fetch
and makes no claim to authenticate the local process: this is an assertion by
the authorized reporting owner. `project_ref` must refer to the project's
already resolved identity; the recipient does not select or register a backend.

Every semantic report for a bound task must carry exactly the same
`report.runtime_binding`. Every heartbeat must do likewise. Omission and
mismatch fail with `report_runtime_binding_conflict`. Binding is immutable,
including null: old unbound tasks continue to accept old unbound reports and
cannot acquire a binding later. Use a new task UUID for a different run/session,
optionally linking it through the existing task hierarchy. Reconnects and
transport retries keep the original binding and task UUID. A resumed local
session with a new run gets a new task stream. SQL migration also prevents
updates to the registered binding.

## Submission and durable replay

`reporting_write` continues to require `agent:report`, `workspace.manage`, an
active authorized workspace, and the registering agent's user identity. Task
and linked record lookups remain workspace-scoped. Connection IDs are audit
provenance, not the owner or idempotency namespace.

1. Before sending, durably persist the complete validated command, key, target
   organization/workspace, reporting user, binding, and expected revision in a
   local outbox. Persist before network dispatch; atomically publish and sync
   the outbox using the owning runtime's existing safe file conventions. Store
   credentials separately through their existing credential authority.
2. Send that command to `reporting_write`. The server serializes writes using
   the existing workspace row lock. The idempotency namespace is
   `(workspace_id, reporter_user_id, key)`. Keys are 1–120 characters. A command
   is limited to 64 KiB after validated canonical JSON serialization.
3. The transaction commits state, append-only reports/results, audit, and the
   receipt together. A successful response contains `record`, `report_id`,
   `audit_event_id`, and `received_at`. Registration has a null `report_id`.
   Existing pre-upgrade receipts retain their original response shape.
4. Persist the returned acknowledgement before marking an outbox entry done.
   A lost acknowledgement or disconnect leaves delivery unknown. Retry the
   identical command with the same key, binding, target, and user, including
   after credential rotation/reconnect. The server returns the original stored
   response before checking the current revision. It neither writes another
   report nor refreshes receipt timestamps. A concurrent identical delivery has
   the same outcome. Current authorization is still required for every retry.
5. Reusing a key with a different canonical command yields
   `report_idempotency_conflict`. Different keys with the same expected semantic
   revision yield one successful mutation and `report_revision_conflict` for
   the other. On revision conflict, read current state and reconcile the local
   intended event before creating a genuinely new command/key. Never rewrite
   a pending outbox command or infer that an ambiguous send failed.

Canonical hashing uses the validated model's JSON-mode dump, sorted keys,
compact separators, default JSON escaping, UTF-8, and SHA-256. Optional null
`heartbeat` and null task/report `runtime_binding` fields are removed before
hashing to preserve old receipt hashes; all existing default fields remain.
Whitespace normalization follows the existing command model. Keep the original
command as well as any local hash; do not substitute a client's hash for the
server receipt. The current recipient does not expire receipts.

Agent configuration uses its existing revision CAS (zero creates). Task
registration creates revision 1. Reports supply the current task revision and
increment it by one on acceptance. Terminal semantic reports remain immutable;
only an identical receipt replay succeeds afterwards. Result links retain
existing workspace/document checks and credential-free HTTP(S) URL validation.
No URL or document body is fetched by reporting or search.

## Observed runtime facts and freshness

`operation: "heartbeat"` supplies exactly a `heartbeat` payload with task `id`,
`runtime_binding`, positive `sequence` (at most 2^63−1), timezone-aware
`observed_at`, and `fact` equal to `process_alive`, `process_exited`, or
`unreachable`. Use the command's normal idempotency key. Each new observation's
sequence must increase and its timestamp must not regress or be in the server's
future. Identical receipt replay is accepted even when its sequence is old.
The local adapter must persist the sequence across reconnects and use observed
facts, never invented progress. Clock skew must be resolved by the adapter;
it must not fabricate a later observation from receipt time.

The task exposes the latest `runtime_observation` with sequence, observed time,
server received time, and fact. Its historical accepted value remains in the
command's receipt. A heartbeat creates an audit record and updates this
observation, including for terminal tasks. It does not create a semantic report,
increment task revision, update agent/task `last_report_at`, modify progress,
or change status/start/finish times. The ordinary row `updated_at` may change.

Read responses expose `server_time` and `stale_after_seconds: 300`. Semantic
freshness is based on `last_report_at`; null means no semantic report. Runtime
freshness is based on `runtime_observation.observed_at`; null means no runtime
observation. Its `received_at` describes delivery freshness only: replay of an
old observation cannot establish that a process is alive now. Do not use
`updated_at` as semantic freshness. Search excerpts are discovery results; read
the task to inspect its status and freshness. Stale reporting or disconnect
means an observation gap, never inferred completion, failure, or cancellation.
An explicit local process exit also does not decide the semantic task outcome
or the Work/Verification loop outcome.

## Literal search

Call `reporting_search` with a `request` object:

```json
{"query":"run-20260905", "kind":"task", "limit":20, "after_id":null}
```

`kind` selects `agent`, `task`, `report`, or `result`. Search checks the selected
record UUID, title/body, and relevant identifiers: agent role/parent; task
agent/parent/runtime binding; report task; result report/document/URL. It uses
parameterized, case-sensitive literal substring matching, independent of
embeddings, FTS language configuration, or provider calls. Korean fragments
such as `한국어` and intact identifiers such as `run-123_a` match. `%`, `_`, `/`,
quotes, and Boolean/operator-looking text are data, not query syntax. It does
not tokenize, stem, rank, or perform Unicode normalization.

Queries trim outer whitespace and must contain 1–256 characters and at most
1024 UTF-8 bytes; control/format characters are rejected. Limit is an integer
1–100, default 20. UUID ordering provides deterministic bounded keyset pages;
pass the returned `next_after_id` with the same kind/query/workspace. Null means
no further page observed. Cursors grant no authority and may not be used to
cross workspace boundaries. Concurrent edits can change matches between pages;
this is not a frozen snapshot. The tool requires `agent:read` and
`workspace.read` before persistence access, and every query filters workspace.

Responses return at most the requested limit with IDs, bounded title (200) and
excerpt (1000) characters, and relevant link/identity fields. SQL fetches at
most limit + 1 rows; it does not perform a separate count. Literal substring
search may scan the selected workspace's rows; no new index or dependency is
introduced and no fixed query-latency guarantee is made.

## Integration handoff

Apply migration `0020_cloud_reporting_bindings.py` before using the updated ORM.
Shared integration orders it after `0019` and before delivery migration `0021`.
Code registration does not apply migrations or import historical runtime data. Existing rows receive null columns;
the new audit policy only adds heartbeat insertion to the existing reporting
policies. No shared model import change is needed: the task model was already
imported by `app/db/models.py`.

Later local-runtime Work should add an optional recipient adapter at durable
run acceptance (enqueue registration after the exact session/run binding is
known), supervisor observations (enqueue heartbeat), and validated semantic
report/result availability (enqueue reports). Loop transitions stay solely in
`loop.py`; enqueue observations after its authoritative transition record is
durable. Each new run maps to a new task; persist the task mapping, outbox, and
heartbeat sequence with the exact managed run identity. Outbox delivery must
not block local runtime authority or restart execution, and reconciling an
unknown delivery must replay only reporting, never `exec.py submit` or legacy
`agent_run_submit`. This bounded change implements the recipient and contract;
it does not modify or install the local adapter.

Independent Verification should run `tests/reporting/regression/test_cloud_reporting.py` and relevant
existing pure reporting tests. The new tests use private SQLite search tables
and a simulated workspace lock for service behavior. They do not prove
PostgreSQL RLS, real row-lock scheduling, migration execution, or deployment
packaging; those require separately authorized isolated integration checks.

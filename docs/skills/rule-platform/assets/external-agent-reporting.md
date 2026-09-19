# External agent reporting over MCP

Agent Factory provides MCP connectivity and a persistent cloud control tower.
Your client runs the AI and performs the work. These tools neither execute models,
submit legacy agent runs, create schedules, nor change planning status.

Discover this guide through `resources/list` and read
`agent-factory://reporting/guide`. Use `reporting_read` and `reporting_write`
from `tools/list`. The legacy `agent_list` and `agent_run_submit` retain their
separate versioned-execution contracts and do not populate this view.

## Authentication and identity

Use your authenticated workspace MCP URL and bearer token. Workspace-bound
tokens resolve the organization and workspace automatically; unbound API tokens
must supply `organization_id` and `workspace_id` to each tool.
Reads require `agent:read` and the current `workspace.read` permission. Writes
require `agent:report` and the current `workspace.manage` permission. Newly
created workspace connections include `agent:report` only for workspace managers.
Existing credentials keep their granted scopes; create a new connection if needed.
A revoked, expired or differently scoped credential cannot resume reporting.

The server obtains the reporter user and connection ID from authentication, never
from payload fields. The user who first registers an agent owns its reports and
configuration updates. Another manager cannot impersonate that agent. Reconnect
with the same user (a new connection/token is fine) and reuse agent/task UUIDs.
Multiple named agents may belong to one user; this is user-bound reporting
identity, not cryptographic proof that a particular AI process produced a report.
Configuration survives disconnection and revocation. Parent agents may belong to
other workspace users; parenthood grants no authority over their reports.

## Commands

Each JSON example below is a **tools/call arguments object** for `reporting_write`.
Use fresh locally generated UUIDs for a new configuration/task. Keep them in your
client's durable state. The example UUIDs show the shape; substitute your own.

Register a configuration (`revision: 0` means create):

```json
{"command":{"key":"config-reviewer-1","operation":"agent","agent":{"id":"a1111111-1111-4111-8111-111111111111","revision":0,"name":"Reviewer","role":"Review","responsibilities":"Review changes and report findings","parent_id":null}}}
```

To update, send all configuration fields, the same ID, the returned revision and
a new key. `parent_id` is another configuration UUID in this workspace. Cycles,
missing/cross-workspace parents, and paths deeper than 64 levels are rejected.
Workspace scope comes from authentication, not free-form configuration text.

Register a pending task:

```json
{"command":{"key":"task-review-1","operation":"task","task":{"id":"b2222222-2222-4222-8222-222222222222","agent_id":"a1111111-1111-4111-8111-111111111111","name":"Review reporting changes","description":"Inspect authorization and result links","parent_id":null,"plan_item_id":null}}}
```

For existing planned work, set `plan_item_id` to its actual `plan_items.id` from
the schedule. This task is a report stream about that work; it does not replace
or copy the planning identity, dates, assignee, acceptance or status. `parent_id`
links another report task. Linked planning items cannot be deleted while referenced. Task assignment, planning link and parent are immutable
once registered. Correct a mistaken stream by cancelling it and registering a
new one with an explanation; no implicit reassignment or scheduling occurs.

Report immediately before work starts:

```json
{"command":{"key":"review-start-1","operation":"report","report":{"id":"b2222222-2222-4222-8222-222222222222","revision":1,"status":"in_progress","message":"Starting authorization review"}}}
```

Report material progress, a blocker, or a heartbeat at least every few minutes
while doing long work. Only supply a percentage if you have actually measured it.

```json
{"command":{"key":"review-progress-1","operation":"report","report":{"id":"b2222222-2222-4222-8222-222222222222","revision":2,"status":"in_progress","message":"Reviewed read boundaries; checking concurrent writes","progress":40}}}
```

Finish with actual results, in the same report:

```json
{"command":{"key":"review-finish-1","operation":"report","report":{"id":"b2222222-2222-4222-8222-222222222222","revision":3,"status":"completed","message":"Review completed; findings attached","results":[{"label":"Review summary","summary":"Describe actual findings and limitations here"}]}}}
```

A result may contain `document_id` for a real, readable workspace Document, or
`url` for an absolute HTTP(S) result link without credentials. Do not supply both.
Document IDs are checked in the workspace; URLs are reported references, not
server-fetched or verified content. Text-only summaries are allowed. Include
results before terminal completion because a terminal stream is immutable.
A valid link result shape is:

```json
{"label":"Review artifact","summary":"Detailed findings","url":"https://example.com/review/123"}
```

A Document result shape (replace the UUID with an existing Document ID) is:

```json
{"label":"Review Document","document_id":"c3333333-3333-4333-8333-333333333333"}
```

## State, concurrency and recovery

| Current state | Allowed next reports |
| --- | --- |
| pending | in_progress, input_required, cancelled |
| in_progress | in_progress, input_required, completed, failed, cancelled |
| input_required | input_required, in_progress, failed, cancelled |
| completed / failed / cancelled | none |

Use `input_required` with a concrete missing input; it does not send a message or
create a human approval automatically. Resume with `in_progress`. Use `failed`
for a failed started attempt and `cancelled` for work that will not continue.
A terminal task needs a new task ID for another attempt, linked to the same
planning item if appropriate. Never infer completion from connection loss.

Server receipt times supply `last_report_at`, `started_at` (first in-progress
report) and `finished_at` (terminal report). They do not claim to measure offline
execution times. Pending registration/configuration alone is “no report”. After
five minutes without a report, nonterminal work is shown as stale with its last
reported state. Percentages never auto-advance; omitting progress preserves the
last reported percentage even on completion.

Every accepted command returns the record/revision and audit ID; task reports
also return a report ID. Keys are scoped to workspace and authenticated user,
across reconnections and all operations. Retry an uncertain response with the
**identical command and same key**: it returns the original receipt and creates
no duplicate report or log. Reusing a key for changed payload is a conflict.
A duplicate retry does not refresh the last report time.

Before resuming, call `reporting_read` with no task ID for configuration/tasks,
or with `task_id` for its latest state, reports, results and bounded related logs.
For older history pass the returned `next_before_revision` as `before_revision`.
On revision conflict, reread and reconcile the actual state before creating a new
command/key; do not blindly overwrite newer reports. Concurrent commands with
the same expected revision permit at most one new accepted report. Task reports
are immutable; server timestamps, audit identity and ownership cannot be supplied.

Commands are closed objects, at most 64 KiB UTF-8, with up to 20 results. Field
limits are exposed in the MCP schema. Reads show at most 1,000 configurations and
1,000 most recently updated tasks and explicitly signal truncation; direct task
reads remain available by UUID. History pages contain up to 50 reports and their
results/logs. Store task UUIDs when operating in larger workspaces.

## Expected MCP errors

Expected authorization and reporting errors return an MCP tool result with
`isError: true`. Its single text content block is a JSON object containing only
stable `code` and safe `message` fields, with no tool-name prefix. Parse the entire
text block as JSON; no prefix removal is needed. For example, a stale write returns
`{"code":"report_revision_conflict","message":"Read current state before sending a new command"}`.
Use `report_idempotency_conflict` to distinguish a reused key with changed
content, `invalid_transition` for a disallowed state change,
`report_owner_required` for a reporter ownership denial, and
`report_record_not_found` for a missing or inaccessible workspace record.
Authorization errors retain their own codes, such as `mcp_scope_required` and
`workspace_token_mismatch`. These errors do not commit a partial report.
Unexpected implementation exceptions retain the SDK's generic tool-error
presentation; internal exception details are not part of this contract.

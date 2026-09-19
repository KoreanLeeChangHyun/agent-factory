---
name: reporting-verification
description: Focused verification of external reporting을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/reporting-verification.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# Focused verification of external reporting

- Work authors these checks and does not run them. Independent Verification should run the commands below from the MCP repository root. No production database, service restart, deployment or credentials are involved.

```bash
bash scripts/verify-reporting.sh
```

- For the managed service's older supplementary group set, Main supplied this alternative using the locally available PostgreSQL image:

```bash
sg docker -c 'REPORTING_POSTGRES_IMAGE=pgvector/pgvector:0.8.6-pg18-bookworm bash scripts/verify-reporting.sh'
```

- This selects the Docker group for the verification process without changing socket permissions. It does not operate existing containers belonging to other work. Work has not executed either command.

- Prerequisites: Docker, the project's `.venv` with development dependencies, Python Playwright and installed Chromium. The script uses the configurable `REPORTING_POSTGRES_IMAGE` (default `pgvector/pgvector:pg16`), creates a uniquely named container with no host mounts, and publishes PostgreSQL on a random loopback port. It explicitly overrides the application's database URL, migrates 0014 → 0015 → 0014 → 0015 using `-c config/alembic.ini` on every Alembic call, creates a non-superuser/non-BYPASSRLS login, and runs:

```bash
.venv/bin/python -m pytest -q tests/test_reporting.py tests/test_reporting_integration.py tests/test_mcp_server.py
.venv/bin/python -m pytest -q tests/browser/reporting.py
bash scripts/verify-reporting-runtime.sh
```

- The runtime check builds the actual Dockerfile `runtime` target with a unique verification image tag, then runs `tests/test_reporting_runtime.py` against it. The container has no checkout mounts, no network and a read-only filesystem. It reads `agent-factory://reporting/guide` through the MCP resource API and checks its JSON examples against the runtime command schemas. The Dockerfile explicitly copies the single guide to `/srv/agent-factory/docs/external-agent-reporting.md`, matching the existing resource path. The check therefore fails if that COPY is removed, even when checkout-based tests still find the guide. The bare wheel is not asserted to contain checkout documentation; the supported runtime image owns this explicit file installation.

- Run that packaging regression independently if database verification fails first:

```bash
sg docker -c 'bash scripts/verify-reporting-runtime.sh'
```

- The image build needs its normal base-image/dependency access. The test container itself cannot access a database or external network. The helper removes only its uniquely tagged verification image; it does not deploy or restart a service.

- Only the disposable container created by the script is removed on exit. A missing Docker/image/database/Chromium dependency fails visibly; the reporting integration test does not skip when its DB environment variable is absent. For an independently prepared disposable database, migrate through 0015 and grant a non-superuser role table DML plus schema/sequence access, then supply `REPORTING_TEST_DATABASE_URL` and `REPORTING_TEST_ADMIN_DATABASE_URL` (the latter only for FK/migration assertions against that same disposable database).

- Coverage includes every status transition, bounded/closed payloads, unsafe URL rejection, actual MCP schema/resource discovery, bearer-authenticated MCP writes, read APIs, scope and RBAC denial, reporter ownership, reconnect/revocation, idempotency payload conflicts, duplicate retries, concurrent revision races, hierarchy rejection, result references, planning status preservation, persisted report/audit history, RLS reads/writes and composite-FK isolation. Browser coverage uses Chromium against the actual repository shell/assets with isolated API fixtures: overview/agent/task selection, explicit stale/no-report/error states, escaping, document/planning/log navigation, late response races, retries, reload, keyboard and narrow layout. Browser fixtures do not alter server authentication.

- The browser test and live PostgreSQL/MCP test have distinct boundaries: browser fixtures exercise rendering/navigation, while API/MCP tests exercise actual auth, SQL persistence and tenant boundaries. They do not claim a production end-to-end session. URL results are validated as safe references without fetching external content. No AI execution or repository-wide full suite is included.

- Implementation limits: workspace snapshots explicitly truncate beyond 1,000 agents / 1,000 latest tasks; direct task-by-ID/history reads remain available. History uses 50-report pages. Reporting identity is the authenticated user with connection history, not attestation of a local model process. Existing tokens retain existing scopes. Assignment/parent/planning links on tasks are immutable; configuration can be updated with revision checks. There is no ownership transfer, AI hosting, scheduler or automatic restart of failed work.

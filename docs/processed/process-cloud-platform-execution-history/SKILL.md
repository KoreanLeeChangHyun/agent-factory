---
name: cloud-platform-execution-history
description: 클라우드 플랫폼의 과거 검사 절차와 조사 기록을 확인합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  sources:
  - docs/skills/design-platform/references/cloud-platform.md
---


# 클라우드 플랫폼 실행 이력

- 과거 검사 절차와 당시 조사 기록입니다. 현재 실행 명령이나 검증 통과를 뜻하지 않습니다.

<a id="independent-verification-commands"></a>

## 1. Independent Verification commands

- Prerequisites: the project's Python environment with dev dependencies, Docker, Node, and an installed Playwright Chromium runtime. No live provider accounts or credentials are needed. Run only this focused harness:

```sh
NODE_PATH=/tmp/af-pw/node_modules bash scripts/verify-cloud-platform.sh
```

- The harness creates one uniquely named pgvector PostgreSQL container without a host volume, binds only a random loopback port, applies migrations through 0017, upgrades through 0021, downgrades the empty disposable DB to 0017 and re-upgrades, then grants a non-owner NOSUPERUSER/NOBYPASSRLS role for actual application calls. It prints a transcript path under `/tmp`. Cleanup targets only its own generated container. It never calls compose, current dev/production containers, `.env` DB, public providers, or the unrelated full suite. Work authored but did not execute this command; there are no execution results to report.

- The new integration tests run an actual Uvicorn HTTP/MCP server, an isolated filesystem object-storage adapter, and actual provider adapters with HTTP fixtures. They cover no-token/expired/revoked/cross-Workspace denial, issuance/call-time write permissions, exact/concurrent imports, RLS, lexical Korean/identifier lookup, synthetic pair rejection preserving publication, complete Git-managed Document and Agent source-package bytes, large binary upload digest/expiry/retry, authenticated preview headers, worker acceptance vs execution, pending and in-loop cancellation, concurrent claims/connection mutations, recovery from persisted RUNNING state, Retry-After/exhaustion, cursor behavior on failed object writes, OAuth exchange/ denial/expiry, optional reporting binding and heartbeat persistence, and the actual current editor opening/closing/reopening a durable Document. The wheel test builds in a disposable copy and compares all packaged browser/resource bytes.

- This new current-editor case must succeed before claiming integrated editor coverage. The earlier broader `document-editor.cjs` timeout remains historical incomplete evidence and is not reclassified as a pass. The recovery test starts from a durably written orphan RUNNING record; it does not simulate killing a live OS worker. Provider fixtures do not establish deployed egress or live account permissions. The isolated storage adapter does not establish a production S3 service's failure guarantees. Verification must report these limits and actual commands/results, including failures, independently.

- Source inventory taken during this Work (read-only, not an import test): Git-managed Document roots contain 27 files / 8,159,332 bytes; Git-managed Agent roots contain 19 files / 4,315,663 bytes. The current Agent source additionally has untracked `skills/agent/references/reporting.md` (4,795 bytes) and `skills/agent/runtime/cloud_reporting.py` (21,490 bytes). The package fixture uses both tracked and nonignored untracked source files and preserves those additions; it does not include ignored generated `__pycache__` files as distributable sources. These measurements differ from the earlier handoff's full-directory totals and do not imply missing vendor assets or Specification acceptance. Per-file hashes and Git-managed flags are recorded in this run's `source-inventory.json`.

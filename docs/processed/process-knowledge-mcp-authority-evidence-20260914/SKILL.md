---
name: knowledge-mcp-authority-evidence-20260914
description: Knowledge MCP authority checkpoint을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-14-knowledge-mcp-authority-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-14-knowledge-mcp-authority-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Knowledge MCP authority checkpoint

- This Processed evidence records the source inventory and authored changes for Work run `run-20260913T173248275646Z-59671048`. It is pre-Verification evidence, not a claim that the checkpoint, integrated stage, or later deletion has passed.

<a id="authority-transition"></a>

## 1. Authority transition

| MCP operation | Previous business authority | Authored target authority | Maintained boundary |
| --- | --- | --- | --- |
| `document_template` | shared authorization followed by construction of legacy ordinary/cloud services before `read_template` | shared read authorization followed directly by the packaged resource reader | version-bound manifest, exact inventory, base64 chunks no larger than 64 KiB, `accepted_pair=false` |
| `document_import` | `CloudDocumentService` | `CloudKnowledgeUseCases.import_bytes` through production PostgreSQL/object-storage composition | closed v1 schema, digest/package limits, idempotency/conflict, reviewed complete Specification pair |
| `document_read` | `DocumentService`/`DocumentRepository` | `DocumentUseCases` and target repository/storage | metadata, old/current immutable revisions, provenance, `document.export`, and the 256 KiB MCP bound checked before storage read |
| `document_write` | `DocumentService`/`DocumentRepository` | `DocumentUseCases` | 32 KiB command bound, typed create/update/delete/provenance, optimistic metadata revision, Specification create rejection |
| `document_search` | `CloudDocumentService.search` | `CloudKnowledgeUseCases.search` | embedding-independent bounded lexical substring search, including Korean and identifiers, current non-deleted revisions only |
| `document_index` | `CloudDocumentService.index_revision` | `CloudKnowledgeUseCases.index` with MCP compatibility checks | document/revision lookup, supported extraction types, pre-read size bound, immutable digest validation, public `{chunks}` result |
| prepare/finalize upload | target delivery authority already present | unchanged target `DocumentDeliveryUseCases` | capability, expiry, digest, audit, replay and first-finalize behavior retained |

- All target repositories are constructed with `source="mcp"` and the authenticated actor carries the authorized user, organization, Workspace and current permissions. Unknown failures remain redacted at the MCP boundary; target Knowledge errors retain their bounded public code and message.

<a id="retained-compatibility-and-consumers"></a>

## 2. Retained compatibility and consumers

- The MCP adapter retains legacy Pydantic request DTOs and enum conversion solely to preserve the maintained public schema. `app.modules.document.template` and `app.resources/document_template*` remain packaged data authorities used by MCP, package tests and installed-resource acceptance; they do not construct a Document business service.

- Legacy `app/router/documents.py`, `app/router/cloud_documents.py`, `app/modules/document/legacy_import.py`, direct legacy service tests, and rollback coverage still consume `DocumentService`, `CloudDocumentService`, or `DocumentRepository`. `app/mcp/server.py` also retains a Document list resource backed by the established repository. Collection adapters consume established document ORM tables/model compatibility. These concrete consumers prevent deletion in this checkpoint and require later authority migration or explicit rollback retention plus independent zero-live-consumer proof.

- Package, source, preview and authoring consumers remain the target cloud Knowledge routes, packaged preview runtime/resources, the standard Documents workbench, template inventory/package acceptance, and legacy rollback surfaces. This checkpoint does not remove or reclassify them.

<a id="authored-acceptance-and-limits"></a>

## 3. Authored acceptance and limits

- The required fresh PostgreSQL scoped-MCP case now covers import replay/conflict, old/current revision reads and downloads, lexical index/search for Korean and an identifier, optimistic metadata update conflict, create/provenance/delete, and direct Specification create rejection. Focused transport tests cover the 256 KiB pre-storage download rejection, corrupted immutable bytes, the 32 KiB metadata bound, target rollback error projection, exact export authorization, and secret-safe errors. Existing core/adapter cases retain package/pair, lexical current/deleted filtering, forced-RLS, digest, and rollback coverage. The existing distributable template inventory test is an explicit Verification gate and was not weakened.

- Work did not run tests, lint/type checks, builds, migrations, servers, browsers, or runtime probes. Independent Verification must establish the actual results, including the two required fresh three-role PostgreSQL cases and the distributable inventory regression. RF-801–804, RF-1000–1005, the full Documents browser matrix, integrated acceptance, definitive deletion, and commit remain incomplete.

<a id="current-distributable-inventory-ownership"></a>

## 4. Current distributable inventory ownership

- The explicit Human correction for this checkpoint confirms that Mermaid is not a universal Agent-distribution requirement. The 2026-09-06 Document and Agent inventory measurements in `cloud-documents.md` are historical observations of the then-current sibling source layout; the observed largest Mermaid member does not impose a renderer asset on every later Provider Skill.

- The current sibling plugin manifest at version `1.0.6+codex.20260913144505` declares only the `agent` and `convention` Skills. Its complete Git-confirmed `skills/agent` inventory is therefore tested by itself, including the required `SKILL.md`, real source volume, archive path equality, and member byte/digest equality. No MCP Document template files are added to or relabeled as Agent source.

- The maintained Mermaid, Tabulator, license, and third-party-notice assertions apply to the actual MCP-owned Document/template inventories under `app/resources/document_template/`. The installed-resource template view remains bound to `document_template_inventory.json`. This distinction preserves current source completeness without weakening archive limits, paired-Specification validation, or asset checks for packages that actually declare those resources.

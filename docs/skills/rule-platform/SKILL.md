---
name: rule-platform
description: Apply mandatory Agent Factory platform rules for identity, authorization,
  persistence, Documents, integrations, MCP, jobs, security, operations, search, and
  Workspace behavior. Use for implementation and acceptance decisions; use design-platform
  for architecture intent.
metadata:
  specification-id: rule-platform
  language: ko
  document-type: specification
  category: rule
  domain: null
  name: platform
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/rule-platform/SKILL.md
    - docs/skills/rule-platform/references/admin.md
    - docs/skills/rule-platform/references/agents.md
    - docs/skills/rule-platform/references/authentication.md
    - docs/skills/rule-platform/references/authorization.md
    - docs/skills/rule-platform/references/database.md
    - docs/skills/rule-platform/references/documents.md
    - docs/skills/rule-platform/references/integrations.md
    - docs/skills/rule-platform/references/mcp-connections.md
    - docs/skills/rule-platform/references/mcp.md
    - docs/skills/rule-platform/references/migration.md
    - docs/skills/rule-platform/references/observability.md
    - docs/skills/rule-platform/references/operations.md
    - docs/skills/rule-platform/references/search.md
    - docs/skills/rule-platform/references/security.md
    - docs/skills/rule-platform/references/workers.md
    - docs/skills/rule-platform/references/workspaces.md
    - docs/specification/rule-platform/index.html
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: rule-platform
      description: Apply mandatory Agent Factory platform rules for identity, authorization,
        persistence, Documents, integrations, MCP, jobs, security, operations, search,
        and Workspace behavior. Use for implementation and acceptance decisions; use
        design-platform for architecture intent.
      metadata:
        specification-id: rule-platform
        specification-version: '1'
        projection: ai
        language: en
        counterpart: ../docs/specification/rule-platform/index.html
        semantic-revision: '1'
        sync-base-revision: '1'
        modified-at: '2026-09-14T03:40:00+09:00'
---


# 플랫폼 규칙

## 1. 적용 범위와 필수 정책

- 제품 동작과 제약의 기준입니다. 사용자 지시를 우선하고 테넌트 격리, 불변 이력, 자격 증명 비밀성, 멱등성, 실패 동작과 HTTP·MCP의 일치성을 유지합니다.
- 코드와 테스트는 구현 근거이며 규칙을 자동 대체하지 않습니다.
- 신원·권한·관리, 저장·보안·관측·운영, 작업공간·문서·검색·이전, 에이전트·worker, 연동·MCP 정책을 아래 해당 절에서 확인합니다.
- [외부 에이전트 보고 안내](assets/external-agent-reporting.md)는 제품 안내와 함께 유지하는 인터페이스 자료입니다.

<a id="admin"></a>

## 2. admin

- The admin surface is separate from the tenant Workspace at `/admin/` internally and `/factory/admin/` publicly. Its data APIs live below `/api/admin` internally and `/factory/api/admin` publicly. Loading static assets grants no authority; every admin API independently requires an active platform-administrator principal and establishes an explicit cross-tenant database context.

- The initial control plane exposes aggregate health, users and session revocation, organizations, Workspaces, ownership grants, durable jobs, integration health, feature flags, safe runtime configuration, application version, and Alembic revision. Secret values and encrypted credential bytes are never serialized. Mutations require CSRF protection and an administrator cannot suspend its own account.

- Ownership endpoints grant an additional owner instead of silently removing existing owners. This preserves recoverability. Audit history becomes available through the same control plane when the immutable audit domain is added.

<a id="agents"></a>

## 3. agents

- An Agent definition is mutable identity and presentation metadata. Every executable configuration is an immutable Agent version. Runs always pin a specific version, so later edits cannot change historical behavior.

- Run creation is idempotent within a Workspace. The durable status machine is `queued -> running -> succeeded|failed`, with immediate cancellation for queued runs and cooperative `cancel_requested` handling for running jobs. Only failed or cancelled runs may be retried, and retries preserve a link to the original. HTTP and MCP submission use the same application service. It persists the Run and its durable Job in one database transaction before broker publication; retries create the linked Run and Job through that same boundary. A broker publication failure leaves the committed Job eligible for outbox recovery.

- Usage, estimated cost, tool calls, artifacts, linked input/output Documents, and ordered run events are tenant-scoped records. The event table is the durable replay boundary for polling or server-sent event delivery; Redis may accelerate live delivery but never replaces this record. Execution workers are connected in the scheduling and worker stage.

<a id="authentication"></a>

## 4. authentication

- Browser authentication uses server-side opaque sessions. Only an HMAC-SHA-256 digest of each session, recovery token, verification token, or MCP API token is stored. Session cookies are HTTP-only; state-changing browser requests also require the matching CSRF cookie and header. Unauthenticated browser requests to `/workspace/` are redirected server-side to the separate `/login/` page. An active session is required before the Workspace HTML is returned; an authenticated request to `/login/` returns to Workspace.

- Local credentials use pwdlib's recommended Argon2 hasher. Repeated failures lock the credential without changing the generic login error. A successful password reset revokes every active session.

- Google uses OpenID Connect. GitHub uses its OAuth web flow with PKCE and the primary verified email endpoint. Provider access tokens are used to validate identity for the current login and are not persisted as application sessions. The Google OAuth client must be a Web application and its authorized redirect URI must exactly match `<AGENT_FACTORY_PUBLIC_BASE_URL>/api/auth/oauth/google/callback`. Both `AGENT_FACTORY_GOOGLE_CLIENT_ID` and `AGENT_FACTORY_GOOGLE_CLIENT_SECRET` are required; a partially configured provider fails settings validation and an unconfigured provider is not advertised to the browser.

- Staging and production reject the known development secret, insecure cookies, and non-HTTPS public URLs at settings validation time. MFA enrollment has an encrypted provider-neutral persistence boundary; factor implementation and key management are completed with the security milestone.

<a id="authorization"></a>

## 5. authorization

- Authentication establishes a user identity. Every tenant operation resolves an organization and, for Workspace resources, a Workspace. Authorization establishes transaction-local PostgreSQL RLS context and verifies active membership and live Workspace state. Organization membership suspension/removal overrides direct and team Workspace grants.

- `packages/platform-core/src/agent_factory_core/organizations/permissions.py` owns the permission catalog and built-in role definitions; `app/modules/organization/permissions.py` is a transitional compatible import. Organization roles govern organization operations; Workspace roles apply only through direct or team membership in the selected Workspace. Effective permissions are the union of those grants. User-defined roles cannot include unknown keys, another scope, or owner-only transfer/delete permissions. The platform admin identity remains separate.

- Route dependencies and domain services enforce action permissions. Hiding controls is not authorization. Delegation checks both existing and proposed roles, including all Workspace grants affected by team membership changes. Organization owners can administer assignments; they need Workspace membership to read its content.

- MCP contexts contain the intersection of current user permissions and token scopes. New API tokens require a Workspace binding, token.create, and a scope subset of the issuer's effective permissions. Legacy token scopes expand to documented action sets before the intersection, never to organization administration.

- Documents inherit Workspace permissions. Per-document ACLs, nested teams, guest membership and public Workspace joining remain future changes. See `organization-management.md` for lifecycle rules and verification commands.

<a id="database"></a>

## 6. database

- PostgreSQL is the only authoritative relational database. All identifiers are application-generated UUIDs, timestamps are stored with time zone semantics, and mutable aggregate roots carry a revision for optimistic concurrency.

- Tenant-owned tables must contain an `organization_id` or `workspace_id` foreign key and enable PostgreSQL row-level security. Application authorization remains mandatory: RLS is defense in depth, not the primary permission system.

- Tests marked `integration` use a dedicated PostgreSQL database and may run only when `AGENT_FACTORY_TEST_DATABASE_URL` is explicitly supplied. Unit tests must not silently connect to a developer or production database.

<a id="documents"></a>

## 7. documents

- Documents belong to one Workspace and have one of three semantic types: Original, Processed, or Specification. Metadata and immutable revision records are authoritative in PostgreSQL. Revision bytes are stored under tenant-scoped, server-generated keys in the configured S3-compatible object store.

- Provenance is deliberately a loose graph. A Processed Document may identify the Original Documents it processed, and a Specification may identify the Processed Documents it specifies without changing the authority of either record.

- Uploads are size- and media-type constrained, filenames are reduced to a single safe path component, and checksums are recorded. A failed database transaction triggers removal of the newly uploaded object. Document deletion is initially a recoverable metadata soft-delete; object lifecycle and retention jobs perform eventual physical deletion.

<a id="external-agent-reporting-인터페이스-자료"></a>

## 8. external-agent-reporting 인터페이스 자료

- [external-agent-reporting 원문](assets/external-agent-reporting.md)은 제품 내장 안내와 바이트 일치를 유지하는 인터페이스 자료입니다. 이 파일이 해당 안내의 편집 원본이며 본문을 중복 저장하지 않습니다.

<a id="integrations"></a>

## 9. integrations

- The global provider catalog describes supported authentication modes and capabilities. Each connection belongs to exactly one Workspace. Credentials, OAuth PKCE verifiers, and webhook signing secrets are AES-GCM encrypted with a versioned server key; responses never return stored credentials. Disconnecting a connection removes credentials and its synchronization cursor.

- OAuth state is random, stored only as a keyed digest, expires after ten minutes, and is consumed once. The PKCE verifier stays encrypted server-side. Provider drivers own authorization URLs, code exchange, credential validation, and sync behavior behind a common interface.

- Webhook endpoints use unguessable public identifiers and return signing secrets only on creation. RLS permits unauthenticated lookup only for the exact public identifier placed in transaction-local context. Signatures and payload limits are checked before durable, idempotent delivery creation. Delivery attempts use pending/processing/succeeded/failed/dead states and are dispatched in the worker stage. Cursors advance only after successful processing.

<a id="mcp-connections"></a>

## 10. mcp-connections

- 사용 흐름은 **인증 토큰 발급·선택 → MCP 클라이언트 설정 ZIP 다운로드 → AI 지침 복사·전달 → MCP 연결 확인**이다. 사용자가 클라이언트나 사용 환경을 미리 선택하지 않는다. 다운로드·복사·새로고침은 새 토큰을 발급하지 않는다. 새 토큰은 명시적인 토큰 발급 버튼으로만 만든다. 토큰 선택은 계정·조직·작업공간별 ID만 브라우저 저장소에 기억한다. 토큰 원문은 브라우저 저장소에 저장하지 않는다.

<a id="토큰-저장조회수명"></a>

## 11. 토큰 저장·조회·수명

- API 인증에는 기존 해시를 계속 사용한다. 새 연결 토큰은 추가로 AES-GCM 암호화해 mcp_connections.encrypted_token에 저장한다. 기존 통합 비밀 암호화 키와 버전 (AGENT_FACTORY_INTEGRATION_ENCRYPTION_KEY 및 VERSION)을 사용한다. 운영 키는 재시작 사이에 동일하게 보존해야 한다. 버전 불일치·복호화 실패는 토큰 값을 반환하지 않으며 조회 오류로 처리한다. 키 변경 시 기존 암호문 재암호화 또는 새 발급 절차가 필요하다.

- 암호화 내용은 용도와 연결 ID에 묶이고 조회 시 토큰 해시도 대조한다. 조회는 로그인 사용자 소유·조직·작업공간 일치, 작업공간 권한·활성 상태, 토큰 만료·폐기를 검사한다. 토큰 수명은 90일이다. 폐기 시 인증을 차단하고 암호문도 삭제한다. 새로고침·재접속 시 유효한 선택 토큰을 조회해 복사를 다시 제공한다. 서버 목록 응답에는 원문을 포함하지 않는다.

- 마이그레이션 이전 토큰은 해시만 있으므로 복구할 수 없다. retrievable=false로 표시하고 원문 없음과 명시적인 새 토큰 발급을 안내한다. 자동으로 대체 발급하거나 기존 토큰을 폐기하지 않는다.

<a id="api"></a>

## 12. API

- 기본 경로: /api/organizations/{organization_id}/workspaces/{workspace_id}/mcp-connections

- GET: 본인 연결 목록·종합 상태·retrievable. 비밀 값 제외.
- POST: 명시적 새 발급. 사용자가 작성한 1~120자의 토큰 이름을 공백 제거 후 저장한다. 이름은 클라이언트 종류가 아니라 사용 위치·용도를 구분한다.
- POST /{connection_id}/secret: 본인 토큰 원문 조회. CSRF 검사 및 Cache-Control: no-store.
- DELETE /{connection_id}: 본인 토큰 폐기와 암호문 제거.

- 서버가 소유하는 pending, verified, reauth_required 상태를 사용한다. verified는 성공한 MCP 사용 기록이며 실시간 접속을 뜻하지 않는다. 연결 확인 전에는 작업 기능을 잠그고, 확인 후 활성화한다. 작업공간을 선택하면 작업공간 정보와 MCP 연결 탭이 있는 패널을 연다. 연결 확인 전에는 MCP 연결 탭을 먼저 표시하며 이미 연결된 공간은 마지막 탭 선택이 없으면 작업공간 정보 탭을 표시한다. MCP 연결 탭의 목록은 외부 MCP 서버가 아니라 본인이 발급한 작업공간 연결 토큰이다. 이미 연결된 공간에서는 작업 화면으로 이동할 수 있다. 작업공간 사이드바에는 별도 MCP 연결 버튼을 두지 않는다.

<a id="다운로드-zip"></a>

## 13. 다운로드 ZIP

- 브라우저는 다운로드 직전에 선택 토큰을 다시 조회해 유효성을 확인한다. ZIP은 공통 파일과 지원하는 13개 클라이언트·18개 환경의 설정 디렉터리로 구성한다.

| 파일 | 내용 |
| --- | --- |
| clients/&lt;client&gt;/&lt;environment&gt;/mcp-settings.json / .yaml / .toml | 해당 클라이언트·환경의 실제 네이티브 설정 |
| clients/&lt;client&gt;/&lt;environment&gt;/register.sh | 등록 명령을 지원하는 환경의 POSIX 셸 명령 |
| credentials.json | 선택 토큰 ID와 토큰 값 |
| connection.json | 작업공간과 전체 클라이언트별 대상 경로·인증·등록 명령·공식 문서 목록 |
| README.txt | 워크스페이스에 놓인 ZIP을 적용할 AI 지침 |

- 직접 토큰 값을 요구하는 클라이언트 설정의 PASTE_TOKEN_HERE는 선택 토큰으로 바꾼다. 환경변수나 VS Code inputs를 사용하는 설정은 참조를 유지하고 credentials.json의 값을 해당 방식으로 적용한다. ZIP에는 비밀 값이 포함되므로 개인 임시 위치에서 처리하며 저장소에 커밋하지 않는다. 일반 화면의 설정·설치 URI에는 비밀 값을 넣지 않는다.

- 파일명에는 작업공간·전체 클라이언트 표시·토큰 ID가 들어간다. 토큰이나 작업공간이 바뀌면 현재 선택에 맞는 파일명과 지침을 다시 생성한다. 지침 복사는 다운로드 기록에 의존하지 않으며 토큰 원문 조회나 ZIP 생성 없이 처리한다. AI 지침은 `첨부한`이라고 표현하지 않고 워크스페이스 루트에 놓인 해당 ZIP 파일명을 명시하며 다운로드 파일의 README와 동일하다. ZIP을 워크스페이스 안의 임시 디렉터리에 풀고, 기존 설정 병합, 안전한 인증 값 적용, 실제 MCP 도구 목록 확인을 순서대로 진행한다. 설정과 연결 확인이 끝나면 워크스페이스 루트의 원본 ZIP과 압축을 풀어 만든 임시 디렉터리를 삭제하라고 지시한다. 브라우저 다운로드 저장 완료는 사용자 브라우저가 결정하므로 UI는 다운로드 시작으로 표시한다. 실제 저장 파일과 ZIP 구조·CRC는 브라우저 테스트에서 확인한다.

- AI 지침 자체에는 토큰 원문을 넣지 않는다. 자동 복사 실패 시 직접 복사할 텍스트를 표시한다. 설정 파일 생성·조회 실패에는 결과 메시지를 표시하고 자동 토큰 발급으로 우회하지 않는다. ZIP에는 발급자의 토큰 원문이 들어가므로 팀원에게 전달하지 않는다. 팀원은 `token.create` 권한을 위임받아 자신의 토큰으로 ZIP을 새로 다운로드한다.

<a id="클라이언트와-검증"></a>

## 14. 클라이언트와 검증

- 13개 클라이언트·18개 환경을 기존 설정 어댑터로 지원한다. 상세 출처와 실제 클라이언트별 기존 실행 검증 수준은 mcp-clients.md에 있다. 이번 파일 전달 검증은 실제 모든 에디터를 실행했다는 의미가 아니다.

- tests/connections/browser/mcp-handoff.cjs: 하나의 ZIP에 전 클라이언트·환경 설정 저장·CRC·설정과 지침 일치,
  재접속·토큰 선택 복원·재복사, 자동 발급 없음, 전환 중 늦은 응답, 생성·조회 실패,
- 복사 실패, legacy/폐기 상태, 많은 목록과 좁은 화면.
- tests/connections/browser/mcp-onboarding.cjs: 동일 검증의 기존 진입점.
- tests/workspaces/browser/workspace-start.cjs: 작업공간 탐색·전환·복원·아이콘 회귀.
- scripts/verify-mcp-handoff.sh: 폐기 가능한 PostgreSQL에 마이그레이션 적용·역적용·재적용,
  비슈퍼유저 RLS 환경에서 실제 API·MCP SDK와 토큰 암호화·조회·CSRF·소유권·만료·폐기·권한 회수 검사.
- tests/workspaces/regression/test_workspace_ui.py 및 tests/mcp/regression/test_mcp_server.py: 기본 UI·MCP 등록 계약.

- 스키마는 0017 (선행 0016)이다. 운영에서는 API 재시작 전에 upgrade head를 적용한다.

<a id="토큰-목록과-영구-삭제"></a>

## 15. 토큰 목록과 영구 삭제

- 오른쪽 목록은 본인이 해당 작업공간에서 발급한 모든 토큰을 표시한다. 선택 메뉴에는 원문 조회가 가능한 유효 토큰만 포함하며 만료·폐기 토큰은 제외한다. 폐기된 본인 토큰은 DELETE /{connection_id}/purge로 연결 기록과 인증 토큰을 함께 영구 삭제한다. 활성 토큰은 먼저 폐기해야 하며 다른 사용자의 토큰은 삭제할 수 없다.

- 2026-09-06 검증: 실제 PostgreSQL 통합 테스트에서 두 DB 기록 삭제, 반복 삭제 404, 활성 토큰 409, 타인 요청 404, CSRF 실패 403을 확인했다. 브라우저 테스트에서 클라이언트별 목록, 만료 토큰 선택 제외, 폐기 후 영구 삭제 및 새로고침 이후 제거 상태를 확인했다. 직접 설정 안내는 항상 펼치며 안내 본문은 기본 글자색을 상속한다.

<a id="여러-서버-프로세스에서의-mcp-전송"></a>

## 16. 여러 서버 프로세스에서의 MCP 전송

- HTTP MCP는 `stateless_http=True`로 제공한다. 프로세스 메모리에 세션을 저장하면 2개 이상의 API 워커 사이에서 후속 요청이 다른 워커로 전달될 때 세션 404가 발생한다. 작업공간·사용자 권한과 토큰 검사는 각 요청에서 유지한다. 전송 세션을 없애는 것은 영속 토큰 및 연결 기록을 삭제하는 것과 다르다.

- 2026-09-06: 독립 ASGI 앱 두 개를 사용해 2025-11-25 초기화 이후 다른 워커로 tools/list를 보내는 테스트에서 수정 전 404를 재현했고 수정 후 통과했다. 실제 2-worker 배포 반영 후 Codex 시작을 5회 반복해 모두 connected 및 도구 33개 조회를 확인했다.

<a id="mcp"></a>

## 17. mcp

- The MCP endpoint is an authenticated resource server at `/mcp` internally and at `/factory/mcp` through the production proxy. It accepts only revocable `afm_` API bearer tokens and maps each tool to an explicit token scope. Token scope never replaces RBAC: every call also verifies organization and Workspace membership before applying transaction-local RLS context.

- Six fixed resources describe the Workspace Activities. Read tools expose Workspace, Document, Agent, schedule, integration, log, and test status data without credentials or internal storage keys. Mutation tools return durable Job identities when introduced; long-running work is never held inside one MCP request. Tool names and schemas are versioned API surface and breaking changes require a new tool name or server major version.

<a id="migration"></a>

## 18. migration

- The SaaS application is the sole Workspace runtime and Document authority. Legacy plugin launchers, copied browser assets, project-local Workspace state, and SQLite Workspace projections are unsupported after cutoff. Do not delete a legacy Document tree merely because the application starts successfully.

<a id="migration-procedure"></a>

## 19. Migration procedure

1. Stop writers to the legacy project-local Document tree.
2. Create a recoverable backup outside the source tree.
3. Run `python -m app.modules.document.legacy_import --source <project>
   --manifest .backup/legacy-documents.json` without `--apply`.
4. Review `item_count`, each source-relative path, size, and SHA-256 digest.
5. Ensure all packages fit `AGENT_FACTORY_DOCUMENT_MAX_UPLOAD_BYTES` and the
   destination user, organization, and workspace already exist.
6. Add `--apply --organization-id <uuid> --workspace-id <uuid> --user-id
   <uuid>`. The configured PostgreSQL and S3-compatible services receive the
- records and immutable revision bodies.
7. Run the dry run again and compare its `items_sha256` with the retained
   manifest. Confirm destination Document counts and download representative
- revisions for an independent hash check.
8. Keep the backup through the retention period. Remove the old tree only as a
   separate, explicitly approved operation.

- The importer is source-preserving and resumable. A destination slug with the same recorded legacy digest is skipped; a different digest fails closed. A multi-file package becomes a deterministic ZIP revision, retaining every relative file path and byte sequence. Symlinks, special files, and empty packages are rejected.

<a id="observability"></a>

## 20. observability

- Audit events are append-only security records, distinct from diagnostic logs. Database triggers reject updates and deletes. Mutation auditing records route, outcome, request ID, actor and tenant identifiers, but never request bodies, tokens, credentials, or document content. Audit write failure is logged without changing the original HTTP response; production alerting must treat it as urgent.

- Structured JSON logs carry the same request ID returned to clients. OpenTelemetry establishes the tracing provider and Prometheus exposes bounded route-template counters and latency histograms at `/metrics`. Access logs and audit metadata must be covered by documented retention and privacy policies before production.

<a id="operations"></a>

## 21. operations

<a id="release-and-rollback"></a>

## 22. Release and rollback

- Build immutable images tagged with the Git SHA, scan them, deploy migrations as a one-shot release task, then roll API instances start-first and workers after API readiness succeeds. Migrations must be expand/contract compatible with the previous release. Roll back the image immediately on elevated errors; never downgrade a migration until its downgrade was rehearsed against a restored copy.

<a id="probes-and-scaling"></a>

## 23. Probes and scaling

- `/live` checks only the process. `/ready` checks authoritative PostgreSQL and removes an instance from traffic on failure. The public probe paths are `/factory/live` and `/factory/ready`; the proxy actively probes internal `/ready`. Scale stateless API replicas on concurrency/latency and workers per named queue on queue age, not only CPU. Run exactly one Beat scheduler; database locks and idempotency remain the final duplicate-execution defense.

<a id="backup-and-recovery"></a>

## 24. Backup and recovery

- Run `deploy/backup.sh` into encrypted, immutable remote storage. Retain daily, weekly, and monthly generations according to policy. Each quarter, restore both PostgreSQL and object storage into an isolated account, run migrations and smoke tests, verify Document checksums, and record achieved RPO/RTO in audit history.

<a id="alerts-and-cost"></a>

## 25. Alerts and cost

- Page on readiness failure, sustained 5xx rate, authentication spikes, audit write failures, dead jobs, queue age, database saturation, backup failure, and object-store errors. Ticket on p95 latency, vector-index growth, webhook retry rate, email delivery, and expiring OAuth credentials. Track cost by Workspace from Agent token usage, storage bytes, vector chunks, job runtime, and egress.

<a id="search"></a>

## 26. search

- Document search is a rebuildable projection, never the authority for Document content. Each Workspace owns one or more embedding profiles recording provider, model, and dimensions. The initial deployment standardizes on 1,536 dimensions so one HNSW cosine index remains predictable.

- Indexing replaces all chunks for the same Document and profile atomically. The indexer reads bytes from the authoritative immutable revision; callers cannot submit alternate text under an existing revision identity. Binary PDF and office files must first produce a text Processed Document. PostgreSQL row-level security applies before retrieval. Search combines vector similarity (70%) with the built-in `simple` full-text configuration (30%). The simple configuration avoids language-specific stemming surprises for mixed Korean, English, identifiers, and source material; language-aware analyzers may be added as distinct profiles.

- Embedding credentials remain server-side. The deterministic provider is only available in local and test environments. Re-embedding is safe because chunks are derived state tied to an immutable Document revision and embedding profile.

- Before production rollout, benchmark representative per-tenant and cross-tenant corpora with `EXPLAIN (ANALYZE, BUFFERS)` and record recall plus p50/p95 latency. Keep the shared table while tenant filtering preserves acceptable recall and latency. Introduce hash partitioning by Workspace only when measured corpus size or tenant skew makes index maintenance or filtered HNSW recall unacceptable.

<a id="security"></a>

## 27. security

- Production and staging reject wildcard hosts/origins, weak auth and integration keys, insecure cookies, and non-HTTPS public URLs at startup. HTTP responses use a same-origin CSP, clickjacking, MIME-sniffing, referrer, permissions, opener, and HTTPS transport protections. CORS is disabled unless exact origins are set.

- Login, webhook, and MCP requests use Redis-backed distributed rate limiting. Sensitive production endpoints fail closed when Redis is unavailable. Webhook signatures, event IDs, payload size, CSRF, upload media/size rules, and safe path resolution provide additional boundary-specific protection. Outbound connector adapters must validate HTTPS URLs and re-check resolved addresses to prevent DNS rebinding before making requests.

- API, worker, and migration database identities are separate. Only the worker role has BYPASSRLS for explicit cross-tenant schedulers; every job reapplies its stored tenant context before domain work. Containers run as UID 10001. Secrets come from deployment secret stores and never from images or source control.

- Backups contain PostgreSQL plus object storage and are valid only after restore tests. Tenant deletion is a staged workflow: suspend access, export on request, soft-delete authoritative rows, expire object versions and derived indexes after retention, then record completion in the immutable audit system.

<a id="workers"></a>

## 28. workers

- PostgreSQL Job rows are authoritative; Celery and Redis provide delivery. Each job has a Workspace-scoped idempotency key, bounded task type and queue, priority, attempt budget, ordered events, and explicit cancellation state. Workers claim jobs under row lock and tenant context before executing handlers.

- Failures retry with bounded exponential backoff. Exhausted jobs enter `dead` with their error and timestamp retained for operator inspection and manual retry. Beat scans schedules every minute and retry/outbox records every thirty seconds. Missing broker publication leaves a queued row with no task ID, which the outbox scan republishes. Duplicate deliveries are harmless because only one worker can move a queued/retry row to running.

- Schedules accept either a five-field cron expression with an IANA timezone or an interval of at least sixty seconds. Task types are pinned to named queues so untrusted payloads cannot select arbitrary Celery tasks. Running cancellation is cooperative; handlers must check durable cancellation at safe boundaries.

<a id="workspaces"></a>

## 29. workspaces

- Workspace is the tenant boundary for Documents, Agents, integrations, schedules, logs, and tests. Personal Workspaces belong to the individual in the product model. The current database adapter represents that ownership with an internal personal organization and owner membership. Organization Workspaces use the same tenant authorization. The final Workspace owner cannot be removed.

- Source repositories are registered by canonical HTTPS, SSH, or Git identity. Filesystem locations are accepted only in local and test environments. The service never creates or reads a project-local `.agent-factory/` directory; authoritative state belongs to PostgreSQL and object storage.

- Workspace reads are safe HTTP operations. Recent-use state is recorded through an explicit CSRF-protected mutation endpoint. Updates carry a revision and fail on concurrent modification rather than silently overwriting newer state.

<a id="workspace-entry-and-navigation"></a>

## 30. Workspace entry and navigation

- The organization toolbar remains visible above both the Workspace list view and an opened Workspace. It contains the product identity, personal/organization selector, and signed-in profile. A separate Workspace toolbar below it contains the Workspace selector and persistent create/open menu. Organization changes load only the selected ownership context through the authenticated API.

- The first login has no Workspace selected; later refreshes restore an authorized saved selection. The single Activity Bar shows the Workspace-list icon, and its sidebar shows actual Workspaces, a name filter, and creation control. The unselected content area shows the product mark, create/open actions, and server-backed recent visits. Empty, loading and failed discovery are distinct states with retry. Opening a Workspace changes the icons in that same Activity Bar and reveals its Primary Sidebar and Workspace area. The Workspace-list icon remains in that same bar after selection, providing a return to the Workspace list. There is no separate common-icon group or second Workspace Activity Bar; the organization toolbar is a separate parent context. Icon visibility and order preferences are keyed by user, organization and Workspace in browser storage; switching restores the target Workspace preferences and never inherits a different Workspace's order. Opening the list preserves the selected Workspace and its document views; late responses from a previously selected Workspace cannot repopulate another one.

- Creation asks for a name and uses the selected ownership context. Users with no personal tenant can create one through the authenticated, CSRF-protected `POST /api/account/personal-workspaces` operation; the server resolves ownership from the caller, serializes first-use provisioning, restores caller privileges, and applies normal Workspace authorization. New external-login users no longer receive an automatically created Workspace. Existing Workspaces remain intact.

- The selected Workspace shows MCP setup in its body until the current user has a verified connection. Its menu can reopen setup to add or revoke client tokens. The scoped MCP URL binds the target Workspace on the server; explicit tool IDs are unnecessary and conflicting IDs are rejected. Successful authenticated MCP requests establish connection evidence in PostgreSQL. Configuration copy and installation clicks do not verify a connection. See [MCP connections](#mcp-connections) for state, authentication, APIs, VS Code setup and integration verification. Automatic directory binding and Skill delivery remain separate work.

- The runtime uses compact rows, SVG icons, subtle region borders, visible keyboard focus, native dialogs, and a stacked sidebar/content layout on narrow screens.

- Focused checks:

```sh
.venv/bin/pytest tests/workspaces/regression/test_workspace_ui.py tests/workspaces/regression/test_workspace_management.py tests/identity/regression/test_authentication.py tests/workspaces/regression/test_personal_workspaces.py -q
NODE_PATH=<directory-containing-playwright> node tests/workspaces/browser/workspace-start.cjs
```

- The browser check uses synthetic HTTP API fixtures, verifies empty/create/open/ switch/list/error/late-response behavior under `/factory`, and saves desktop and mobile screenshots under `/tmp/workspace-*.png`. It does not validate a live MCP client connection or production database provisioning.

<a id="panel-presentation-2026-09-05-revision"></a>

## 31. Panel presentation (2026-09-05 revision)

- Spacing, typography, indentation and scroll behavior follow [Workspace UI conventions](../rule-ui/SKILL.md#workspace-ui).

- The supplied VS Code screenshot is the visual reference for the complete shell. The header sits above one Activity Bar and the sidebar/editor grid. Sidebar and editor surfaces have a 5px gap, 1px neutral borders and 7px corner radii over a #111111 shell background, with #181818 panel surfaces. Compact titles, 23px Workspace rows, 52px activity buttons with 8px captions and 24px existing editor tabs preserve the reference's density. The separator resizes both the list and selected sidebars; keyboard resizing remains available. Narrow screens stack sidebar and editor. Split-editor functionality is not added by this visual revision.

- The Activity Bar also has a 1px border and rounded corners. Its 60px column keeps the small Korean captions visible beneath each icon, including Workspace.

- Clicking the Workspace-list icon opens the list while retaining the selected Workspace, its activity icons and loaded document views. Clicking a Workspace activity returns to that view. Only loading a different ownership context clears the previous selection and its loaded state. The UI has no separate home or start-screen action.

- All authored Korean UI labels use `작업공간`, including the picker, creation, account and admin views. Workspace identifiers, API paths and stored user names are unchanged. The picker placeholder opens the list without clearing selection.

- Selection and view state survive a refresh in the same browser tab using sessionStorage keyed by authenticated user and ownership context. Restoration only uses Workspaces returned by current authorized discovery; missing or inactive Workspaces discard stale selection. Picker mode keeps the selected Workspace and its icons. Activity preferences continue to use their separate user/Workspace keys. No credentials are stored with selection state.

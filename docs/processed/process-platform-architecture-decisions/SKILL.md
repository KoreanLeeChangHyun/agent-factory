---
name: platform-architecture-decisions
description: 플랫폼 아키텍처 결정 이력을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/specification/design-platform/adr/ADR-001-python-typescript-monorepo.md
  - docs/specification/design-platform/adr/ADR-002-application-runtime-boundaries.md
  - docs/specification/design-platform/adr/ADR-003-workbench-json-schema.md
  - docs/specification/design-platform/adr/ADR-004-single-workbench-registry.md
  - docs/specification/design-platform/adr/ADR-005-native-renderer-and-mcp-app-sandbox.md
  - docs/specification/design-platform/adr/ADR-006-postgresql-pgvector-and-rls.md
  - docs/specification/design-platform/adr/ADR-007-draft-publish-immutable-release.md
  - docs/specification/design-platform/adr/ADR-008-connection-references-and-server-secrets.md
  - docs/specification/design-platform/adr/ADR-009-incremental-port-and-rollback.md
  - docs/specification/design-platform/adr/ADR-010-design-system-assets-and-theme.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 플랫폼 아키텍처 결정 이력

<a id="기록의-성격"></a>

## 1. 기록의 성격

- 과거 결정과 대안·구현 기록입니다. 현재 규칙은 `docs/skills/`에서 확인합니다.
- 고객 코드 작성, contracts/workbench 묶음, jobs 명칭, 앱·패키지별 테스트와 직접 실행 명령은 후속 사용자 결정이 우선합니다.

<a id="adr-001-python-typescript-monorepo"></a>

<a id="adr-001-pythontypescript-모노레포와-잠금-파일"></a>

## 2. ADR-001: Python·TypeScript 모노레포와 잠금 파일

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: RF-100 이후의 신규 Workbench 코드와 순차 포팅

<a id="맥락"></a>

## 3. 맥락

- React 렌더러와 Python 도메인이 같은 JSON Schema를 소비해야 하며, 현행 단일 Python 패키지의 배포 동작은 포팅 동안 유지해야 한다. 언어별 변경을 별도 저장소로 나누면 계약 변경을 한 검증 단위에서 고정하기 어렵고, 반대로 모든 코드를 한 패키지에 두면 실행 단위와 의존 경계가 흐려진다.

<a id="결정"></a>

## 4. 결정

- 하나의 저장소 안에 `apps/`, `packages/`, `contracts/`를 둔다. TypeScript는 pnpm workspace와 루트 `pnpm-lock.yaml`, Python은 uv workspace와 루트 `uv.lock`을 각각 사용한다. 내부 JavaScript 의존성은 `workspace:` 범위로 제한한다. 언어 중립 schema는 `contracts/`만 원본이며 생성된 Python·TypeScript 파일은 각각 `packages/contracts-py`, `packages/contracts-ts`에 둔다. 루트 `Makefile`은 두 생태계의 재현 가능한 공통 gate를 호출하되 각 앱과 패키지가 자체 단위 테스트를 소유한다.

<a id="대안"></a>

## 5. 대안

- 저장소 분리: 계약 원자성과 포팅 추적성이 약해져 제외한다.
- Node 백엔드로 통일: 현행 Python 문서·검색·worker 자산을 불필요하게 재작성하므로 제외한다.
- 기존 단일 `pyproject.toml`에 프런트 자산만 추가: 배포·재사용 경계를 표현하지 못해
  전환 호환 경로로만 유지한다.

<a id="결과와-적용"></a>

## 6. 결과와 적용

- 첫 scaffold는 Documents vertical slice에 필요한 앱·패키지만 만든다. 빈 최종 트리를 먼저 만들지 않는다. 현행 `pyproject.toml`, wheel, `Dockerfile`은 새 API/worker 이미지가 같은 행동을 검증할 때까지 유지한다. 잠금 파일 생성은 RF-200~203에서 실제 의존성과 함께 수행한다.

- 계약 소유자는 `.codex/skills/rule-workbench-structure/references/target-structure.md`이며, 현재 제품 행동은 계속 `.codex/skills/{info-platform,design-platform,rule-platform}/references/`가 소유한다. 본 ADR은 그 요구사항을 복제하지 않는다. 제거 기준은 새 공통 gate, wheel/image 비교, rollback 경로가 통과하고 현행 단일 패키지 소비자가 없다는 참조 검사가 완료되는 것이다.

<a id="adr-002-application-runtime-boundaries"></a>

<a id="adr-002-fastapi-제어면-react-workbench-python-worker"></a>

## 7. ADR-002: FastAPI 제어면, React Workbench, Python worker

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: `apps/web`, `apps/api`, `apps/worker`

<a id="맥락"></a>

## 8. 맥락

- 고객 정의 화면과 작성기는 복잡한 브라우저 상태를 요구하지만 문서 처리, 검색 및 durable Job 구현은 Python에 있다. 현행 router, MCP tool, worker handler에 규칙을 반복하면 HTTP, MCP와 예약 실행의 의미가 갈라진다.

<a id="결정"></a>

## 9. 결정

- React·TypeScript는 브라우저 Workbench host와 작성기를 소유한다. FastAPI는 HTTP와 MCP composition root 및 얇은 adapter를 소유한다. Python worker와 scheduler는 별도 process와 container command로 실행하지만 API와 동일한 `platform-core` use case를 조립한다. `platform-core`에는 FastAPI, Celery, SQLAlchemy, Redis, MCP 또는 provider SDK import를 허용하지 않는다. API/worker에서 기술 구현은 `platform-adapters`의 port 구현으로 주입한다.

<a id="대안"></a>

## 10. 대안

- 서버 템플릿과 직접 DOM 조작만 확장: 작성기와 선언형 renderer의 결합 비용 때문에 제외한다.
- Node 전체 스택: Python 기능 재작성 비용 때문에 제외한다.
- 초기부터 마이크로서비스: 계약과 트랜잭션 경계가 변하는 단계의 운영 비용 때문에 제외한다.

<a id="결과와-적용"></a>

## 11. 결과와 적용

- `app/main.py`, `app/router`, `app/mcp`, `app/worker`, `app/scheduler`는 기능 플래그가 있는 compatibility 경로로 유지한다. Documents slice에서 같은 use case를 새 HTTP/MCP/worker composition이 호출한 뒤 도메인별로 이동한다. framework 독립성은 금지 import 검사로 강제한다. 인증·CSRF·RBAC·RLS의 현행 의미는 adapter 이동으로 변경하지 않는다.

- 배치와 권한 계약은 `info-platform`/`design-platform`/`rule-platform`의 authentication, authorization, workers, operations가 계속 소유한다. 기존 entrypoint 제거 조건은 API 결과 비교, worker idempotency/cancellation, MCP schema, image/smoke 및 즉시 rollback 검증이 모두 통과하는 것이다.

<a id="adr-003-workbench-json-schema"></a>

<a id="adr-003-json-schema-기반-workbench-계약-v1"></a>

## 12. ADR-003: JSON Schema 기반 Workbench 계약 v1

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: Workbench 정의·release·descriptor·view state·appearance

<a id="맥락"></a>

## 13. 맥락

- Python 서버와 TypeScript renderer가 고객 정의를 같은 방식으로 거부하거나 수용해야 한다. 언어별 모델을 원본으로 사용하면 드리프트가 생기고 고객 정의에 실행 코드가 들어갈 위험이 있다.

<a id="결정"></a>

## 14. 결정

- `contracts/schemas/`의 JSON Schema를 유일한 실행 계약 원본으로 사용한다. v1은 definition, release, descriptor, sidebar, panel, component, binding, action, view-state와 ThemeProfile을 각각 닫힌 객체로 정의한다. 외부 `$ref`, 재귀, executable expression, raw CSS/SVG, import 경로, credential, raw header, 임의 URL을 금지한다. JSON 크기·깊이·컴포넌트 수·문자열 길이와 검증 시간을 제한한다. 공개 component/action/binding은 versioned ID만 참조한다.

- Python과 TypeScript 타입 및 validator는 생성물이며 직접 수정하지 않는다. 같은 valid/invalid/ compatibility fixture에 같은 판정을 해야 한다. minor 호환 변경과 major breaking 변경을 fixture로 구분하고 schema digest를 release에 고정한다.

<a id="대안"></a>

## 15. 대안

- Pydantic 또는 TypeScript 타입 원본: 다른 언어를 종속시키므로 제외한다.
- 자유 형식 JSON과 런타임 관용 처리: 보안·호환성 실패가 늦게 드러나므로 제외한다.
- 고객 React 코드: 신뢰 경계와 배포 재현성을 깨므로 제외한다.

<a id="결과와-적용"></a>

## 16. 결과와 적용

- RF-100~104에서 source schema, 생성기와 parity gate를 함께 추가한다. Documents fixture가 첫 실제 소비자다. 현행 HTTP/MCP Pydantic schema는 해당 endpoint가 새 계약 adapter로 전환될 때까지 유지한다. 제품별 권한·문서·연동 의미는 `info-platform`/`design-platform`/`rule-platform`에 남고 이 schema에 복사하지 않는다. v1 제거는 새 major renderer와 저장된 모든 release의 호환/마이그레이션 증거 및 rollback 기간이 확보된 뒤에만 가능하다.

<a id="adr-004-single-workbench-registry"></a>

<a id="adr-004-표준고객-작업의-단일-workbenchregistry"></a>

## 17. ADR-004: 표준·고객 작업의 단일 WorkbenchRegistry

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: 작업 목록, 선택, 권한 필터, 상태 복원

<a id="맥락"></a>

## 18. 맥락

- 표준 화면과 고객 화면이 별도 navigation을 가지면 순서, 표시, 권한 및 복원 규칙이 이중화된다. 현재 서버 템플릿의 activity 목록은 포팅 입력이지만 고객 정의의 영구 API가 될 수 없다.

<a id="결정"></a>

## 19. 결정

- `apps/web/src/registry/WorkbenchRegistry`가 code-owned 표준 descriptor, server-owned 고객 release descriptor와 MCP App descriptor를 한 목록으로 조합한다. 세 종류는 동일한 stable ID, 표시 순서, 허용 여부, render mode, selection 및 view-state key 계약을 쓴다. 표준 작업은 제품 코드가 정의하고 고객은 이를 덮어쓰거나 필수 권한을 변경할 수 없다. 서버가 권한을 판정하며 UI 필터는 권한 경계가 아니다.

- 내부에서 작업 목록 항목은 `WorkbenchDefinition`, 게시 snapshot은 `WorkbenchRelease`, 장시간 실행은 `Job`이라 부른다. 사용자 UI 용어는 `작업`을 사용한다.

<a id="대안"></a>

## 20. 대안

- 표준 작업 hard-coded navigation 유지: 상태·권한이 중복되어 제외한다.
- 모든 표준 화면을 즉시 고객 JSON으로 변환: 기능별 projection과 안정화 순서를 무시하므로 제외한다.

<a id="결과와-적용"></a>

## 21. 결과와 적용

- Documents를 첫 표준 descriptor로 등록하고 compatibility adapter로 현행 데이터를 읽는다. 이후 workspace/admin, knowledge, schedule, agent/reporting, integration/MCP 순으로 결과를 비교한다. 현행 `template/workspace/index.html`과 `static/js/workspace.js` navigation은 전환 기간에만 유지한다. 권한/Workspace 계약은 `info-platform`/`design-platform`/`rule-platform`이 소유한다. 제거 조건은 모든 표준 작업의 descriptor, 권한·복원 browser gate, 잔존 route/asset 참조 부재 및 Workspace별 rollback 관측 기간이다.

<a id="adr-005-native-renderer-and-mcp-app-sandbox"></a>

<a id="adr-005-native-allowlist-renderer와-mcp-app-sandbox-분리"></a>

## 22. ADR-005: native allowlist renderer와 MCP App sandbox 분리

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: 고객 선언형 Workbench와 외부 MCP UI

<a id="맥락"></a>

## 23. 맥락

- 대부분의 고객 작업은 일관된 공통 에셋으로 표현할 수 있지만, 외부 공급자의 특수 UI에는 실행 코드가 필요할 수 있다. 두 경로를 같은 DOM 신뢰 수준으로 처리할 수 없다.

<a id="결정"></a>

## 24. 결정

- 고객 선언형 Workbench는 `workbench-runtime`이 검증된 component/action/binding ID만 native React로 렌더링한다. 외부 HTML·JavaScript는 `mcp-app-host`만 로드하며 별도/opaque origin의 iframe, 최소 sandbox attribute, host/resource CSP 교집합, capability negotiation, 정확한 origin/source/message schema 검증, 제한된 download/link 정책과 완전한 teardown을 적용한다. host cookie, storage와 credential 접근은 기본 거부한다. 모든 tool 호출은 서버에서 Workspace 권한과 connection scope를 다시 검사한다.

<a id="대안"></a>

## 25. 대안

- `dangerouslySetInnerHTML` 또는 same-origin script: 데이터 노출과 실행 제어 상실 때문에 제외한다.
- 모든 고객 UI를 iframe으로 처리: native 카탈로그의 접근성·일관성 이점을 잃으므로 제외한다.
- MCP App을 먼저 구현: 실제 외부 UI 사례 없이 capability를 과도하게 열 수 있어 후순위로 둔다.

<a id="결과와-적용"></a>

## 26. 결과와 적용

- Documents native slice와 broad asset catalog가 먼저다. MCP App host는 실제 사례가 확인된 RF-900 이후 별도 보안 gate와 함께 도입한다. 외부 App에는 계산된 read-only theme context만 제공한다. 현행 Document package preview sandbox는 보존하며 MCP AppBridge 구현으로 간주하지 않는다. 보안·MCP 제품 계약은 `info-platform`/`design-platform`/`rule-platform`이 소유한다. 외부 UI 경로의 기본 활성화 조건은 CSP, postMessage, capability, teardown, SSRF와 fallback 검증이며 native 경로 rollback과 독립적이다.

<a id="adr-006-postgresql-pgvector-and-rls"></a>

<a id="adr-006-postgresql-권위-데이터-pgvector-검색-workspace-rls"></a>

## 27. ADR-006: PostgreSQL 권위 데이터, pgvector 검색, Workspace RLS

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: 모든 서버 도메인과 Workbench/ThemeProfile 영속성

<a id="맥락"></a>

## 28. 맥락

- 현재 서비스의 authoritative relational state, revision, Job, audit 및 검색 projection이 PostgreSQL을 기준으로 설계되어 있다. 포팅 중 개발 fixture나 browser storage를 새 권위로 오인하면 tenant 격리와 복구 계약이 약해진다.

<a id="결정"></a>

## 29. 결정

- PostgreSQL만 권위 관계형 저장소로 사용하고 pgvector는 재구축 가능한 검색 projection에 사용한다. tenant row는 `organization_id` 또는 `workspace_id`를 갖고 RLS를 활성화한다. 애플리케이션 RBAC를 먼저 적용하고 transaction-local tenant context와 RLS를 방어 계층으로 함께 쓴다. UUID, timezone timestamp, mutable aggregate revision과 append-only migration 원칙을 유지한다. Redis/queue, object storage와 browser cache는 각자의 delivery/body/cache 책임만 가진다.

<a id="대안"></a>

## 30. 대안

- SQLite를 운영 authority로 유지: RLS와 현행 운영 계약을 충족하지 못해 제외한다.
- 브라우저에 theme/view authority 저장: 사용자 전환·기기 간 복원에 부적합하여 제외한다.
- 검색 store를 문서 원본으로 사용: 재구축 가능한 projection 원칙에 어긋나 제외한다.

<a id="결과와-적용"></a>

## 31. 결과와 적용

- 현행 `app/db/migrations/versions/0001`~`0024`는 배포 이력이므로 수정하지 않고 루트 `migrations/`로 이관할 때 byte/history를 보존한다. Workbench와 ThemeProfile은 새 append-only revision을 추가한다. `platform-core`는 repository port만 알고 SQLAlchemy는 adapter에 둔다. database/search/security 계약은 `info-platform`/`design-platform`/`rule-platform`이 계속 소유한다. 실제 DB gate는 명시적인 일회용 PostgreSQL만 사용하며 `.env` DB에 자동 연결하지 않는다. legacy DB 경로 제거는 clean upgrade, RLS cross-tenant, backup/restore 및 이전 이미지 호환이 검증된 뒤 가능하다.

<a id="adr-007-draft-publish-immutable-release"></a>

<a id="adr-007-draftpublish와-불변-workbenchrelease"></a>

## 32. ADR-007: draft/publish와 불변 WorkbenchRelease

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: WorkbenchDefinition 생명주기와 게시

<a id="맥락"></a>

## 33. 맥락

- 고객이 편집 중인 정의와 실제 사용자가 실행하는 정의를 같은 mutable row로 제공하면 동시 편집, 감사, rollback 및 실행 재현성이 깨진다.

<a id="결정"></a>

## 34. 결정

- `WorkbenchDefinition`은 Workspace 소유 aggregate로 draft/update/archive와 optimistic revision을 가진다. publish는 현재 draft를 완전히 검증한 뒤 schema version, canonical digest, asset version과 actor를 포함한 새 `WorkbenchRelease` snapshot을 한 transaction에서 생성한다. 게시 release는 수정하거나 덮어쓰지 않는다. 변경은 새 definition revision과 새 release를 만든다. preview 권한과 publish 권한을 분리하며 표준 code-owned descriptor는 같은 읽기 projection을 제공하되 고객이 변경할 수 없다.

<a id="대안"></a>

## 35. 대안

- 하나의 mutable JSON row: 실행 이력과 rollback을 재현할 수 없어 제외한다.
- 파일 기반 고객 정의: Workspace RBAC/RLS, 동시성 및 감사 경계를 제공하지 못해 제외한다.

<a id="결과와-적용"></a>

## 36. 결과와 적용

- RF-600~604에서 core 상태 전이, repository port, PostgreSQL adapter와 HTTP/MCP 표현을 순서대로 구현한다. 삭제는 즉시 물리 삭제가 아니라 계약에 맞는 archive/retention 흐름으로 다룬다. 정의/release의 제품 권한과 영속성 계약은 향후 `info-platform`/`design-platform`/`rule-platform`의 owning reference에서 관리한다. 전환 중에는 feature flag가 선택한 release만 새 renderer로 보내며 legacy 화면은 원본 데이터에 대한 rollback 경로로 남긴다. rollback 기간과 release 참조가 끝나기 전에는 snapshot을 제거하지 않는다.

<a id="adr-008-connection-references-and-server-secrets"></a>

<a id="adr-008-connection-reference와-서버-보관-credential"></a>

## 37. ADR-008: connection reference와 서버 보관 credential

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: Binding, 외부 provider, MCP/HTTP connector

<a id="맥락"></a>

## 38. 맥락

- Workbench 정의가 token, header 또는 fetch URL을 포함하면 게시 snapshot, 로그와 브라우저에 비밀이 복제되고 SSRF 경계도 우회된다. 현행 integration과 MCP token 계약은 credential을 서버 측 암호화 경계에서 관리한다.

<a id="결정"></a>

## 39. 결정

- Workbench Binding은 권한이 확인되는 `connection_id`와 allowlisted operation 이름만 저장한다. credential, OAuth verifier, refresh token, webhook secret, raw header, arbitrary URL 및 provider response body는 정의와 browser result에 넣지 않는다. `platform-core`는 Connection 식별자와 capability port만 사용하고, `platform-adapters`가 encrypted secret, OAuth, MCP client와 HTTP connector를 구현한다. 호출마다 사용자·조직·Workspace, token scope, connection scope와 operation 권한을 재검사한다. outbound URL은 allowlist, DNS 재검사, redirect 및 byte/time bound를 적용한다.

<a id="대안"></a>

## 40. 대안

- 정의에 환경변수 이름 또는 header 저장: 배포별 의미와 노출 위험 때문에 제외한다.
- 브라우저에서 provider 직접 호출: credential과 tenant 정책을 우회하므로 제외한다.

<a id="결과와-적용"></a>

## 41. 결과와 적용

- 현행 `app/modules/integration`, `app/modules/mcp_connection`, `app/mcp/integrations.py` 및 secret infrastructure는 adapter 포팅 입력이다. 기존 auth와 암호문은 새 connection schema로 자동 확대하거나 재발급하지 않는다. integrations/MCP/security 계약은 `info-platform`/`design-platform`/`rule-platform`이 소유한다. compatibility adapter 제거 조건은 OAuth/token 갱신, credential 비노출, cancellation/retry, provider fixture, RLS/SSRF와 실제 rollback 검증이며 live provider 호출은 별도 명시 권한 없이는 수행하지 않는다.

<a id="adr-009-incremental-port-and-rollback"></a>

<a id="adr-009-feature-flag-compatibility-adapter와-rollback"></a>

## 42. ADR-009: feature flag, compatibility adapter와 rollback

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: 모든 표준 작업의 단계적 포팅과 legacy 제거

<a id="맥락"></a>

## 43. 맥락

- 파일 이동, renderer 교체와 API 의미 변경을 동시에 수행하면 회귀의 원인을 분리하기 어렵고 복구 경로가 사라진다. 현행 server template과 API에는 admin, planning/reporting, Documents, integration 및 MCP의 다수 행동이 있다.

<a id="결정"></a>

## 44. 결정

- Documents를 첫 vertical slice로 고정한다. 새 React shell은 shadow route로 배포하고 Workspace 단위 feature flag가 legacy/new 경로를 선택한다. compatibility adapter는 현행 API 결과를 새 Workbench binding 형태로 번역하되 도메인 의미를 바꾸지 않는다. 각 표준 작업은 characterization 기준선, API 결과 비교, 권한/tenant, browser state와 운영 계측을 통과한 뒤 개별 전환한다.

- rollback은 이전 이미지뿐 아니라 같은 배포에서 legacy route로 즉시 복귀하고 새 state key를 안전하게 무시/변환할 수 있어야 한다. 오류율, binding latency, publish rollback, stale/error 상태를 관측한다. 제거는 참조 검색, 사용자 잔존 부재, 관측 기간과 복구 연습을 증거로 판단한다.

<a id="대안"></a>

## 45. 대안

- 빅뱅 이동: 회귀 격리와 rollback이 불가능해 제외한다.
- 무기한 이중 구현: 드리프트 비용 때문에 제거 기준을 반드시 둔다.
- Documents가 아닌 가상 Stocks 구현: 실제 제품 행동을 검증하지 못해 제외한다.

<a id="결과와-적용"></a>

## 46. 결과와 적용

- 순서는 Documents, workspace/organization/admin, knowledge, schedule/planning, agent/reporting, integration/MCP이며 공유 기반은 먼저 포팅할 수 있다. 현행 인증 방식, URL/cookie/CSRF 계약과 published migration은 flag와 무관하게 보존한다. 제품 행동의 소유자는 계속 `info-platform`/`design-platform`/`rule-platform`이고 포팅 상태/증거는 날짜가 있는 `docs/processed/notes/`가 소유한다. 어떤 legacy 경로도 관련 제거 조건이 충족되기 전에 삭제하지 않는다.

<a id="adr-010-design-system-assets-and-theme"></a>

<a id="adr-010-broad-공통-에셋-카탈로그와-사용자별-semantic-token-테마"></a>

## 47. ADR-010: broad 공통 에셋 카탈로그와 사용자별 semantic-token 테마

- 상태: 적용됨
- 결정일: 2026-09-12
- 적용 범위: design-system, authoring catalog, ThemeProfile

<a id="맥락"></a>

## 48. 맥락

- 첫 Documents 화면에 필요한 한두 컴포넌트만 제공하면 고객이 일반적인 SaaS 작업을 조합할 수 없다. 반대로 자유 CSS, SVG와 컴포넌트별 색상은 제품 일관성, 접근성 및 보안 검증을 깨뜨린다. 현행 UI kit, inline SVG와 고정 token은 유용한 포팅 입력이지만 사용자별 테마 authority가 없다.

<a id="결정"></a>

## 49. 결정

- `packages/design-system`만 foundations, reviewed assets, primitives, navigation, data-display, layout, patterns, shell surfaces, content와 accessibility를 소유한다. 초기 공개 catalog에는 다수의 작업 아이콘과 flat/group/tree/search/filter/detail-row 사이드바 조합, detail/list-detail/collection/ settings/dashboard/document/split/timeline/kanban 패널, 입력·표·상태·dialog·toast와 loading/empty/ stale/error/permission 상태를 포함한다. 각 항목은 stable version ID, allowed region, prop schema, binding I/O, state/action, 접근성, provenance/license, 예제와 interactive preview를 가진다.

- 모든 공개 에셋은 semantic token만 소비한다. 서버 저장 `ThemeProfile`은 사용자 소유 revision, dark/light/high-contrast 기반과 allowlisted color/density override만 허용한다. 저장 전에 contrast와 focus visibility를 검증한다. 서버가 기기 간 authority이고 user/organization/workspace가 분리된 browser cache는 초기 paint만 보조한다. 로그아웃/사용자 전환 시 격리하며 reduced motion과 high-contrast 접근성 선택이 조직/Workspace 기본보다 우선한다. 임의 CSS, raw SVG, React import와 per-component color override는 금지한다.

<a id="대안"></a>

## 50. 대안

- 현행 CSS를 그대로 공개 API화: vanilla DOM과 생성물 계약을 고정하므로 제외한다.
- fixture 최소 catalog: 고객 조합성 요구를 충족하지 못해 제외한다.
- arbitrary theming: contrast와 일관성을 검증할 수 없어 제외한다.

<a id="결과와-적용"></a>

## 51. 결과와 적용

- `assets/ui-kit/src`는 editable 포팅 입력, `static/ui`는 legacy 생성 runtime, vendor/provenance와 license는 보존 대상으로 분리한다. 기능 전용 chart 좌표나 document preview는 해당 feature에 남긴다. catalog descriptor는 ADR-003 schema를 소비하고 authoring surface도 같은 registry를 쓴다. UI 행동 계약은 `rule-ui`, 제품별 행동은 `info-platform`/`design-platform`/`rule-platform`, 목표 배치는 `rule-workbench-structure`가 소유한다. legacy asset 제거 조건은 byte/provenance 비교, public ID/state/accessibility/visual gate, 모든 소비자 전환과 rollback 관측 기간의 완료다.

- Stage 3에서 `ThemeProfile`의 core port/use case, PostgreSQL adapter와 forced user RLS, revision `0` 기본값에서 시작하는 compare-and-set 저장, semantic palette 검증기, 인증 HTTP compatibility mount 및 React cache/bootstrap/editor 경계를 구현했다. 현행 vanilla Workspace 전체 소비자 전환은 RF-800~804와 RF-1004, sandboxed MCP App theme context는 RF-903 이후 완료 대상으로 유지한다.

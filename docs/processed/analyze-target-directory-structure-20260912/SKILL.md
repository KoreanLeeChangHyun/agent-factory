---
name: target-directory-structure-20260912
description: MCP 클라우드 Workbench 상세 디렉터리 구조을 확인할 때 사용합니다.
document-type: processed
category: analyze
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-12-target-directory-structure.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-12-target-directory-structure
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# MCP 클라우드 Workbench 상세 디렉터리 구조

- 구현 진행 상태와 단계별 완료 조건은 [Workbench 리팩터링 작업 현황](../process-workbench-refactoring-status-20260912/SKILL.md)에서 추적한다.

<a id="결정"></a>

## 1. 결정

- 목표 저장소는 Python과 TypeScript를 함께 관리하는 모노레포로 구성한다. 실행 애플리케이션은 `apps/`, 재사용 가능한 코드와 디자인 시스템은 `packages/`, 언어 중립 계약은 `contracts/`에 둔다.

```text
apps       실행·배포 진입점
packages   재사용 코드와 기술 adapter
contracts  고객 정의와 플랫폼 실행 사이의 언어 중립 계약
tests      둘 이상의 앱·패키지를 관통하는 검증
deploy     컨테이너·프록시·배포·복구
docs       제품 계약·ADR·운영 문서
```

- 가장 중요한 규칙은 다음과 같다.

- 표준 작업과 고객 작업은 동일한 Workbench registry를 사용한다.
- 작업 목록, 사이드바, 패널은 `apps/web`의 단일 shell이 소유한다.
- 고객 정의 해석은 `packages/workbench-runtime`만 담당한다.
- 색상·간격·타이포그래피·아이콘·공통 상호작용은 `packages/design-system`만 소유한다.
- `packages/design-system`은 작업 목록 SVG, 사이드바 구성 요소, 패널 레이아웃을 각각 여러 개 제공하며 고객도 같은 카탈로그를 조합해 작업을 만든다.
- 모든 공통 에셋은 의미 기반 테마 토큰만 사용하고 사용자별 색상·명암·밀도 설정을 일관되게 적용한다.
- HTTP, MCP, worker는 동일한 Python use case를 호출한다.
- 외부 고객 코드는 `packages/mcp-app-host`의 sandbox 밖으로 나오지 않는다.

<a id="전체-트리"></a>

## 2. 전체 트리

```text
agent-factory/
├── apps/
│   ├── web/
│   ├── api/
│   └── worker/
├── packages/
│   ├── design-system/
│   ├── workbench-runtime/
│   ├── mcp-app-host/
│   ├── contracts-ts/
│   ├── contracts-py/
│   ├── platform-core/
│   └── platform-adapters/
├── contracts/
│   ├── schemas/
│   ├── examples/
│   ├── compatibility/
│   └── codegen/
├── migrations/
├── tests/
│   ├── contracts/
│   ├── integration/
│   ├── e2e/
│   └── security/
├── deploy/
│   ├── containers/
│   ├── compose/
│   ├── kubernetes/
│   ├── proxy/
│   ├── smoke/
│   └── backup/
├── docs/
│   ├── specs/
│   ├── adr/
│   └── runbooks/
├── scripts/
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── pyproject.toml
├── uv.lock
├── Makefile
├── .env.example
├── .editorconfig
└── .gitignore
```

<a id="appsweb--react-workbench-호스트"></a>

## 3. `apps/web` — React Workbench 호스트

```text
apps/web/
├── src/
│   ├── main.tsx
│   ├── app/
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   ├── providers.tsx
│   │   ├── error-boundary.tsx
│   │   └── app.test.tsx
│   ├── shell/
│   │   ├── WorkbenchShell.tsx
│   │   ├── TaskList.tsx
│   │   ├── SidebarHost.tsx
│   │   ├── PanelHost.tsx
│   │   ├── ShellContext.tsx
│   │   ├── shell-state.ts
│   │   ├── shell-storage.ts
│   │   └── shell.test.tsx
│   ├── registry/
│   │   ├── WorkbenchRegistry.ts
│   │   ├── standard-workbenches.ts
│   │   ├── customer-workbenches.ts
│   │   └── registry.test.ts
│   ├── standard/
│   │   ├── workspace/
│   │   ├── documents/
│   │   ├── knowledge/
│   │   ├── connections/
│   │   ├── jobs/
│   │   └── audit/
│   ├── authoring/
│   │   ├── WorkbenchListPage.tsx
│   │   ├── WorkbenchEditorPage.tsx
│   │   ├── WorkbenchPreview.tsx
│   │   ├── AssetCatalog.tsx
│   │   ├── ComponentPalette.tsx
│   │   ├── LayoutPalette.tsx
│   │   ├── PropertyEditor.tsx
│   │   ├── BindingEditor.tsx
│   │   ├── ThemeEditor.tsx
│   │   ├── SchemaDiagnostics.tsx
│   │   └── PublicationDialog.tsx
│   ├── api/
│   │   ├── client.ts
│   │   ├── session-api.ts
│   │   ├── workbench-api.ts
│   │   ├── connection-api.ts
│   │   ├── knowledge-api.ts
│   │   └── job-api.ts
│   ├── auth/
│   │   ├── AuthProvider.tsx
│   │   ├── PermissionBoundary.tsx
│   │   └── permissions.ts
│   ├── state/
│   │   ├── tenant-state.ts
│   │   ├── view-preferences.ts
│   │   └── query-keys.ts
│   ├── telemetry/
│   │   ├── browser-events.ts
│   │   └── error-reporting.ts
│   ├── styles/
│   │   ├── app.css
│   │   └── shell.css
│   └── test/
│       ├── setup.ts
│       └── fixtures.ts
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── vitest.config.ts
```

- `shell/`은 세 영역의 배치, 선택과 반응형 동작만 소유한다. 고객 JSON 해석과 component 렌더링은 하지 않는다. `standard/`은 플랫폼 기본 작업의 데이터 조립만 담당하며 Button, Table, Tree를 자체 구현하지 않는다.

<a id="appsapi--fastapi-httpmcp-제어면"></a>

## 4. `apps/api` — FastAPI HTTP·MCP 제어면

```text
apps/api/
├── src/agent_factory_api/
│   ├── __init__.py
│   ├── main.py
│   ├── lifespan.py
│   ├── settings.py
│   ├── composition/
│   │   ├── container.py
│   │   ├── repositories.py
│   │   └── providers.py
│   ├── http/
│   │   ├── router.py
│   │   ├── dependencies/
│   │   │   ├── authentication.py
│   │   │   ├── organization.py
│   │   │   ├── workspace.py
│   │   │   ├── permissions.py
│   │   │   └── idempotency.py
│   │   ├── routes/
│   │   │   ├── sessions.py
│   │   │   ├── organizations.py
│   │   │   ├── workspaces.py
│   │   │   ├── workbenches.py
│   │   │   ├── workbench_releases.py
│   │   │   ├── connections.py
│   │   │   ├── knowledge.py
│   │   │   ├── jobs.py
│   │   │   └── audit.py
│   │   ├── presenters/
│   │   │   ├── errors.py
│   │   │   ├── pagination.py
│   │   │   └── timestamps.py
│   │   └── middleware/
│   │       ├── request_context.py
│   │       ├── security_headers.py
│   │       ├── rate_limit.py
│   │       └── observability.py
│   ├── mcp/
│   │   ├── server.py
│   │   ├── transport.py
│   │   ├── context.py
│   │   ├── resources/
│   │   │   ├── workspace.py
│   │   │   ├── workbenches.py
│   │   │   └── knowledge.py
│   │   └── tools/
│   │       ├── workbenches.py
│   │       ├── search.py
│   │       ├── documents.py
│   │       └── jobs.py
│   └── health/
│       ├── liveness.py
│       └── readiness.py
├── tests/
│   ├── http/
│   ├── mcp/
│   └── middleware/
├── pyproject.toml
└── Dockerfile
```

- `http/`와 `mcp/`는 입력·출력 adapter다. SQL, commit, Workbench 상태 전이는 넣지 않는다. 같은 게시 use case를 HTTP와 MCP가 호출하고 표현만 달리한다.

<a id="appsworker--비동기-실행"></a>

## 5. `apps/worker` — 비동기 실행

```text
apps/worker/
├── src/agent_factory_worker/
│   ├── __init__.py
│   ├── main.py
│   ├── scheduler.py
│   ├── settings.py
│   ├── composition.py
│   ├── claim.py
│   ├── cancellation.py
│   └── handlers/
│       ├── source_sync.py
│       ├── document_parse.py
│       ├── chunk_documents.py
│       ├── create_embeddings.py
│       ├── rebuild_index.py
│       ├── refresh_binding.py
│       └── retention.py
├── tests/
│   ├── test_claim.py
│   ├── test_cancellation.py
│   ├── test_retries.py
│   └── test_handlers.py
├── pyproject.toml
└── Dockerfile
```

- worker는 queue payload의 tenant 정보를 권위로 사용하지 않는다. Job ID로 PostgreSQL의 레코드를 다시 읽고 Workspace, 권한, 취소 상태를 확인한다.

<a id="packagesdesign-system--공통-에셋과-제품-일관성"></a>

## 6. `packages/design-system` — 공통 에셋과 제품 일관성

```text
packages/design-system/
├── src/
│   ├── index.ts
│   ├── foundations/
│   │   ├── tokens/
│   │   │   ├── color.tokens.json
│   │   │   ├── spacing.tokens.json
│   │   │   ├── typography.tokens.json
│   │   │   ├── geometry.tokens.json
│   │   │   ├── motion.tokens.json
│   │   │   └── z-index.tokens.json
│   │   ├── themes/
│   │   │   ├── dark.css
│   │   │   ├── light.css
│   │   │   ├── high-contrast.css
│   │   │   ├── theme-contract.ts
│   │   │   └── apply-theme.ts
│   │   ├── reset.css
│   │   └── global.css
│   ├── assets/
│   │   ├── brand/
│   │   │   ├── logo.svg
│   │   │   ├── symbol.svg
│   │   │   └── wordmark.svg
│   │   ├── icons/
│   │   │   ├── source/
│   │   │   ├── manifest.json
│   │   │   ├── Icon.tsx
│   │   │   └── TaskIcon.tsx
│   │   └── illustrations/
│   ├── primitives/
│   │   ├── Button/
│   │   ├── Field/
│   │   ├── Select/
│   │   ├── Checkbox/
│   │   ├── Status/
│   │   ├── Badge/
│   │   ├── Dialog/
│   │   ├── Popover/
│   │   └── Toast/
│   ├── navigation/
│   │   ├── Tabs/
│   │   ├── Tree/
│   │   ├── ResourceList/
│   │   ├── SearchList/
│   │   ├── FilterBar/
│   │   └── Pagination/
│   ├── data-display/
│   │   ├── Table/
│   │   ├── MetricGrid/
│   │   ├── ChartFrame/
│   │   ├── DefinitionList/
│   │   ├── Markdown/
│   │   └── JsonView/
│   ├── layout/
│   │   ├── Stack/
│   │   ├── Inline/
│   │   ├── Grid/
│   │   ├── SplitPane/
│   │   ├── WorkbenchSurface/
│   │   ├── PageLayout/
│   │   ├── ListDetailLayout/
│   │   ├── CollectionLayout/
│   │   ├── SettingsLayout/
│   │   ├── DashboardLayout/
│   │   ├── DocumentLayout/
│   │   ├── TimelineLayout/
│   │   └── KanbanLayout/
│   ├── patterns/
│   │   ├── ResourceCollection/
│   │   ├── ResourceDetails/
│   │   ├── SettingsForm/
│   │   ├── EmptyState/
│   │   ├── ErrorState/
│   │   └── PermissionState/
│   ├── shell/
│   │   ├── TaskListSurface/
│   │   ├── SidebarSurface/
│   │   └── PanelSurface/
│   ├── content/
│   │   ├── terminology.ko.json
│   │   ├── action-labels.ko.json
│   │   └── status-labels.ko.json
│   └── accessibility/
│       ├── focus.ts
│       ├── keyboard.ts
│       └── live-region.ts
├── catalog/
│   ├── foundations/
│   ├── task-icons/
│   ├── sidebars/
│   ├── panel-layouts/
│   ├── components/
│   ├── patterns/
│   ├── states/
│   └── themes/
├── scripts/
│   ├── build-tokens.mjs
│   ├── build-icons.mjs
│   └── verify-assets.mjs
├── tests/
│   ├── accessibility/
│   ├── visual/
│   └── contracts/
├── package.json
└── tsconfig.json
```

- 공통 에셋은 이미지 모음이 아니라 다음 전체를 의미한다.

- foundations: 색상, 간격, 글꼴, 경계, elevation, motion
- assets: 로고, 검토된 아이콘, 필요한 일러스트
- primitives: 버튼, 입력, 상태, 대화상자
- patterns: 목록, 상세, 설정, 빈 화면, 오류와 권한 거부
- shell surfaces: 작업 목록, 사이드바, 패널
- task icons: 작업 목록에서 선택할 수 있는 검토된 SVG와 상태 표현
- sidebar assets: 평면 목록, 그룹, 트리, 검색·필터, 상세 행, 상태와 보조 동작
- panel layouts: 상세, 목록-상세, 컬렉션, 설정, 대시보드, 문서, 분할, 타임라인과 칸반
- content: 동일한 의미에 사용하는 한국어 용어와 동작 라벨
- accessibility: 포커스, 키보드, live region 계약

- 카탈로그는 내부 표준 작업뿐 아니라 고객 작업 작성기가 사용하는 제품 기능이다. 각 항목은 안정적인 버전 ID, 허용 영역, 속성 schema, binding 입출력, 지원 상태와 action, 접근성 계약, 예제와 미리보기를 제공한다. 고객 정의는 SVG 본문, React import 경로나 임의 CSS 대신 `documents@1`, `resource-tree@1`, `list-detail@1` 같은 등록 ID를 참조한다.

- 사용자 테마는 `ThemeProfile`로 관리한다. dark, light, high-contrast 기본 테마 위에서 허용된 의미 토큰의 색상과 밀도를 조정하며, 저장 전에 대비와 포커스 가시성을 검증한다. 임의 CSS와 컴포넌트별 색상 덮어쓰기는 허용하지 않는다. 서버에 저장한 사용자 선호가 기기 간 권위 상태이며 브라우저 캐시는 최초 렌더링을 보조하는 용도로만 사용한다. 외부 MCP App에는 계산된 읽기 전용 테마 context만 전달한다.

- 각 컴포넌트 디렉터리는 기본적으로 다음 단위를 가진다.

```text
Button/
├── Button.tsx
├── Button.css
├── Button.test.tsx
├── Button.visual.spec.ts
└── index.ts
```

- 기능 화면은 raw 색상, 임의 SVG, 자체 버튼, 자체 오류 UI를 만들지 않는다. 일반적인 SaaS 작업을 코드 없이 구성할 수 있도록 작업 목록, 사이드바와 패널에 충분히 넓은 공통 에셋 카탈로그를 계획해서 제공한다. 의미가 겹치는 변형은 추가하지 않으며 한 기능에만 필요한 차트 좌표나 문서 미리보기 표현은 기능 소유로 남긴다.

<a id="packagesworkbench-runtime--고객-정의-렌더러"></a>

## 7. `packages/workbench-runtime` — 고객 정의 렌더러

```text
packages/workbench-runtime/
├── src/
│   ├── index.ts
│   ├── registry/
│   │   ├── ComponentRegistry.ts
│   │   ├── ActionRegistry.ts
│   │   ├── BindingRegistry.ts
│   │   └── builtin-components.ts
│   ├── renderer/
│   │   ├── WorkbenchRenderer.tsx
│   │   ├── SidebarRenderer.tsx
│   │   ├── PanelRenderer.tsx
│   │   ├── ComponentNode.tsx
│   │   ├── RenderBoundary.tsx
│   │   └── UnsupportedComponent.tsx
│   ├── bindings/
│   │   ├── BindingClient.ts
│   │   ├── BindingCache.ts
│   │   ├── input-mapping.ts
│   │   ├── output-validation.ts
│   │   └── cancellation.ts
│   ├── actions/
│   │   ├── dispatch.ts
│   │   ├── navigate.ts
│   │   ├── refresh.ts
│   │   ├── select.ts
│   │   └── submit.ts
│   ├── state/
│   │   ├── WorkbenchStore.ts
│   │   ├── reducer.ts
│   │   ├── selectors.ts
│   │   └── persistence.ts
│   ├── validation/
│   │   ├── validate-definition.ts
│   │   ├── limits.ts
│   │   └── diagnostics.ts
│   ├── security/
│   │   ├── safe-links.ts
│   │   ├── content-policy.ts
│   │   └── redact.ts
│   └── telemetry/
│       ├── events.ts
│       └── timings.ts
├── tests/
│   ├── renderer/
│   ├── bindings/
│   ├── validation/
│   └── fixtures/
├── package.json
└── tsconfig.json
```

- 고객 schema는 React import 경로 대신 `resource-table@1`, `metric-grid@1` 같은 공개 ID를 사용한다. registry만 공개 ID를 디자인 시스템 컴포넌트에 연결한다.

<a id="packagesmcp-app-host--외부-ui-격리"></a>

## 8. `packages/mcp-app-host` — 외부 UI 격리

```text
packages/mcp-app-host/
├── src/
│   ├── index.ts
│   ├── host/
│   │   ├── McpAppView.tsx
│   │   ├── bridge-lifecycle.ts
│   │   └── capability-negotiation.ts
│   ├── sandbox/
│   │   ├── SandboxFrame.tsx
│   │   ├── sandbox-attributes.ts
│   │   └── teardown.ts
│   ├── messaging/
│   │   ├── channel.ts
│   │   ├── validate-message.ts
│   │   └── origins.ts
│   └── policy/
│       ├── csp.ts
│       ├── permissions.ts
│       ├── downloads.ts
│       └── external-links.ts
├── tests/
│   ├── sandbox.test.tsx
│   ├── messaging.test.ts
│   └── teardown.test.ts
├── package.json
└── tsconfig.json
```

- 선언형 고객 작업은 디자인 시스템을 강제하므로 제품 일관성을 보장할 수 있다. MCP App은 sandbox 안의 독립 UI이므로 완전한 시각 통제는 불가능하다. 대신 theme context와 읽기 전용 token CSS를 제공하고, 작업 목록과 사이드바 등 host chrome은 항상 플랫폼 디자인을 유지한다.

<a id="contracts와-생성-패키지"></a>

## 9. `contracts`와 생성 패키지

```text
contracts/
├── schemas/
│   ├── common/v1/
│   ├── workbench/v1/
│   │   ├── definition.schema.json
│   │   ├── release.schema.json
│   │   ├── descriptor.schema.json
│   │   ├── sidebar.schema.json
│   │   ├── panel.schema.json
│   │   ├── component.schema.json
│   │   ├── binding.schema.json
│   │   ├── action.schema.json
│   │   └── view-state.schema.json
│   ├── appearance/v1/
│   │   └── theme-profile.schema.json
│   ├── events/v1/
│   └── mcp/v1/
├── examples/
│   ├── workbenches/reference/
│   │   ├── valid.json
│   │   └── expected-render.json
│   ├── knowledge-search/
│   └── invalid/
│       ├── unknown-component.json
│       ├── secret-in-definition.json
│       ├── excessive-depth.json
│       └── external-ref.json
├── compatibility/
│   ├── v1-minimum.json
│   └── policy.md
└── codegen/
    ├── generate-typescript.mjs
    ├── generate-python.py
    └── verify-generated.sh

packages/contracts-ts/
├── src/generated/
├── src/validators/
├── package.json
└── tsconfig.json

packages/contracts-py/
├── src/agent_factory_contracts/generated/
├── tests/
└── pyproject.toml
```

- JSON Schema가 원본이며 `contracts-ts`와 `contracts-py`는 생성 대상이다. 생성 파일은 직접 수정하지 않는다.

<a id="packagesplatform-core--python-도메인과-use-case"></a>

## 10. `packages/platform-core` — Python 도메인과 use case

```text
packages/platform-core/
├── src/agent_factory_core/
│   ├── shared/
│   │   ├── ids.py
│   │   ├── clock.py
│   │   ├── revision.py
│   │   ├── pagination.py
│   │   └── result.py
│   ├── identity/
│   ├── organizations/
│   ├── workspaces/
│   ├── workbenches/
│   │   ├── domain.py
│   │   ├── commands.py
│   │   ├── queries.py
│   │   ├── policies.py
│   │   ├── ports.py
│   │   ├── events.py
│   │   └── errors.py
│   ├── connections/
│   │   ├── domain.py
│   │   ├── commands.py
│   │   ├── queries.py
│   │   ├── policies.py
│   │   └── ports.py
│   ├── knowledge/
│   │   ├── documents.py
│   │   ├── collections.py
│   │   ├── chunks.py
│   │   ├── indexes.py
│   │   ├── retrieval.py
│   │   ├── commands.py
│   │   ├── queries.py
│   │   └── ports.py
│   ├── executions/
│   │   ├── jobs.py
│   │   ├── attempts.py
│   │   ├── cancellation.py
│   │   ├── commands.py
│   │   └── ports.py
│   └── audit/
│       ├── events.py
│       ├── queries.py
│       └── ports.py
├── tests/
│   ├── workbenches/
│   ├── connections/
│   ├── knowledge/
│   └── executions/
└── pyproject.toml
```

- 도메인별 vertical slice를 사용한다. 전역 `models/`, `services/`, `repositories/` 폴더로 모든 도메인을 다시 섞지 않는다.

<a id="packagesplatform-adapters--외부-기술-구현"></a>

## 11. `packages/platform-adapters` — 외부 기술 구현

```text
packages/platform-adapters/
├── src/agent_factory_adapters/
│   ├── postgres/
│   │   ├── session.py
│   │   ├── tenant_context.py
│   │   ├── unit_of_work.py
│   │   └── repositories/
│   │       ├── workbenches.py
│   │       ├── connections.py
│   │       ├── knowledge.py
│   │       ├── jobs.py
│   │       └── audit.py
│   ├── pgvector/
│   │   ├── index.py
│   │   └── retrieval.py
│   ├── redis/
│   │   ├── queue.py
│   │   ├── rate_limit.py
│   │   └── cache.py
│   ├── object_storage/
│   │   ├── s3.py
│   │   └── local.py
│   ├── mcp_client/
│   │   ├── sessions.py
│   │   ├── discovery.py
│   │   ├── tools.py
│   │   └── resources.py
│   ├── http_connectors/
│   │   ├── client.py
│   │   ├── url_policy.py
│   │   └── oauth.py
│   ├── embeddings/
│   │   ├── provider.py
│   │   ├── managed.py
│   │   └── customer_endpoint.py
│   └── secrets/
│       ├── vault.py
│       └── envelope_encryption.py
├── tests/
└── pyproject.toml
```

- `platform-adapters`가 `platform-core`의 port를 구현한다. core가 SQLAlchemy, Redis, MCP SDK 또는 특정 embedding SDK를 import하는 방향은 금지한다.

<a id="마이그레이션-교차-테스트와-배포"></a>

## 12. 마이그레이션, 교차 테스트와 배포

```text
migrations/
├── env.py
├── script.py.mako
└── versions/

tests/
├── contracts/
│   ├── test_python_types.py
│   ├── workbench-contracts.test.ts
│   └── fixtures/
├── integration/
│   ├── postgres/
│   ├── mcp/
│   ├── queue/
│   ├── object_storage/
│   └── providers/
├── e2e/
│   ├── author-publish-render.spec.ts
│   ├── documents-workbench.spec.ts
│   ├── tenant-isolation.spec.ts
│   ├── mcp-app-sandbox.spec.ts
│   └── responsive-keyboard.spec.ts
└── security/
    ├── schema-limits/
    ├── cross-tenant/
    ├── ssrf/
    ├── csp/
    └── postmessage/

deploy/
├── containers/
│   ├── api.Dockerfile
│   ├── worker.Dockerfile
│   └── web.Dockerfile
├── compose/
│   ├── compose.dev.yml
│   └── compose.test.yml
├── kubernetes/
│   ├── base/
│   └── overlays/
├── proxy/Caddyfile
├── smoke/
└── backup/
```

- 패키지 내부 `tests/`는 단위 테스트를, 루트 `tests/`는 둘 이상의 실행 단위를 관통하는 계약·통합·E2E 검증을 소유한다.

<a id="디자인-시스템-검증"></a>

## 13. 디자인 시스템 검증

- 공통 에셋과 일관된 디자인이 제품성을 높인다는 판단은 타당하다. GOV.UK Design System은 재사용 가능한 접근성 컴포넌트가 서비스의 일관성을 만들고 반복 구현을 줄인다고 설명한다.^1 또한 일관된 디자인을 여러 서비스에서 신뢰와 보안을 형성하는 핵심 요소로 분류한다.^2 Atlassian은 디자인 토큰을 UI 의사결정의 단일 원본으로 정의하며 색상, 간격, 타이포그래피와 경계를 앱 전반에서 표준화한다.^3

- 그러나 SaaS다운 느낌은 공통 CSS만으로 생기지 않는다. 다음 네 층이 함께 일관되어야 한다.

1. 시각: token, typography, icon, spacing, surface
2. 행동: 선택, 저장, 취소, destructive confirm, keyboard
3. 상태: loading, empty, success, stale, error, permission-denied
4. 언어: 동일한 객체명, 동작 라벨, 오류 문장

- 따라서 `packages/design-system`은 단순 asset directory가 아니라 코드, 사용 규칙, 접근성 계약, visual regression을 함께 소유하는 제품 기반으로 취급한다.

- 테마도 같은 기반에 포함한다. 모든 공통 에셋은 semantic token만 소비하고 사용자별 `ThemeProfile` 하나가 작업 목록, 사이드바, 패널, 작성기 미리보기와 고객 선언형 작업에 동일하게 적용되어야 한다. 기본 테마, 사용자 조정값, 고대비·접근성 보정의 우선순위를 계약과 테스트로 고정한다.

<a id="의존-방향"></a>

## 14. 의존 방향

```text
apps/web ───────────────> workbench-runtime ───> design-system
   │                              │                    │
   ├──────────────────────────────┴────────────────────┤
   └──────────────> contracts-ts <────────────────────┘
   └──────────────> mcp-app-host ─> contracts-ts

apps/api ─────┐
              ├──> platform-core ─────> contracts-py
apps/worker ──┘          ▲
                         │ implements ports
                 platform-adapters
```

- 금지 방향은 다음과 같다.

- `platform-core` → FastAPI, Celery, SQLAlchemy, Redis, MCP SDK
- `design-system` → 제품 기능 또는 Workbench 데이터 호출
- `workbench-runtime` → 특정 표준 작업
- `apps/api/http` → PostgreSQL repository 직접 호출
- `apps/worker/handlers` → 다른 handler
- `contracts` → 제품 구현 코드
- 고객 작업 → raw CSS, raw icon, React import path

<a id="첫-scaffold-범위"></a>

## 15. 첫 scaffold 범위

- 전체 트리를 빈 폴더로 한 번에 만들지 않는다. 첫 구현에서는 다음만 생성한다.

```text
apps/web
apps/api
apps/worker
packages/design-system
packages/workbench-runtime
packages/contracts-ts
packages/contracts-py
packages/platform-core/workbenches
packages/platform-adapters/postgres
contracts/schemas/workbench/v1
contracts/schemas/appearance/v1
contracts/examples/workbenches
tests/contracts
tests/e2e
```

- 첫 scaffold에는 한두 개의 임시 컴포넌트만 두지 않는다. 작업 목록 SVG, 사이드바 구성 요소, 패널 레이아웃과 상태·입력 컴포넌트의 초기 카탈로그를 함께 정의하고 각 항목의 schema와 미리보기를 검증한다. 첫 vertical slice는 기존 `문서` 작업으로 고정한다. 완료 조건은 문서 정의가 검증되고, 카탈로그의 문서 아이콘·사이드바 트리·문서 패널 레이아웃을 조합해 렌더링되며, 동일 화면에서 사용자 테마 변경과 복원이 검증되는 것이다. `주식`은 계약 설명용 가상 fixture일 뿐 제품 구현 범위가 아니다.

<a id="sources"></a>

## 16. Sources

1. GOV.UK Design System. “[Components](https://design-system.service.gov.uk/components/).” Accessed September 2026.
2. GOV.UK Design System. “[Upcoming components and patterns](https://design-system.service.gov.uk/community/upcoming-components-patterns/).” Accessed September 2026.
3. Atlassian Design System. “[Foundations](https://atlassian.design/foundations).” Accessed September 2026.
4. Atlassian Design System. “[Use tokens in code](https://atlassian.design/foundations/tokens/use-tokens-in-code/).” Accessed September 2026.

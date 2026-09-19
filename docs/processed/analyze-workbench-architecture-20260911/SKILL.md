---
name: workbench-architecture-20260911
description: MCP 클라우드 Workbench 목표 아키텍처을 확인할 때 사용합니다.
document-type: processed
category: analyze
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-11-greenfield-workbench-architecture.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-11-greenfield-workbench-architecture
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# MCP 클라우드 Workbench 목표 아키텍처

- 상세 파일·패키지 배치는 [MCP 클라우드 Workbench 상세 디렉터리 구조](../analyze-target-directory-structure-20260912/SKILL.md)를 따른다. 구현 진행 상태와 완료 조건은 [Workbench 리팩터링 작업 현황](../process-workbench-refactoring-status-20260912/SKILL.md)에서 추적한다.

<a id="결론"></a>

## 1. 결론

- 이 제품은 “FastAPI 애플리케이션에 React 화면을 붙인 서비스”가 아니라, 고객이 업무별 화면과 데이터 연결을 정의하고 플랫폼이 이를 일관된 **작업 목록 | 사이드바 | 패널** 구조로 실행하는 Workbench 플랫폼으로 설계해야 한다.

- 가장 적절한 목표는 다음과 같다.

- 하나의 저장소에서 Python과 TypeScript를 함께 관리하는 모노레포
- React·TypeScript 기반의 Workbench 호스트와 선언형 렌더러
- FastAPI 기반의 HTTP·MCP 제어면
- Python 워커 기반의 수집·색인·장시간 실행
- 언어 중립 JSON Schema를 단일 계약 원본으로 사용
- 표준 작업과 고객 작업이 동일한 등록·선택·상태 복원 계약을 사용
- 작업 목록 SVG, 사이드바 구성 요소, 패널 레이아웃을 각각 다수 제공하는 조합형 공통 에셋 카탈로그
- 모든 공통 에셋에 일관되게 적용되는 사용자별 의미 기반 테마
- 외부 HTML·JavaScript는 동일 DOM에서 실행하지 않고 MCP Apps 호환 샌드박스로 격리
- PostgreSQL과 pgvector를 권위 데이터 및 검색 저장소로 사용

- Node.js는 React 개발·빌드와 MCP Apps 호스트 SDK 실행에 사용한다. HTTP·MCP 백엔드를 Node.js로 다시 만드는 것은 권장하지 않는다. AI 답변 생성은 제품 범위에서 제외하고, 지식 수집·임베딩·벡터 검색·출처 반환을 제공한다.

<a id="제품-모델"></a>

## 2. 제품 모델

<a id="사용자에게-보이는-모델"></a>

### 2.1. 사용자에게 보이는 모델

- 화면은 항상 세 영역으로 유지한다.

| 영역 | 책임 |
| --- | --- |
| 작업 목록 | 현재 Workspace에서 사용할 수 있는 표준 작업과 고객 작업을 전환한다. |
| 사이드바 | 선택한 작업의 탐색 대상, 목록, 필터와 보조 동작을 표시한다. |
| 패널 | 선택한 대상의 상세 화면, 표, 차트, 폼, 문서, 실행 결과를 표시한다. |

- 예를 들어 고객이 `주식` 작업을 게시하면 작업 목록에는 `주식`이 추가되고, 사이드바에는 관심 종목이, 패널에는 시세·차트·뉴스가 나타날 수 있다. 이는 계약을 설명하는 가상 예시이며 필수 제품 기능이 아니다. 데이터는 고객이 연결한 MCP 서버 또는 승인된 외부 API에서 가져오며 플랫폼은 데이터의 진실성을 만들어내지 않는다.

<a id="내부-모델"></a>

### 2.2. 내부 모델

- `task`라는 내부 명칭은 백그라운드 실행 작업과 혼동된다. 내부 도메인에서는 다음 이름을 사용한다.

| 개념 | 내부 이름 | 설명 |
| --- | --- | --- |
| 작업 목록의 한 항목 | `WorkbenchDefinition` | 사이드바·패널·데이터 바인딩의 버전된 정의 |
| 게시된 불변 버전 | `WorkbenchRelease` | 사용자가 실제로 실행하는 스냅샷 |
| 외부 데이터 연결 | `Connection` | MCP 또는 HTTP 공급자와 자격 증명 참조 |
| 데이터 호출 정의 | `Binding` | 화면 입력을 도구·리소스 호출로 연결 |
| 장시간 서버 실행 | `Job` | 수집, 재색인, 대량 처리의 durable 실행 |
| 개인 화면 상태 | `ViewPreference` | 순서, 표시 여부, 선택, 접힘과 너비 |
| 개인 표시 테마 | `ThemeProfile` | 기본 테마와 허용된 색상·밀도 토큰 조정값 |

- `WorkbenchDefinition`은 Workspace 소유의 aggregate root다. 초안, 게시, 보관 상태를 가지며 게시된 `WorkbenchRelease`는 수정하지 않는다. 수정은 새 revision과 새 release를 생성한다.

<a id="아키텍처-선택"></a>

## 3. 아키텍처 선택

<a id="선택지-비교"></a>

### 3.1. 선택지 비교

| 선택지 | 장점 | 결정적 문제 | 판단 |
| --- | --- | --- | --- |
| Python 서버 템플릿과 직접 DOM 조작만 확장 | 초기 변경량이 작다. | 고객 정의 컴포넌트, 복잡한 상태, 미리보기와 편집기의 규모가 커질수록 명령형 결합이 급증한다. | 단기 호환 계층으로만 사용 |
| React 전체 스택과 Node.js 백엔드 | 한 언어로 프론트엔드·백엔드를 구성한다. | RAG·문서 처리 Python 생태계를 별도 서비스로 다시 분리해야 하며 백엔드 재작성 이익이 부족하다. | 제외 |
| React Workbench + FastAPI 제어면 + Python 워커 | 동적 UI와 지식 파이프라인을 각 생태계의 강점에 배치한다. | 두 언어의 계약 드리프트를 통제해야 한다. | 권장 |
| 처음부터 다수의 마이크로서비스 | 독립 배포 경계가 선명해 보인다. | 제품 계약이 변하는 단계에서 네트워크·운영·트랜잭션 비용이 너무 크다. | 제외 |

- FastAPI는 큰 애플리케이션을 여러 `APIRouter`로 구성할 수 있으므로 HTTP와 MCP 어댑터를 얇게 유지하면서 도메인 모듈을 분리할 수 있다.^1 React는 기존 서버 기술을 유지한 채 특정 화면이나 하위 경로부터 점진적으로 도입할 수 있다.^2 Vite는 전통적인 백엔드와 결합할 때 빌드 manifest를 생성해 서버가 해시된 정적 자산을 참조하는 방식을 공식적으로 지원한다.^3

<a id="논리-구조"></a>

### 3.2. 논리 구조

```text
Browser
┌─────────────────────────────────────────────────────────────┐
│ React Workbench Host                                        │
│ 작업 목록 │ 사이드바 │ 패널                                │
│           Native Renderer / Sandboxed MCP App Host          │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTPS / SSE / WebSocket when needed
┌───────────────────────▼─────────────────────────────────────┐
│ FastAPI Control Plane                                       │
│ HTTP API │ MCP Resource Server │ Auth/RBAC │ Workbench API  │
└──────────┬─────────────────────┬────────────────────────────┘
           │                     │ durable Job
           │                     ▼
           │              Python Worker
           │              ingest / chunk / embed / index
           ▼
 PostgreSQL + pgvector ─ Redis/Queue ─ Object Storage
           │
           └──────────── MCP / approved HTTP providers
```

- API와 워커는 별도 프로세스로 실행하지만 동일한 도메인·애플리케이션 패키지를 사용한다. 처음부터 별도 데이터 소유권을 가진 마이크로서비스로 나누지 않는다.

<a id="목표-저장소-구조"></a>

## 4. 목표 저장소 구조

```text
agent-factory/
├── apps/
│   ├── web/                         # React Workbench 호스트
│   │   ├── src/
│   │   │   ├── app/                 # 부트스트랩, 라우팅, 전역 provider
│   │   │   ├── shell/               # 작업 목록 | 사이드바 | 패널 고정 셸
│   │   │   ├── standard/            # 플랫폼 표준 작업 등록
│   │   │   ├── authoring/           # 고객 작업 편집·미리보기·게시
│   │   │   └── shared/              # 앱 내부 전용 유틸리티
│   │   ├── public/
│   │   ├── tests/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── vite.config.ts
│   ├── api/                          # FastAPI composition root
│   │   ├── src/agent_factory_api/
│   │   │   ├── main.py
│   │   │   ├── http/                 # 라우터, dependency, DTO 변환
│   │   │   ├── mcp/                  # MCP tool/resource adapter
│   │   │   └── composition/          # port와 adapter 조립
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── worker/                       # 비동기 실행 composition root
│       ├── src/agent_factory_worker/
│       │   ├── main.py
│       │   ├── handlers/
│       │   └── scheduler.py
│       ├── tests/
│       └── pyproject.toml
├── packages/
│   ├── contracts/                    # 언어 중립 단일 계약 원본
│   │   ├── workbench/
│   │   │   ├── definition.schema.json
│   │   │   ├── sidebar.schema.json
│   │   │   ├── panel.schema.json
│   │   │   ├── binding.schema.json
│   │   │   └── action.schema.json
│   │   ├── events/
│   │   ├── examples/
│   │   └── generated/                # CI 생성물; 손으로 수정하지 않음
│   ├── ui/                           # React 디자인 시스템
│   │   ├── src/components/
│   │   ├── src/tokens/
│   │   ├── src/accessibility/
│   │   ├── tests/
│   │   └── package.json
│   ├── workbench-runtime/            # 선언형 렌더링 엔진
│   │   ├── src/registry/
│   │   ├── src/renderer/
│   │   ├── src/bindings/
│   │   ├── src/actions/
│   │   ├── src/state/
│   │   ├── src/validation/
│   │   ├── src/telemetry/
│   │   ├── tests/
│   │   └── package.json
│   ├── mcp-app-host/                 # 외부 UI iframe/AppBridge 경계
│   │   ├── src/sandbox/
│   │   ├── src/bridge/
│   │   ├── src/policy/
│   │   ├── tests/
│   │   └── package.json
│   ├── platform-core/                # 순수 Python 도메인·use case
│   │   ├── src/agent_factory_core/
│   │   │   ├── identity/
│   │   │   ├── organizations/
│   │   │   ├── workspaces/
│   │   │   ├── workbenches/
│   │   │   ├── connections/
│   │   │   ├── knowledge/
│   │   │   ├── executions/
│   │   │   ├── audit/
│   │   │   └── shared/
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── platform-adapters/            # 외부 기술 구현
│       ├── src/agent_factory_adapters/
│       │   ├── postgres/
│       │   ├── pgvector/
│       │   ├── redis/
│       │   ├── object_storage/
│       │   ├── mcp_client/
│       │   ├── http_connectors/
│       │   └── embeddings/
│       ├── tests/
│       └── pyproject.toml
├── migrations/                       # PostgreSQL append-only migration
├── tests/
│   ├── contracts/                    # Python/TS 동일 fixture 검증
│   ├── integration/                  # DB, queue, MCP, object storage
│   ├── e2e/                          # Playwright 사용자 흐름
│   └── security/                     # tenant, sandbox, SSRF, CSP
├── deploy/
│   ├── containers/
│   ├── compose/
│   ├── kubernetes/
│   └── smoke/
├── docs/
│   ├── adr/                          # 결정과 대안
│   ├── specs/                        # 현재 제품 계약
│   └── runbooks/                     # 배포·복구·운영
├── scripts/                          # 재현 가능한 생성·검증 명령
├── package.json                      # TypeScript workspace root
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── pyproject.toml                    # Python workspace root
├── uv.lock
└── Makefile                          # 언어 간 공통 진입점
```

- pnpm은 하나의 저장소에 여러 JavaScript 프로젝트를 묶는 workspace와 로컬 패키지만 사용하도록 강제하는 `workspace:` 프로토콜을 제공한다.^4 uv workspace는 여러 Python 애플리케이션과 라이브러리가 각자 `pyproject.toml`을 가지면서 하나의 lockfile을 공유하도록 지원한다.^5 따라서 모노레포는 “모든 코드를 한 패키지에 섞는 구조”가 아니라, 계약 변경을 한 커밋에서 원자적으로 검증하기 위한 배치 단위다.

<a id="디렉터리별-책임"></a>

## 5. 디렉터리별 책임

<a id="apps"></a>

### 5.1. `apps/`

- `apps/`에는 독립적으로 실행되거나 배포되는 진입점만 둔다. 비즈니스 규칙은 두지 않는다.

- `web`: 브라우저 호스트와 고객 작업 작성 도구
- `api`: HTTP와 MCP 요청을 use case로 번역
- `worker`: Job을 claim하고 use case를 실행

- `api`와 `worker`가 동일한 서비스 코드를 복사하면 안 된다. 둘 다 `platform-core`의 공개 use case와 `platform-adapters`의 구현을 composition root에서 조립한다.

<a id="packagescontracts"></a>

### 5.2. `packages/contracts/`

- 이 디렉터리가 가장 중요한 경계다. Python Pydantic 모델이나 TypeScript 타입을 계약 원본으로 삼지 않고 JSON Schema 문서를 원본으로 삼는다. JSON Schema는 정의되지 않은 속성을 기본적으로 허용하므로, 실행 계약의 각 객체는 의도적으로 `additionalProperties: false`를 사용해야 한다.^6

- 생성 파이프라인은 다음 산출물을 만든다.

- TypeScript 타입과 런타임 validator
- Python DTO 또는 validator
- API 문서 예제
- 호환성 fixture
- schema version과 digest

- 생성물은 원본과 같은 디렉터리에 섞지 않는다. CI는 생성 후 Git diff가 없는지 검사한다.

<a id="packagesplatform-core"></a>

### 5.3. `packages/platform-core/`

- 도메인별 vertical slice를 사용한다. 모든 도메인을 `models/`, `services/`, `repositories/`라는 전역 폴더로 다시 나누지 않는다.

```text
workbenches/
├── domain.py             # aggregate, value object, 상태 전이
├── commands.py           # create/update/publish/archive
├── queries.py            # list/get/render projection
├── policies.py           # 권한과 게시 가능성
├── ports.py              # repository, clock, event publisher
├── schemas.py            # core 내부 DTO
└── errors.py
```

- `knowledge/`는 문서, chunk, embedding, index, retrieval을 소유한다. 최종 LLM 답변 생성은 소유하지 않는다. `connections/`는 자격 증명과 공급자 capability를 소유하고, `workbenches/`는 connection ID만 참조한다. `executions/`는 호출 이력과 Job 상태를 소유하며 화면 정의가 실행 상태를 직접 저장하지 않게 한다.

<a id="packagesplatform-adapters"></a>

### 5.4. `packages/platform-adapters/`

- 외부 기술을 도메인에서 분리한다.

- SQLAlchemy/PostgreSQL repository
- pgvector 검색 adapter
- Redis queue와 cache
- S3 호환 object storage
- 외부 MCP client
- 허용된 HTTP connector
- embedding provider

- 도메인 객체가 SQLAlchemy session, Redis client, MCP SDK 타입을 직접 노출하지 않는다. 프로세스 분리가 필요해질 때도 core use case 계약을 유지할 수 있어야 한다.

<a id="packagesdesign-system"></a>

### 5.5. `packages/design-system/`

- 제품의 시각·접근성 primitive와 사용자가 작업을 조합하는 공통 에셋 카탈로그를 둔다. 데이터 호출, Workspace 권한, 작업별 비즈니스 로직은 넣지 않는다.

- 작업 목록에는 여러 검토된 SVG 아이콘을, 사이드바에는 평면 목록·그룹·트리·검색·필터·상태·보조 동작 조합을, 패널에는 상세·목록-상세·컬렉션·설정·대시보드·문서·분할·타임라인·칸반 등 여러 레이아웃을 제공한다. Button, Field, Status, Tabs, Table, ChartFrame, Dialog, Toast와 공통 상태도 같은 카탈로그에 포함한다. 각 에셋은 버전 ID, 속성 schema, binding 계약, 허용 영역, 접근성, 예제와 미리보기를 가지며 `workbench-runtime`은 등록된 에셋만 해석한다.

- 모든 에셋은 raw 색상 대신 semantic token을 사용한다. 사용자별 `ThemeProfile`은 dark, light, high-contrast 기반과 허용된 색상·밀도 조정값을 저장하며 대비와 포커스 가시성을 검증한다. 임의 CSS와 컴포넌트별 색상 덮어쓰기는 허용하지 않는다. 계산된 테마는 작업 목록, 사이드바, 패널, 작성기 미리보기와 고객 선언형 작업에 함께 적용한다.

<a id="packagesworkbench-runtime"></a>

### 5.6. `packages/workbench-runtime/`

- 고객 정의를 실행하는 핵심이다.

- `registry`: schema의 component 이름을 검토된 React 컴포넌트에 매핑
- `renderer`: sidebar/panel component tree 렌더링
- `bindings`: UI 입력을 승인된 data binding으로 변환
- `actions`: refresh, select, submit, navigate 같은 제한된 action 실행
- `state`: 작업·사용자·Workspace별 화면 상태
- `validation`: schema version, 크기, 깊이, component와 property allowlist 검사
- `telemetry`: 렌더 실패, binding 지연, action 결과 계측

- React 컴포넌트 이름이나 import 경로를 고객 schema에 직접 저장하지 않는다. `metric-grid@1`, `resource-table@1` 같은 안정된 공개 component ID만 저장한다.

<a id="packagesmcp-app-host"></a>

### 5.7. `packages/mcp-app-host/`

- 선언형 renderer와 외부 코드를 분리한다. MCP Apps는 도구가 `ui://` resource를 선언하고 host가 이를 sandboxed iframe으로 렌더링하며 `postMessage` 기반 JSON-RPC로 통신하는 공식 확장이다.^7 Host-side `AppBridge`도 View와 MCP 서버 사이의 별도 연결 및 teardown lifecycle을 명시한다.^8

- 따라서 외부 고객 코드가 필요한 경우에는 다음 경계를 사용한다.

```text
React Host
  └── mcp-app-host
      └── sandbox proxy iframe
          └── customer MCP App iframe
```

- 외부 HTML을 React의 `dangerouslySetInnerHTML`이나 같은 origin의 script로 실행하지 않는다. OWASP는 제3자 JavaScript의 주요 위험으로 실행 제어 상실과 데이터 노출을 들며 iframe sandbox와 CSP를 함께 고려하도록 권고한다.^9 `postMessage`는 정확한 target origin을 사용하고 수신 시 `origin`, `source`, message schema를 모두 검증한다.^10

<a id="workbench-계약"></a>

## 6. Workbench 계약

<a id="정의-예시--제품-기능-요구사항이-아닌-가상-fixture"></a>

### 6.1. 정의 예시 — 제품 기능 요구사항이 아닌 가상 fixture

```json
{
  "schemaVersion": "1.0",
  "slug": "stocks",
  "title": "주식",
  "icon": "chart-line",
  "renderMode": "native",
  "sidebar": {
    "component": "resource-list@1",
    "props": {
      "title": "관심 종목",
      "binding": "watchlist"
    }
  },
  "panel": {
    "component": "stack@1",
    "children": [
      {
        "component": "metric-grid@1",
        "props": { "binding": "quote" }
      },
      {
        "component": "line-chart@1",
        "props": { "binding": "history" }
      },
      {
        "component": "resource-table@1",
        "props": { "binding": "news" }
      }
    ]
  },
  "bindings": {
    "watchlist": {
      "connection": "market-data",
      "operation": { "type": "mcp-resource", "name": "watchlist" }
    },
    "quote": {
      "connection": "market-data",
      "operation": { "type": "mcp-tool", "name": "quote_get" },
      "input": { "symbol": { "$state": "selected.symbol" } }
    }
  }
}
```

- 정의에는 토큰, 임의 HTTP header, 데이터베이스 접속 문자열, JavaScript 식을 넣지 않는다. `connection`은 서버가 권한을 확인한 식별자이며 비밀 값은 서버 측 vault에서 해석한다.

<a id="렌더링-순서"></a>

### 6.2. 렌더링 순서

1. 사용자가 작업 목록에서 작업을 선택한다.
2. Host가 현재 Workspace와 사용자의 권한으로 게시된 release를 요청한다.
3. 브라우저와 서버가 schema version과 digest를 검증한다.
4. Host가 사이드바를 먼저 렌더링하고 필요한 binding을 요청한다.
5. 사이드바 선택을 작업별 local view state에 기록한다.
6. 패널 renderer가 선택 state를 사용하는 binding을 요청한다.
7. 서버가 Workspace, connection, operation 권한을 다시 검사한다.
8. 결과를 output schema로 검증한 뒤 UI에 전달한다.
9. 화면은 데이터의 `asOf`, 공급자, 오류와 stale 여부를 정직하게 표시한다.

- MCP tools는 `outputSchema`와 `structuredContent`를 지원하며 client도 구조화 결과를 검증하도록 권고한다.^11 이 구조를 binding 결과의 기본 계약으로 사용하되, 이전 MCP client와의 호환이 필요하면 text fallback도 보존한다.

<a id="표준-작업과-고객-작업"></a>

### 6.3. 표준 작업과 고객 작업

- 표준 작업과 고객 작업은 동일한 `WorkbenchDescriptor`를 작업 목록에 제공한다.

```text
WorkbenchRegistry
├── code-owned standard definitions
├── server-owned customer definitions
└── MCP App-backed definitions
```

- 차이는 신뢰 수준과 renderer다.

| 종류 | 정의 소유 | 렌더 방식 | 변경 방식 |
| --- | --- | --- | --- |
| 표준 작업 | 제품 코드 | native React | 제품 배포 |
| 고객 선언형 작업 | Workspace | native allowlist renderer | draft → validate → publish |
| 외부 MCP App 작업 | 외부 MCP server | sandbox iframe | capability·resource 검증 후 로드 |

- 표준 작업을 별도의 하드코딩된 navigation 시스템에 남겨두면 순서, 상태 복원, 권한과 테스트가 이중화된다. 표준 작업도 registry를 통해 등록하되, 고객이 그 정의나 필수 권한을 덮어쓸 수는 없게 한다.

<a id="데이터-및-rag-경계"></a>

## 7. 데이터 및 RAG 경계

- 제품은 생성형 AI를 제공하지 않는다. 지식 계층은 다음을 제공한다.

- source 연결과 수집
- 원본 보존 및 revision
- parsing과 chunking
- embedding 생성 또는 고객 제공 embedding 사용
- vector·keyword·hybrid retrieval
- 권한 필터와 provenance
- 결과의 출처, score, index version, `asOf` 반환

- `knowledge/`의 쓰기와 재색인은 Job으로 실행한다. 짧은 검색 요청은 API/MCP request 안에서 처리할 수 있지만, 외부 수집·대량 embedding·index rebuild는 worker로 넘긴다.

- Tenant-owned row에는 Workspace 식별자를 두고 애플리케이션 권한 검사와 PostgreSQL RLS를 함께 사용한다. PostgreSQL RLS는 SELECT와 mutation에 행 단위 정책을 적용할 수 있다.^12 RLS는 애플리케이션 RBAC의 대체물이 아니라 방어 계층이다.

<a id="보안-경계"></a>

## 8. 보안 경계

<a id="선언형-작업"></a>

### 8.1. 선언형 작업

- 모든 객체는 닫힌 schema로 검증한다.
- 최대 JSON 크기, component 수, tree 깊이, 문자열 길이를 제한한다.
- 외부 `$ref`, 재귀 schema, 임의 expression과 `eval`을 금지한다.
- URL을 직접 받지 않고 승인된 connection ID만 받는다.
- component와 action은 allowlist 및 version으로 선택한다.
- destructive action은 서버 권한과 사용자 확인을 모두 요구한다.
- 미리보기와 게시 권한을 분리한다.

<a id="mcp-app-작업"></a>

### 8.2. MCP App 작업

- 별도 origin 또는 opaque origin의 sandbox iframe
- 최소 sandbox capability
- resource가 선언한 CSP를 host 정책과 교집합으로 적용
- cookie와 host storage 접근 금지
- `postMessage` origin/source/schema 검증
- 도구 호출마다 Workspace RBAC와 connection scope 재검증
- iframe 제거 시 bridge와 pending request teardown
- 네트워크, 다운로드, 팝업, clipboard capability를 기본 거부

<a id="공급자-데이터"></a>

### 8.3. 공급자 데이터

- UI가 공급자 credential을 직접 받지 않음
- outbound URL allowlist와 SSRF/DNS rebinding 방어
- 호출 시간·결과 크기·pagination·rate limit 제한
- provider의 `asOf`와 platform 수신 시간을 분리
- “최신”을 실시간으로 오인시키지 않도록 갱신 주기와 stale 상태 표시

<a id="배포-구조"></a>

## 9. 배포 구조

- 초기 운영 단위는 네 개면 충분하다.

| 단위 | 내용 | 독립 확장 기준 |
| --- | --- | --- |
| `web` | CDN 또는 reverse proxy가 제공하는 정적 React 자산 | 정적 트래픽과 배포 cadence |
| `api` | FastAPI HTTP + MCP | request latency와 연결 수 |
| `worker` | ingestion, embedding, indexing, durable Job | queue depth와 CPU/GPU/provider quota |
| `scheduler` | 주기 수집과 retry dispatch | 단일 leader와 정확한 schedule |

- `scheduler`는 `apps/worker`의 별도 entrypoint와 container command로 시작한다. 코드가 같다는 이유로 같은 프로세스에 넣지 않고, 별도 디렉터리가 필요하다는 이유만으로 별도 도메인 서비스를 만들지도 않는다.

<a id="테스트-구조"></a>

## 10. 테스트 구조

<a id="계약-테스트"></a>

### 10.1. 계약 테스트

- 모든 예제 definition이 JSON Schema를 통과
- Python과 TypeScript validator가 같은 fixture에 같은 판정
- 이전 minor schema가 새 renderer에서 열림
- breaking change는 새 major schema version 없이는 실패
- MCP output schema 불일치가 UI까지 전달되지 않음

<a id="단위-테스트"></a>

### 10.2. 단위 테스트

- 도메인 상태 전이와 권한 policy
- component registry와 renderer
- binding input mapping
- view state reducer
- sandbox message validator

<a id="통합-테스트"></a>

### 10.3. 통합 테스트

- Workspace RLS와 cross-tenant denial
- publish transaction과 immutable release
- connection secret 비노출
- MCP tool/resource discovery와 호출
- Job idempotency, cancellation, retry
- pgvector 권한 필터와 provenance

<a id="e2e-테스트"></a>

### 10.4. E2E 테스트

- 고객 작업 초안 작성 → 미리보기 → 게시 → 작업 목록 표시
- 대표 작업 선택 → 사이드바 대상 선택 → 패널 데이터 갱신
- loading, empty, stale, error, permission-denied 상태
- 작업 순서·표시·사이드바 너비 복원
- narrow viewport와 keyboard navigation
- 외부 MCP App sandbox와 teardown

<a id="포팅-전략"></a>

## 11. 포팅 전략

- 목표 구조를 먼저 확정하되, 포팅은 빅뱅 방식으로 하지 않는다. React 공식 문서도 기존 프로젝트의 일부 화면부터 React를 추가할 수 있음을 명시한다.^2

<a id="0단계--결정-고정"></a>

### 11.1. 0단계 — 결정 고정

- ADR로 모노레포, FastAPI/React 경계, Workbench 계약 원본, sandbox 정책을 기록하고 구현에 적용
- `작업`, `WorkbenchDefinition`, `Job` 용어를 확정
- 포팅 전 핵심 사용자 흐름의 characterization test 확보

- 완료 조건은 디렉터리 생성이 아니라 금지된 의존 방향과 public contract가 합의된 상태다.

<a id="1단계--목표-골격-생성"></a>

### 11.2. 1단계 — 목표 골격 생성

- `apps/`, `packages/`, `contracts/`, `tests/`, `deploy/` 생성
- pnpm·uv workspace와 공통 `make check` 구성
- 빈 앱이 아니라 최소 health page/API와 cross-language fixture 검증까지 연결

<a id="2단계--계약-우선"></a>

### 11.3. 2단계 — 계약 우선

- Workbench JSON Schema v1 작성
- 공통 에셋 descriptor와 사용자 ThemeProfile schema 작성
- 대표 작업 예제와 failure fixture 작성
- Python·TypeScript 타입 및 validator 생성
- schema compatibility CI 추가

- UI나 DB 구현 전에 정의가 “무엇을 표현할 수 있고 무엇을 금지하는지”를 테스트한다.

<a id="3단계--새-react-셸을-병행-경로에-도입"></a>

### 11.4. 3단계 — 새 React 셸을 병행 경로에 도입

- 기존 서비스와 충돌하지 않는 shadow route에 React Workbench를 배포
- API는 compatibility adapter를 통해 기존 기능을 읽음
- 작업 목록 | 사이드바 | 패널과 상태 복원만 먼저 검증
- 작업 목록 SVG, 사이드바 구성 요소와 패널 레이아웃의 초기 다중 에셋 카탈로그 및 작성기 미리보기 제공
- 사용자 테마 편집, 검증, 서버 저장, 초기 렌더링과 기기 간 복원 검증
- Vite manifest를 통해 production asset을 서빙

<a id="4단계--workbench-도메인-도입"></a>

### 11.5. 4단계 — Workbench 도메인 도입

- draft, validate, publish, archive use case
- immutable release와 optimistic revision
- Workspace RBAC와 RLS
- 고객 작업 목록 조회 API

<a id="5단계--선언형-renderer와-첫-vertical-slice"></a>

### 11.6. 5단계 — 선언형 renderer와 첫 vertical slice

- 기존 `문서` 작업을 첫 vertical slice로 끝까지 구현한다. `주식`은 계약 설명용 가상 fixture일 뿐 제품 구현 범위가 아니다.

- 작업 정의
- 등록된 작업 목록 SVG
- 대표 사이드바 구성과 대상 선택
- 입력·출력 schema가 있는 binding
- 등록된 패널 레이아웃과 컴포넌트
- 데이터 출처와 stale 상태
- 권한·실패·rate limit

- 첫 작업만 겨우 표현하는 한두 개 컴포넌트에 범위를 제한하지 않는다. 일반적인 SaaS 작업을 사용자가 코드 없이 조합할 수 있도록 여러 작업 목록 아이콘, 사이드바 구성과 패널 레이아웃을 계획해서 제공하고, 의미가 겹치는 변형은 카탈로그 검토에서 제거한다.

<a id="6단계--표준-작업-포팅"></a>

### 11.7. 6단계 — 표준 작업 포팅

- 표준 작업을 하나씩 registry 기반 descriptor로 전환
- 각 작업마다 기존/신규 화면의 API 결과와 E2E 흐름을 비교
- 기능 플래그로 Workspace 단위 rollback 유지
- 화면 상태 key migration을 명시적으로 수행

- 파일 이동, renderer 교체, API 의미 변경을 한 변경 묶음에서 동시에 하지 않는다.

<a id="7단계--mcp-apps-호스트"></a>

### 11.8. 7단계 — MCP Apps 호스트

- 외부 UI가 실제로 필요한 고객 사례가 확인된 뒤 도입
- official AppBridge와 capability negotiation을 사용
- sandbox·CSP·message bridge 보안 테스트를 release gate로 지정
- 미지원 MCP host/client에는 structured data fallback 제공

- MCP Apps는 UI를 도구의 progressive enhancement로 취급한다.^13 Agent Factory의 자체 Workbench 정의를 MCP Apps 형식에 억지로 맞추지 말고, 외부 UI를 담는 하나의 render mode로 사용한다.

<a id="8단계--전환과-제거"></a>

### 11.9. 8단계 — 전환과 제거

- 신규 셸을 기본 경로로 전환
- 관측 기간 동안 compatibility route 유지
- 오류율, binding latency, iframe violation, publish rollback을 관찰
- 사용자가 남아 있지 않은 것이 확인된 뒤 이전 렌더 경로와 adapter 제거

<a id="구현과-함께-고정할-adr"></a>

## 12. 구현과 함께 고정할 ADR

| ADR | 결정 |
| --- | --- |
| ADR-001 | Python + TypeScript 모노레포와 독립 lockfile |
| ADR-002 | FastAPI 제어면, React Workbench, Python worker |
| ADR-003 | JSON Schema 기반 WorkbenchDefinition v1 |
| ADR-004 | 표준·고객 작업의 단일 WorkbenchRegistry |
| ADR-005 | native allowlist renderer와 MCP App sandbox의 분리 |
| ADR-006 | PostgreSQL 권위 데이터, pgvector 검색, Workspace RLS |
| ADR-007 | draft/publish와 immutable WorkbenchRelease |
| ADR-008 | connection reference만 허용하고 credential은 서버 보관 |
| ADR-009 | 포팅 feature flag, compatibility adapter, rollback 기준 |
| ADR-010 | 다중 공통 에셋 카탈로그, 버전 ID와 사용자별 semantic-token 테마 |

<a id="피해야-할-구조"></a>

## 13. 피해야 할 구조

- `frontend/components/` 하나에 모든 제품 화면을 평면으로 저장
- 고객 schema에서 React import 경로나 컴포넌트 코드를 지정
- 동일 DOM에서 고객 JavaScript 실행
- 작업 정의에 API token이나 임의 header 저장
- 표준 작업과 고객 작업에 별도 navigation·상태 시스템 사용
- HTTP router, MCP adapter, worker handler가 각자 같은 비즈니스 규칙 구현
- API와 worker가 서로 다른 도메인 모델 복사본 사용
- React 도입과 동시에 모든 백엔드를 Node.js로 재작성
- 제품 계약이 안정되기 전에 도메인을 마이크로서비스로 분해
- 생성형 AI가 없는데 검색 결과를 “AI 답변”으로 표현

<a id="최종-권고"></a>

## 14. 최종 권고

- 디렉터리는 기술 이름이 아니라 변경 책임과 신뢰 경계를 드러내야 한다. 이 제품에서 가장 중요한 경계는 다음 네 개다.

1. `contracts`: 고객 정의와 플랫폼 실행 사이의 공개 계약
2. `workbench-runtime`: 신뢰된 선언형 렌더링
3. `mcp-app-host`: 신뢰하지 않는 외부 UI 격리
4. `platform-core`: tenant, 권한, 지식, 실행의 서버 권위

- 따라서 이 목표 구조를 ADR로 기록하면서 `문서` vertical slice로 계약을 검증한 뒤 현행 기능을 하나씩 포팅한다. ADR은 별도 승인 대기 단계가 아니라 일괄 리팩터링의 구현 판단과 결과를 남기는 기록이다. 목표 디렉터리만 먼저 대규모로 만들거나 파일을 일괄 이동하는 것은 구조를 만든 것이 아니라 이름을 바꾼 것에 불과하다.

<a id="sources"></a>

## 15. Sources

1. FastAPI. “[Bigger Applications - Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/).” Accessed September 2026.
2. React. “[Add React to an Existing Project](https://react.dev/learn/add-react-to-an-existing-project).” Accessed September 2026.
3. Vite. “[Backend Integration](https://vite.dev/guide/backend-integration.html).” Accessed September 2026.
4. pnpm. “[Workspace](https://pnpm.io/workspaces).” Accessed September 2026.
5. Astral. “[Using workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/).” September 2026.
6. JSON Schema. “[Objects](https://json-schema.org/understanding-json-schema/reference/object).” Accessed September 2026.
7. Model Context Protocol. “[MCP Apps](https://modelcontextprotocol.io/extensions/apps/overview).” Accessed September 2026.
8. Model Context Protocol. “[AppBridge](https://apps.extensions.modelcontextprotocol.io/api/classes/app-bridge.AppBridge.html).” Accessed September 2026.
9. OWASP. “[Third Party JavaScript Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Third_Party_Javascript_Management_Cheat_Sheet.html).” Accessed September 2026.
10. MDN Web Docs. “[Window: postMessage() method](https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage).” Accessed September 2026.
11. Model Context Protocol. “[Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).” Accessed September 2026.
12. PostgreSQL Global Development Group. “[Row Security Policies](https://www.postgresql.org/docs/17/ddl-rowsecurity.html).” Accessed September 2026.
13. Model Context Protocol. “[MCP Apps Overview](https://apps.extensions.modelcontextprotocol.io/api/documents/overview.html).” Accessed September 2026.

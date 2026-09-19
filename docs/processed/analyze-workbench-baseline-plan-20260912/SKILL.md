---
name: workbench-baseline-plan-20260912
description: Workbench 리팩터링 RF-003 기준선 실행 계획을 확인할 때 사용합니다.
document-type: processed
category: analyze
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-12-workbench-baseline.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-12-workbench-baseline
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench 리팩터링 RF-003 기준선 실행 계획

- 기준일: 2026-09-12

<a id="목적과-현재-상태"></a>

## 1. 목적과 현재 상태

- 이 문서는 리팩터링 전 핵심 행동을 재현하는 실행 계획이다. 현재 소스와 테스트 계약을 선별했으며 이 Work 실행에서는 테스트, 브라우저, build, migration 또는 server를 실행하지 않았다. 따라서 RF-003은 **부분 완료**이고, 아래 명령의 독립 Verification 결과가 기록될 때까지 기준선 통과로 간주하지 않는다.

- 현재 제품 계약은 `.codex/skills/{info-platform,design-platform,rule-platform}/references/`가 계속 소유한다. 이 문서는 요구사항을 복제하거나 새 acceptance를 만들지 않고, 기존 테스트가 관찰하는 범위와 빠진 범위를 연결한다.

<a id="공통-안전-조건"></a>

## 2. 공통 안전 조건

- fixture/API Python 명령은 repository root에서 실행하고 `.venv`의 고정된 환경을 사용한다.
  wheel 검사는 예외이며 아래 build prerequisite 절차로 선택한 **기존** 호환 interpreter를 쓴다.
- `pytest` 명령에는 integration marker를 제외한다. fixture/memory repository/API test는 실제
  PostgreSQL, Redis, object storage 또는 provider 계정을 검증하지 않는다.
- 이 문서의 §2 browser 명령만 synthetic HTTP fixture 또는 test-local server를 사용한다.
  `tests/browser/cloud-platform.cjs`는 actual disposable server 전용이며 직접 실행하지 않는다.
- `NODE_PATH`는 이미 설치된 Playwright 위치를 명시하며 결과 경로와 Chromium 버전을 기록한다.
- 실제 DB 검증은 `AGENT_FACTORY_TEST_DATABASE_URL` 또는 전용 검증 script가 새로 만든 disposable
  PostgreSQL만 사용한다. `.env`를 읽거나 기존 개발/운영 DB URL을 재사용하지 않는다.
- provider live call, 운영 compose, 배포, restart와 destructive migration은 이 기준선에 없다.
- prerequisite가 없는 경우 새 checkout, package 또는 tool을 설치하지 않고 해당 행을 `차단`으로
  기록한다. 특히 현재 sibling plugin에 Document source가 없거나 build-capable interpreter가
- 없다는 사실을 product/test regression으로 바꾸지 않는다.

<a id="빠른-architecture-및-fixtureapi-기준선"></a>

## 3. 빠른 architecture 및 fixture/API 기준선

- 아래 명령은 순서대로 실행할 수 있으며 모두 실제 DB가 필요 없는 선별 기준선이다.

| 영역 | 명령 | 현재 관찰 범위 | 명시적 한계 |
| --- | --- | --- | --- |
| Architecture | `.venv/bin/python -m pytest -q tests/test_architecture_boundaries.py` | router transaction/persistence 금지, 공유 Agent 실행 composition | 아직 `apps/packages` 금지 import는 존재하지 않음 |
| 조직·권한 | `.venv/bin/python -m pytest -q -m "not integration" tests/test_organization_management.py tests/test_authorization.py tests/test_authentication.py` | permission catalog, token scope 교집합, auth/session/CSRF fixture | 실제 RLS, SMTP/OAuth provider 없음 |
| 작업공간 | `.venv/bin/python -m pytest -q -m "not integration" tests/test_workspace_management.py tests/test_personal_workspaces.py tests/test_workspace_ui.py` | 생성자 owner, 마지막 owner, repository identity, personal Workspace, HTML/API 계약 | 실제 PostgreSQL provisioning 없음 |
| 문서 | `.venv/bin/python -m pytest -q -m "not integration" -k "not actual_distributable_source_inventories_fit_without_omissions" tests/test_documents.py tests/test_document_paths.py tests/test_document_search.py tests/test_cloud_documents.py tests/test_cloud_document_delivery.py tests/test_cloud_document_delivery_http.py` | immutable revision, upload limits, path, search construction, cloud import/package/preview HTTP fixture | 실제 source checkout inventory, S3·RLS·동시 transaction 없음 |
| 일정·계획 | `.venv/bin/python -m pytest -q -m "not integration" tests/test_scheduling.py tests/test_planning.py tests/test_planning_calendar.py tests/test_planning_import.py` | cron/interval, queue pinning, 계획 계층·날짜·preview/apply fixture | Beat/worker 및 실제 DB lock 없음 |
| Agent | `.venv/bin/python -m pytest -q -m "not integration" tests/test_agents.py tests/test_reporting.py tests/test_cloud_reporting.py tests/test_reporting_runtime.py` | immutable version/run state, durable Job submission, reporting transition/idempotency/search fixture | 실제 broker, cloud recipient 또는 runtime process 없음 |
| 연동 | `.venv/bin/python -m pytest -q -m "not integration" tests/test_integrations.py tests/test_cloud_integrations_providers.py tests/test_cloud_integrations_collections.py tests/test_cloud_integrations_packaging.py` | secret tamper, webhook ordering, bounded provider HTTP fixture, collection replay/credential redaction | live provider, deployed egress, PostgreSQL claim 없음 |
| MCP | `.venv/bin/python -m pytest -q -m "not integration" tests/test_mcp_server.py tests/test_mcp_connections.py` | resource/tool 등록, token naming과 stateless transport fixture | wheel/package, 실제 client fleet와 DB token lifecycle 없음 |
| Admin·운영 회귀 | `.venv/bin/python -m pytest -q -m "not integration" tests/test_admin.py tests/test_security.py tests/test_observability.py tests/test_health.py tests/test_deployment.py` | fail-closed admin, headers/SSRF, probes, deploy asset/runbook contract | image build, staging smoke, backup restore 없음 |

- 명령마다 exit code, test count, skip/deselect 수, duration과 실패 traceback을 그대로 보존한다. 한 행의 실패 때문에 다른 독립 행의 결과를 통과로 재분류하지 않는다.

<a id="fixture-browser-characterization"></a>

## 4. fixture browser characterization

- 다음 검사는 실제 Chromium 상호작용을 사용하지만 API 응답은 fixture이므로 실제 DB 검증과 분리해 기록한다.

| 영역 | 명령 | 핵심 흐름 | 산출물/한계 |
| --- | --- | --- | --- |
| 작업공간·조직 | `NODE_PATH=/tmp/af-pw/node_modules node tests/browser/workspace-start.cjs && NODE_PATH=/tmp/af-pw/node_modules node tests/browser/organizations.cjs` | empty/create/open/switch/list/late response, 조직 메뉴·권한 상태 | `/tmp/workspace-*.png`; synthetic API |
| 문서 | `NODE_PATH=/tmp/af-pw/node_modules node tests/browser/document-editor.cjs` | tree, tab/split, DND, 오류/재시도, Workspace 전환, narrow UI | fixture content; 이전 timeout과 혼동 금지 |
| 문서 package | `NODE_PATH=/tmp/af-pw/node_modules node tests/browser/cloud-document-delivery.cjs` | isolated preview, local resources, CSP 공격 시도, teardown | test-local server; integrated header/RLS 아님 |
| 일정·계획 | `NODE_PATH=/tmp/af-pw/node_modules node tests/browser/planning.cjs` | tree/timeline/today/kanban과 편집 상태 | synthetic API; 실제 schedule execution 아님 |
| Agent·보고·관리 | `.venv/bin/python -m pytest -q tests/browser/reporting.py && NODE_PATH=/tmp/af-pw/node_modules node tests/browser/admin-assets.cjs` | reporting hierarchy/status/evidence 및 admin asset 접근 | 보고된 fixture; 실제 Agent 실행 아님 |
| MCP | `NODE_PATH=/tmp/af-pw/node_modules node tests/browser/mcp-clients.cjs && NODE_PATH=/tmp/af-pw/node_modules node tests/browser/mcp-handoff.cjs` | 13 client/18 environment config, ZIP/CRC, token 선택·오류 | client 실행 및 server connection 아님 |
| 공통 UI | `NODE_PATH=/tmp/af-pw/node_modules node tests/browser/ui-boundaries.cjs && NODE_PATH=/tmp/af-pw/node_modules node tests/browser/ui-components.cjs && NODE_PATH=/tmp/af-pw/node_modules node tests/browser/ui-screens.cjs` | 작업 목록·사이드바·패널, state, compact/responsive primitives | legacy vanilla UI characterization |

- `tests/browser/reporting.py`는 pytest가 test-local HTTP server와 Chromium을 구성한다. Python Playwright package/browser prerequisite가 없으면 실패 또는 미실행으로 기록하며, 명령을 임의로 live endpoint로 바꾸지 않는다.

- `tests/browser/cloud-platform.cjs`는 `CLOUD_BROWSER_URL`, `CLOUD_BROWSER_COOKIE`, `CLOUD_BROWSER_COOKIE_NAME`, `CLOUD_BROWSER_WORKSPACE`, `CLOUD_BROWSER_DOCUMENT`를 요구하고 API interception을 사용하지 않는다. 이 값들은 사람이 임의로 만들지 않는다. §4의 cloud harness가 disposable PostgreSQL과 actual Uvicorn server에 인증된 Workspace/Document를 만든 뒤 `tests/test_cloud_platform_integration.py::test_current_editor_with_real_http_and_document` 안에서 정확한 값을 설정하여 이 script를 호출한다.

<a id="source-inventory와-wheel-prerequisite-검사"></a>

## 5. source inventory와 wheel prerequisite 검사

- 두 검사는 fixture/API 행과 분리한다. checkout이나 interpreter가 이미 존재하지 않으면 실행하지 않고 차단 근거를 기록한다. 이 절차는 network fetch, package install 또는 repository `.venv` 변경을 허가하지 않는다.

| 대상 | 사전 조건과 명령 | 판정 경계 |
| --- | --- | --- |
| 실제 distributable source inventory | repository의 sibling `../plugin`이 하나의 Git checkout이며 `skills/document`, `skills/agent`, `docs/specifications/document`, `docs/specifications/agent`의 tracked/nonignored source와 각 package의 Mermaid 자산을 포함하는지 읽기 전용으로 확인한다. 충족할 때만 `.venv/bin/python -m pytest -q tests/test_cloud_document_delivery.py::test_actual_distributable_source_inventories_fit_without_omissions`를 실행한다. | 현재 plugin 소유 구조에 `skills/document`가 없으면 `차단: source checkout prerequisite 부재`다. template inventory fixture나 Documents regression 실패로 분류하지 않는다. |
| inventory selection policy fixture | `.venv/bin/python -m pytest -q tests/test_cloud_source_inventory.py` | test-local Git repository의 tracked/untracked/deleted/generated 선택 정책만 입증하며 실제 plugin source 존재를 입증하지 않는다. |
| wheel/package fidelity | 기존 interpreter 후보를 절대 경로로 정한 뒤 `CLOUD_VERIFY_PYTHON=/absolute/path/to/existing-compatible-python; "$CLOUD_VERIFY_PYTHON" -c 'from importlib.metadata import version; import setuptools.build_meta; assert int(version("setuptools").split(".", 1)[0]) >= 75; import pytest'`를 실행한다. 성공한 같은 interpreter로 `CLOUD_VERIFY_PYTHON="$CLOUD_VERIFY_PYTHON" "$CLOUD_VERIFY_PYTHON" -m pytest -q tests/test_cloud_platform_packaging.py`를 실행한다. | interpreter에는 project test/runtime dependencies와 `setuptools>=75`/`setuptools.build_meta`가 이미 있어야 한다. 후보가 없으면 `차단: compatible build interpreter 부재`이며 application regression이 아니다. `pip install`이나 build isolation network fetch로 보완하지 않는다. |

- `tests/test_cloud_platform_packaging.py`는 isolated source copy에서 `pip wheel --no-build-isolation`을 실행하므로 project `.venv`라는 이유만으로 적합하다고 가정하지 않는다. 선택한 interpreter path, Python/setuptools version, prerequisite probe exit code와 wheel test 결과를 함께 기록한다.

<a id="actual-dbprocess-기준선"></a>

## 6. actual DB·process 기준선

- 이 구간은 fixture 통과와 별개이며 disposable infrastructure가 명시적으로 준비된 경우에만 Verification이 실행한다.

| 대상 | 실행 명령/경계 | 입증하는 것 | 입증하지 않는 것 |
| --- | --- | --- | --- |
| 조직·Workspace RLS | `bash scripts/verify-organizations.sh` | script가 만든 새 PostgreSQL, migration, NOSUPERUSER/NOBYPASSRLS 조직·팀·Workspace 격리 | 운영 DB와 기존 데이터 upgrade |
| 공통 cloud 흐름과 actual browser | §3 probe를 통과한 기존 interpreter를 사용하여 `CLOUD_VERIFY_PYTHON=/absolute/path/to/existing-compatible-python NODE_PATH=/tmp/af-pw/node_modules bash scripts/verify-cloud-platform.sh` | 고유 pgvector container, head upgrade/downgrade/re-upgrade, actual Uvicorn HTTP/MCP/worker와 harness가 제공한 `CLOUD_BROWSER_*`로 실행되는 current-editor Chromium 검사 | live provider, production S3/egress; Docker 또는 명시된 rootless 대체가 없으면 차단 |
| MCP token handoff | `bash scripts/verify-mcp-handoff.sh` | disposable PostgreSQL의 token encryption/retrieval/revoke/RLS와 실제 API/MCP SDK | 13개 실제 GUI client 실행 |
| planning import | `bash scripts/verify-planning-import.sh` | disposable DB migration/RLS/API/MCP preview/apply | 외부 AI/source connector 정확성 |
| reporting | `bash scripts/verify-reporting.sh` | reporting persistence/RLS 및 runtime image·binding recipient 경계 | 실제 Agent 프로세스의 진실성 |
| 명시 URL migration test | `AGENT_FACTORY_TEST_DATABASE_URL='<disposable-url>' .venv/bin/python -m pytest -q -m integration tests/integration/test_migrations.py` | 지정 DB의 clean migration head | URL이 disposable인지 자동 증명하지 않음; Verification이 생성 근거 기록 |

- script를 실행하기 전에 소스에서 container 이름, random loopback port, `.env` 비활성화와 cleanup target을 확인한다. cloud harness는 `AGENT_FACTORY_ENV_FILE=''`를 설정하고 자신의 actual server test가 browser 값을 생성한다. 기존 container/volume을 대상으로 하거나 Docker 접근과 문서화된 private rootless PG16+pgvector 대체가 모두 없다면 실행하지 않고 차단으로 보고한다. 실행 후에는 script가 출력한 transcript 위치와 제한된 cleanup 결과만 기록한다.

<a id="기준선-판정표"></a>

## 7. 기준선 판정표

| 도메인 | 최소 통과 증거 | RF-003에 남는 제한 |
| --- | --- | --- |
| 조직 | fixture/API + `verify-organizations.sh` | live mail/OAuth는 별도 운영 검증 |
| 작업공간 | fixture/API + workspace browser + 조직 RLS | 실제 기존 tenant 데이터 migration은 별도 |
| 문서 | fixture/API + 두 fixture browser check + 실제 source inventory(또는 명시적 prerequisite 차단) + cloud disposable harness의 actual browser | production object storage failure/retention 제외 |
| 일정 | fixture/API + planning browser + planning disposable harness | 실제 Beat 장시간 실행 제외 |
| Agent | fixture/API + reporting browser + reporting disposable harness | 외부 Agent 행동은 자기 보고 범위를 넘지 않음 |
| 연동 | provider fixture + cloud disposable server/browser harness | live account/scope/egress 제외 |
| MCP | MCP fixture/API + 별도 wheel/package 결과 + handoff browser + handoff/cloud disposable harness | 전체 실제 client fleet 재실행 제외 |

- 각 도메인은 위 최소 증거가 모두 성공해야 `통과`로 기록한다. 실패, 미실행, prerequisite 부재는 그대로 표시한다. RF-003 완료 시 이 문서에 날짜, 환경 식별자(비밀 제외), 명령, exit code, transcript/screenshot 위치와 한계를 추가하고 상태 문서의 RF-003만 `완료`로 변경한다.

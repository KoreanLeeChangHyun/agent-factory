---
name: workbench-refactoring-status-20260912
description: Workbench 리팩터링 작업 현황을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-12-workbench-refactoring-status.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-12-workbench-refactoring-status
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench 리팩터링 작업 현황

- 기준일: 2026-09-12

- 이 문서는 [목표 아키텍처](../analyze-workbench-architecture-20260911/SKILL.md)와 [상세 목표 구조](../analyze-target-directory-structure-20260912/SKILL.md)를 실제 코드로 옮기는 작업을 추적한다. `docs/processed/notes/`의 날짜별 현황 기록이며 제품 계약을 대신하지 않는다.

<a id="상태-기준"></a>

## 1. 상태 기준

| 상태      | 의미                                                              |
| --------- | ----------------------------------------------------------------- |
| 완료      | 목표 구조와 완료 조건을 충족하고 해당 검증 근거가 있다.           |
| 부분 완료 | 재사용할 현행 구현이나 문서는 있지만 목표 경계로 이전되지 않았다. |
| 미착수    | 목표 파일·계약·실행 경로가 아직 없다.                             |
| 후순위    | 선행 vertical slice 또는 실제 고객 사례가 확인된 뒤 진행한다.     |

- 상태는 소스 트리와 기존 기록을 바탕으로 판정했다. 이번 현황표 작성 과정에서는 제품 테스트, 브라우저 테스트, PostgreSQL 통합 테스트, 빌드 또는 배포를 다시 실행하지 않았다.

<a id="실행-방식"></a>

## 2. 실행 방식

- 전체 리팩터링은 한 번의 사용자 요청으로 연속 실행한다. 아래 단계와 선행 관계는 작업 순서를 정하는 장치이며 사용자 승인 대기 지점이 아니다. 구현 중 필요한 기술 선택은 목표 아키텍처, 현재 제품 계약과 테스트 증거에 따라 결정하고 ADR에 바로 기록한다. 각 단계의 검증이 통과하면 다음 단계로 계속 진행하며, 복구할 수 없는 외부 상태 변경이나 현재 환경으로 해결할 수 없는 실제 차단 조건이 생긴 경우에만 사용자 입력을 요청한다.

<a id="전체-현황"></a>

## 3. 전체 현황

| 영역                  | 현재 상태 | 현재 근거                                                                                                        | 다음 완료 지점                                              |
| --------------------- | --------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 목표 아키텍처         | 부분 완료 | 모노레포·Workbench·포팅 방향과 [ADR-001~010](../process-platform-architecture-decisions/SKILL.md) 적용 결정 존재                                             | 신규 apps/packages 의존성 규칙 자동 검사                    |
| 현행 서비스 경계      | 부분 완료 | Stage 7 identity/authorization, Stage 8 organization/Workspace/account backend·B101 closure, Stage 9 administrator backend 독립 pass | 이후 도메인 경계를 순차 포팅 |
| 모노레포 골격         | 완료      | Stage 1 독립 Verification에서 frozen install, 공통 gate, worker smoke, web/Python build와 no-cleanup 재실행 통과 | 후속 slice에서 같은 gate 유지                               |
| 공통 UI 기반          | 완료      | Stage 2 독립 Verification에서 17 design-system tests, Chromium matrix와 10 screenshots 통과                      | 후속 소비자 전환 동안 같은 catalog gate 유지                |
| 작업 목록 에셋        | 완료      | 16개 versioned React SVG와 상태·provenance가 Stage 2 독립 catalog/Chromium gate 통과                             | 후속 registry/runtime 소비에서 호환성 유지                  |
| 사이드바 에셋         | 완료      | 단일 host의 7개 조합과 keyboard/width behavior가 Stage 2 독립 gate 통과                                          | 작성기와 표준 Workbench에서 같은 registry 사용              |
| 패널 레이아웃         | 완료      | 9개 React 조합과 responsive split/remount behavior가 Stage 2 독립 gate 통과                                      | 작성기와 표준 Workbench에서 같은 registry 사용              |
| 사용자 테마           | 부분 완료 | Stage 3 독립 Verification에서 DB/RLS/concurrency/audit와 Chromium context/theme gate 통과                        | legacy 소비자 전환                                          |
| Workbench 계약        | 완료      | 닫힌 schema, 제한, 예제, 생성 Python/TypeScript 패키지가 Stage 1 parity/codegen gate 통과                        | Stage 2 확장 enum 재검증 및 이후 호환성 유지                |
| Workbench runtime     | 완료      | Stage 4 registry/renderer/binding/action/view-state 독립 package/browser gate 통과                               | 후속 server-backed 소비자에서 같은 gate 유지                |
| 사용자 작성기         | 완료      | Stage 5 최종 독립 Verification에서 실제 DB-backed 저장·게시·release·reload browser gate 통과                     | 후속 표준 작업 포팅에서 같은 작성/게시 계약 유지            |
| Workbench 도메인      | 완료      | Stage 5 최종 독립 Verification에서 0026, transaction/RBAC/RLS/HTTP·MCP parity와 불변 release 통과                | 후속 binding/표준 작업 소비에서 같은 계약 유지              |
| React Workbench shell | 완료      | Stage 6 독립 Verification에서 production route·DB·browser·양방향 rollback 통과                                   | 후속 표준 작업 포팅 동안 같은 production gate 유지          |
| 표준 작업 포팅        | 부분 완료 | Stage 6 Documents 대표 범위 작성; 전체 Documents와 나머지 표준 작업은 legacy 유지                                | RF-801 전체 Documents parity와 RF-800/802~804 순차 전환     |
| MCP App host          | 후순위    | Document preview sandbox는 있으나 MCP AppBridge host는 없음                                                      | 실제 사례 후 CSP·capability·message·teardown 보안 gate 통과 |
| 전환·제거             | 후순위    | production shadow route와 즉시 legacy rollback은 검증됨; 실제 rollout 관측과 제거 조건은 미충족                  | 관측·rollback 조건 충족 후 legacy 경로 제거                 |

<a id="단계별-작업-현황표"></a>

## 4. 단계별 작업 현황표

<a id="결정과-기준선"></a>

### 4.1. 결정과 기준선

| ID     | 작업                                         | 상태      | 남은 작업                                                                                                                           | 완료 조건                                                                                                    |
| ------ | -------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| RF-000 | 목표 아키텍처와 상세 디렉터리 구조 작성      | 완료      | 변경 시 유지관리 구조 계약과 동기화                                                                                                 | 목표 문서와 구조 계약이 같은 경계·명칭 사용                                                                  |
| RF-001 | 다중 공통 에셋과 사용자별 테마를 범위에 포함 | 완료      | 구현 ADR과 schema에서 구체화                                                                                                        | 작업 목록·사이드바·패널 카탈로그와 `ThemeProfile`이 계획·완료 조건에 존재                                    |
| RF-002 | ADR-001~010 작성                             | 완료      | 후속 구현과 실제 결과가 결정을 변경하면 같은 ADR의 상태·결과 갱신                                                                   | `docs/specification/design-platform/adr/`에 결정·대안·결과·계약 소유·rollout과 적용 상태 기록                                              |
| RF-003 | 현행 핵심 흐름 characterization 기준선       | 부분 완료 | [실행 계획](../analyze-workbench-baseline-plan-20260912/SKILL.md)의 fixture/API·browser·disposable DB matrix를 독립 Verification에서 실행하고 결과 기록 | 조직·작업공간·문서·일정·에이전트·연동·MCP 핵심 흐름 기준선 통과                                              |
| RF-004 | 현행 파일의 목표 소유자 매핑                 | 완료      | 실제 포팅 때 tracked inventory 변화와 removal checkpoint를 행별 갱신                                                                | [migration map](../analyze-workbench-migration-map-20260912/SKILL.md)에 모든 포팅 대상의 목표 경로·호환 경계·제거 조건 존재 |

<a id="계약과-의존성-기반"></a>

### 4.2. 계약과 의존성 기반

| ID     | 작업                          | 상태 | 선행       | 완료 조건                                                       |
| ------ | ----------------------------- | ---- | ---------- | --------------------------------------------------------------- |
| RF-100 | Workbench JSON Schema v1      | 완료 | RF-002     | Stage 1 독립 parity·제한 검증 통과; 후속 확장 재검증 유지       |
| RF-101 | 공통 에셋 descriptor schema   | 완료 | RF-002     | 닫힌 descriptor와 catalog 계약 독립 검증 통과                   |
| RF-102 | 사용자 `ThemeProfile` schema  | 완료 | RF-002     | allowlist schema·거부 fixture 독립 parity 통과                  |
| RF-103 | Python·TypeScript 생성 패키지 | 완료 | RF-100~102 | frozen install, codegen byte check와 두 생성 package build 통과 |
| RF-104 | schema 호환성 정책과 CI       | 완료 | RF-100~103 | compatibility fixture와 dedicated Workbench gate 통과           |
| RF-105 | 목표 의존 방향 검사           | 완료 | RF-002     | Python/TS·manifest·generated-output 경계 검증 통과              |

<a id="최소-모노레포-골격"></a>

### 4.3. 최소 모노레포 골격

| ID     | 작업                                              | 상태      | 선행       | 완료 조건                                                                          |
| ------ | ------------------------------------------------- | --------- | ---------- | ---------------------------------------------------------------------------------- |
| RF-200 | pnpm workspace와 루트 TypeScript 구성             | 완료      | RF-002     | pnpm 10.15.1 frozen install, gate와 Vite build 통과                                |
| RF-201 | uv Python workspace와 공통 lock                   | 완료      | RF-002     | uv 0.8.15 frozen sync와 여섯 Python package build 통과                             |
| RF-202 | `apps/web`, `apps/api`, `apps/worker` 최소 실행점 | 완료      | RF-200~201 | health/readiness 계약, worker smoke와 web build 통과                               |
| RF-203 | `packages/*`와 `contracts/*` 최소 실제 slice      | 완료      | RF-100~103 | validated Documents fixture가 package test/build 경로에서 통과                     |
| RF-204 | 공통 `make check` 확장                            | 부분 완료 | RF-200~203 | `make workbench-check`는 반복 통과; root legacy Ruff·pytest prerequisite 제한 유지 |

<a id="design-system과-공통-에셋-카탈로그"></a>

### 4.4. Design System과 공통 에셋 카탈로그

| ID     | 작업                                                | 상태 | 선행           | 완료 조건                                                             |
| ------ | --------------------------------------------------- | ---- | -------------- | --------------------------------------------------------------------- |
| RF-300 | 기존 UI kit 자산·라이선스·검증 포팅 계획            | 완료 | RF-004         | Stage 2 독립 frozen install, provenance/catalog 및 Chromium gate 통과 |
| RF-301 | semantic token과 기본 dark/light/high-contrast 테마 | 완료 | RF-200         | 세 foundation과 React 소비가 독립 component/visual gate 통과          |
| RF-302 | 작업 목록 SVG 카탈로그                              | 완료 | RF-101, RF-300 | 16개 React SVG와 상태가 catalog/Chromium matrix 통과                  |
| RF-303 | 사이드바 에셋 카탈로그                              | 완료 | RF-101, RF-300 | 단일 host 7개 조합과 폭·키보드 검증 통과                              |
| RF-304 | 패널 레이아웃 카탈로그                              | 완료 | RF-101, RF-300 | 9개 조합과 responsive split/remount 검증 통과                         |
| RF-305 | 기본 입력·표시·피드백 컴포넌트                      | 완료 | RF-101, RF-300 | 공통 component와 상태의 접근성 test 통과                              |
| RF-306 | 카탈로그 metadata와 미리보기                        | 완료 | RF-302~305     | 단일 registry와 `/catalog` production Chromium preview 통과           |
| RF-307 | 중복·폐기 정책                                      | 완료 | RF-306         | alias/descriptor/compatibility gate 통과                              |
| RF-308 | 접근성·반응형·visual gate                           | 완료 | RF-302~306     | 180/268/520px, 390px, focus와 10 screenshots 검증 통과                |

<a id="사용자별-테마"></a>

### 4.5. 사용자별 테마

| ID     | 작업                                         | 상태      | 선행               | 완료 조건                                                                  |
| ------ | -------------------------------------------- | --------- | ------------------ | -------------------------------------------------------------------------- |
| RF-400 | `ThemeProfile` 도메인과 PostgreSQL migration | 완료      | RF-102, RF-201     | Stage 3 독립 clean migration·forced RLS·concurrency gate 통과              |
| RF-401 | 테마 조회·저장 API와 권한                    | 완료      | RF-400             | Stage 3 독립 session/CAS/audit/audit-failure gate 통과                     |
| RF-402 | 테마 해석·검증기                             | 완료      | RF-102, RF-301     | Stage 3 독립 Python/TypeScript allowlist·contrast gate 통과                |
| RF-403 | 초기 렌더링과 브라우저 캐시                  | 완료      | RF-401~402         | Stage 3 독립 browser context/stale/second-context gate 통과                |
| RF-404 | Theme editor와 전체 적용                     | 부분 완료 | RF-306, RF-401~403 | React shell/editor preview 구현; legacy 전체 소비자 전환은 RF-800~804 의존 |
| RF-405 | 접근성 우선순위                              | 완료      | RF-402~404         | Stage 3 독립 고대비/reduced motion/keyboard/focus gate 통과                |

<a id="workbench-runtime과-작성기"></a>

### 4.6. Workbench runtime과 작성기

| ID     | 작업                                        | 상태 | 선행                   | 완료 조건                                                     |
| ------ | ------------------------------------------- | ---- | ---------------------- | ------------------------------------------------------------- |
| RF-500 | Component/Layout/Icon registry              | 완료 | RF-101, RF-302~306     | Stage 4 독립 Verification 통과                                |
| RF-501 | sidebar/panel renderer                      | 완료 | RF-100, RF-500         | Stage 4 package/browser gate 통과                             |
| RF-502 | Binding client와 입출력 검증                | 완료 | RF-100, RF-103         | cancel/cache/closed I/O gate 통과                             |
| RF-503 | 제한된 Action registry                      | 완료 | RF-100, RF-500         | 실제 refresh와 중복 실행 gate 통과                            |
| RF-504 | view state와 복원                           | 완료 | RF-100, RF-501         | theme/keyboard/state/remount/390px gate 통과                  |
| RF-505 | runtime 보안 제한                           | 완료 | RF-100~104             | schema와 runtime rejection gate 통과                          |
| RF-506 | AssetCatalog·ComponentPalette·LayoutPalette | 완료 | RF-306, RF-500         | asset별 접근 가능한 삽입 이름 포함 gate 통과                  |
| RF-507 | Property·Binding·Theme editor               | 완료 | RF-404, RF-502, RF-506 | exact preview/import/undo editor gate 통과                    |
| RF-508 | draft→preview→validate→publish UX           | 완료 | RF-600~604             | Stage 5 실제 API 저장·게시·reload DB-backed browser 검증 통과 |

<a id="서버-도메인과-adapter"></a>

### 4.7. 서버 도메인과 adapter

| ID     | 작업                                           | 상태      | 선행           | 완료 조건                                                                |
| ------ | ---------------------------------------------- | --------- | -------------- | ------------------------------------------------------------------------ |
| RF-600 | `WorkbenchDefinition` aggregate                | 완료      | RF-100, RF-201 | Stage 5 독립 core 전이·stale·archive/restore 검증 통과                   |
| RF-601 | immutable `WorkbenchRelease`                   | 완료      | RF-600         | Stage 5 독립 transaction snapshot/digest/DB mutation 거부 검증 통과      |
| RF-602 | Workbench repository port와 PostgreSQL adapter | 완료      | RF-600~601     | Stage 5 독립 0026 migration·forced RLS·동시성 PostgreSQL 검증 통과       |
| RF-603 | Workbench command/query use case               | 완료      | RF-602         | Stage 5 독립 권한·CAS·idempotency·transaction failure 검증 통과          |
| RF-604 | 얇은 HTTP·MCP adapter                          | 완료      | RF-603         | Stage 5 독립 인증 HTTP/MCP 결과·오류 parity 검증 통과                    |
| RF-605 | 기존 도메인의 `platform-core` 포팅             | 부분 완료 | RF-201, RF-004 | Stage 8·9 독립 pass; 나머지 도메인 필요 |
| RF-606 | 기존 외부 구현의 `platform-adapters` 포팅      | 부분 완료 | RF-201, RF-004 | Stage 8·9 독립 pass; 나머지 provider/도메인 adapter 필요 |
| RF-607 | API/worker composition 분리                    | 부분 완료 | RF-605~606     | Stage 8·9 독립 pass; worker/나머지 도메인 필요 |

<a id="react-shell과-첫-vertical-slice"></a>

### 4.8. React shell과 첫 vertical slice

| ID     | 작업                                        | 상태      | 선행                               | 완료 조건                                                                        |
| ------ | ------------------------------------------- | --------- | ---------------------------------- | -------------------------------------------------------------------------------- |
| RF-700 | Vite React shadow route                     | 완료      | RF-200, RF-202                     | Stage 6 독립 production deep-link/manifest/package/CSP gate 통과                  |
| RF-701 | 작업 목록｜사이드바｜패널 shell             | 완료      | RF-700, RF-302~304                 | Stage 6 독립 shell/resize/keyboard/390px/theme gate 통과                          |
| RF-702 | 표준·고객 단일 WorkbenchRegistry            | 완료      | RF-500, RF-603                     | Stage 6 독립 authorized projection/isolation/collision gate 통과                  |
| RF-703 | 대표 vertical slice로 `문서` 작업 범위 고정 | 완료      | RF-002, RF-004                     | 대표 범위와 RF-801 잔여 inventory를 Stage 6 evidence에 고정                       |
| RF-704 | 대표 vertical slice 구현                    | 완료      | RF-501~505, RF-603~604, RF-701~703 | Stage 6 실제 DB-backed create/read/edit/conflict/revision/preview gate 통과       |
| RF-705 | feature flag와 rollback                     | 완료      | RF-700, RF-704                     | Stage 6 one-shot legacy 복귀와 React 재진입 양방향 gate 통과                      |

<a id="표준-작업-순차-포팅"></a>

### 4.9. 표준 작업 순차 포팅

| ID     | 작업                       | 상태   | 선행       | 완료 조건                                                          |
| ------ | -------------------------- | ------ | ---------- | ------------------------------------------------------------------ |
| RF-800 | 작업공간·조직·계정·관리자  | 완료 | RF-704~705 | Stage 10 closure Work `run-20260913T070534675629Z-ca2c4713` / Verification `run-20260913T070752562929Z-3f95393b` 독립 통과, commit `2f2fcf7` |
| RF-801 | 문서·검색·지식             | 부분 완료 | RF-704~705 | focused lane 통과 및 production router 구성 작성; fresh forced-RLS·통합 browser/package 검증 필요 |
| RF-802 | 일정                       | 부분 완료 | RF-704~705 | focused lane 통과 및 schedule/planning/Job composition 작성; 통합 worker·fresh forced-RLS·browser 검증 필요 |
| RF-803 | 에이전트·보고·로그·테스트  | 부분 완료 | RF-704~705 | Agent/보고 focused lane 통과 및 표준 registry/API composition 작성; 통합 실행·증거·장시간 갱신 검증 필요 |
| RF-804 | 연동·MCP 연결·데이터베이스 | 부분 완료 | RF-704~705 | provider/MCP focused lane 통과 및 OAuth/token/configuration composition 작성; collection/webhook worker·통합 보안/browser 검증 필요 |
| RF-805 | legacy UI 제거 후보 확인   | 후순위 | RF-800~804 | 실제 사용자·route·asset 참조가 없고 관측 기간과 rollback 기준 충족 |

<a id="rf-801804-통합-work-기록"></a>

### 4.10. RF-801~804 통합 Work 기록

- 세 focused lane은 각각 RF-801 Work/Verification `run-20260913T083534720587Z-3bb6198a` / `run-20260913T084128004582Z-6cc9e083`, RF-802 `run-20260913T082753475354Z-839adb11` / `run-20260913T083251358354Z-ec062498`, RF-803/804 `run-20260913T110144713204Z-3a5744e5` / `run-20260913T110524289328Z-3ddee3f3`에서 독립 focused pass였다. 해당 근거는 lane 소유 입력만 검증하며 이 통합 Work의 registry/router/worker/migration 변경은 검증하지 않는다.

- 통합 Work는 유지보수되는 표준 ID로 일정·에이전트·문서·보고·연동을 단일 registry에 등록하고, 문서/검색, 일정/계획, Agent/보고, provider/MCP의 target HTTP use case를 production router에서 구성했다. `agent.run`은 Run·초기 event와 같은 transaction에 shared Job을 stage한 뒤 durable identity 하나만 broker에 전달한다. append-only `0027`은 knowledge audit INSERT policy, scheduler scan index, webhook terminal state, 불변 execution/report evidence trigger와 provider 요청 byte reservation 저장 schema를 추가한다. revision Work는 target CollectionJobs, credential refresh/six-provider driver, run-bound reservation/settlement, Original/reference Document mapping을 HTTP·MCP·worker collection 경로에 구성했다. 이 문서는 Verification 전 Work 기록이므로 완료나 실행 통과를 주장하지 않는다.

- target receiver가 신규·기존 webhook header를 모두 수용하도록 한 뒤 충돌하던 legacy public receiver 등록 하나만 제거했다. 그 밖의 legacy 구현은 combined permission/RLS/browser/package/ rollback parity와 최종 live consumer 부재가 아직 독립 검증되지 않아 삭제하지 않았다. 구체적인 보존 dependency와 삭제 checkpoint는 migration map에 기록한다. RF-1000~1005와 외부 rollout 관측은 계속 남는다. SaaS 기반 완성 뒤 Workbench별 공통 asset 적용, 이후 종합 UI 조정은 Human이 지정한 다음 단계이며 이번 통합 완료로 표시하지 않는다. logs/tests/database의 새 제품 기능도 계속 정직한 placeholder다.

- credential/status authority checkpoint Work `run-20260913T165204388195Z-c2791fae`는 MCP의 `integration_token_set`, `integration_oauth_begin`, `integration_oauth_complete` 신규 요청을 legacy `cloud_services`에서 target credential use case/PostgreSQL adapter composition으로 옮기고, 기존 MCP schema에 없는 provider는 consume된 state에 결합된 Workspace connection에서만 해결하도록 작성했다. 이미 발급된 `redirect_uri` state shape는 configuration 비교와 일회성 consume을 유지한 채 호환한다. target MCP status `{state, connections}`는 React Workspace/ Connections 소비자와 native browser assertion이 같은 형태를 사용하도록 정리했다. 실제 권한, wrong Workspace, replay/expiry, 암호화·secret 비노출, transaction failure, pending→verified→ reauth-required 수용 근거를 위한 focused/fresh-DB/browser test도 작성했다. 세부 authority와 retained consumer inventory는 `2026-09-14-mcp-consumer-authority-evidence.md`에 있다. 이 문단은 독립 Verification 전 기록이며 RF-801~804 또는 RF-1000~1005 완료 판정이 아니다.

- Knowledge MCP authority checkpoint Work `run-20260913T173248275646Z-59671048`는 `app/mcp/documents.py`의 import/read/write/ lexical search/index 신규 요청을 legacy `DocumentService`/`CloudDocumentService`에서 target `DocumentUseCases`/`CloudKnowledgeUseCases`와 production PostgreSQL/object-storage composition으로 옮겼다. prepare/finalize의 기존 target delivery authority는 유지하고, template은 read 권한 뒤 packaged resource를 직접 읽어 불필요한 legacy business-service 구성을 제거했다. 256 KiB download pre-read, 32 KiB command, reviewed Specification pair, old/current revision, optimistic conflict, provenance/delete와 current-only Korean/identifier lexical semantics를 유지하는 focused/fresh-DB acceptance를 작성했다. 구체적인 authority/retained consumer inventory는 `2026-09-14-knowledge-mcp-authority-evidence.md`에 있다. 이 기록은 독립 Verification 전이며 RF-801~804, RF-1000~1005, 전체 Documents browser matrix 또는 deletion 완료 판정이 아니다.

- Verification `run-20260913T112657393505Z-bc9ab2a4`는 V001~V004로 실패했다. revision Work `run-20260913T113054396323Z-69aff322`는 collection Job/credential/driver/byte budget/Document bridge와 target HTTP·MCP·worker 경로, target reporting MCP와 Agent MCP Job staging, local PDF.js deployment-resource acceptance를 작성하고 V004 import block을 formatter로 정리했다. 독립 재검증 전이므로 pass로 표시하지 않는다. PlanningImports transport, target Agent execution, webhook delivery dispatch와 definitive legacy tree removal은 여전히 RF-801~804 완료 조건으로 남는다.

- continuation Work `run-20260913T114620614720Z-5155554d`는 아래 V002 code-side construction을 작성했지만 runtime result를 내기 전에 timeout되어 그 receipt만으로 완료 근거가 되지 않는다. exact-session continuation Work `run-20260913T121757800727Z-d289bbca`가 보존된 checkout을 검토하고 Agent cooperative cancellation transition과 concurrent PlanningImports apply replay를 보정했다. Planning import HTTP/MCP는 target `PlanningImports`와 atomic PostgreSQL adapter를 사용하고, production Celery entrypoint는 target `JobRuntime`/`SchedulerRuntime`, 물리 연결 `PostgresExecutionLeaseFactory`, 현재 권한 authorizer를 구성한다. Agent handler는 고정 version의 등록 model handler를 호출해 immutable tool/artifact/Document evidence, 순서 event, usage/cost를 저장하며 terminal Job 상태를 Run/collection에 조정한다. webhook receiver는 commit된 pending row를 즉시 publish하고 periodic scanner가 미발행/실패 delivery를 재전송하며, worker는 endpoint 생성자의 현재 권한을 다시 확인한 뒤 enabled collection refresh Job을 idempotent하게 만든다. root wheel/image는 worker package를 포함하고 fresh-DB harness는 migration-admin, NOBYPASSRLS app, BYPASSRLS worker를 분리한다. 이 기록은 독립 Verification 전 implementation handoff이며 pass 주장이 아니다. parity가 확인되면 다음 sole Work revision에서 아래 removal 후보를 삭제하고 다시 독립 검증해야 한다.

- Verification `run-20260913T122821362904Z-8849fbf8`은 V005~V007로 실패했다. revision Work `run-20260913T123128702096Z-de2a653a`는 PlanningImports parent kind를 명시적으로 좁히고, 새 표준 Workbench 다섯 개의 reserved-ID 순서·충돌 test를 registry 계약과 동기화했으며, cumulative Python 경로의 Ruff formatter/lint 지적 15건을 해당 redaction·retry·durable outbox 동작을 유지하면서 수정했다. 이 기록도 재검증 전 Work handoff이며 통과 근거가 아니다.

<a id="mcp-apps-host"></a>

### 4.11. MCP Apps host

| ID     | 작업                                     | 상태   | 선행               | 완료 조건                                                             |
| ------ | ---------------------------------------- | ------ | ------------------ | --------------------------------------------------------------------- |
| RF-900 | 실제 외부 UI 사례와 capability 범위 확인 | 후순위 | RF-704             | native renderer로 부족한 사례를 확인하고 최소 capability를 ADR에 기록 |
| RF-901 | sandbox iframe과 CSP 교집합              | 후순위 | RF-900             | opaque/별도 origin, 최소 sandbox와 네트워크 정책 보안 테스트          |
| RF-902 | AppBridge lifecycle과 messaging          | 후순위 | RF-900             | exact origin/source/schema, pending request와 teardown 검증           |
| RF-903 | 읽기 전용 theme context                  | 후순위 | RF-404, RF-901~902 | 계산된 token만 전달하고 host storage·credential 접근 차단             |

<a id="검증배포전환"></a>

### 4.12. 검증·배포·전환

| ID      | 작업                                     | 상태      | 선행                     | 완료 조건                                                           |
| ------- | ---------------------------------------- | --------- | ------------------------ | ------------------------------------------------------------------- |
| RF-1000 | package별 unit 및 root contract gate     | 미착수    | RF-103, RF-200~204       | Python/TS validator parity, package unit, cross-boundary test 통과  |
| RF-1001 | tenant·RLS·schema·SSRF·sandbox 보안 gate | 부분 완료 | 관련 slice               | 현행 보안 테스트를 목표 경계로 포팅하고 새 제한 검증                |
| RF-1002 | 브라우저·접근성·visual gate              | 부분 완료 | RF-308, RF-701           | 데스크톱/좁은 폭, keyboard, 복원, theme, 권한과 모든 상태 통과      |
| RF-1003 | migration·build·image·smoke gate         | 부분 완료 | RF-201~204, DB 변경      | clean DB head, immutable build, staging smoke와 rollback rehearsal  |
| RF-1004 | 관측과 단계적 기본 경로 전환             | 후순위    | RF-800~804, RF-1000~1003 | 오류율·binding latency·publish rollback·sandbox violation 기준 충족 |
| RF-1005 | compatibility adapter와 legacy 경로 제거 | 후순위    | RF-1004                  | 사용자 잔존 없음 확인, 제거 후 전체 gate 및 복구 절차 검증          |

<a id="현재-재사용-가능한-기반"></a>

## 5. 현재 재사용 가능한 기반

| 현행 자산                                  | 목표 사용                                           | 주의점                                                             |
| ------------------------------------------ | --------------------------------------------------- | ------------------------------------------------------------------ |
| `assets/ui-kit/src/components/`            | design-system primitive·navigation·layout 포팅 입력 | vanilla DOM 계약을 React 공개 API로 그대로 간주하지 않는다.        |
| `assets/ui-kit/vendor/`와 provenance       | 아이콘·외부 소스의 출처 및 라이선스 입력            | 생성물과 editable source를 분리하고 고지를 보존한다.               |
| `static/ui/`                               | 전환 기간 legacy runtime                            | 목표 design-system의 편집 원본으로 직접 수정하지 않는다.           |
| `static/css/ui.css`                        | semantic token과 공통 상태의 현행 기준              | 사용자 테마와 React용 token build 계약이 추가로 필요하다.          |
| `template/workspace/index.html` inline SVG | 작업 목록 아이콘 inventory                          | stable ID와 manifest로 이동 후 compatibility route에서만 유지한다. |
| `tests/test_architecture_boundaries.py`    | 목표 dependency 검사 출발점                         | Python legacy 경계 외에 TS와 apps/packages 방향을 추가한다.        |
| `tests/browser/*.cjs`                      | 현행 사용자 흐름 characterization                   | mocked API 범위와 실제 DB/브라우저 범위를 구분한다.                |
| `app/modules/*` 서비스·repository          | `platform-core`/`platform-adapters` 포팅 입력       | 파일 이동과 도메인 의미 변경을 같은 단계에서 수행하지 않는다.      |
| `app/worker`, `app/scheduler`              | `apps/worker`와 execution use case 포팅 입력        | durable Job 권위와 payload 재검증을 유지한다.                      |
| `app/db/migrations`                        | 루트 `migrations` 전환 입력                         | 배포된 revision history를 다시 쓰지 않고 append-only로 유지한다.   |

<a id="진행-순서"></a>

## 6. 진행 순서

```text
RF-002~004
    ↓
RF-100~105
    ↓
RF-200~204
    ↓
RF-300~308 ──→ RF-400~405
    ↓                 ↓
RF-500~507 ←──────────┘
    ↓
RF-600~607
    ↓
RF-700~705
    ↓
RF-800~805
    ↓
RF-1000~1005
```

- MCP Apps host(RF-900~903)는 대표 native Workbench가 완성되고 실제 외부 UI 사례가 확인된 뒤 병행할 수 있다. 각 단계는 기존 경로의 rollback 가능성을 유지하며, 파일 이동·renderer 교체·API 의미 변경을 하나의 변경 묶음에서 동시에 수행하지 않는다.

<a id="현-시점의-다음-작업"></a>

## 7. 현 시점의 다음 작업

<a id="stage-9-독립-검증-근거"></a>

### 7.1. Stage 9 독립 검증 근거

- Verification `rf-stage9-verification/run-20260912T235201721498Z-246bfca2`가 Work `rf-stage9-work/run-20260912T234949674533Z-b60e000e` (원 요청 SHA-256 `165e3ee196e9ce9bd19967f72b1648ed35ae0322e3549ebd846563e2b24ed3d8`)를 통과시켰다. `make workbench-check` 61 TypeScript/75 Python, 관련 회귀 51 통과/기존 skip 1, 관리자 45 tests, PostgreSQL 16/pgvector의 NOSUPERUSER·NOBYPASSRLS 실제 세션 HTTP, scoped Bandit 무발견, legacy mypy 173, private 관리자 catalog의 1440/390 browser와 offline wheel/installed-resource 근거를 포함한다. 이 근거는 Stage 9 slice의 독립 통과이며 전역 리팩터링·배포 완료 근거로 승격하지 않는다.

<a id="stage-10-독립-통과와-폐쇄-상태"></a>

### 7.2. Stage 10 독립 통과와 폐쇄 상태

- 최종 native loop의 Work `rf-stage10-work/run-20260913T063735636121Z-496ee188`와 Verification `rf-stage10-verification/run-20260913T064055646404Z-84f786b9`는 원 요청 SHA-256 `3e74148930c0b2d06e44d533bca923b20c4a553bc970b6feea33f9ab40a53860`에 묶여 있다. Verification은 다음 현재 입력 근거를 실제로 만들었다.

- `scripts/verify-native-management.sh`: PostgreSQL 16/pgvector를 migration `0026`까지 올리고
  NOSUPERUSER·NOBYPASSRLS app role을 사용한 production React/FastAPI `/factory` browser가
- `1 passed in 47.58s`였다. 같은 실행에서 `auth-assets`가 통과했고 `/tmp/af-native-stage10-1440.png`, `/tmp/af-native-stage10-390.png`를 검사했다.
- `make workbench-check`: formatting, Ruff/ESLint, Python/TypeScript type, schema 생성·parity,
  dependency guard, 86 TypeScript tests와 80 Python tests가 통과했다.
- 같은 session의 앞선 반복은 desktop sidebar 180/268/520px, 390px, 제공 theme, 긴 한국어
  group label, mobile tab과 MCP 영역을 실제로 검사했다. 최종 browser는 조직·작업공간·구성원·
- 역할·팀·초대·group·MCP ZIP/provenance/evidence·계정·theme/CAS·customer authoring·관리자· session revocation·rollback 동작을 포함한다.

- 위 근거는 native production slice와 aggregate gate의 독립 통과이다. 이 closure 문서만 변경되므로 해당 전체 browser와 aggregate를 다시 실행할 이유는 없다. 다만 bare `pass` 결과를 원 요구사항 5 전체의 근거로 확대하지 않는다. `pnpm -r build` 성공은 이전 `rf-stage10-verification/run-20260913T032019391644Z-e41c5f3f`, `policies.py` scoped Bandit 성공은 `rf-stage10-verification/run-20260913T013608659927Z-6563d760`에 존재하지만, 각각 이후 누적 입력 전체나 packaging/legacy 범위를 증명하지 않는다.

<a id="요구사항구현testevidence-map"></a>

### 7.3. 요구사항→구현·test·evidence map

| 원 acceptance | 주요 구현 | 작성된 test/evidence | 폐쇄 판정 |
| --- | --- | --- | --- |
| 1. 네 native 소비자, registry, selection/theme/state 격리 | `apps/web/src/standard/{workspace,organization,account,admin}`, `app/WorkbenchContext.tsx`, `registry/WorkbenchRegistry.ts`, `ThemeBootstrap.tsx`, design-system catalog/components | `NativeManagement.test.tsx`, `WorkbenchContext.test.tsx`, `WorkbenchRegistry.test.ts`, theme/App/design-system tests; 최종 `make workbench-check` 86 TS/80 Python | 현재 입력 근거 있음 |
| 2. production `/factory`, 실제 session/API, fresh forced-RLS DB | `scripts/verify-native-management.sh`, `tests/test_cloud_platform_integration.py`, `tests/browser/native-management.cjs` | 최종 Verification `1 passed in 47.58s`; migration 0001~0026, 두 tenant/user, admin/nonadmin, CAS·revocation·rollback 포함 | 현재 입력 근거 있음 |
| 3. exhaustive native browser와 legacy rollback | `native-management.cjs`, legacy `static/js/{workspace,mcp-connection,mcp-handoff}.js`와 기존 browser suites | native/MCP ZIP·credential/state assertion은 최종 pass; Stage 10에서 바뀐 legacy JS와 `mcp-handoff.cjs`에 대한 이후 독립 rollback 실행 기록은 없음 | legacy rollback 근거 필요 |
| 4. responsive/theme/keyboard visual inspection | shared shell/design-system/app CSS와 native 네 소비자 | 최종 1440/390 artifact 및 앞선 180/268/520/theme/긴 한국어 검사 | 현재 입력 근거 있음; artifact는 runtime-only |
| 5. build/type/security/package/deploy slice | web build, generated contracts, `MANIFEST.in`, packaged runtime paths, shadow route/security middleware | 최종 web production build와 aggregate type/lint/tests는 있음. 이전 `pnpm -r build`와 단일-file Bandit은 baseline만 제공 | offline wheel·installed web dist/manifest, root_path/cache/CSP, legacy mypy, current changed-scope Bandit 필요 |

<a id="남은-stage-10-verification-handoff"></a>

### 7.4. 남은 Stage 10 Verification handoff

- Verification은 서로 독립적인 아래 묶음을 별도 output path로 실행한다. 현재 native 전체 browser와 `make workbench-check`는 관련 source가 이 문서 closure로 바뀌지 않았으므로 위 최종 run을 재사용한다.

```sh
pnpm --filter @agent-factory/web build
STAGE10_PACKAGE_PYTHON=/tmp/organization-build-env/bin/python
STAGE10_PACKAGE_PYTHONPATH=/home/deus/.cache/uv/archive-v0/AkgFl_dbkmT4zDjN:/home/deus/.cache/uv/archive-v0/H6wpYZ3q5wzmMW69xwsab:/home/deus/.cache/uv/archive-v0/vNviCP3LdL58pAW2:/home/deus/.cache/uv/archive-v0/tSSQuf3EI2AWvD4l9ORSo
PYTHONPATH="$STAGE10_PACKAGE_PYTHONPATH" "$STAGE10_PACKAGE_PYTHON" -c \
  'import hatchling.build, pytest'
AGENT_FACTORY_ENV_FILE='' AGENT_FACTORY_ENVIRONMENT=test \
  PYTHONPATH="$STAGE10_PACKAGE_PYTHONPATH" \
  "$STAGE10_PACKAGE_PYTHON" -m pytest -q \
  tests/test_cloud_platform_packaging.py tests/test_workbench_shadow_route.py \
  tests/test_security.py tests/test_admin.py tests/test_deployment.py

uv run mypy app
.venv/bin/bandit -q \
  packages/platform-core/src/agent_factory_core/workbenches/policies.py \
  scripts/generate_workbench_contracts.py

export NODE_PATH=/tmp/af-pw/node_modules
export PLAYWRIGHT_BROWSERS_PATH=/home/deus/.cache/ms-playwright
node tests/browser/workspace-start.cjs
node tests/browser/organizations.cjs
node tests/browser/mcp-handoff.cjs
node tests/browser/admin-assets.cjs
node tests/browser/ui-boundaries.cjs
node tests/browser/ui-components.cjs
node tests/browser/ui-screens.cjs

# THEME_*_DATABASE_URL은 같은 Verification이 소유한 disposable PostgreSQL의
# 각각 NOSUPERUSER·NOBYPASSRLS app URL과 migration-admin URL이다.
: "${THEME_APP_DATABASE_URL:?set the disposable app-role URL}"
: "${THEME_ADMIN_DATABASE_URL:?set the disposable migration-admin URL}"
AGENT_FACTORY_TEST_DATABASE_URL="$THEME_APP_DATABASE_URL" \
AGENT_FACTORY_TEST_ADMIN_DATABASE_URL="$THEME_ADMIN_DATABASE_URL" \
PYTHONPATH="$STAGE10_PACKAGE_PYTHONPATH" \
THEME_VERIFY_PYTHON=/tmp/organization-build-env/bin/python \
THEME_PLAYWRIGHT_NODE_PATH=/tmp/af-pw/node_modules \
PLAYWRIGHT_BROWSERS_PATH=/home/deus/.cache/ms-playwright \
  scripts/verify-theme-profiles.sh
```

- 첫 묶음은 Node 22/pnpm 10.15.1의 현재 production dist를 먼저 만들고, offline/no-index wheel과 설치 layout의 `WORKBENCH_WEB_ROOT`, `.vite/manifest.json`, byte-equivalent resources를 확인한다. 현재 host에서는 Hatchling과 project dependency가 함께 해석되는 위 execution-only Python/PYTHONPATH 조합을 먼저 import probe로 확인한다. 이 `/tmp`·uv archive 조합은 저장소의 일반 개발 명령이 아니라 해당 Verification 환경에만 적용되는 근거이며, 다른 host에서는 같은 import probe를 만족하는 기존 호환 interpreter를 절대 경로로 정한다. dependency를 설치하거나 network build isolation으로 보완하지 않는다. 같은 묶음의 shadow/security/deployment tests가 `/factory`, deep link, index `no-store`, hashed asset immutable cache, CSP와 catalog no-store를 맡는다. theme profile은 직접 browser 파일을 호출하지 않고 `scripts/verify-theme-profiles.sh`가 build·preview server·browser cleanup을 소유한다. 두 database URL은 같은 실행이 만든 명시적 disposable PostgreSQL에만 연결한다. browser 묶음은 fixture이며 실제 DB native 근거와 구분한다. 어느 묶음이 실패해도 아직 RF-800 Stage 10 폐쇄 완료로 올리지 않는다.

<a id="통합-이후-순서와-단일-writer-경계"></a>

### 7.5. 통합 이후 순서와 단일 writer 경계

1. 위 Stage 10 closure를 먼저 마친다. Main만 이 누적 Stage 10 변경을 commit한다.
2. 준비만 된 `/tmp/af-refactor-loop-jBb77E/parallel-migration`의 세 lane을 그 뒤 시작한다:
   RF-801 knowledge/documents, RF-802 planning/durable scheduling, RF-803/804
- agents/reporting/providers/MCP. 각 lane은 disjoint allowlist만 쓴다.
3. registry, shell, context, `app.css`, design-system, schema/generated, `__init__`, global
   registration, integration tests, browser harness와 status evidence는 lane writer에서 제외하고
- 마지막 단일 integration writer가 소유한다.
4. SaaS 기반 완성 → Workbench별 공통 asset 적용 → 종합 UI 조정 순서를 유지한다. logs/tests/
   database 제품 기능은 정의될 때까지 placeholder이며, 12~20시간은 목표 추정치일 뿐 범위나
- 품질 조건을 줄이지 않는다.
5. RF-801 전체 Documents parity와 RF-802~805의 남은 기능, 전역 baseline·배포·관측은 후속
   slice다. parity, 독립 검증과 live reference 부재를 모두 확인하기 전에는 legacy를 삭제하지
- 않으며 실제 rollback/compatibility 경로는 유지한다.

- 단순 디렉터리 생성만으로 상태를 완료로 바꾸지 않는다. 각 행의 완료 조건과 해당 검증이 함께 충족된 경우에만 완료로 갱신한다.
